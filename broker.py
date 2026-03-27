import os
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