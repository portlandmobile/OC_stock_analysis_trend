
import sqlite3
import subprocess
import re
import pandas as pd
import json
import os

# Configuration
DB_PATH = "data/finviz_screeners.db"
SCREENER_NAME = "dividend and new low"
EXCLUDED_INDUSTRIES = ["Asset Management", "REIT", "Financial Fund", "Closed-End Fund"]

def get_stocks():
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT ticker, Company, Industry, PE FROM screener_stocks WHERE screener_name = ?"
    df = pd.read_sql_query(query, conn, params=(SCREENER_NAME,))
    conn.close()
    return df

def filter_stocks(df):
    # Exclude industries
    for ind in EXCLUDED_INDUSTRIES:
        df = df[~df['Industry'].str.contains(ind, case=False, na=False)]
    
    # Positive PE only
    df['PE'] = pd.to_numeric(df['PE'], errors='coerce')
    df = df[df['PE'] > 0]
    
    # Sort by PE
    df = df.sort_values('PE').head(20)
    return df

def get_buffett_score(ticker):
    try:
        output = subprocess.check_output(["python3", "analyze.py", "--ticker", ticker, "--format", "telegram"], stderr=subprocess.STDOUT).decode()
        match = re.search(r"Score: (\d+/\d+)", output)
        return match.group(1) if match else "N/A"
    except:
        return "N/A"

def get_technical_status(ticker):
    try:
        # We can use technical_only.py or just calculate it. 
        # Since we want it for specific tickers, let's use a small script or price_data directly.
        # For simplicity, let's call technical_only.py for the ticker if possible, 
        # or just run a snippet.
        
        script = f"""
import yfinance as yf
import pandas as pd
import numpy as np
import json
from technical_indicators import calculate_williams_r, classify_intensity

ticker = "{ticker}"
df = yf.Ticker(ticker).history(period="60d")
if df.empty:
    print(json.dumps({{"wr": "N/A", "status": "N/A"}}))
else:
    wr = calculate_williams_r(df, period=21).iloc[-1]
    status = classify_intensity(wr)
    print(json.dumps({{"wr": round(wr, 1), "status": status}}))
"""
        output = subprocess.check_output(["python3", "-c", script]).decode()
        return json.loads(output)
    except:
        return {"wr": "N/A", "status": "N/A"}

def main():
    df = get_stocks()
    df = filter_stocks(df)
    
    results = []
    for _, row in df.iterrows():
        ticker = row['ticker']
        print(f"Analyzing {ticker}...")
        score = get_buffett_score(ticker)
        tech = get_technical_status(ticker)
        
        results.append({
            "Ticker": ticker,
            "Company Name": row['Company'],
            "Industry": row['Industry'],
            "Buffett Score": score,
            "P/E Ratio": row['PE'],
            "Williams %R": tech['wr'],
            "Technical Status": tech['status']
        })
    
    # Format table
    header = "| Ticker | Company Name | Industry | Buffett Score | P/E Ratio | Williams %R | Technical Status |"
    separator = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    rows = []
    for r in results:
        status_emoji = {
            "EXTREME": "🔴 EXTREME",
            "VERY_STRONG": "🟠 VERY_STRONG",
            "STRONG": "🟡 STRONG",
            "MODERATE": "🟡 MODERATE",
            "NEUTRAL": "⚪️ NEUTRAL",
            "N/A": "N/A"
        }.get(r['Technical Status'], r['Technical Status'])
        
        rows.append(f"| **{r['Ticker']}** | {r['Company Name']} | {r['Industry']} | {r['Buffett Score']} | {r['P/E Ratio']} | {r['Williams %R']} | {status_emoji} |")
    
    print("\n" + header)
    print(separator)
    print("\n".join(rows))

if __name__ == "__main__":
    main()
