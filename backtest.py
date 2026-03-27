import pandas as pd
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
        # Convert to lowercase for volume_profile.py compatibility
        df.columns = df.columns.str.lower()
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
            
            current_price = df['close'].iloc[i]
            next_open = df['open'].iloc[i+1]
            next_high = df['high'].iloc[i+1]
            next_low = df['low'].iloc[i+1]
            current_vol = df['volume'].iloc[i]
            avg_vol = df['volume'].iloc[i-10:i].mean()

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
        
        print("\n" + "="*40)
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