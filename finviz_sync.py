"""
Fetch stocks from a FinViz screener URL and store them in SQLite.
Skips fetch if screener data is already fresh (1-day TTL).

Usage:
  - With params: --screener "name" --url "https://finviz.com/screener.ashx?..."
  - Without params: reads finviz_config.json (array of {screener, url})
  - URL value parameters only supports the following table types:
    - 111 Overview
    - 121 (Valuation)
    - 131 (Ownership)
    - 141 (Performance)
    - 152 (Custom)
    - 161 (Financial)
    - 171 (Technical)
"""
import argparse
import json
import os
import sys
import time
from finviz_db import ScreenerCache
from finviz.screener import Screener
import finviz

CONFIG_FILE = "finviz_config.json"


def _sync_one(cache, screener_name, url, force_refresh):
    """Sync one screener. Returns 0 on success, 1 on error."""
    if not force_refresh and cache.is_fresh(screener_name):
        tickers = cache.get_tickers(screener_name)
        if tickers is not None:
            print(f"Screener '{screener_name}' is current ({len(tickers)} tickers). Use --force-refresh to update.")
            return 0

    try:
        stock_list = Screener.init_from_url(url)
    except Exception as e:
        print(f"Error loading FinViz screener '{screener_name}': {e}", file=sys.stderr)
        return 1

    tickers = []
    for row in stock_list.data:
        t = row.get("Ticker") if isinstance(row, dict) else None
        if t and str(t).strip():
            tickers.append(str(t).strip())

    if not tickers:
        print(f"No tickers returned from FinViz for '{screener_name}'.", file=sys.stderr)
        return 1

    # Enrich each ticker with get_stock(): Company, Sector, Industry, Country, P/E, Market Cap
    rows = []
    for t in tickers:
        try:
            info = finviz.get_stock(t)
            if info is None:
                info = {}
            pe_val = info.get("P/E") or info.get("PE")
            cap_val = info.get("Market Cap") or info.get("MarketCap")
            rows.append({
                "ticker": t,
                "Company": info.get("Company"),
                "Sector": info.get("Sector"),
                "Industry": info.get("Industry"),
                "Country": info.get("Country"),
                "PE": str(pe_val) if pe_val is not None else None,
                "MarketCap": str(cap_val) if cap_val is not None else None,
            })
        except Exception as e:
            print(f"Warning: get_stock({t}) failed: {e}", file=sys.stderr)
            rows.append({
                "ticker": t,
                "Company": None,
                "Sector": None,
                "Industry": None,
                "Country": None,
                "PE": None,
                "MarketCap": None,
            })
        time.sleep(0.15)

    cache.store(screener_name, rows)
    print(f"Stored {len(rows)} tickers for screener '{screener_name}'.")
    return 0


def _load_config():
    """Load screener list from finviz_config.json. Returns list of (screener, url) or None."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading {CONFIG_FILE}: {e}", file=sys.stderr)
        return None
    if not isinstance(data, list) or not data:
        return None
    result = []
    for node in data:
        name = node.get("screener")
        url = node.get("url")
        if name and url:
            result.append((name, url))
    return result if result else None


def main():
    parser = argparse.ArgumentParser(
        description="Sync FinViz screener results to local DB (1-day TTL)."
    )
    parser.add_argument("--screener", type=str, help="Screener label (e.g. 'refined 50D drop')")
    parser.add_argument("--url", type=str, help="FinViz screener URL (e.g. from finviz.com)")
    parser.add_argument("--force-refresh", action="store_true", help="Fetch from FinViz even if cache is fresh")
    args = parser.parse_args()

    screeners = []
    if args.screener and args.url:
        screeners = [(args.screener, args.url)]
    else:
        config = _load_config()
        if config:
            screeners = config
        else:
            print(
                "No screener specified. Either pass --screener and --url, "
                f"or create {CONFIG_FILE} with an array of {{'screener': 'name', 'url': 'https://...'}} nodes.",
                file=sys.stderr,
            )
            return 1

    cache = ScreenerCache()
    failed = 0
    for screener_name, url in screeners:
        if _sync_one(cache, screener_name, url, args.force_refresh) != 0:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
