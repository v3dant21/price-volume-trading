# Dhan API Integration Setup

## Overview

This project now supports real-time market data from Dhan API instead of only historical data from Yahoo Finance.

## Prerequisites

1. **Dhan Trading Account**: You need an active Dhan trading account
2. **Dhan Pro Access**: Enable API access at https://dhan.co/
3. **Generate API Credentials**:
   - Go to https://dhan.co/ and log in
   - Navigate to API section
   - Generate your Access Token and Client ID

## Configuration

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Dhan API Configuration
DHAN_ACCESS_TOKEN=your_actual_access_token
DHAN_CLIENT_ID=your_actual_client_id
DHAN_BASE_URL=https://api.dhan.co

# Trading Symbol (use NSE format)
# For Nifty 50: NIFTY
# For Bank Nifty: BANKNIFTY
# For stocks: RELIANCE, INFY, TCS, etc.
SYMBOL=NIFTY

# Timeframe: 1m, 5m, 15m, 1h, 1d
TIMEFRAME=5m
```

### 3. Supported Symbols

| Instrument Type | Format | Example |
|----------------|--------|---------|
| NSE Stocks | Symbol name | `RELIANCE`, `INFY`, `HDFC` |
| NSE Indices | Symbol name | `NIFTY`, `BANKNIFTY`, `FINNIFTY` |
| BSE Stocks | Symbol name | `500325`, `500209` |

### 4. Supported Timeframes

- `1m` - 1 minute
- `5m` - 5 minutes
- `15m` - 15 minutes
- `1h` - 1 hour
- `1d` - 1 day

## Running the Strategy

```bash
python main.py
```

The bot will:
1. Connect to Dhan API using your credentials
2. Fetch real-time/historical data for the configured symbol
3. Run the volume profile strategy
4. Print signals when detected

## Troubleshooting

### "DHAN_ACCESS_TOKEN not found"
- Ensure you've copied `.env.example` to `.env`
- Check that `DHAN_ACCESS_TOKEN` is set correctly in `.env`

### "No data received"
- Verify the symbol is valid for NSE/NSE_INDEX exchange
- Check your Dhan API credentials are active
- Ensure market is open (9:15 AM - 3:30 PM IST for NSE)

### API Rate Limits
- Dhan API has rate limits (typically 100 requests/minute)
- The bot waits 60 seconds between data fetches by default

## API Reference

For more details on Dhan API:
- Documentation: https://dhan.co/developer/
- Python SDK: https://github.com/dhanco/dhanhq-python

## Security

- Never commit your `.env` file with real credentials
- The `.env` file is in `.gitignore` by default
- Rotate your access token if compromised
