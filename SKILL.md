---
name: stock-analysis
description: >
  Wall Street-grade S&P 500 stock screener. Three commands: "oversold" scans
  all 503 S&P 500 stocks for technically oversold signals using Williams %R in
  15-30 seconds. "screen" combines technical oversold signals with Warren
  Buffett's 10 fundamental quality formulas to find the best opportunities.
  "analyze TICKER" runs a deep Buffett analysis on a single stock using
  official SEC EDGAR data. Uses 100% free public APIs — no subscriptions or
  API keys required.
user-invocable: true
requires:
  bins:
    - python3
  packages:
    - yfinance
    - pandas
    - numpy
    - requests
    - TA-Lib
    - finviz
---

# Stock Analysis Skill

Professional S&P 500 stock screener combining technical analysis (Williams %R)
with Warren Buffett's 10 fundamental quality formulas. All data is free:
Yahoo Finance for prices, SEC EDGAR for financials, GitHub CSV for the S&P 500
ticker list.

---

## IMPORTANT: First-Time Setup

Before running any command, check whether the required Python scripts exist
in the skill directory. If any are missing, generate them automatically.

### Step 1: Check for scripts

```bash
ls {skillDir}/*.py 2>/dev/null
```

If the output shows all 11 scripts below, skip to the command sections.
If any are missing, proceed to Step 2.

### Step 2: Create data directory

```bash
mkdir -p {skillDir}/data
```

### Step 3: Install dependencies

```bash
pip3 install yfinance pandas numpy requests finviz --break-system-packages
```

For TA-Lib — try pip first, fall back to numpy if it fails:
```bash
pip3 install TA-Lib --break-system-packages || echo "TA-Lib not available, will use numpy fallback"
```

### Step 4: Generate all missing scripts

Generate each missing script by writing it to `{skillDir}/`. Use the detailed
specifications in this SKILL.md as the source of truth for every script.
After writing each file, verify it exists before moving to the next.

The 11 required scripts and what each must do:

---

#### `sp500_tickers.py`
Fetches the S&P 500 ticker list from GitHub CSV and returns it as a Python list.

Must implement:
- `get_sp500_tickers()` → returns list of ~503 ticker strings
- Source URL: `https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv`
- Read column `Symbol` from the CSV
- Handle network errors gracefully — return cached list if fetch fails
- Cache the ticker list locally at `{skillDir}/data/sp500_tickers.json` with
  a 7-day TTL so it doesn't re-fetch on every run

---

#### `database.py`
SQLite caching layer used by price_data.py and sec_api.py.

Must implement:
- `PriceCache(db_path)` class:
  - `get(ticker, days)` → returns DataFrame or None if expired/missing
  - `store(ticker, df)` → saves OHLCV DataFrame to SQLite
  - TTL: 1 day — if cached_at timestamp is older than 24 hours, return None
- `SECCache(db_path)` class:
  - `get(cik)` → returns dict or None if expired/missing
  - `store(cik, data)` → saves SEC companyfacts dict to SQLite
  - TTL: 7 days
- Both classes must create their tables on __init__ if they don't exist
- Store DataFrames as JSON text in SQLite (use df.to_json() / pd.read_json())
- Store dicts as JSON text (use json.dumps() / json.loads())

---

#### `price_data.py`
Yahoo Finance price fetching with SQLite caching.

Must implement:
- `PriceDataManager(db_path="{skillDir}/data/price_cache.db")` class:
  - `get_daily_prices(ticker, days=90, force_refresh=False)` → DataFrame
    - Check PriceCache first unless force_refresh=True
    - On cache miss: fetch via `yf.Ticker(ticker).history(period=f"{days}d")`
    - Store result in cache before returning
    - Return None if fetch fails (log warning)
  - `batch_fetch_prices(tickers, days=90, workers=10, force_refresh=False)` → dict
    - Use ThreadPoolExecutor with `workers` threads
    - Returns dict: {ticker: DataFrame}
    - Skip tickers where fetch returns None
    - Add small delay (0.1s) between worker batches to avoid rate limiting

---

#### `technical_indicators.py`
Williams %R and EMA calculations.

