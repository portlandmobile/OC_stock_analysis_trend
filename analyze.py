import argparse
from datetime import date
from sec_api import SECClient
from formulas import FormulaEngine

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


def run_analysis(client, ticker, args):
    """Run Buffett analysis for one ticker. Returns True on success, False on skip/error."""
    ticker = ticker.strip().upper()
    if not ticker:
        return False
    cik = client.resolve_ticker(ticker)
    if not cik:
        print(f"Error: Could not resolve ticker {ticker} to a CIK.")
        return False
    facts_data = client.get_companyfacts(cik, force_refresh=args.force_refresh)
    if not facts_data:
        print(f"Error: Could not retrieve SEC data for {ticker} (CIK: {cik}).")
        return False

    extracted = {}
    provenance = None
    for key, tags in TAGS_MAP.items():
        val, prov = client.extract_fact(facts_data, tags)
        extracted[key] = val
        if prov:
            provenance = prov

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
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, help="Single ticker to analyze (required if not using --finviz-screener)")
    parser.add_argument("--finviz-screener", type=str, help="FinViz screener name, or 'all' for all screeners")
    parser.add_argument("--date-range", type=str, help="Date for screener stocks (YYYY-MM-DD). Default: today.")
    parser.add_argument("--format", type=str, default="telegram")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    if args.finviz_screener is not None:
        # Batch: get tickers from finviz_screeners.db for the given date
        on_date = args.date_range if args.date_range else date.today().isoformat()
        try:
            from finviz_db import ScreenerCache
        except ImportError:
            print("Error: finviz_db not available. Cannot use --finviz-screener.")
            return 1
        cache = ScreenerCache()
        tickers = cache.get_tickers_for_date(args.finviz_screener.strip(), on_date)
        if not tickers:
            print(f"No stocks found for screener '{args.finviz_screener}' with updated date {on_date}. Run finviz_sync first or use --date-range.")
            return 1
        client = SECClient()
        if args.format == "telegram":
            print(f"📋 Buffett Analysis — FinViz screener: {args.finviz_screener} (updated {on_date}, {len(tickers)} stocks)\n")
        for t in tickers:
            run_analysis(client, t, args)
        return 0

    # Single-ticker mode
    if not args.ticker:
        parser.error("Either --ticker or --finviz-screener is required.")
    client = SECClient()
    run_analysis(client, args.ticker, args)
    return 0


if __name__ == "__main__":
    exit(main() or 0)
