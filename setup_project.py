import os

# Define file contents
FILES = {
    "requirements.txt": """pandas
numpy
python-dotenv
requests
alpaca-trade-api
matplotlib
yfinance
tqdm
""",

    ".env.example": """API_KEY=your_api_key_here
API_SECRET=your_api_secret_here
BASE_URL=https://paper-api.alpaca.markets
SYMBOL=AAPL
TIMEFRAME=5Min
RISK_PER_TRADE=0.02
""",

    "config.py": """import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("API_SECRET")
    BASE_URL = os.getenv("BASE_URL")
    SYMBOL = os.getenv("SYMBOL", "AAPL")
    TIMEFRAME = os.getenv("TIMEFRAME", "5Min")
    
    # Strategy Params
    RISK_REWARD_RATIO = 3.0
    WIN_RATE_TARGET = 0.33
    VP_LOOKBACK_BARS = 78 
    VOLUME_THRESHOLD = 1.5 
    
    # Risk
    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", 0.02))
""",

    "volume_profile.py": """import numpy as np
import pandas as pd

class VolumeProfile:
    def __init__(self, df, lookback=78):
        self.df = df.tail(lookback).copy()
        self.poc = None
        self.vah = None
        self.val = None
        self.calculate()

    def calculate(self):
        if len(self.df) < 2:
            return

        # Calculate Typical Price
        self.df['TP'] = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        
        min_price = self.df['TP'].min()
        max_price = self.df['TP'].max()
        
        # Create 20 bins for the profile range
        bins = np.linspace(min_price, max_price, 20)
        self.df['bins'] = np.digitize(self.df['TP'], bins)
        
        # Group volume by bin
        profile = self.df.groupby('bins')['volume'].sum()
        total_volume = profile.sum()
        sorted_profile = profile.sort_values(ascending=False)
        
        # POC (Point of Control)
        if len(sorted_profile) > 0:
            poc_bin = sorted_profile.index[0]
            self.poc = bins[poc_bin-1] if poc_bin > 0 else bins[0]
            
            # Value Area (70% of volume)
            cumulative_vol = sorted_profile.cumsum()
            va_threshold = total_volume * 0.70
            va_bins = cumulative_vol[cumulative_vol <= va_threshold].index
            
            if len(va_bins) > 0:
                self.vah = bins[max(va_bins)-1] if max(va_bins) < len(bins) else max(bins)
                self.val = bins[min(va_bins)-1] if min(va_bins) > 0 else min(bins)
            else:
                self.vah = self.df['TP'].max()
                self.val = self.df['TP'].min()
        else:
            self.poc = self.df['TP'].iloc[-1]
            self.vah = self.df['TP'].max()
            self.val = self.df['TP'].min()
""",

    "strategy.py": """import pandas as pd
from volume_profile import VolumeProfile
from config import Config

class Strategy:
    def __init__(self):
        self.position = None 
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None

    def analyze(self, df):
        vp = VolumeProfile(df, lookback=Config.VP_LOOKBACK_BARS)
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        current_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].iloc[-10:-1].mean() if len(df) > 10 else df['volume'].iloc[-1]

        signal = None
        
        # Bullish: Price above VAH, Pullback to VAH, Volume Spike
        if current_price > vp.vah and prev_price <= vp.vah * 1.002: 
            if current_vol > (avg_vol * Config.VOLUME_THRESHOLD):
                signal = self.generate_signal('LONG', current_price, vp.vah)
        
        # Bearish: Price below VAL, Pullup to VAL
        elif current_price < vp.val and prev_price >= vp.val * 0.998:
            if current_vol > (avg_vol * Config.VOLUME_THRESHOLD):
                signal = self.generate_signal('SHORT', current_price, vp.val)

        return signal, vp

    def generate_signal(self, direction, price, level):
        if direction == 'LONG':
            sl = level * 0.995 
            tp = price + (3 * (price - sl)) 
        else:
            sl = level * 1.005 
            tp = price - (3 * (sl - price)) 

        return {
            'direction': direction,
            'entry': price,
            'stop_loss': sl,
            'take_profit': tp,
            'risk': abs(price - sl),
            'reward': abs(tp - price)
        }
""",

    "broker.py": """import os
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
""",

    "main.py": """import time
import pandas as pd
from config import Config
from strategy import Strategy
from broker import MockBroker, AlpacaBroker

def main():
    # Switch to AlpacaBroker for live trading
    broker = MockBroker() 
    strategy = Strategy()
    
    print(f"🚀 Starting Volume Node Strategy on {Config.SYMBOL}")
    
    while True:
        try:
            df = broker.get_data(Config.SYMBOL, Config.TIMEFRAME)
            
            if df is None or len(df) < 20:
                time.sleep(60)
                continue

            signal, vp = strategy.analyze(df)
            
            print(f"📊 Price: {df['close'].iloc[-1]:.2f} | VAH: {vp.vah:.2f} | VAL: {vp.val:.2f}")

            if signal:
                print(f"🚨 SIGNAL DETECTED: {signal['direction']} @ {signal['entry']}")
                print(f"   SL: {signal['stop_loss']} | TP: {signal['take_profit']}")
                # broker.place_order(Config.SYMBOL, qty, signal['direction'])

            time.sleep(60)
            
        except KeyboardInterrupt:
            print("🛑 Stopping bot...")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
""",

    "backtest.py": """import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from tqdm import tqdm
from volume_profile import VolumeProfile
from config import Config as BotConfig

class BacktestConfig:
    SYMBOL = "AAPL"
    START_DATE = "2022-01-01"
    END_DATE = "2023-12-31"
    VP_LOOKBACK = 20
    VOLUME_MULTIPLIER = 1.5
    RISK_REWARD_RATIO = 3.0
    STOP_LOSS_PCT = 0.02
    INITIAL_CAPITAL = 10000

class Backtester:
    def __init__(self, config):
        self.config = config
        self.data = None
        self.trades = []
        self.equity_curve = []

    def load_data(self):
        print(f"📥 Downloading {self.config.SYMBOL}...")
        df = yf.download(self.config.SYMBOL, start=self.config.START_DATE, end=self.config.END_DATE)
        if len(df) == 0: raise Exception("No data downloaded.")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        self.data = df
        print(f"✅ Data loaded: {len(df)} rows")

    def run(self):
        if self.data is None: self.load_data()
        df = self.data
        capital = self.config.INITIAL_CAPITAL
        equity = []
        
        print("🚀 Running Backtest...")
        
        for i in range(self.config.VP_LOOKBACK, len(df) - 1):
            past_data = df.iloc[i-self.config.VP_LOOKBACK:i]
            vp = VolumeProfile(past_data, self.config.VP_LOOKBACK)
            
            current_price = df['Close'].iloc[i]
            next_open = df['Open'].iloc[i+1]
            next_high = df['High'].iloc[i+1]
            next_low = df['Low'].iloc[i+1]
            current_vol = df['Volume'].iloc[i]
            avg_vol = df['Volume'].iloc[i-10:i].mean()

            long_signal = (current_price > vp.vah) and (current_vol > avg_vol * self.config.VOLUME_MULTIPLIER)
            short_signal = (current_price < vp.val) and (current_vol > avg_vol * self.config.VOLUME_MULTIPLIER)

            if long_signal:
                risk_per_share = current_price * self.config.STOP_LOSS_PCT
                reward_per_share = risk_per_share * self.config.RISK_REWARD_RATIO
                entry = next_open
                sl = entry - risk_per_share
                tp = entry + reward_per_share
                
                if next_low <= sl:
                    pnl = -risk_per_share
                    outcome = "LOSS"
                elif next_high >= tp:
                    pnl = reward_per_share
                    outcome = "WIN"
                else:
                    pnl = 0
                    outcome = "NO FILL"
                    
                if pnl != 0:
                    self.trades.append({'type': 'LONG', 'entry': entry, 'pnl': pnl, 'outcome': outcome})
                    capital += pnl
                    
            elif short_signal:
                risk_per_share = current_price * self.config.STOP_LOSS_PCT
                reward_per_share = risk_per_share * self.config.RISK_REWARD_RATIO
                entry = next_open
                sl = entry + risk_per_share
                tp = entry - reward_per_share
                
                if next_high >= sl:
                    pnl = -risk_per_share
                    outcome = "LOSS"
                elif next_low <= tp:
                    pnl = reward_per_share
                    outcome = "WIN"
                else:
                    pnl = 0
                    outcome = "NO FILL"
                    
                if pnl != 0:
                    self.trades.append({'type': 'SHORT', 'entry': entry, 'pnl': pnl, 'outcome': outcome})
                    capital += pnl
            
            equity.append(capital)
            
        self.equity_curve = equity
        self.final_capital = capital

    def report(self):
        if not self.trades:
            print("No trades generated.")
            return
        df_trades = pd.DataFrame(self.trades)
        wins = df_trades[df_trades['outcome'] == 'WIN']
        losses = df_trades[df_trades['outcome'] == 'LOSS']
        win_rate = len(wins) / len(df_trades) if len(df_trades) > 0 else 0
        total_return = (self.final_capital - self.config.INITIAL_CAPITAL) / self.config.INITIAL_CAPITAL * 100
        
        print("\\n" + "="*40)
        print(f"📊 BACKTEST REPORT: {self.config.SYMBOL}")
        print("="*40)
        print(f"Total Trades: {len(df_trades)}")
        print(f"Win Rate: {win_rate:.2%}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Net PnL: ${self.final_capital - self.config.INITIAL_CAPITAL:,.2f}")
        print(f"Return: {total_return:.2f}%")
        print("="*40)
        
        plt.figure(figsize=(12, 6))
        plt.plot(self.equity_curve, label='Equity Curve', color='green')
        plt.title(f'Strategy Equity Curve ({self.config.SYMBOL})')
        plt.xlabel('Bars')
        plt.ylabel('Capital ($)')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.show()

if __name__ == "__main__":
    config = BacktestConfig()
    bt = Backtester(config)
    try:
        bt.run()
        bt.report()
    except Exception as e:
        print(f"❌ Error during backtest: {e}")
""",

    "strategy.pine": """//@version=5
strategy("Volume Node Expansion 1:3", overlay=true, initial_capital=10000, default_qty_type=percent_of_equity, default_qty_value=10)

sessionStart = timestamp(year, month, dayofmonth, 09, 30)
sessionEnd = timestamp(year, month, dayofmonth, 16, 00)
sessionHigh = ta.highest(high, 100)
sessionLow = ta.lowest(low, 100)
sessionRange = sessionHigh - sessionLow

poc = (sessionHigh + sessionLow) / 2
vah = sessionLow + (sessionRange * 0.70)
val = sessionLow + (sessionRange * 0.30)

longCondition = close > vah and volume > ta.sma(volume, 10) * 1.5
shortCondition = close < val and volume > ta.sma(volume, 10) * 1.5

if (longCondition)
    strategy.entry("Long", strategy.long)
    sl = vah * 0.995
    tp = close + (3 * (close - sl))
    strategy.exit("Exit Long", "Long", stop=sl, limit=tp)

if (shortCondition)
    strategy.entry("Short", strategy.short)
    sl = val * 1.005
    tp = close - (3 * (sl - close))
    strategy.exit("Exit Short", "Short", stop=sl, limit=tp)

plot(vah, "VAH", color=color.green, style=style.line_dashed)
plot(val, "VAL", color=color.red, style=style.line_dashed)
plot(poc, "POC", color=color.gray)
""",

    "README.md": """# Volume Node Expansion Bot

A Python-based options trading bot focusing on a 33% win rate with 1:3 Risk-Reward ratio using Volume Profile analysis.

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and add your API keys.
3. Run Backtest: `python backtest.py`
4. Run Bot: `python main.py`

## Strategy
- **Entry:** Breakout of Value Area High/Low with Volume Spike + Retest.
- **Exit:** 1:3 Risk Reward Ratio.
- **Risk:** 1-2% per trade.

## Files
- `main.py`: Live trading entry point.
- `backtest.py`: Historical testing.
- `strategy.pine`: TradingView verification script.
"""
}

def create_project():
    print("🚀 Generating Volume Node Bot Project...")
    for filename, content in FILES.items():
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content.strip())
            print(f"✅ Created: {filename}")
        except Exception as e:
            print(f"❌ Error creating {filename}: {e}")
    print("\n🎉 Project generation complete!")
    print("👉 Next steps:")
    print("   1. Run: pip install -r requirements.txt")
    print("   2. Copy .env.example to .env and add your keys")
    print("   3. Run: python backtest.py")

if __name__ == "__main__":
    create_project()