Must implement:
- `calculate_williams_r(df, period=21)` → pandas Series
  - Formula: `((high_period.max - close) / (high_period.max - low_period.min)) * -100`
  - Use rolling window of `period` days on High and Low columns
  - Try TA-Lib first: `import talib; talib.WILLR(high, low, close, timeperiod=period)`
  - Fall back to manual numpy/pandas calculation if TA-Lib import fails
- `calculate_ema(series, period=13)` → pandas Series
  - Try TA-Lib first: `talib.EMA(series.values, timeperiod=period)`
  - Fall back to: `series.ewm(span=period, adjust=False).mean()`
- `classify_intensity(williams_r_value)` → string
  - < -95: "EXTREME"
  - -95 to -90: "VERY_STRONG"
  - -90 to -85: "STRONG"
  - -85 to -80: "MODERATE"
  - >= -80: "NEUTRAL"

---

#### `sec_api.py`
SEC EDGAR API client with caching and retry logic.

Must implement:
- `SECClient(cache_db="{skillDir}/data/askten.db")` class:
  - `get_cik_map()` → dict mapping ticker→CIK
    - Fetch from: `https://www.sec.gov/files/company_tickers.json`
    - Cache locally at `{skillDir}/data/cik_map.json` with 30-day TTL
    - CIK must be zero-padded to 10 digits: `str(cik).zfill(10)`
  - `get_companyfacts(cik, force_refresh=False)` → dict
    - Check SECCache first unless force_refresh=True
    - Endpoint: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
    - Always send header: `{'User-Agent': 'StockAnalysis/1.0 openclaw@local'}`
    - Retry logic: on failure wait 2s, 4s, 8s (exponential backoff), max 3 retries
    - Store in SECCache on success
    - Return None on persistent failure
  - `resolve_ticker(ticker)` → CIK string or None
    - Look up ticker in cik_map, handle common variants (BRK.B → BRK-B)
  - `extract_fact(companyfacts, tags, period='annual')` → (value, provenance_dict) or (None, None)
    - `tags` is a list of XBRL tag names to try in order (aliases)
    - Find the most recent annual 10-K value
    - Return tuple: (numeric_value, {tag, label, period_end, fiscal_year, unit, form})

---

#### `formulas.py`
Warren Buffett's 10 investment formulas.

Must implement:
- `FormulaEngine(facts_dict)` class where facts_dict contains extracted SEC values
- `evaluate_all()` → list of result dicts, one per formula
- Each result dict: `{name, status, value, target, description, provenance}`
- Status: "PASS", "FAIL", or "NA" (if data missing — never count NA as FAIL)

The 10 formulas and their exact logic:

```
1. cash_test:
   value  = (cash + short_term_investments) / total_debt
   target = > 1.0
   tags: cash=CashAndCashEquivalentsAtCarryingValue,
         investments=ShortTermInvestments,
         debt=LongTermDebt + ShortTermBorrowings

2. debt_to_equity:
   value  = total_liabilities / stockholders_equity
   target = < 0.5
   tags: liabilities=Liabilities, equity=StockholdersEquity

3. free_cash_flow:
   value  = (operating_cash_flow - capex) / total_debt
   target = > 0.25
   tags: ocf=NetCashProvidedByUsedInOperatingActivities,
         capex=PaymentsToAcquirePropertyPlantAndEquipment,
         debt=LongTermDebt + ShortTermBorrowings

4. return_on_equity:
   value  = net_income / stockholders_equity
   target = > 0.15 (15%)
   tags: income=NetIncomeLoss, equity=StockholdersEquity

5. current_ratio:
   value  = current_assets / current_liabilities
   target = > 1.5
   tags: current_assets=AssetsCurrent, current_liabilities=LiabilitiesCurrent

6. operating_margin:
   value  = operating_income / revenue
   target = > 0.12 (12%)
   tags: oi=OperatingIncomeLoss,
         revenue=Revenues|RevenueFromContractWithCustomerExcludingAssessedTax|SalesRevenueNet

7. asset_turnover:
   value  = revenue / total_assets
   target = > 0.5
   tags: revenue=(same as above), assets=Assets

8. interest_coverage:
   value  = operating_income / interest_expense
   target = > 3.0
   tags: oi=OperatingIncomeLoss, interest=InterestExpense
   special: if interest_expense is 0 or None, mark as PASS (no debt burden)

9. earnings_stability:
   value  = count of years with positive net income over last 10 fiscal years
   target = >= 8
   tags: NetIncomeLoss (fetch all annual values, count positives in last 10)

10. capital_allocation:
    value  = net_income / stockholders_equity  (same as ROE)
    target = > 0.15 (15%)
    tags: income=NetIncomeLoss, equity=StockholdersEquity
```

