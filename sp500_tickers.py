import os
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SKILL_DIR, "data", "sp500_tickers.json")
CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
TTL_DAYS = 7

def get_sp500_tickers():
    # Check cache
    if os.path.exists(CACHE_FILE):
        mtime = os.path.getmtime(CACHE_FILE)
        if datetime.fromtimestamp(mtime) > datetime.now() - timedelta(days=TTL_DAYS):
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass

    # Fetch from GitHub
    try:
        df = pd.read_csv(CSV_URL)
        tickers = df['Symbol'].tolist()
        
        # Save to cache
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(tickers, f)
            
        return tickers
    except Exception as e:
        print(f"Error fetching S&P 500 tickers: {e}")
        # Return cached even if expired if fetch fails
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        return []

if __name__ == "__main__":
    tickers = get_sp500_tickers()
    print(f"Retrieved {len(tickers)} tickers.")
