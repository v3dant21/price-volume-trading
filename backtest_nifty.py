import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from tqdm import tqdm
from volume_profile import VolumeProfile
from config import Config as BotConfig
import matplotlib.dates as mdates
from datetime import datetime

# Set style for better readability
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 14
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
plt.rcParams['legend.fontsize'] = 14
plt.rcParams['figure.titlesize'] = 20

class BacktestConfig:
    SYMBOL = "NIFTYBEES.NS"  # Nifty BeES ETF - tracks Nifty 50 index
    START_DATE = "2022-01-01"
    END_DATE = "2026-03-26"
    VP_LOOKBACK = 20
    VOLUME_MULTIPLIER = 1.5
    RISK_REWARD_RATIO = 3.0
    STOP_LOSS_PCT = 0.02
    INITIAL_CAPITAL = 100000  # ₹1,00,000
    POSITION_SIZE_PCT = 0.1  # 10% of capital per trade

class Backtester:
    def __init__(self, config):
        self.config = config
        self.data = None
        self.trades = []
        self.equity_curve = []
        self.equity_dates = []

    def load_data(self):
        print(f"📥 Downloading {self.config.SYMBOL} (Nifty BeES ETF)...")
        df = yf.download(self.config.SYMBOL, start=self.config.START_DATE, end=self.config.END_DATE)
        if len(df) == 0:
            raise Exception("No data downloaded.")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = df.columns.str.lower()
        df = df.dropna()
        self.data = df
        print(f"✅ Data loaded: {len(df)} rows from {df.index[0].date()} to {df.index[-1].date()}")

    def run(self):
        if self.data is None:
            self.load_data()
        df = self.data
        capital = self.config.INITIAL_CAPITAL
        equity = []

        print("🚀 Running Backtest on Nifty 50 (via Nifty BeES)...")

        for i in range(self.config.VP_LOOKBACK, len(df) - 1):
            past_data = df.iloc[i-self.config.VP_LOOKBACK:i]
            vp = VolumeProfile(past_data, self.config.VP_LOOKBACK)

            current_price = df['close'].iloc[i]
            next_open = df['open'].iloc[i+1]
            next_high = df['high'].iloc[i+1]
            next_low = df['low'].iloc[i+1]
            current_vol = df['volume'].iloc[i]
            avg_vol = df['volume'].iloc[i-10:i].mean()

            # LONG signal
            long_signal = (current_price > vp.vah) and (current_vol > avg_vol * self.config.VOLUME_MULTIPLIER)
            # SHORT signal
            short_signal = (current_price < vp.val) and (current_vol > avg_vol * self.config.VOLUME_MULTIPLIER)

            if long_signal:
                risk_per_share = current_price * self.config.STOP_LOSS_PCT
                reward_per_share = risk_per_share * self.config.RISK_REWARD_RATIO
                entry = next_open
                sl = entry - risk_per_share
                tp = entry + reward_per_share

                shares = int((capital * self.config.POSITION_SIZE_PCT) / entry)
                if shares < 1:
                    shares = 1

                if next_low <= sl:
                    pnl = -risk_per_share * shares
                    outcome = "LOSS"
                elif next_high >= tp:
                    pnl = reward_per_share * shares
                    outcome = "WIN"
                else:
                    pnl = 0
                    outcome = "NO FILL"

                if pnl != 0:
                    self.trades.append({
                        'date': df.index[i+1],
                        'type': 'LONG',
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'shares': shares,
                        'pnl': pnl,
                        'outcome': outcome,
                        'capital_after': capital + pnl
                    })
                    capital += pnl

            elif short_signal:
                risk_per_share = current_price * self.config.STOP_LOSS_PCT
                reward_per_share = risk_per_share * self.config.RISK_REWARD_RATIO
                entry = next_open
                sl = entry + risk_per_share
                tp = entry - reward_per_share

                shares = int((capital * self.config.POSITION_SIZE_PCT) / entry)
                if shares < 1:
                    shares = 1

                if next_high >= sl:
                    pnl = -risk_per_share * shares
                    outcome = "LOSS"
                elif next_low <= tp:
                    pnl = reward_per_share * shares
                    outcome = "WIN"
                else:
                    pnl = 0
                    outcome = "NO FILL"

                if pnl != 0:
                    self.trades.append({
                        'date': df.index[i+1],
                        'type': 'SHORT',
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'shares': shares,
                        'pnl': pnl,
                        'outcome': outcome,
                        'capital_after': capital + pnl
                    })
                    capital += pnl

            equity.append(capital)
            self.equity_dates.append(df.index[i])

        self.equity_curve = equity
        self.final_capital = capital

    def generate_report(self):
        if not self.trades:
            print("No trades generated.")
            return None

        df_trades = pd.DataFrame(self.trades)
        df_trades.set_index('date', inplace=True)

        wins = df_trades[df_trades['outcome'] == 'WIN']
        losses = df_trades[df_trades['outcome'] == 'LOSS']

        total_trades = len(df_trades)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0

        total_pnl = df_trades['pnl'].sum()
        total_return = (self.final_capital - self.config.INITIAL_CAPITAL) / self.config.INITIAL_CAPITAL * 100

        # Calculate metrics
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else float('inf')

        # Drawdown calculation
        equity_series = pd.Series(self.equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown = drawdown.min()

        # Sharpe ratio (simplified, assuming 252 trading days)
        daily_returns = equity_series.pct_change().dropna()
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0

        # Consecutive losses
        loss_streaks = []
        current_streak = 0
        for _, row in df_trades.iterrows():
            if row['outcome'] == 'LOSS':
                current_streak += 1
                loss_streaks.append(current_streak)
            else:
                current_streak = 0
        max_consecutive_losses = max(loss_streaks) if loss_streaks else 0

        report = {
            'total_trades': total_trades,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'max_consecutive_losses': max_consecutive_losses,
            'final_capital': self.final_capital,
            'df_trades': df_trades,
            'equity_curve': self.equity_curve,
            'equity_dates': self.equity_dates,
            'drawdown': drawdown
        }

        return report

    def plot_report(self, report):
        """Generate comprehensive performance charts with large readable text"""
        fig = plt.figure(figsize=(12, 8))
        fig.suptitle('NIFTY 50 VOLUME PROFILE STRATEGY - PERFORMANCE REPORT',
                     fontsize=28, fontweight='bold', y=0.98)

        gs = fig.add_gridspec(4, 2, hspace=0.35, wspace=0.25,
                              top=0.93, bottom=0.05, left=0.06, right=0.96)

        # Color scheme
        green = '#27ae60'
        red = '#c0392b'
        blue = '#2980b9'

        # 1. Equity Curve (full width top)
        ax1 = fig.add_subplot(gs[0, :])
        equity_series = pd.Series(report['equity_curve'], index=report['equity_dates'])
        ax1.plot(equity_series.index, equity_series.values, color=green, linewidth=3, label='Equity Curve')
        ax1.axhline(y=self.config.INITIAL_CAPITAL, color='gray', linestyle='--', linewidth=2, label='Initial Capital')
        ax1.set_title('EQUITY CURVE OVER TIME', fontsize=20, fontweight='bold', pad=15)
        ax1.set_xlabel('Date', fontsize=16, fontweight='bold')
        ax1.set_ylabel('Capital (₹)', fontsize=16, fontweight='bold')
        ax1.legend(loc='upper left', fontsize=14, framealpha=0.9)
        ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.8)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax1.tick_params(labelsize=12)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Add final value annotation
        final_val = report['final_capital']
        ax1.annotate(f'Final: ₹{final_val:,.0f}',
                    xy=(equity_series.index[-1], final_val),
                    xytext=(0.02, 0.95),
                    transform=ax1.transAxes,
                    fontsize=16, fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor=green, alpha=0.8),
                    color='white')

        # 2. Drawdown Chart
        ax2 = fig.add_subplot(gs[1, 0])
        ax2.fill_between(report['drawdown'].index, report['drawdown'].values, 0,
                        color=red, alpha=0.6, edgecolor='darkred', linewidth=1)
        ax2.set_title('DRAWDOWN (%)', fontsize=18, fontweight='bold', pad=12)
        ax2.set_xlabel('Date', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Drawdown %', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, linestyle='-', linewidth=0.8)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax2.tick_params(labelsize=12)
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        # Add max DD annotation
        max_dd = report['max_drawdown']
        ax2.annotate(f'Max DD: {max_dd:.1f}%',
                    xy=(0.5, 0.1),
                    transform=ax2.transAxes,
                    fontsize=14, fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor=red, alpha=0.8),
                    color='white')

        # 3. Monthly Returns
        ax3 = fig.add_subplot(gs[1, 1])
        df_trades = report['df_trades']
        monthly_pnl = df_trades['pnl'].resample('ME').sum()
        colors = [green if x >= 0 else red for x in monthly_pnl.values]
        bars = ax3.bar(monthly_pnl.index, monthly_pnl.values, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
        ax3.set_title('MONTHLY P&L', fontsize=18, fontweight='bold', pad=12)
        ax3.set_xlabel('Month', fontsize=14, fontweight='bold')
        ax3.set_ylabel('P&L (₹)', fontsize=14, fontweight='bold')
        ax3.grid(True, alpha=0.3, linestyle='-', linewidth=0.8, axis='y')
        ax3.axhline(y=0, color='black', linewidth=1)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax3.tick_params(labelsize=11)
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

        # 4. Win/Loss Distribution
        ax4 = fig.add_subplot(gs[2, 0])
        pnl_values = df_trades['pnl'].values
        wins_pnl = [x for x in pnl_values if x > 0]
        losses_pnl = [x for x in pnl_values if x < 0]

        n, bins_w, patches_w = ax4.hist(wins_pnl, bins=15, color=green, alpha=0.7,
                                         label=f'Wins ({len(wins_pnl)})', edgecolor='black', linewidth=1)
        n, bins_l, patches_l = ax4.hist(losses_pnl, bins=15, color=red, alpha=0.7,
                                         label=f'Losses ({len(losses_pnl)})', edgecolor='black', linewidth=1)
        ax4.set_title('P&L DISTRIBUTION', fontsize=18, fontweight='bold', pad=12)
        ax4.set_xlabel('P&L (₹)', fontsize=14, fontweight='bold')
        ax4.set_ylabel('Frequency', fontsize=14, fontweight='bold')
        ax4.legend(fontsize=14, framealpha=0.9)
        ax4.grid(True, alpha=0.3, linestyle='-', linewidth=0.8)
        ax4.tick_params(labelsize=12)

        # 5. Cumulative P&L
        ax5 = fig.add_subplot(gs[2, 1])
        cumulative_pnl = df_trades['pnl'].cumsum()
        ax5.plot(cumulative_pnl.index, cumulative_pnl.values, color=blue, linewidth=3, marker='o', markersize=4)
        ax5.axhline(y=0, color='gray', linestyle='-', linewidth=1.5)
        ax5.set_title('CUMULATIVE P&L', fontsize=18, fontweight='bold', pad=12)
        ax5.set_xlabel('Trade Number', fontsize=14, fontweight='bold')
        ax5.set_ylabel('Cumulative P&L (₹)', fontsize=14, fontweight='bold')
        ax5.grid(True, alpha=0.3, linestyle='-', linewidth=0.8)
        ax5.tick_params(labelsize=12)

        # Add total annotation
        total_pnl = cumulative_pnl.iloc[-1]
        ax5.annotate(f'Total: ₹{total_pnl:,.0f}',
                    xy=(len(cumulative_pnl)-1, total_pnl),
                    xytext=(0.98, 0.95),
                    transform=ax5.transAxes,
                    fontsize=14, fontweight='bold',
                    horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor=blue, alpha=0.8),
                    color='white')

        # 6. Key Metrics Table (full width bottom)
        ax6 = fig.add_subplot(gs[3, :])
        ax6.axis('off')

        metrics_text = (
            f"PERFORMANCE SUMMARY\n"
            f"{'─'*80}\n"
            f"│  Total Trades: {report['total_trades']:<10} │  Win Rate: {report['win_rate']*100:>6.1f}%{'':>4} │  Profit Factor: {report['profit_factor']:>6.2f}{'':>4} │\n"
            f"│  Wins: {report['wins']:<15} │  Losses: {report['losses']:<13} │  Max Consecutive Losses: {report['max_consecutive_losses']:<3} │\n"
            f"│  Avg Win: ₹{report['avg_win']:>10,.0f} │  Avg Loss: ₹{report['avg_loss']:>10,.0f} │  Sharpe Ratio: {report['sharpe_ratio']:>6.2f}{'':>4} │\n"
            f"{'─'*80}\n"
            f"│  Initial Capital: ₹{self.config.INITIAL_CAPITAL:>10,} │  Final Capital: ₹{report['final_capital']:>12,.0f} │\n"
            f"│  Total P&L: ₹{report['total_pnl']:>12,.0f} │  Total Return: {report['total_return']:>8.1f}% │  Max Drawdown: {report['max_drawdown']:>7.1f}% │\n"
            f"{'─'*80}"
        )

        ax6.text(0.5, 0.5, metrics_text, fontsize=14, fontfamily='monospace',
                verticalalignment='center', horizontalalignment='center',
                bbox=dict(boxstyle='round', facecolor='#ecf0f1', alpha=0.8, edgecolor='#34495e', linewidth=2))

        # Save the plot
        plt.savefig('nifty_performance_report.png', dpi=80, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        print("\n📊 Performance report saved to: nifty_performance_report.png")

        # Also save as PDF for better quality
        plt.savefig('nifty_performance_report.pdf', bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        print("📄 PDF report saved to: nifty_performance_report.pdf")

        return fig

    def print_summary(self, report):
        """Print detailed summary to console"""
        print("\n" + "="*70)
        print(f"📊 NIFTY 50 STRATEGY PERFORMANCE REPORT")
        print("="*70)
        print(f"Period: {self.config.START_DATE} to {self.config.END_DATE}")
        print(f"Initial Capital: ₹{self.config.INITIAL_CAPITAL:,.2f}")
        print("-"*70)
        print(f"📈 FINAL CAPITAL: ₹{report['final_capital']:,.2f}")
        print(f"💰 TOTAL P&L: ₹{report['total_pnl']:,.2f}")
        print(f"📊 TOTAL RETURN: {report['total_return']:.2f}%")
        print("-"*70)
        print(f"📝 Total Trades: {report['total_trades']}")
        print(f"✅ Wins: {report['wins']} ({report['win_rate']*100:.1f}%)")
        print(f"❌ Losses: {report['losses']}")
        print(f"📉 Max Consecutive Losses: {report['max_consecutive_losses']}")
        print("-"*70)
        print(f"🏆 Average Win: ₹{report['avg_win']:,.2f}")
        print(f"📉 Average Loss: ₹{report['avg_loss']:,.2f}")
        print(f"📊 Profit Factor: {report['profit_factor']:.2f}")
        print("-"*70)
        print(f"📉 Max Drawdown: {report['max_drawdown']:.2f}%")
        print(f"📈 Sharpe Ratio: {report['sharpe_ratio']:.2f}")
        print("="*70)


if __name__ == "__main__":
    config = BacktestConfig()
    bt = Backtester(config)
    try:
        bt.run()
        report = bt.generate_report()
        if report:
            bt.print_summary(report)
            bt.plot_report(report)
            print("\n✅ Report generation complete!")
    except Exception as e:
        print(f"❌ Error during backtest: {e}")
        import traceback
        traceback.print_exc()
