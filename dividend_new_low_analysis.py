import sys
import os
import pandas as pd
import numpy as np
from finviz.screener import Screener
from sec_api import SECClient
from formulas import FormulaEngine
from price_data import PriceDataManager
from technical_indicators import calculate_williams_r, classify_intensity

# Add current dir to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
    cik = client.resolve_ticker(ticker)
    if not cik:
        return "N/A"
    facts_data = client.get_companyfacts(cik)
    if not facts_data:
        return "N/A"

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
        return "0/0"
    return f"{pass_count}/{total_valid}"

def get_oversold_info(price_manager, ticker):
    df = price_manager.get_daily_prices(ticker, days=60)
    if df is None or df.empty:
        return "N/A", "N/A"
    
    wr = calculate_williams_r(df, period=21)
    if wr is None or wr.empty:
        return "N/A", "N/A"
    
    latest_wr = wr.iloc[-1]
    intensity = classify_intensity(latest_wr)
    return round(latest_wr, 2), intensity

def main():
    print("Fetching FinViz data (Stocks Only, Dividend > 0, New Low, Positive P/E, Sorted by P/E)...")
    url = "https://finviz.com/screener.ashx?v=111&f=fa_div_pos,fa_pe_pos,ip_stocksonly,ta_highlow52w_a0to5h&o=pe"
    
    try:
        screener = Screener.init_from_url(url)
    except Exception as e:
        print(f"Error fetching FinViz: {e}")
        return

    top_20 = screener.data[:20]
    if not top_20:
        print("No stocks found matching criteria.")
        return

    # Debug: print keys of the first stock
    if top_20:
        print(f"Available keys: {list(top_20[0].keys())}")

    client = SECClient()
    price_manager = PriceDataManager()
    
    results = []
    print(f"Analyzing {len(top_20)} stocks...")
    
    for stock in top_20:
        ticker = stock['Ticker']
        pe = stock.get('P/E', 'N/A')
        div = stock.get('Dividend Yield', stock.get('Dividend', 'N/A'))
        price = stock.get('Price', 'N/A')
        
        score = get_buffett_score(client, ticker)
        wr_val, intensity = get_oversold_info(price_manager, ticker)
        
        results.append({
            "Ticker": ticker,
            "P/E": pe,
            "Div": div,
            "Price": price,
            "Buffett": score,
            "Williams %R": wr_val,
            "Intensity": intensity
        })

    # Print Table
    print("\n📊 Dividend & New Low Analysis (Top 20 by P/E)")
    print(f"{'Ticker':<8} | {'P/E':<6} | {'Div':<6} | {'Price':<8} | {'Buffett':<8} | {'%R':<8} | {'Status':<12}")
    print("-" * 75)
    for r in results:
        print(f"{r['Ticker']:<8} | {r['P/E']:<6} | {r['Div']:<6} | {r['Price']:<8} | {r['Buffett']:<8} | {str(r['Williams %R']):<8} | {r['Intensity']:<12}")
    
    print("\n⚠️ Not financial advice. Data: FinViz, SEC EDGAR, Yahoo Finance.")

if __name__ == "__main__":
    main()
