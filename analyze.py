import argparse
from sec_api import SECClient
from formulas import FormulaEngine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, required=True)
    parser.add_argument("--format", type=str, default="telegram")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    client = SECClient()
    ticker = args.ticker.upper()
    cik = client.resolve_ticker(ticker)
    
    if not cik:
        print(f"Error: Could not resolve ticker {ticker} to a CIK.")
        return

    facts_data = client.get_companyfacts(cik, force_refresh=args.force_refresh)
    if not facts_data:
        print(f"Error: Could not retrieve SEC data for {ticker} (CIK: {cik}).")
        return

    # Extract required facts
    tags_map = {
        'cash': ['CashAndCashEquivalentsAtCarryingValue'],
        'investments': ['ShortTermInvestments'],
        'debt': ['LongTermDebt', 'LongTermDebtNoncurrent'], # Simplified
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
    provenance = None
    for key, tags in tags_map.items():
        val, prov = client.extract_fact(facts_data, tags)
        extracted[key] = val
        if prov: provenance = prov # Keep the last one for metadata

    # Special case for debt: sum LongTerm + ShortTerm
    std_val, _ = client.extract_fact(facts_data, ['ShortTermBorrowings'])
    if std_val and extracted['debt']:
        extracted['debt'] += std_val
    elif std_val:
        extracted['debt'] = std_val

    # Historical for stability
    history = {'NetIncomeLoss': client.extract_historical_facts(facts_data, 'NetIncomeLoss')}

    engine = FormulaEngine(extracted, history)
    results = engine.evaluate_all()
    
    pass_count = len([r for r in results if r['status'] == "PASS"])
    na_count = len([r for r in results if r['status'] == "NA"])
    total_valid = len(results) - na_count
    
    if args.format == "telegram":
        print(f"📊 {ticker} — Buffett Analysis")
        print(f"Score: {pass_count}/{total_valid} Buffett Criteria\n")
        
        strengths = [r for r in results if r['status'] == "PASS"]
        if strengths:
            print("✅ Strengths")
            print(f"| {'Metric':<20} | {'Value':<10} | {'Target':<10} |")
            print(f"| {'-'*20} | {'-'*10} | {'-'*10} |")
            for r in strengths:
                print(f"| {r['name']:<20} | {str(r['value']):<10} | {r['target']:<10} |")
            print()

        concerns = [r for r in results if r['status'] == "FAIL"]
        if concerns:
            print("❌ Concerns")
            print(f"| {'Metric':<20} | {'Value':<10} | {'Target':<10} |")
            print(f"| {'-'*20} | {'-'*10} | {'-'*10} |")
            for r in concerns:
                print(f"| {r['name']:<20} | {str(r['value']):<10} | {r['target']:<10} |")
            print()

        missing = [r for r in results if r['status'] == "NA"]
        if missing:
            print(f"ℹ️ Missing Data: {', '.join([r['name'] for r in missing])}\n")

        if provenance:
            print(f"📎 Data: SEC EDGAR 10-K ({provenance['period_end']})")
        print("⚠️ Not financial advice.")

if __name__ == "__main__":
    main()
