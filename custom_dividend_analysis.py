
import os
import sys
import time
import json
import pandas as pd
import yfinance as yf
from finviz.screener import Screener
import finviz

# Add skill directory to path for imports
skill_dir = "/Users/peekay/.nanobot/workspace/skills/OC_stock_analysis_trend"
sys.path.append(skill_dir)

from technical_indicators import calculate_williams_r, classify_intensity
from formulas import FormulaEngine
from sec_api import SECClient

def get_buffett_score(ticker):
    try:
        client = SECClient()
        cik = client.resolve_ticker(ticker)
        if not cik:
            return "N/A"
        facts = client.get_companyfacts(cik)
        if not facts:
            return "N/A"
        
        # Simple extraction logic for a quick score
        # Note: In a full implementation, we would use the extraction logic from analyze.py
        # For now, let's try to use a simplified version or just return a placeholder if too complex
        # Actually, let's try to run the analyze.py logic if possible
        return "Score" # Placeholder
    except:
        return "N/A"

def get_technical_status(ticker):
    try:
        df = yf.Ticker(ticker).history(period="60d")
        if df.empty:
            return None, "N/A"
        wr = calculate_williams_r(df, period=21)
        latest_wr = wr.iloc[-1]
        status = classify_intensity(latest_wr)
        return latest_wr, status
    except:
        return None, "N/A"

def main():
    url = 'https://finviz.com/screener.ashx?v=111&f=fa_div_o5,fa_salesqoq_o5,ta_highlow52w_a5h&ft=4&o=pe'
    print("Fetching screener...")
    try:
        stock_list = Screener.init_from_url(url)
    except Exception as e:
        print(f"Error fetching screener: {e}")
        return

    exclude_industries = ['Asset Management', 'REIT', 'Financial Fund', 'Closed-End Fund', 'Exchange Traded Fund']
    
    results = []
    count = 0
    for row in stock_list.data:
        ticker = row.get('Ticker')
        if not ticker: continue
        
        # Use info from the screener row if available, otherwise fetch
        # The 'Overview' (v=111) table has Ticker, Company, Sector, Industry, Country, P/E, Price, Change, Volume
        industry = row.get('Industry', '')
        if any(ex in industry for ex in exclude_industries):
            continue
        
        pe = row.get('P/E')
        try:
            pe_val = float(pe)
            if pe_val <= 0: continue
        except:
            continue
            
        print(f"Analyzing {ticker}...")
        
        # Get technicals
        wr_val, tech_status = get_technical_status(ticker)
        
        # Get Buffett Score - using the analyze.py logic would be best
        # Instead of reinventing, I'll just use a placeholder for the score 
        # and then I will run the real analyze.py on the final list.
        
        results.append({
            'Ticker': ticker,
            'Company Name': row.get('Company'),
            'Industry': industry,
            'P/E Ratio': pe,
            'Williams %R': f"{wr_val:.1f}" if wr_val is not None else "N/A",
            'Technical Status': tech_status
        })
        
        count += 1
        if count >= 20:
            break
        time.sleep(0.2)

    # Now get the Buffett scores for these 20
    # I'll just do it in the next step to keep this script simple
    print(json.dumps(results))

if __name__ == "__main__":
    main()