---

#### `technical_only.py`
Fast Williams %R oversold scanner. This is the main entry point for the
`oversold` command.

Must implement as a runnable script with argparse:
- `--threshold FLOAT` default -80.0
- `--top-n INT` default 20
- `--format STRING` default "telegram"
- `--force-refresh` flag

Logic:
1. Call `get_sp500_tickers()` from sp500_tickers.py
2. Call `PriceDataManager().batch_fetch_prices(tickers, days=90, workers=10)`
3. For each ticker with price data:
   - Call `calculate_williams_r(df, period=21)`
   - Call `calculate_ema(williams_r, period=13)`
   - Get latest value: `williams_r.iloc[-1]`
   - If latest value < threshold: add to signals list
4. Sort signals by williams_r ascending (most negative = most oversold first)
5. Take top N results
6. Format and print output

Output format (telegram):
```
📊 S&P 500 Oversold Scan
Scanned: 503 | Found: N oversold (X%)

🔴 EXTREME (< -95): N stocks
1. TICK — %R: -99.3 | EMA: -97.1
...

🟠 VERY STRONG (-95 to -90): N stocks
...

⚡ Xs (cached) | ⚠️ Not financial advice.
```

---

#### `analyze.py`
Deep Buffett fundamental analysis for a single stock or for all stocks from a
FinViz screener. Main entry point for `analyze TICKER` and for "analyze FinViz
screener" (nanobot: use `--finviz-screener` to get stocks from finviz_screeners.db
and run analysis on each; output includes metadata per stock when available).

Must implement as a runnable script with argparse:
- `--ticker STRING` optional — single ticker (required if not using --finviz-screener)
- `--finviz-screener STRING` optional — `"all"` or a specific screener name (e.g. "refined 50D drop")
- `--date-range STRING` optional — date for screener filter (YYYY-MM-DD). Default: today.
- `--format STRING` default "telegram"
- `--force-refresh` flag

Logic:
- **Single-ticker mode** (when `--ticker` is set): resolve CIK, get companyfacts, extract facts, FormulaEngine, print. No metadata line.
- **FinViz screener mode** (when `--finviz-screener` is set):
  1. Resolve `on_date` = `--date-range` if provided, else today (YYYY-MM-DD).
  2. From `finviz_db.ScreenerCache`, call `get_tickers_with_metadata(screener_name, on_date)` to get rows from `finviz_screeners.db` where `date(updated_at) = on_date`. Each row includes ticker plus Company, Sector, Industry, Country, PE, MarketCap (from finviz_sync). Use screener name as given, or `"all"` for distinct tickers from any screener (one row per ticker).
  3. Only stocks with updated date equal to `on_date` are processed; older dates are ignored unless `--date-range` is set.
  4. Loop through each row: for each ticker, run the same Buffett analysis (resolve CIK, companyfacts, FormulaEngine). When printing in telegram format, **pull and display metadata** from the row: right after the `📊 {TICKER} — Buffett Analysis` line, print one line: `Company | Industry | P/E: {PE} | Market Cap: {MarketCap}`. Use **N/A** for any missing value (Company, Industry, PE, or MarketCap).
- Either `--ticker` or `--finviz-screener` must be provided.

Output format (telegram), single-ticker:
```
📊 {TICKER} — Buffett Analysis
Score: X/10 Buffett Criteria
...
```

Output format (telegram), FinViz screener mode (per stock):
```
📊 {TICKER} — Buffett Analysis
{Company} | {Industry} | P/E: {PE} | Market Cap: {MarketCap}
Score: X/10 Buffett Criteria

✅ Strengths
| Metric             | Value   | Target |
...

❌ Concerns
| Metric             | Value   | Target |
...

📎 Data: SEC EDGAR 10-K ({period_end})
⚠️ Not financial advice.
```
Missing Company, Industry, PE, or MarketCap are shown as **N/A**.

