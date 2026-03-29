import pandas as pd
import numpy as np
import yfinance as yf
from volume_profile import VolumeProfile
from datetime import datetime
import json

class BacktestConfig:
    SYMBOL = "NIFTYBEES.NS"
    START_DATE = "2025-03-29"
    END_DATE = "2026-03-29"
    VP_LOOKBACK = 20
    VOLUME_MULTIPLIER = 1.5
    RISK_REWARD_RATIO = 3.0
    STOP_LOSS_PCT = 0.02
    INITIAL_CAPITAL = 100000
    POSITION_SIZE_PCT = 0.1

class Backtester:
    def __init__(self, config):
        self.config = config
        self.data = None
        self.trades = []
        self.equity_curve = []
        self.equity_dates = []

    def load_data(self):
        df = yf.download(self.config.SYMBOL, start=self.config.START_DATE, end=self.config.END_DATE)
        if len(df) == 0:
            raise Exception("No data downloaded.")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = df.columns.str.lower()
        df = df.dropna()
        self.data = df

    def run(self):
        if self.data is None:
            self.load_data()
        df = self.data
        capital = self.config.INITIAL_CAPITAL
        equity = []

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
                        'date': df.index[i+1].strftime('%Y-%m-%d'),
                        'type': 'LONG',
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'shares': shares,
                        'pnl': pnl,
                        'outcome': outcome,
                        'exit': sl if outcome == "LOSS" else tp,
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
                        'date': df.index[i+1].strftime('%Y-%m-%d'),
                        'type': 'SHORT',
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'shares': shares,
                        'pnl': pnl,
                        'outcome': outcome,
                        'exit': sl if outcome == "LOSS" else tp,
                        'capital_after': capital + pnl
                    })
                    capital += pnl

            equity.append(capital)
            self.equity_dates.append(df.index[i])

        self.equity_curve = equity
        self.final_capital = capital

    def generate_report_data(self):
        if not self.trades:
            return None

        df_trades = pd.DataFrame(self.trades)
        wins = df_trades[df_trades['outcome'] == 'WIN']
        losses = df_trades[df_trades['outcome'] == 'LOSS']

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
                'win_rate': win_rate * 100,
                'total_pnl': total_pnl,
                'total_return': total_return,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
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
            }
        }

