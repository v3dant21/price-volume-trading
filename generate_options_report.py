"""
Generate HTML performance report for Nifty 50 Options backtest.
Format matches the Notion-style report template.
"""
import pandas as pd
import numpy as np
from datetime import datetime
from backtest_options import OptionsBacktestConfig, OptionsBacktester

def generate_html_report(report_data, report_type="Options"):
    trades = report_data['trades']
    m = report_data['metrics']
    c = report_data['config']

    # Build trade log HTML
    trades_html = ""
    for i, trade in enumerate(trades):
        color_class = "win" if trade['outcome'] == "WIN" else ("loss" if trade['outcome'] == "LOSS" else "neutral")
        pnl_class = "positive" if trade['pnl'] >= 0 else "negative"
        type_color = "#00ff88" if trade['type'] == 'LONG' else "#ff4757"
        pnl_sign = "+" if trade['pnl'] >= 0 else ""

        if report_type == "Options":
            # Options-specific columns
            trades_html += f"""
                    <tr>
                        <td>{i + 1}</td>
                        <td>{trade['date']}</td>
                        <td style="color: {type_color}">{trade['type']} {trade['option_type']}</td>
                        <td>₹{trade['underlying_entry']:.2f}</td>
                        <td>₹{trade['underlying_exit']:.2f}</td>
                        <td>₹{trade['entry_premium']:.2f}</td>
                        <td>₹{trade['exit_premium']:.2f}</td>
                        <td class="{pnl_class}">{pnl_sign}₹{trade['pnl']:.2f}</td>
                        <td class="{color_class}">{trade['outcome']}</td>
                    </tr>"""
        else:
            # Equity/ETF columns
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
    profit_factor_class = "positive" if m['profit_factor'] >= 1.5 else ("neutral" if m['profit_factor'] >= 1 else "negative")

    # Analysis text based on performance
    performance_emoji = "✅" if m['total_return'] >= 0 else "⚠️"
    performance_color = "#00ff88" if m['total_return'] >= 0 else "#ff4757"
    win_rate_assessment = "Good" if m['win_rate'] >= 50 else "Low"
    risk_control = "good" if abs(m['max_drawdown']) < 5 else "concerning"
    trade_freq = "High" if m['total_trades'] > 20 else "Low"
    entry_criteria = "appropriate" if m['total_trades'] > 20 else "strict"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nifty 50 {report_type} Strategy Performance Report</title>
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
            max-width: 1400px;
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
            font-size: 0.95em;
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
        .neutral {{ color: #ffa500; }}
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
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
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
        .chart-section {{
            text-align: center;
        }}
        .chart-section img {{
            max-width: 100%;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
            background: #fff;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 NIFTY 50 {report_type.upper()} STRATEGY PERFORMANCE REPORT</h1>
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
                <div class="metric-value {profit_factor_class}">{m['profit_factor']:.2f}</div>
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

        <div class="section chart-section">
            <h2>📈 Performance Chart</h2>
            <img src="nifty_options_report.png" alt="Performance Report Chart">
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
                    <div class="info-value">{c['period'].split(' to ')[0]}</div>
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
                        <th>Underlying Entry</th>
                        <th>Underlying Exit</th>
                        <th>Option Entry</th>
                        <th>Option Exit</th>
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
                <p><strong style="color: {performance_color};">{performance_emoji} Strategy Performance:</strong> The strategy generated a {m['total_return']:.2f}% return over the period with {m['total_trades']} trades.</p>
                <br>
                <p><strong>Key Observations:</strong></p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>{win_rate_assessment} win rate ({m['win_rate']:.1f}%) {'with favorable' if m['profit_factor'] > 1 else 'but unfavorable'} risk/reward profile</li>
                    <li>{m['wins']} winning trade{'s' if m['wins'] != 1 else ''} out of {m['total_trades']} total trades</li>
                    <li>Maximum drawdown was limited to {m['max_drawdown']:.2f}%, showing {risk_control} risk control</li>
                    <li>{trade_freq} trade frequency may indicate {entry_criteria} entry criteria</li>
                </ul>
                <br>
                <p><strong style="color: #00d9ff;">💡 Recommendations:</strong></p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>{'Consider reducing' if m['total_trades'] < 10 else 'Current'} volume threshold to generate {'more' if m['total_trades'] < 10 else 'appropriate'} signals</li>
                    <li>Test different VP lookback periods (try 10-15 bars)</li>
                    <li>{'Consider tighter' if abs(m['avg_loss']) > 5000 else 'Current'} stop-loss to reduce loss per trade</li>
                    <li>Add additional confirmation indicators (RSI, MACD)</li>
                    <li>Consider implementing trailing stop-loss for winning trades</li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>"""

    return html

if __name__ == "__main__":
    config = OptionsBacktestConfig()
    bt = OptionsBacktester(config)

    if bt.run():
        report_data = bt.generate_report()

        if report_data:
            html_content = generate_html_report(report_data, report_type="Options")

            with open('nifty_options_report.html', 'w') as f:
                f.write(html_content)

            m = report_data['metrics']
            print("\n✅ HTML Report generated: nifty_options_report.html")
            print(f"   Total Trades: {m['total_trades']}")
            print(f"   Win Rate: {m['win_rate']:.1f}%")
            print(f"   Total Return: {m['total_return']:.2f}%")
            print(f"   Profit Factor: {m['profit_factor']:.2f}")
