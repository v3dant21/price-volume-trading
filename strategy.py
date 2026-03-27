import pandas as pd
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