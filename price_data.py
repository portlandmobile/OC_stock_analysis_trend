import os
import time
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from database import PriceCache

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(SKILL_DIR, "data", "price_cache.db")

class PriceDataManager:
    def __init__(self, db_path=DEFAULT_DB):
        print(f"DEBUG: db_path={db_path}")
        self.cache = PriceCache(db_path)

    def get_daily_prices(self, ticker, days=90, force_refresh=False):
        if not force_refresh:
            cached_df = self.cache.get(ticker)
            if cached_df is not None:
                return cached_df

        try:
            # yfinance can be noisy, but we'll let it be for now
            df = yf.Ticker(ticker).history(period=f"{days}d")
            if df.empty:
                return None
            
            self.cache.store(ticker, df)
            return df
        except Exception as e:
            print(f"Warning: Failed to fetch prices for {ticker}: {e}")
            return None

    def batch_fetch_prices(self, tickers, days=90, workers=1, force_refresh=False):
        results = {}
        
        def fetch_task(ticker):
            return ticker, self.get_daily_prices(ticker, days, force_refresh)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            # We'll batch them to add a small delay
            batch_size = workers
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i:i + batch_size]
                futures = [executor.submit(fetch_task, t) for t in batch]
                for future in futures:
                    ticker, df = future.result()
                    if df is not None:
                        results[ticker] = df
                time.sleep(0.1)  # Small delay between batches

        return results
