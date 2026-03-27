import os
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