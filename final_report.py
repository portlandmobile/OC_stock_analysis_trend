
import sqlite3
import subprocess
import re
import pandas as pd
import json
import os
import sys
from datetime import date

# Change to the skill directory so imports and paths work
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SKILL_DIR)
sys.path.append(SKILL_DIR)

# Configuration
DB_PATH = "data/finviz_screeners.db"
EXCLUDED_INDUSTRIES = ["Asset Management", "REIT", "Financial Fund", "Closed-End Fund"]

def get_stocks(screener_name):
    conn = sqlite3.connect(DB_PATH)
    if screener_name == "all":
        query = f"SELECT ticker, Company, Industry, PE, PS, Q1_Revenue, Q2_Revenue, Q3_Revenue FROM screener_stocks"
        df = pd.read_sql_query(query, conn)
    else:
        query = f"SELECT ticker, Company, Industry, PE, PS, Q1_Revenue, Q2_Revenue, Q3_Revenue FROM screener_stocks WHERE screener_name = ?"
        df = pd.read_sql_query(query, conn, params=(screener_name,))
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


def _ps_score(ps_val):
    """Score P/S ratio: 1-5 (lower is better)."""
    try:
        ps = float(ps_val)
    except (TypeError, ValueError):
        return "N/A"
    if ps < 1:
        return 5
    elif ps < 3:
        return 4
    elif ps < 5:
        return 3
    elif ps < 10:
        return 2
    else:
        return 1


def _qoq_score(q1, q2, q3):
    """Score QoQ revenue growth trend: 1-5.
    
    q1, q2, q3: quarterly revenue values (most recent first).
    With 3 values we get 2 QoQ changes.
    """
    vals = []
    for v in [q1, q2, q3]:
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            return "N/A"
    
    if len(vals) < 3:
        return "N/A"
    
    # Compute QoQ % changes
    changes = []
    for i in range(len(vals) - 1):
        prev = vals[i + 1]
        curr = vals[i]
        if prev > 0:
            changes.append((curr - prev) / prev * 100)
    
    if not changes:
        return "N/A"
    
    # With 3 quarters we have 2 QoQ changes
    last_2 = changes[:2]
    positive_count = sum(1 for c in last_2 if c > 0)
    avg_change = sum(last_2) / len(last_2)
    
    if positive_count >= 2 and avg_change > 20:
        return 5
    elif positive_count >= 2 and avg_change > 10:
        return 4
    elif positive_count >= 2:
        return 3
    elif positive_count >= 1:
        return 2
    else:
        return 1

def get_buffett_score(ticker):
    try:
        output = subprocess.check_output(["python3", "analyze.py", "--ticker", ticker, "--format", "telegram"], stderr=subprocess.STDOUT).decode()
        match = re.search(r"Score: (\d+/\d+)", output)
        return match.group(1) if match else "N/A"
    except:
        return "N/A"

def get_technical_status(ticker):
    try:
        script = f"""
import yfinance as yf
import pandas as pd
import numpy as np
import json
import sys
sys.path.append("{SKILL_DIR}")
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
    except Exception as e:
        return {"wr": "N/A", "status": "N/A"}

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str)
    parser.add_argument("--screener", type=str, default="dividend and new low")
    parser.add_argument("--vault", action="store_true", help="Also write report to Obsidian vault")
    args = parser.parse_args()

    if args.ticker:
        # Handle single ticker logic
        ticker = args.ticker
        # (Assuming for a single ticker we might just want a one-row table or reuse existing logic)
        # For now, let's just make it work for the single ticker
        df = pd.DataFrame([{"ticker": ticker, "Company": ticker, "Industry": "Manual", "PE": "N/A"}])
    else:
        df = get_stocks(args.screener)
        df = filter_stocks(df)
    
    results = []
    for _, row in df.iterrows():
        ticker = row['ticker']
        # print(f"Analyzing {ticker}...", file=sys.stderr)
        score = get_buffett_score(ticker)
        tech = get_technical_status(ticker)
        
        ps = row.get('PS')
        q1 = row.get('Q1_Revenue')
        q2 = row.get('Q2_Revenue')
        q3 = row.get('Q3_Revenue')
        ps_sc = _ps_score(ps)
        qoq_sc = _qoq_score(q1, q2, q3)
        
        results.append({
            "Ticker": ticker,
            "Company Name": row['Company'],
            "Industry": row['Industry'],
            "Buffett Score": score,
            "P/E Ratio": row['PE'],
            "Williams %R": tech['wr'],
            "Technical Status": tech['status'],
            "P/S Ratio": ps if ps else "N/A",
            "PS Score": ps_sc,
            "QoQ Revenue Growth": qoq_sc,
        })
    
    # Format table
    header = "| Ticker | Company Name | Industry | Buffett Score | P/E Ratio | Williams %R | Technical Status | P/S Ratio | PS Score | QoQ Revenue Growth |"
    separator = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
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
        
        # Format scores as emoji + value
        ps_display = f"{r['PS Score']}" if isinstance(r['PS Score'], int) else r['PS Score']
        qoq_display = f"{r['QoQ Revenue Growth']}" if isinstance(r['QoQ Revenue Growth'], int) else r['QoQ Revenue Growth']
        
        rows.append(f"| **{r['Ticker']}** | {r['Company Name']} | {r['Industry']} | {r['Buffett Score']} | {r['P/E Ratio']} | {r['Williams %R']} | {status_emoji} | {r['P/S Ratio']} | {ps_display} | {qoq_display} |")
    
    print(header)
    print(separator)
    print("\n".join(rows))

    if args.vault:
        vault_dir = "/home/openclaw/MyVault/Projects/Trading/Screener"
        os.makedirs(vault_dir, exist_ok=True)
        filename = os.path.join(vault_dir, f"{date.today().isoformat()}-{args.screener}.md")
        with open(filename, "w") as f:
            f.write(f"# Screener Report — {args.screener} ({date.today().isoformat()})\n\n")
            f.write(header + "\n")
            f.write(separator + "\n")
            f.write("\n".join(rows) + "\n")
        print(f"\n📁 Saved to {filename}", file=sys.stderr)

if __name__ == "__main__":
    main()
