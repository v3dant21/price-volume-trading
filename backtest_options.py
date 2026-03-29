"""
Nifty 50 Options Backtest
Simulates ATM Call/Put options trading based on volume profile strategy signals.
Uses Nifty 50 index data and calculates options P&L based on delta/gamma approximation.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from volume_profile import VolumeProfile
from config import Config as BotConfig
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 12

class OptionsBacktestConfig:
    SYMBOL = "NIFTYBEES.NS"  # Nifty BeES ETF
    START_DATE = "2025-03-29"  # 1 year ago
    END_DATE = "2026-03-29"
    VP_LOOKBACK = 20
    VOLUME_MULTIPLIER = 1.5
    RISK_REWARD_RATIO = 3.0
    STOP_LOSS_PCT = 0.02
    INITIAL_CAPITAL = 100000  # ₹1,00,000

    # Options specific
    OPTION_LOT_SIZE = 25  # Nifty lot size
    ATM_STRIKE_DISTANCE = 0  # ATM option
    PREMIUM_DECAY_PER_DAY = 0.05  # 5% theta decay per day
    DELTA_CALL = 0.5  # ATM call delta
    DELTA_PUT = -0.5  # ATM put delta
    GAMMA = 0.0002  # Gamma for delta adjustment
    POSITION_SIZE_PCT = 0.2  # 20% of capital per trade

class OptionsBacktester:
    def __init__(self, config):
        self.config = config
        self.data = None
        self.trades = []
        self.equity_curve = []
        self.equity_dates = []

    def load_data_from_dhan(self):
        """Fetch Nifty 50 data from Dhan API"""
        try:
            from dhanhq import dhanhq
            from config import Config

            if not Config.DHAN_ACCESS_TOKEN:
                print("⚠️ Dhan credentials not found. Using yfinance fallback.")
                return self.load_data_from_yfinance()

            api = dhanhq.DhanHQ(Config.DHAN_ACCESS_TOKEN)
            print("📥 Fetching Nifty 50 data from Dhan API...")

            # Fetch 1 year of daily data for Nifty BeES
            response = api.get_historical(scrip="NIFTYBEES", exchange='NSE', timeframe='ONE_DAY')

            if response['status'] != 'success':
                print(f"⚠️ Dhan API Error: {response.get('remarks', 'Unknown error')}")
                return self.load_data_from_yfinance()

            data = response['data']
            if not data:
                return self.load_data_from_yfinance()

            df = pd.DataFrame(data)
            df = df.rename(columns={
                'open': 'open', 'high': 'high', 'low': 'low',
                'close': 'close', 'volume': 'volume', 'time': 'datetime'
            })
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')

            # Filter by date range
            df = df.loc[self.config.START_DATE:self.config.END_DATE]

            # Convert types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna()
            self.data = df
            print(f"✅ Dhan data loaded: {len(df)} rows")
            return True

        except Exception as e:
            print(f"⚠️ Dhan API error: {e}. Using yfinance fallback.")
            return self.load_data_from_yfinance()

    def load_data_from_yfinance(self):
        """Fallback to yfinance for Nifty 50 index"""
        print(f"📥 Downloading NIFTY.NS from Yahoo Finance...")
        try:
            df = yf.download("NIFTY.NS", start=self.config.START_DATE, end=self.config.END_DATE)
            if len(df) == 0:
                # Try alternative symbol
                df = yf.download("^NSEI", start=self.config.START_DATE, end=self.config.END_DATE)

            if len(df) == 0:
                raise Exception("No data downloaded from either symbol")

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = df.columns.str.lower()
            df = df.dropna()
            self.data = df
            print(f"✅ Data loaded: {len(df)} rows from {df.index[0].date()} to {df.index[-1].date()}")
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def calculate_option_premium(self, underlying_price, option_type, entry_date, exit_date=None):
        """
        Calculate approximate option premium using delta-gamma approximation.
        This is a simplified model - real options pricing uses Black-Scholes.
        """
        # Base premium (simplified - typically ATM options are ~0.5-1% of underlying)
        base_premium = underlying_price * 0.008  # 0.8% of underlying

        if option_type == 'CE':
            delta = self.config.DELTA_CALL
        else:
            delta = self.config.DELTA_PUT

        return base_premium

    def calculate_option_pnl(self, entry_price, underlying_entry, underlying_exit, option_type, days_held=1):
        """
        Calculate P&L for an options position.
        Uses delta-gamma approximation with theta decay.
        """
        price_change = underlying_exit - underlying_entry

        # Delta P&L
        if option_type == 'CE':
            delta_pnl = price_change * self.config.DELTA_CALL
        else:
            delta_pnl = -price_change * self.config.DELTA_PUT  # Put delta is negative

        # Gamma adjustment (delta changes with price)
        gamma_pnl = 0.5 * self.config.GAMMA * (price_change ** 2) * 100

        # Theta decay (time value loss)
        theta_decay = entry_price * self.config.PREMIUM_DECAY_PER_DAY * days_held

        # Exit premium
        exit_premium = entry_price + delta_pnl + gamma_pnl - theta_decay

        pnl_per_unit = exit_premium - entry_price

        return pnl_per_unit, exit_premium

    def run(self):
        if self.data is None:
            if not self.load_data_from_dhan():
                print("❌ Failed to load data")
                return False

        df = self.data
        capital = self.config.INITIAL_CAPITAL
        equity = []

        print("🚀 Running Options Backtest...")
        print(f"   Strategy: Volume Profile Breakout on Nifty 50")
        print(f"   Instrument: ATM Options (simulated)")

        for i in range(self.config.VP_LOOKBACK, len(df) - 1):
            past_data = df.iloc[i-self.config.VP_LOOKBACK:i]
            vp = VolumeProfile(past_data, self.config.VP_LOOKBACK)

            current_price = df['close'].iloc[i]
            next_open = df['open'].iloc[i+1]
            next_high = df['high'].iloc[i+1]
            next_low = df['low'].iloc[i+1]
            current_vol = df['volume'].iloc[i]
            avg_vol = df['volume'].iloc[i-10:i].mean() if i >= 10 else current_vol

            # LONG signal -> Buy CE
            long_signal = (current_price > vp.vah) and (current_vol > avg_vol * self.config.VOLUME_MULTIPLIER)
            # SHORT signal -> Buy PE
            short_signal = (current_price < vp.val) and (current_vol > avg_vol * self.config.VOLUME_MULTIPLIER)

            if long_signal:
                option_type = 'CE'
                entry_price = self.calculate_option_premium(next_open, option_type, df.index[i+1])
                sl_price = entry_price * 0.80  # 20% SL on premium
                tp_price = entry_price * 1.60  # 60% target (approx 1:3 RR)

                # Calculate units (lots)
                risk_per_lot = entry_price * 0.20 * self.config.OPTION_LOT_SIZE
                lots = int((capital * self.config.POSITION_SIZE_PCT) / (entry_price * self.config.OPTION_LOT_SIZE))
                if lots < 1:
                    lots = 1

                # Simulate exit (use next day's data)
                days_held = 1
                underlying_exit = df['close'].iloc[i+1] if i+1 < len(df) else next_open

                pnl_per_unit, exit_premium = self.calculate_option_pnl(
                    entry_price, next_open, underlying_exit, option_type, days_held
                )

                # Check SL/TP
                if exit_premium <= sl_price:
                    pnl = -risk_per_lot * lots
                    outcome = "LOSS"
                    actual_exit = sl_price
                elif exit_premium >= tp_price:
                    pnl = (tp_price - entry_price) * self.config.OPTION_LOT_SIZE * lots
                    outcome = "WIN"
                    actual_exit = tp_price
                else:
                    pnl = pnl_per_unit * self.config.OPTION_LOT_SIZE * lots
                    outcome = "EXIT"
                    actual_exit = exit_premium

                if pnl != 0:
                    self.trades.append({
                        'date': df.index[i+1].strftime('%Y-%m-%d'),
                        'type': 'LONG',
                        'option_type': option_type,
                        'underlying_entry': next_open,
                        'underlying_exit': underlying_exit,
                        'entry_premium': entry_price,
                        'exit_premium': actual_exit,
                        'lots': lots,
                        'pnl': pnl,
                        'outcome': outcome,
                        'capital_after': capital + pnl
                    })
                    capital += pnl

            elif short_signal:
                option_type = 'PE'
                entry_price = self.calculate_option_premium(next_open, option_type, df.index[i+1])
                sl_price = entry_price * 1.20  # 20% SL on premium
                tp_price = entry_price * 0.40  # 60% profit

                lots = int((capital * self.config.POSITION_SIZE_PCT) / (entry_price * self.config.OPTION_LOT_SIZE))
                if lots < 1:
                    lots = 1

                days_held = 1
                underlying_exit = df['close'].iloc[i+1] if i+1 < len(df) else next_open

                pnl_per_unit, exit_premium = self.calculate_option_pnl(
                    entry_price, next_open, underlying_exit, option_type, days_held
                )

                if exit_premium >= sl_price:
                    pnl = -(sl_price - entry_price) * self.config.OPTION_LOT_SIZE * lots
                    outcome = "LOSS"
                    actual_exit = sl_price
                elif exit_premium <= tp_price:
                    pnl = (entry_price - tp_price) * self.config.OPTION_LOT_SIZE * lots
                    outcome = "WIN"
                    actual_exit = tp_price
                else:
                    pnl = (entry_price - exit_premium) * self.config.OPTION_LOT_SIZE * lots
                    outcome = "EXIT"
                    actual_exit = exit_premium

                if pnl != 0:
                    self.trades.append({
                        'date': df.index[i+1].strftime('%Y-%m-%d'),
                        'type': 'SHORT',
                        'option_type': option_type,
                        'underlying_entry': next_open,
                        'underlying_exit': underlying_exit,
                        'entry_premium': entry_price,
                        'exit_premium': actual_exit,
                        'lots': lots,
                        'pnl': pnl,
                        'outcome': outcome,
                        'capital_after': capital + pnl
                    })
                    capital += pnl

            equity.append(capital)
            self.equity_dates.append(df.index[i])

        self.equity_curve = equity
        self.final_capital = capital
        print(f"✅ Backtest complete. Final capital: ₹{self.final_capital:,.0f}")
        return True

    def generate_report(self):
        if not self.trades:
            print("No trades generated.")
            return None

        df_trades = pd.DataFrame(self.trades)
        df_trades.set_index('date', inplace=True)

        wins = df_trades[df_trades['outcome'] == 'WIN']
        losses = df_trades[df_trades['outcome'] == 'LOSS']
        exits = df_trades[df_trades['outcome'] == 'EXIT']

        total_trades = len(df_trades)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0

        total_pnl = df_trades['pnl'].sum()
        total_return = (self.final_capital - self.config.INITIAL_CAPITAL) / self.config.INITIAL_CAPITAL * 100

        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else float('inf')

        equity_series = pd.Series(self.equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown = drawdown.min()

        daily_returns = equity_series.pct_change().dropna()
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0

        # Max consecutive losses
        loss_streaks = []
        current_streak = 0
        for _, row in df_trades.iterrows():
            if row['outcome'] == 'LOSS':
                current_streak += 1
                loss_streaks.append(current_streak)
            else:
                current_streak = 0
        max_consecutive_losses = max(loss_streaks) if loss_streaks else 0

        return {
            'trades': self.trades,
            'metrics': {
                'total_trades': total_trades,
                'wins': len(wins),
                'losses': len(losses),
                'exits': len(exits),
                'win_rate': win_rate * 100,
                'total_pnl': total_pnl,
                'total_return': total_return,
                'avg_win': avg_win,
                'avg_loss': abs(avg_loss) if avg_loss else 0,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'max_consecutive_losses': max_consecutive_losses,
                'final_capital': self.final_capital,
                'initial_capital': self.config.INITIAL_CAPITAL
            },
            'config': {
                'symbol': self.config.SYMBOL,
                'period': f"{self.config.START_DATE} to {self.config.END_DATE}",
                'vp_lookback': self.config.VP_LOOKBACK,
                'volume_multiplier': self.config.VOLUME_MULTIPLIER,
                'risk_reward': f"1:{self.config.RISK_REWARD_RATIO}",
                'stop_loss': f"{self.config.STOP_LOSS_PCT*100}%",
                'position_size': f"{self.config.POSITION_SIZE_PCT*100}%",
                'lot_size': self.config.OPTION_LOT_SIZE,
            },
            'df_trades': df_trades,
            'equity_curve': self.equity_curve,
            'equity_dates': self.equity_dates,
            'drawdown': drawdown
        }

    def plot_report(self, report):
        """Generate comprehensive options performance charts"""
        fig = plt.figure(figsize=(16, 12))
        fig.suptitle('NIFTY 50 OPTIONS STRATEGY - PERFORMANCE REPORT', fontsize=20, fontweight='bold')

        gs = fig.add_gridspec(4, 2, hspace=0.4, wspace=0.25)

        green = '#27ae60'
        red = '#c0392b'
        blue = '#2980b9'

        # 1. Equity Curve
        ax1 = fig.add_subplot(gs[0, :])
        equity_series = pd.Series(report['equity_curve'], index=report['equity_dates'])
        ax1.plot(equity_series.index, equity_series.values, color=green, linewidth=2.5, label='Equity')
        ax1.axhline(y=self.config.INITIAL_CAPITAL, color='gray', linestyle='--', linewidth=2, label='Initial')
        ax1.set_title('EQUITY CURVE', fontsize=16, fontweight='bold')
        ax1.set_xlabel('Date', fontsize=12)
        ax1.set_ylabel('Capital (₹)', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # 2. Drawdown
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.fill_between(report['drawdown'].index, report['drawdown'].values, 0, color=red, alpha=0.5)
        ax2.set_title('DRAWDOWN (%)', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Drawdown %', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        # 3. Monthly P&L
        ax3 = fig.add_subplot(gs[1, 1])
        df_trades = report['df_trades']
        df_trades.index = pd.to_datetime(df_trades.index)
        monthly_pnl = df_trades['pnl'].resample('ME').sum()
        colors = [green if x >= 0 else red for x in monthly_pnl.values]
        ax3.bar(monthly_pnl.index, monthly_pnl.values, color=colors, alpha=0.8, edgecolor='black')
        ax3.set_title('MONTHLY P&L', fontsize=14, fontweight='bold')
        ax3.set_ylabel('P&L (₹)', fontsize=12)
        ax3.axhline(y=0, color='black', linewidth=1)
        ax3.grid(True, alpha=0.3, axis='y')
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

        # 4. Win/Loss Distribution
        ax4 = fig.add_subplot(gs[2, 0])
        pnl_values = df_trades['pnl'].values
        wins_pnl = [x for x in pnl_values if x > 0]
        losses_pnl = [x for x in pnl_values if x < 0]

        ax4.hist(wins_pnl, bins=10, color=green, alpha=0.7, label=f'Wins ({len(wins_pnl)})', edgecolor='black')
        ax4.hist(losses_pnl, bins=10, color=red, alpha=0.7, label=f'Losses ({len(losses_pnl)})', edgecolor='black')
        ax4.set_title('P&L DISTRIBUTION', fontsize=14, fontweight='bold')
        ax4.set_xlabel('P&L (₹)', fontsize=12)
        ax4.set_ylabel('Frequency', fontsize=12)
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        # 5. Cumulative P&L
        ax5 = fig.add_subplot(gs[2, 1])
        cumulative_pnl = df_trades['pnl'].cumsum()
        ax5.plot(cumulative_pnl.index, cumulative_pnl.values, color=blue, linewidth=2.5, marker='o', markersize=5)
        ax5.axhline(y=0, color='gray', linestyle='-', linewidth=1)
        ax5.set_title('CUMULATIVE P&L', fontsize=14, fontweight='bold')
        ax5.set_xlabel('Trade Number', fontsize=12)
        ax5.set_ylabel('Cumulative P&L (₹)', fontsize=12)
        ax5.grid(True, alpha=0.3)

        # 6. Metrics Table
        ax6 = fig.add_subplot(gs[3, :])
        ax6.axis('off')

        m = report['metrics']
        metrics_text = (
            f"PERFORMANCE SUMMARY\n"
            f"{'─'*85}\n"
            f"│  Total Trades: {m['total_trades']:<12} │  Win Rate: {m['win_rate']:>6.1f}%{'':>4} │  Profit Factor: {m['profit_factor']:>8.2f}   │\n"
            f"│  Wins: {m['wins']:<15} │  Losses: {m['losses']:<13} │  Max Consecutive: {m['max_consecutive_losses']:<3} │\n"
            f"│  Avg Win: ₹{m['avg_win']:>10,.0f} │  Avg Loss: ₹{m['avg_loss']:>10,.0f} │  Sharpe Ratio: {m['sharpe_ratio']:>8.2f} │\n"
            f"{'─'*85}\n"
            f"│  Initial Capital: ₹{self.config.INITIAL_CAPITAL:>10,} │  Final Capital: ₹{m['final_capital']:>12,.0f} │\n"
            f"│  Total P&L: ₹{m['total_pnl']:>12,.0f} │  Total Return: {m['total_return']:>10.1f}% │  Max DD: {m['max_drawdown']:>8.1f}% │\n"
            f"{'─'*85}"
        )

        ax6.text(0.5, 0.5, metrics_text, fontsize=12, fontfamily='monospace',
                verticalalignment='center', horizontalalignment='center',
                bbox=dict(boxstyle='round', facecolor='#ecf0f1', alpha=0.9, edgecolor='#34495e'))

        plt.savefig('nifty_options_report.png', dpi=150, bbox_inches='tight', facecolor='white')
        print("📊 Chart saved: nifty_options_report.png")

        return fig

    def print_summary(self, report):
        m = report['metrics']
        c = report['config']

        print("\n" + "="*70)
        print(f"📊 NIFTY 50 OPTIONS STRATEGY PERFORMANCE REPORT")
        print("="*70)
        print(f"Period: {c['period']}")
        print(f"Initial Capital: ₹{self.config.INITIAL_CAPITAL:,.0f}")
        print("-"*70)
        print(f"📈 FINAL CAPITAL: ₹{m['final_capital']:,.0f}")
        print(f"💰 TOTAL P&L: ₹{m['total_pnl']:,.0f}")
        print(f"📊 TOTAL RETURN: {m['total_return']:.2f}%")
        print("-"*70)
        print(f"📝 Total Trades: {m['total_trades']}")
        print(f"✅ Wins: {m['wins']} ({m['win_rate']:.1f}%)")
        print(f"❌ Losses: {m['losses']}")
        print(f"🔄 Exits: {m['exits']}")
        print(f"📉 Max Consecutive Losses: {m['max_consecutive_losses']}")
        print("-"*70)
        print(f"🏆 Average Win: ₹{m['avg_win']:,.0f}")
        print(f"📉 Average Loss: ₹{m['avg_loss']:,.0f}")
        print(f"📊 Profit Factor: {m['profit_factor']:.2f}")
        print("-"*70)
        print(f"📉 Max Drawdown: {m['max_drawdown']:.2f}%")
        print(f"📈 Sharpe Ratio: {m['sharpe_ratio']:.2f}")
        print("="*70)

import yfinance as yf

if __name__ == "__main__":
    config = OptionsBacktestConfig()
    bt = OptionsBacktester(config)

    if bt.run():
        report = bt.generate_report()
        if report:
            bt.print_summary(report)
            bt.plot_report(report)
            print("\n✅ Report generation complete!")