---

#### `screening.py`
Combined technical + fundamental screen. Main entry point for `screen` command.

Must implement as a runnable script with argparse:
- `--min-score INT` default 5
- `--threshold FLOAT` default -80.0
- `--top-n INT` default 10
- `--format STRING` default "telegram"
- `--force-refresh` flag

Logic:
1. Run full technical scan (same as technical_only.py) to get oversold list
2. For each oversold ticker, run Buffett analysis (same as analyze.py)
3. Filter: keep only stocks where buffett_pass_count >= min_score
4. Calculate combined score:
   ```python
   tech_score        = (williams_r + 100) / 100
   fundamental_score = pass_count / 10
   combined_score    = (tech_score * 0.3) + (fundamental_score * 0.7)
   ```
5. Sort by combined_score descending
6. Return top N results

Output format (telegram):
```
🔍 S&P 500 Quality Screen
Filter: Williams %R < {threshold} AND Buffett ≥ {min_score}/10

Top {N} Opportunities:

1. TICK — Combined: 8.2/10
   %R: -94.3 🔴 | Buffett: 8/10

2. TICK — Combined: 7.6/10
   %R: -89.1 🟡 | Buffett: 7/10
...

⏱ Xm Xs | Yahoo Finance + SEC EDGAR | ⚠️ Not financial advice.
```

---

#### `finviz_db.py`
SQLite layer for FinViz screener results. Used by finviz_sync.py (writes) and
analyze.py (reads tickers + metadata for screener mode).

Must implement:
- `ScreenerCache(db_path="{skillDir}/data/finviz_screeners.db")` class:
  - Table `screener_stocks`: columns `screener_name`, `ticker`, `updated_at`, `Company`, `Sector`, `Industry`, `Country`, `PE`, `MarketCap` (no spaces in column names; P/E → PE, Market Cap → MarketCap). PRIMARY KEY (screener_name, ticker).
  - `is_fresh(screener_name)` → True if screener has data and updated_at is within TTL
  - `get_tickers(screener_name)` → list of ticker strings, or None if missing/stale
  - `get_tickers_for_date(screener_name, on_date)` → list of tickers where `date(updated_at) = on_date` (on_date str "YYYY-MM-DD"); screener_name `"all"` returns distinct tickers from any screener for that date
  - `get_tickers_with_metadata(screener_name, on_date)` → list of dicts, each with keys `ticker`, `Company`, `Sector`, `Industry`, `Country`, `PE`, `MarketCap` for rows where `date(updated_at) = on_date`; for `"all"`, dedupe by ticker (one row per ticker). Used by analyze.py in FinViz screener mode to display metadata per stock.
  - `store(screener_name, rows)` → replace all rows for that screener; each row is a dict with `ticker` and optionally Company, Sector, Industry, Country, PE, MarketCap
- TTL: 1 day — data older than 24 hours is treated as stale
- Create table on __init__ if it doesn't exist; add new metadata columns via ALTER if table already exists

---

#### `finviz_sync.py`
Fetch stocks from a FinViz screener URL and store them in SQLite (1-day TTL).
Enriches each ticker with `finviz.get_stock(ticker)` to store Company, Sector,
Industry, Country, P/E (as PE), Market Cap (as MarketCap). Skips fetch if
screener data is already fresh unless `--force-refresh` is used.

Must implement as a runnable script with argparse:
- `--screener STRING` optional — screener label (e.g. "refined 50D drop")
- `--url STRING` optional — FinViz screener URL (e.g. from finviz.com)
- `--force-refresh` flag
- `--clean STRING` optional — `"true"` (default) or `"false"`. When true, exclude from storage: Industry = "Asset Management", Industry contains "Closed-End Fund", Industry = "REIT - Office", Country = "China". Use `--clean false` to disable filtering.

Logic:
1. If both `--screener` and `--url` are passed: sync that one screener
2. If neither is passed: read `finviz_config.json` from skill directory;
   each node must have `screener` and `url`; sync each screener in order
3. If no parameters and no valid config: print message asking user to pass
   parameters or create finviz_config.json, then exit with error
