import sys
import os
import pandas as pd
import numpy as np
from finviz.screener import Screener

# Add current dir to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sec_api import SECClient
from formulas import FormulaEngine
from price_data import PriceDataManager
from technical_indicators import calculate_williams_r, classify_intensity

def calculate_rsi(df, period=14):
    if df is None or len(df) < period:
        return np.nan
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

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

def main():
    print("Fetching FinViz data (Dividend > 0, New 52W Low, Positive P/E, Sorted by P/E)...")
    # ta_highlow52w_nl = New 52-Week Low
    # fa_div_pos = Positive Dividend
    # fa_pe_pos = Positive P/E
    url = "https://finviz.com/screener.ashx?v=111&f=fa_div_pos,fa_pe_pos,ta_highlow52w_nl&o=pe"
    
    try:
        screener = Screener.init_from_url(url)
    except Exception as e:
        print(f"Error fetching FinViz: {e}")
        # Fallback to the 'near new low' filter if 'new low' is empty
        print("Trying 'near new low' filter (0-5% above 52W low) instead...")
        url = "https://finviz.com/screener.ashx?v=111&f=fa_div_pos,fa_pe_pos,ta_highlow52w_a0to5h&o=pe"
        try:
            screener = Screener.init_from_url(url)
        except Exception as e2:
            print(f"Error fetching FinViz fallback: {e2}")
            return

    top_20 = screener.data[:20]
    if not top_20:
        print("No stocks found matching criteria.")
        return

    client = SECClient()
    price_manager = PriceDataManager()
    
    results = []
    print(f"Analyzing {len(top_20)} stocks...")
    
    for stock in top_20:
        ticker = stock['Ticker']
        pe = stock.get('P/E', 'N/A')
        price = stock.get('Price', 'N/A')
        
        # Technicals
        df = price_manager.get_daily_prices(ticker, days=60)
        wr_val = np.nan
        intensity = "N/A"
        rsi_val = np.nan
        
        if df is not None and not df.empty:
            wr = calculate_williams_r(df, period=21)
            if wr is not None and not wr.empty:
                wr_val = wr.iloc[-1]
                intensity = classify_intensity(wr_val)
            rsi_val = calculate_rsi(df)
        
        # Fundamentals
        score = get_buffett_score(client, ticker)
        
        results.append({
            "Ticker": ticker,
            "P/E": pe,
            "Price": price,
            "Buffett": score,
            "Williams %R": wr_val,
            "RSI": rsi_val,
            "Status": intensity
        })

    # Print Table
    print("\n📊 Dividend & New Low Analysis (Top 20 by P/E)")
    print(f"{'Ticker':<8} | {'P/E':<6} | {'Buffett':<8} | {'%R':<8} | {'RSI':<6} | {'Status':<12}")
    print("-" * 65)
    for r in results:
        wr_str = f"{r['Williams %R']:.2f}" if not np.isnan(r['Williams %R']) else "N/A"
        rsi_str = f"{r['RSI']:.2f}" if not np.isnan(r['RSI']) else "N/A"
        print(f"{r['Ticker']:<8} | {r['P/E']:<6} | {r['Buffett']:<8} | {wr_str:<8} | {rsi_str:<6} | {r['Status']:<12}")
    
    print("\n⚠️ Not financial advice. Data: FinViz, SEC EDGAR, Yahoo Finance.")

if __name__ == "__main__":
    main()
