import os
import time
import pandas as pd
from datetime import datetime, timedelta
from config import Config

class BrokerAPI:
    def get_data(self, symbol, timeframe):
        raise NotImplementedError
    def place_order(self, symbol, qty, side, type='market'):
        raise NotImplementedError
    def get_position(self, symbol):
        raise NotImplementedError

class MockBroker(BrokerAPI):
    def __init__(self):
        print("🔗 Connected to Mock Broker")
    
    def get_data(self, symbol, timeframe):
        import pandas as pd
        import numpy as np
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq='5min')
        df = pd.DataFrame({
            'open': np.random.rand(100)*100,
            'high': np.random.rand(100)*100,
            'low': np.random.rand(100)*100,
            'close': np.random.rand(100)*100,
            'volume': np.random.randint(1000, 5000, 100)
        }, index=dates)
        return df

    def place_order(self, symbol, qty, side, type='market'):
        print(f"📝 [MOCK] Order: {side} {qty} {symbol} @ {type}")
        return True

    def get_position(self, symbol):
        return None

class AlpacaBroker(BrokerAPI):
    def __init__(self):
        try:
            import alpaca_trade_api as tradeapi
            self.api = tradeapi.REST(Config.API_KEY, Config.API_SECRET, Config.BASE_URL, api_version='v2')
            print("🔗 Connected to Alpaca")
        except Exception as e:
            print(f"❌ Alpaca Connection Failed: {e}")
            self.api = None

    def get_data(self, symbol, timeframe):
        if not self.api: return None
        df = self.api.get_bars(symbol, timeframe, limit=100).df
        return df

    def place_order(self, symbol, qty, side, type='market'):
        if not self.api: return False
        try:
            self.api.submit_order(symbol=symbol, qty=qty, side=side, type=type, time_in_force='gtc')
            print(f"✅ Order Submitted: {side} {qty} {symbol}")
            return True
        except Exception as e:
            print(f"❌ Order Failed: {e}")
            return False

    def get_position(self, symbol):
        if not self.api: return None
        try:
            return self.api.get_position(symbol)
        except:
            return None


class DhanBroker(BrokerAPI):
    """
    Dhan API integration for real-time market data.
    Get your access token from Dhan Pro: https://dhan.co/
    """
    def __init__(self):
        try:
            from dhanhq import dhanhq
            self.access_token = Config.DHAN_ACCESS_TOKEN
            self.client_id = Config.DHAN_CLIENT_ID

            if not self.access_token:
                raise Exception("DHAN_ACCESS_TOKEN not found in .env file")

            self.api = dhanhq.DhanHQ(self.access_token)
            print("🔗 Connected to Dhan API")
        except Exception as e:
            print(f"❌ Dhan Connection Failed: {e}")
            self.api = None

    def get_data(self, symbol, timeframe):
        """
        Fetch historical data from Dhan API.
        Dhan supports: 1m, 5m, 15m, 1h, 1d timeframes
        """
        if not self.api:
            return None

        try:
            # Map timeframe to Dhan format
            timeframe_map = {
                '1m': 'ONE_MINUTE',
                '5m': 'FIVE_MINUTE',
                '15m': 'FIFTEEN_MINUTE',
                '1h': 'ONE_HOUR',
                '1d': 'ONE_DAY'
            }

            tf_key = timeframe_map.get(timeframe.lower(), 'FIVE_MINUTE')

            # For Dhan, we need security ID. For NSE stocks: NSE:{SYMBOL}
            # For NSE indices: NSE:{SYMBOL}-INDEX
            # Try to fetch with NSE exchange first
            try:
                # Fetch historical data (last 100 candles)
                response = self.api.get_historical(scrip=symbol, exchange='NSE', timeframe=tf_key)
            except:
                # Fallback for indices or other instruments
                response = self.api.get_historical(scrip=symbol, exchange='NSE_INDEX', timeframe=tf_key)

            if response['status'] != 'success':
                print(f"⚠️ Dhan API Error: {response.get('remarks', 'Unknown error')}")
                return None

            data = response['data']

            if not data:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Rename columns to match expected format (lowercase)
            df = df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'time': 'datetime'
            })

            # Parse datetime
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')

            # Ensure correct data types
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

            df = df.dropna()

            return df[['open', 'high', 'low', 'close', 'volume']]

        except Exception as e:
            print(f"❌ Error fetching Dhan data: {e}")
            return None

    def get_quote(self, symbol):
        """Fetch real-time quote from Dhan"""
        if not self.api:
            return None

        try:
            response = self.api.get_quote(scrip=symbol, exchange='NSE')
            if response['status'] == 'success':
                return response['data']
        except:
            pass

        # Try NSE_INDEX for indices
        try:
            response = self.api.get_quote(scrip=symbol, exchange='NSE_INDEX')
            if response['status'] == 'success':
                return response['data']
        except:
            pass

        return None

    def place_order(self, symbol, qty, side, type='market'):
        """Place order through Dhan"""
        if not self.api:
            return False

        try:
            # Map side to Dhan order type
            transaction_type = 'BUY' if side.upper() == 'LONG' else 'SELL'

            response = self.api.place_order(
                scrip=symbol,
                exchange='NSE',
                qty=qty,
                transaction_type=transaction_type,
                order_type='MARKET' if type == 'market' else 'LIMIT',
                product_type='MIS'  # Intraday
            )

            if response['status'] == 'success':
                print(f"✅ Order Placed: {side} {qty} {symbol}")
                return True
            else:
                print(f"❌ Order Failed: {response.get('remarks', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ Order Error: {e}")
            return False

    def get_position(self, symbol):
        """Get current position from Dhan"""
        if not self.api:
            return None

        try:
            response = self.api.get_positions()
            if response['status'] == 'success':
                positions = response['data']
                for pos in positions:
                    if pos.get('tradingSymbol') == symbol:
                        return pos
            return None
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")
            return None