4. For each screener: if not fresh (or force-refresh), call
   `Screener.init_from_url(url)` (finviz library), extract tickers from
   `row["Ticker"]`, then for each ticker call `finviz.get_stock(ticker)` to get
   Company, Sector, Industry, Country, P/E, Market Cap; build rows and pass to
   ScreenerCache.store(screener_name, rows). If `--clean` is true, filter out
   rows matching the excluded Industry/Country rules before storing.

Config format (`finviz_config.json`):
```json
[
  {"screener": "refined 50D drop", "url": "https://finviz.com/screener.ashx?v=111&f=..."},
  {"screener": "another", "url": "https://finviz.com/screener.ashx?..."}
]
```

Requires the `finviz` Python package (`pip install finviz`). FinViz table `v`
must be a type the library supports (e.g. 111 Overview); if the URL uses
an unsupported view (e.g. 110), use v=111 in the URL.

---

## Running Commands

Once all scripts exist, execute commands as follows.

### oversold
```bash
cd {skillDir}
python3 technical_only.py --top-n 20 --format telegram
```

With custom threshold:
```bash
python3 technical_only.py --threshold -90 --top-n 10 --format telegram
```

### analyze TICKER
```bash
cd {skillDir}
python3 analyze.py --ticker AAPL --format telegram
```
### update FinViz data
```bash
cd {skillDir}
python3 finviz_sync.py
```

### analyze FinViz screener
When the user asks to analyze a FinViz screener (e.g. "analyze finviz screener refined 50D drop"), get the stock list **with metadata** from `finviz_screeners.db` and run Buffett analysis on each. Only process stocks whose screener updated date is today (or the date given by `--date-range`). For each stock, analyze uses `get_tickers_with_metadata` so it can display **Company, Industry, P/E, Market Cap** from the DB right after the ticker line (shows **N/A** for any missing value).

```bash
cd {skillDir}
# Specific screener (stocks updated today)
python3 analyze.py --finviz-screener "refined 50D drop" --format telegram

# All screeners (distinct tickers updated today)
python3 analyze.py --finviz-screener all --format telegram

# Use a specific date (e.g. yesterday)
python3 analyze.py --finviz-screener "refined 50D drop" --date-range 2025-02-22 --format telegram
```

Ensure `finviz_sync.py` has been run for the desired screener(s) so that `finviz_screeners.db` has rows (with metadata) and the desired `updated_at` date.

### screen
```bash
cd {skillDir}
python3 screening.py --min-score 5 --top-n 10 --format telegram
```

With high quality filter:
```bash
python3 screening.py --min-score 8 --top-n 10 --format telegram
```

---

## Error Handling

- **Yahoo Finance rate limit:** If > 10% of fetches fail, reduce workers to 5
  and add `time.sleep(0.5)` between batches
- **SEC timeout:** Exponential backoff 2s/4s/8s, max 3 retries, then skip
- **Missing XBRL tag:** Try all aliases, mark formula NA if all fail
- **TA-Lib missing:** Use numpy/pandas fallback (defined in technical_indicators.py)
- **Ticker not in SEC:** Log warning and skip (~3 stocks affected, e.g. BRK.B)

---

## Example Telegram Interactions & Cron Jobs

```
User: oversold
→ python3 technical_only.py --top-n 20 --format telegram

User: oversold --threshold -95
→ python3 technical_only.py --threshold -95 --top-n 20 --format telegram

User: analyze V
→ python3 analyze.py --ticker V --format telegram

User: analyze AAPL
→ python3 analyze.py --ticker AAPL --format telegram

User: analyze finviz screener refined 50D drop
→ python3 analyze.py --finviz-screener "refined 50D drop" --format telegram
(Output includes Company, Industry, P/E, Market Cap per stock from finviz_screeners.db; N/A if missing.)

User: analyze finviz screener all
→ python3 analyze.py --finviz-screener all --format telegram
(Output includes metadata per stock as above.)

User: screen
→ python3 screening.py --min-score 5 --top-n 10 --format telegram

User: screen --min-score 8
→ python3 screening.py --min-score 8 --top-n 10 --format telegram

User: finviz sync
→ python3 finviz_sync.py
```

Always append to every Telegram response:
`⚠️ This is not financial advice. Data: Yahoo Finance + SEC EDGAR.`
