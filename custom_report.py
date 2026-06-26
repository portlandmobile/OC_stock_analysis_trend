
import sqlite3
import subprocess
import re
import json
from datetime import datetime

db_path = "/Users/peekay/.nanobot/workspace/skills/OC_stock_analysis_trend/data/finviz_screeners.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get today's date
today = datetime.now().strftime("%Y-%m-%d")

# Fetch stocks for "dividend and new low"
query = "SELECT * FROM screener_stocks WHERE screener_name = ? AND date(updated_at) = ?"
cursor.execute(query, ("dividend and new low", today))
rows = [dict(r) for r in cursor.fetchall()]
conn.close()

# Exclude industries: Asset Management, REIT, financial funds
excluded_industries = ["Asset Management", "REIT", "Financial Funds"]

filtered_stocks = []
for r in rows:
    industry = r.get('Industry', '')
    if any(excl.lower() in industry.lower() for excl in excluded_industries):
        continue
    
    # Ensure positive PE
    try:
        pe = float(r.get('PE', 0))
    except (ValueError, TypeError):
        pe = 0
    
    if pe > 0:
        filtered_stocks.append(r)

# Sort by PE ascending
filtered_stocks.sort(key=lambda x: float(x.get('PE', 999999)))

# Limit to top 20
top_20 = filtered_stocks[:20]

results = []
for s in top_20:
    ticker = s['ticker']
    company = s.get('Company', 'N/A')
    industry = s.get('Industry', 'N/A')
    pe = s.get('PE', 'N/A')
    
    # Get Buffett Score and Technical Status
    # We can run analyze.py for Buffett and technical_only.py for technical
    # But analyze.py doesn't give technical status. 
    # Let's use get_scores.py if it exists or run analyze.py and extract.
    
    buffett_score = "N/A"
    try:
        # Run analyze.py
        cmd = ["python3", "/Users/peekay/.nanobot/workspace/skills/OC_stock_analysis_trend/analyze.py", "--ticker", ticker]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode()
        match = re.search(r"Score: (\d+/\d+)", output)
        if match:
            buffett_score = match.group(1)
    except:
        pass

    williams_r = "N/A"
    tech_status = "N/A"
    try:
        # We need a script to get technical data for a single ticker.
        # Let's write a temporary one or use technical_indicators.py
        temp_script = f"""
import sys
sys.path.append('/Users/peekay/.nanobot/workspace/skills/OC_stock_analysis_trend/')
from price_data import PriceDataManager
from technical_indicators import calculate_williams_r, classify_intensity
import pandas as pd

pdm = PriceDataManager(db_path='/Users/peekay/.nanobot/workspace/skills/OC_stock_analysis_trend/data/price_cache.db')
df = pdm.get_daily_prices('{ticker}')
if df is not None and not df.empty:
    wr = calculate_williams_r(df)
    latest_wr = wr.iloc[-1]
    status = classify_intensity(latest_wr)
    print(f"{{latest_wr:.1f}}|{{status}}")
"""
        tech_output = subprocess.check_output(["python3", "-c", temp_script]).decode().strip()
        if "|" in tech_output:
            williams_r, tech_status = tech_output.split("|")
    except:
        pass

    results.append({
        "Ticker": ticker,
        "Company Name": company,
        "Industry": industry,
        "Buffett Score": buffett_score,
        "P/E Ratio": pe,
        "Williams %R": williams_r,
        "Technical Status": tech_status
    })

# Print as markdown table
print("| Ticker | Company Name | Industry | Buffett Score | P/E Ratio | Williams %R | Technical Status |")
print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
for r in results:
    status_emoji = {
        "EXTREME": "🔴 EXTREME",
        "VERY_STRONG": "🟠 VERY_STRONG",
        "STRONG": "🟡 STRONG",
        "MODERATE": "⚪️ MODERATE",
        "NEUTRAL": "⚪️ NEUTRAL"
    }.get(r['Technical Status'], r['Technical Status'])
    
    print(f"| **{r['Ticker']}** | {r['Company Name']} | {r['Industry']} | {r['Buffett Score']} | {r['P/E Ratio']} | {r['Williams %R']} | {status_emoji} |")
