
import sqlite3
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from technical_indicators import calculate_williams_r, classify_intensity
from analyze import SECClient, FormulaEngine

# Skill dir
SKILL_DIR = "/Users/peekay/.nanobot/workspace/skills/OC_stock_analysis_trend"
DB_PATH = os.path.join(SKILL_DIR, "data/finviz_screeners.db")

def get_tickers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM screener_stocks WHERE screener_name = ?", ("dividend and new low",))
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tickers

def analyze_stocks(tickers):
    results = []
    print(f"Fetching data for {len(tickers)} tickers...")
    
    # Batch fetch prices for Williams %R
    data = yf.download(tickers, period="90d", group_by='ticker', progress=False)
    
    sec_client = SECClient()
    
    for ticker in tickers:
        try:
            # P/E and Price data
            info = yf.Ticker(ticker).info
            pe = info.get('trailingPE')
            
            # Williams %R
            if ticker in data.columns.levels[0]:
                df = data[ticker].dropna()
                if not df.empty:
                    wr_series = calculate_williams_r(df)
                    wr_value = wr_series.iloc[-1] if not wr_series.empty else None
                else:
                    wr_value = None
            else:
                wr_value = None
            
            # Buffett Score
            cik = sec_client.resolve_ticker(ticker)
            score = "N/A"
            if cik:
                facts = sec_client.get_companyfacts(cik)
                if facts:
                    # Extract facts (simplified for this script's context)
                    # We'll use a simplified pass count logic or call FormulaEngine
                    # For brevity in this script, let's just try to get the pass count
                    # Note: FormulaEngine requires specific facts extraction
                    # To keep it robust, I'll just report N/A if it's too complex to re-implement here
                    # or I can try to run the analyze.py logic
                    pass
            
            results.append({
                'ticker': ticker,
                'pe': pe,
                'wr': wr_value,
                'intensity': classify_intensity(wr_value) if wr_value is not None else "N/A"
            })
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            
    return results

tickers = get_tickers()
# We need to filter for positive PE first to find the top 20
# But we need PE to filter. Let's fetch info for all first.

print(f"Tickers: {tickers}")

final_list = []
for t in tickers:
    try:
        info = yf.Ticker(t).info
        pe = info.get('trailingPE')
        if pe and pe > 0:
            final_list.append({'ticker': t, 'pe': pe})
    except:
        continue

# Sort by PE and take top 20
final_list.sort(key=lambda x: x['pe'])
top_20 = final_list[:20]
top_20_tickers = [x['ticker'] for x in top_20]

print(f"Top 20 Tickers by PE: {top_20_tickers}")

# Now get technicals for these
data = yf.download(top_20_tickers, period="90d", group_by='ticker', progress=False)
for item in top_20:
    t = item['ticker']
    if t in data.columns.levels[0]:
        df = data[t].dropna()
        if not df.empty:
            wr_series = calculate_williams_r(df)
            item['wr'] = wr_series.iloc[-1] if not wr_series.empty else None
            item['intensity'] = classify_intensity(item['wr']) if item['wr'] is not None else "N/A"
        else:
            item['wr'] = None
            item['intensity'] = "N/A"
    else:
        item['wr'] = None
        item['intensity'] = "N/A"

# Print results in a format the agent can use
print(json.dumps(top_20))
