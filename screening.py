import argparse
import time
from sp500_tickers import get_sp500_tickers
from price_data import PriceDataManager
from technical_indicators import calculate_williams_r, classify_intensity
from sec_api import SECClient
from formulas import FormulaEngine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=-80.0)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--format", type=str, default="telegram")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    start_time = time.time()
    
    # 1. Technical Scan
    tickers = get_sp500_tickers()
    pdm = PriceDataManager()
    price_data = pdm.batch_fetch_prices(tickers, force_refresh=args.force_refresh)
    
    oversold = []
    for ticker, df in price_data.items():
        wr = calculate_williams_r(df, period=21)
        if len(wr) > 0 and wr.iloc[-1] < args.threshold:
            oversold.append({'ticker': ticker, 'wr': wr.iloc[-1]})
    
    # 2. Fundamental Screen for oversold stocks
    client = SECClient()
    opportunities = []
    
    # Limit number of SEC calls to avoid getting blocked or taking too long
    # We'll take the top 50 most oversold
    oversold.sort(key=lambda x: x['wr'])
    candidates = oversold[:50]
    
    for item in candidates:
        ticker = item['ticker']
        cik = client.resolve_ticker(ticker)
        if not cik: continue
        
        facts_data = client.get_companyfacts(cik)
        if not facts_data: continue
        
        # Extract facts (same as analyze.py for comparable Buffett score)
        tags_map = {
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
            'interest': ['InterestExpense']
        }
        
        extracted = {}
        for key, tags in tags_map.items():
            val, _ = client.extract_fact(facts_data, tags)
            extracted[key] = val

        # Special case for debt: sum LongTerm + ShortTerm
        std_val, _ = client.extract_fact(facts_data, ['ShortTermBorrowings'])
        if std_val and extracted.get('debt'):
            extracted['debt'] += std_val
        elif std_val:
            extracted['debt'] = std_val

        history = {'NetIncomeLoss': client.extract_historical_facts(facts_data, 'NetIncomeLoss')}
        engine = FormulaEngine(extracted, history)
        results = engine.evaluate_all()
        
        pass_count = len([r for r in results if r['status'] == "PASS"])
        if pass_count >= args.min_score:
            # Combined Score
            tech_score = (item['wr'] + 100) / 100 # 0 to 0.2 if < -80
            fundamental_score = pass_count / 10
            combined = (tech_score * 0.3) + (fundamental_score * 0.7)
            
            opportunities.append({
                'ticker': ticker,
                'wr': item['wr'],
                'pass_count': pass_count,
                'combined': combined,
                'intensity': classify_intensity(item['wr'])
            })

    opportunities.sort(key=lambda x: x['combined'], reverse=True)
    top_opps = opportunities[:args.top_n]
    
    elapsed = time.time() - start_time
    
    if args.format == "telegram":
        print(f"🔍 S&P 500 Quality Screen")
        print(f"Filter: Williams %R < {args.threshold} AND Buffett ≥ {args.min_score}/10\n")
        
        if not top_opps:
            print("No stocks found matching the criteria.")
        else:
            print(f"Top {len(top_opps)} Opportunities:\n")
            for i, o in enumerate(top_opps, 1):
                emoji = {"EXTREME": "🔴", "VERY_STRONG": "🟠", "STRONG": "🟡", "MODERATE": "⚡"}[o['intensity']]
                print(f"{i}. {o['ticker']} — Combined: {o['combined']*10:.1f}/10")
                print(f"   %R: {o['wr']:.1f} {emoji} | Buffett: {o['pass_count']}/10\n")

        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        print(f"⏱ {mins}m {secs}s | Yahoo Finance + SEC EDGAR | ⚠️ Not financial advice.")

if __name__ == "__main__":
    main()
