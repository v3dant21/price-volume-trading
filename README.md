# Volume Node Expansion Bot

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