def generate_html_report(report_data):
    trades = report_data['trades']
    m = report_data['metrics']
    c = report_data['config']

    trades_html = ""
    for i, trade in enumerate(trades):
        color_class = "win" if trade['outcome'] == "WIN" else "loss"
        pnl_class = "positive" if trade['pnl'] >= 0 else "negative"
        type_color = "#00ff88" if trade['type'] == "LONG" else "#ff4757"
        pnl_sign = "+" if trade['pnl'] >= 0 else ""
        trades_html += f"""
                    <tr>
                        <td>{i + 1}</td>
                        <td>{trade['date']}</td>
                        <td style="color: {type_color}">{trade['type']}</td>
                        <td>₹{trade['entry']:.2f}</td>
                        <td>₹{trade['exit']:.2f}</td>
                        <td class="{pnl_class}">{pnl_sign}₹{trade['pnl']:.2f}</td>
                        <td class="{color_class}">{trade['outcome']}</td>
                    </tr>"""

    return_class = "positive" if m['total_return'] >= 0 else "negative"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nifty 50 Strategy Performance Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            padding: 40px 20px;
            color: #fff;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            font-size: 2.5em;
            margin-bottom: 10px;
            color: #00d9ff;
            text-shadow: 0 0 20px rgba(0, 217, 255, 0.5);
        }}
        .subtitle {{
            text-align: center;
            color: #888;
            margin-bottom: 40px;
            font-size: 1.1em;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .metric-card {{
            background: linear-gradient(145deg, #1e2a4a, #152238);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0, 217, 255, 0.2);
        }}
        .metric-label {{
            font-size: 0.9em;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
        }}
        .positive {{ color: #00ff88; }}
        .negative {{ color: #ff4757; }}
        .neutral {{ color: #00d9ff; }}
        .section {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .section h2 {{
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #00d9ff;
            border-bottom: 2px solid #00d9ff;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            overflow: hidden;
        }}
        th, td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        th {{
            background: rgba(0, 217, 255, 0.2);
            font-weight: 600;
            color: #00d9ff;
        }}
        tr:hover {{
            background: rgba(255, 255, 255, 0.05);
        }}
        .win {{ color: #00ff88; }}
        .loss {{ color: #ff4757; }}
        .summary-box {{
            background: linear-gradient(145deg, #0f3460, #1a1a2e);
            border-radius: 15px;
            padding: 30px;
            text-align: center;
            border: 2px solid #00d9ff;
            margin-bottom: 30px;
        }}
        .summary-box h3 {{
            font-size: 1.8em;
            margin-bottom: 15px;
            color: #fff;
        }}
        .summary-value {{
            font-size: 3em;
            font-weight: bold;
        }}
        .strategy-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        .info-item {{
            background: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }}
        .info-label {{
            font-size: 0.85em;
            color: #888;
            margin-bottom: 5px;
        }}
        .info-value {{
            font-size: 1.2em;
            color: #fff;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 NIFTY 50 STRATEGY PERFORMANCE REPORT</h1>
        <p class="subtitle">Volume Profile Breakout Strategy | {c['symbol']} | {c['period']}</p>

        <div class="summary-box">
            <h3>Total Return</h3>
            <div class="summary-value {return_class}">{m['total_return']:.2f}%</div>
            <p style="margin-top: 10px; color: #888;">₹{m['initial_capital']:,.0f} → ₹{m['final_capital']:,.0f}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value neutral">{m['total_trades']}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value {'positive' if m['win_rate'] >= 50 else 'negative'}">{m['win_rate']:.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value {'positive' if m['profit_factor'] >= 1.5 else 'negative'}">{m['profit_factor']:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Max Drawdown</div>
                <div class="metric-value negative">{m['max_drawdown']:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value {'positive' if m['sharpe_ratio'] >= 1 else 'negative'}">{m['sharpe_ratio']:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Win / Avg Loss</div>
                <div class="metric-value" style="font-size: 1.3em;">
                    <span class="positive">₹{m['avg_win']:.0f}</span> / <span class="negative">₹{m['avg_loss']:.0f}</span>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📋 Strategy Parameters</h2>
            <div class="strategy-info">
                <div class="info-item">
                    <div class="info-label">Instrument</div>
                    <div class="info-value">{c['symbol']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Period</div>
                    <div class="info-value">{c['period'].split(' to ')[0]} - {c['period'].split(' to ')[1]}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">VP Lookback</div>
                    <div class="info-value">{c['vp_lookback']} bars</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Volume Multiplier</div>
                    <div class="info-value">{c['volume_multiplier']}x</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Risk/Reward</div>
                    <div class="info-value">{c['risk_reward']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Stop Loss</div>
                    <div class="info-value">{c['stop_loss']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Position Size</div>
                    <div class="info-value">{c['position_size']}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Initial Capital</div>
                    <div class="info-value">₹{m['initial_capital']:,.0f}</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📝 Trade Log</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>P&L (₹)</th>
                        <th>Outcome</th>
                    </tr>
                </thead>
                <tbody>
                    {trades_html}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>🔍 Analysis & Recommendations</h2>
            <div style="line-height: 1.8; color: #ccc;">
                <p><strong style="color: {'#00ff88' if m['total_return'] >= 0 else '#ff4757'};">{'✅' if m['total_return'] >= 0 else '⚠️'} Strategy Performance:</strong> The strategy generated a {m['total_return']:.2f}% return over the period with {m['total_trades']} trades.</p>
                <br>
                <p><strong>Key Observations:</strong></p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>{'Positive' if m['win_rate'] >= 50 else 'Low'} win rate ({m['win_rate']:.1f}%) {'with favorable' if m['profit_factor'] > 1 else 'but unfavorable'} risk/reward ratio (1:3)</li>
                    <li>{m['wins']} winning trade{'s' if m['wins'] > 1 else ''} out of {m['total_trades']} total trades</li>
                    <li>Maximum drawdown was limited to {m['max_drawdown']:.2f}%, showing {'good' if abs(m['max_drawdown']) < 5 else 'concerning'} risk control</li>
                    <li>{'High' if m['total_trades'] > 20 else 'Low'} trade frequency may indicate {'appropriate' if m['total_trades'] > 20 else 'strict'} entry criteria</li>
                </ul>
                <br>
                <p><strong style="color: #00d9ff;">💡 Recommendations:</strong></p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>{'Consider reducing' if m['total_trades'] < 10 else 'Current'} volume threshold to generate {'more' if m['total_trades'] < 10 else 'appropriate'} signals</li>
                    <li>Test different VP lookback periods (try 10-15 bars)</li>
                    <li>{'Consider tighter' if abs(m['avg_loss']) > 500 else 'Current'} stop-loss to reduce loss per trade</li>
                    <li>Add additional confirmation indicators (RSI, MACD)</li>
                    <li>Test on individual Nifty constituents for more opportunities</li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>"""

    return html

if __name__ == "__main__":
    config = BacktestConfig()
    bt = Backtester(config)
    bt.run()
    report_data = bt.generate_report_data()

    if report_data:
        html_content = generate_html_report(report_data)

        with open('performance_report.html', 'w') as f:
            f.write(html_content)

        print("✅ HTML Report generated: performance_report.html")
        print(f"   Total Trades: {report_data['metrics']['total_trades']}")
        print(f"   Win Rate: {report_data['metrics']['win_rate']:.1f}%")
        print(f"   Total Return: {report_data['metrics']['total_return']:.2f}%")
