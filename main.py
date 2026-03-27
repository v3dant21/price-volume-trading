import time
import pandas as pd
from config import Config
from strategy import Strategy
from broker import MockBroker, AlpacaBroker

def main():
    # Switch to AlpacaBroker for live trading
    broker = MockBroker() 
    strategy = Strategy()
    
    print(f"🚀 Starting Volume Node Strategy on {Config.SYMBOL}")
    
    while True:
        try:
            df = broker.get_data(Config.SYMBOL, Config.TIMEFRAME)
            
            if df is None or len(df) < 20:
                time.sleep(60)
                continue

            signal, vp = strategy.analyze(df)
            
            print(f"📊 Price: {df['close'].iloc[-1]:.2f} | VAH: {vp.vah:.2f} | VAL: {vp.val:.2f}")

            if signal:
                print(f"🚨 SIGNAL DETECTED: {signal['direction']} @ {signal['entry']}")
                print(f"   SL: {signal['stop_loss']} | TP: {signal['take_profit']}")
                # broker.place_order(Config.SYMBOL, qty, signal['direction'])

            time.sleep(60)
            
        except KeyboardInterrupt:
            print("🛑 Stopping bot...")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()