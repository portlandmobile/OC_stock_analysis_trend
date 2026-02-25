import sys
import os
import sqlite3
import pandas as pd
from datetime import date
from finviz_db import ScreenerCache
from price_data import PriceDataManager
from technical_indicators import calculate_williams_r, classify_intensity
from sec_api import SECClient
from formulas import FormulaEngine

# Map tags for Buffett analysis
TAGS_MAP = {
    'cash': ['CashAndCashEquivalentsAtCarryingValue'],
    'investments': ['ShortTermInvestments'],
    'debt': ['LongTermDebt', 'LongTermDebtNoncurrent'],
    'liabilities': ['Liabilities'],
    'equity': ['StockholdersEquity'],
    'ocf': ['NetCashProvidedByUsedInOperatingActivities'],
    'capex': ['PaymentsToAcquirePropertyPlantAndEquipment'],
    'income': ['NetIncomeLoss'],
    'current_assets': ['AssetsCurrent'],
    'current_liabilities': ['LiabilitiesCurrent'],
    'oi': ['OperatingIncomeLoss'],
    'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet'],
    'assets': ['Assets'],
    'interest': ['InterestExpense'],
}

def get_buffett_score(client, ticker):
    ticker = ticker.strip().upper()
    cik = client.resolve_ticker(ticker)
    if not cik:
        return "0/0*"
    
    facts_data = client.get_companyfacts(cik)
    if not facts_data:
        return "0/0*"

    extracted = {}
    for key, tags in TAGS_MAP.items():
        val, _ = client.extract_fact(facts_data, tags)
        extracted[key] = val

    std_val, _ = client.extract_fact(facts_data, ['ShortTermBorrowings'])
    if std_val and extracted.get('debt'):
        extracted['debt'] += std_val
    elif std_val:
        extracted['debt'] = std_val

    history = {'NetIncomeLoss': client.extract_historical_facts(facts_data, 'NetIncomeLoss')}
    engine = FormulaEngine(extracted, history)
    results = engine.evaluate_all()

    pass_count = len([r for r in results if r['status'] == "PASS"])
    na_count = len([r for r in results if r['status'] == "NA"])
    total_valid = len(results) - na_count
    
    if total_valid == 0:
        return "0/0*"
    return f"{pass_count}/{total_valid}"

def main():
    screener_name = "dividend_new_low"
    on_date = date.today().isoformat()
    
    cache = ScreenerCache()
    rows = cache.get_tickers_with_metadata(screener_name, on_date)
    
    if not rows:
        # Try yesterday if today has no data yet
        from datetime import timedelta
        on_date = (date.today() - timedelta(days=1)).isoformat()
        rows = cache.get_tickers_with_metadata(screener_name, on_date)
        
    if not rows:
        print("No stocks found in database. Run finviz_sync first.")
        return

    # Convert to DataFrame for easier sorting
    df = pd.DataFrame(rows)
    
    # Clean PE: remove commas, convert to float
    def clean_pe(val):
        if val is None or val == "-" or val == "N/A":
            return -1.0
        try:
            return float(str(val).replace(",", ""))
        except:
            return -1.0

    df['PE_float'] = df['PE'].apply(clean_pe)
    
    # Filter for positive PE and sort
    df_filtered = df[df['PE_float'] > 0].sort_values('PE_float').head(20)
    
    if df_filtered.empty:
        print("No stocks with positive P/E found.")
        return

    # Fetch Price Data and calculate Technicals
    pd_manager = PriceDataManager()
    sec_client = SECClient()
    
    print(f"| Ticker | Company Name | Industry | Buffett Score | P/E Ratio | Williams %R | Technical Status |")
    print(f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for _, row in df_filtered.iterrows():
        ticker = row['ticker']
        
        # Technicals
        prices = pd_manager.get_daily_prices(ticker, days=60)
        wr_val = "N/A"
        status = "N/A"
        if prices is not None and not prices.empty:
            wr_series = calculate_williams_r(prices, period=21)
            if not wr_series.empty:
                val = wr_series.iloc[-1]
                wr_val = round(val, 1)
                status = classify_intensity(val)
                
                # Emoji for status
                emoji = "⚪️"
                if status == "EXTREME": emoji = "🔴"
                elif status == "VERY_STRONG": emoji = "🟠"
                elif status == "STRONG": emoji = "🟡"
                status = f"{emoji} {status}"

        # Fundamentals
        score = get_buffett_score(sec_client, ticker)
        
        print(f"| **{ticker}** | {row['Company']} | {row['Industry']} | {score} | {row['PE']} | {wr_val} | {status} |")

if __name__ == "__main__":
    main()
