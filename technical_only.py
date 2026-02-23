import argparse
import time
from sp500_tickers import get_sp500_tickers
from price_data import PriceDataManager
from technical_indicators import calculate_williams_r, calculate_ema, classify_intensity

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=-80.0)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--format", type=str, default="telegram")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    start_time = time.time()
    
    tickers = get_sp500_tickers()
    if not tickers:
        print("Error: Could not retrieve S&P 500 tickers.")
        return

    pdm = PriceDataManager()
    # Fetching 500+ stocks can take time, batch_fetch handles it
    price_data = pdm.batch_fetch_prices(tickers, workers=10, force_refresh=args.force_refresh)
    
    signals = []
    for ticker, df in price_data.items():
        wr = calculate_williams_r(df, period=21)
        ema = calculate_ema(wr, period=13)
        
        if len(wr) > 0:
            latest_wr = wr.iloc[-1]
            latest_ema = ema.iloc[-1] if len(ema) > 0 else None
            
            if latest_wr < args.threshold:
                signals.append({
                    'ticker': ticker,
                    'wr': latest_wr,
                    'ema': latest_ema,
                    'intensity': classify_intensity(latest_wr)
                })

    # Sort by WR ascending (most oversold first)
    signals.sort(key=lambda x: x['wr'])
    top_signals = signals[:args.top_n]
    
    elapsed = time.time() - start_time
    
    if args.format == "telegram":
        print(f"📊 S&P 500 Oversold Scan")
        print(f"Scanned: {len(tickers)} | Found: {len(signals)} oversold ({len(signals)/len(tickers):.1%})\n")
        
        # Group by intensity
        for intensity in ["EXTREME", "VERY_STRONG", "STRONG", "MODERATE"]:
            group = [s for s in top_signals if s['intensity'] == intensity]
            if group:
                emoji = {"EXTREME": "🔴", "VERY_STRONG": "🟠", "STRONG": "🟡", "MODERATE": "⚡"}[intensity]
                threshold_desc = {"EXTREME": "< -95", "VERY_STRONG": "-95 to -90", "STRONG": "-90 to -85", "MODERATE": "-85 to -80"}[intensity]
                print(f"{emoji} {intensity} ({threshold_desc}): {len(group)} stocks")
                for i, s in enumerate(group, 1):
                    ema_str = f" | EMA: {s['ema']:.1f}" if s['ema'] is not None else ""
                    print(f"{i}. {s['ticker']} — %R: {s['wr']:.1f}{ema_str}")
                print()

        print(f"⚡ {elapsed:.1f}s | ⚠️ Not financial advice.")
    else:
        # Simple CSV/Text output
        for s in top_signals:
            print(f"{s['ticker']},{s['wr']:.2f},{s['intensity']}")

if __name__ == "__main__":
    main()
