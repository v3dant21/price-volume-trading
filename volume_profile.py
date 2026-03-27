import numpy as np
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