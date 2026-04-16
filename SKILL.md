---
name: stock-analysis
description: >
  Wall Street-grade stock screener. Three commands: 1) "oversold" scans
  all 503 S&P 500 stocks for technically oversold signals using Williams %R in
  15-30 seconds. 2) "screen" combines technical oversold signals with Warren
  Buffett's 10 fundamental quality formulas to find the best opportunities.
  3) "analyze" runs a deep Buffett analysis on a single stock or stocks resulted from a predefined screenerUses 100% free public APIs — no subscriptions or API keys required. 
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
ticker list, FinViz API to get screener data.

The scripts in this skills handle most of the data gathering.  All outputs from the scripts do not need to send to LLM provider for further analysis. This is to save token usage.

---

## IMPORTANT: First-Time Setup

Before running any command, check whether the required Python scripts exist
in the skill directory. If any are missing, generate them automatically.

### Step 1: Check for scripts

```bash
ls {skillDir}/*.py 2>/dev/null
```

If the output shows all 11 scripts below, skip to the Running Commands section below.
If any are missing, inform human if you need to execute BOOTSTRAP.md

---

## Running Commands

Once all scripts exist, execute commands as follows. For stock-analysis, please make sure to remember that output from any intermediary script execution do not need to send to providers.  Just pass on to the next script.

### oversold
```bash
cd {skillDir}
python3 technical_only.py --top-n 20 --format telegram
```

With custom threshold:
```bash
python3 technical_only.py --threshold -90 --top-n 10 --format telegram
```
### update FinViz data
```bash
cd {skillDir}
python3 finviz_sync.py
```

### analyze TICKER
* Method 1: analyze TICKER
```bash
cd {skillDir}
python3 analyze.py --ticker AAPL --format telegram
pythond3 final_report.py --ticker [TICKER]
```

### analyze TICKER FinViz [SCREENER NAME]
When analyze screener, you will use a combination of 3 commands and scripts.  The sequence is:
 "update FinViz data" -> execute the analyze.py script described below -> "final_report.py --screener [SCREENER NAME]" of the top 20. No need to send final_report output to LLM provider.  Just print out the output from final_report.
```bash
cd {skillDir}
# sync data first
python3 finviz_sync.py

# Specific screener (stocks updated today)
python3 analyze.py --finviz-screener [SCRNEER NAME] #--format telegram

# report all
python3 final_report.py [SCREENER NAME]
```

### analyze TICKER FinViz All Screeners
When analyze screener, you will use a combination of 3 commands and scripts.  The sequence is:
 "update FinViz data" -> execute the analyze.py script described below -> "final_report.py --screeber all" of the top 20. Just print out the output from final_report.
```bash
cd {skillDir}
# sync data first
python3 finviz_sync.py

# All screeners (distinct tickers updated today)
python3 analyze.py --finviz-screener all #--format telegram

# report all
python3 final_report.py [SCREENER NAME]
```

### analyze TICKER FinViz [SCREENER NAME] [DATE]
```bash
cd {skillDir}
# sync data first
python3 finviz_sync.py

# Use a specific date (e.g. analyze FinViz screener 'refined 50D drop' on 2025-02-22)
python3 analyze.py --finviz-screener [SCREEN NAME] --date-range [DATE] #--format telegram

# report all
python3 final_report.py [SCREENER NAME]
```

### screen
```bash
cd {skillDir}
python3 screening.py --min-score 5 --top-n 10 --format telegram
```

With high quality filter:
```bash
python3 screening.py --min-score 8 --top-n 10 --format telegram
```

## MEMORY
After each processing, write the result to  {skillDir}/memory/YYYY-MM-DD-output.md

---

## Error Handling

- **Yahoo Finance rate limit:** If > 10% of fetches fail, reduce workers to 5
  and add `time.sleep(0.5)` between batches
- **SEC timeout:** Exponential backoff 2s/4s/8s, max 3 retries, then skip
- **Missing XBRL tag:** Try all aliases, mark formula NA if all fail
- **TA-Lib missing:** Use numpy/pandas fallback (defined in technical_indicators.py)
- **Ticker not in SEC:** Log warning and skip (~3 stocks affected, e.g. BRK.B)

---

