# Stock Analysis Scoring Rules

## New Metrics (added 2026-04-29)

### P/S Ratio Score (1–5, lower is better)
| Score | P/S Range | Interpretation |
|-------|-----------|----------------|
| 5 | < 1 | Deeply undervalued |
| 4 | 1–3 | Reasonable |
| 3 | 3–5 | Fair |
| 2 | 5–10 | Expensive |
| 1 | > 10 | Very expensive |

### QoQ Revenue Growth Score (1–5, higher is better)
Uses quarterly revenue from yfinance (`income_stmt → Total Revenue`). Stores Q1 (most recent), Q2, Q3 (oldest of 3) in DB.

Computes 2 QoQ changes from 3 values.

| Score | Condition | Example |
|-------|-----------|---------|
| 5 | 2/2 positive, avg > 20% | Explosive growth |
| 4 | 2/2 positive, avg > 10% | Strong growth |
| 3 | 2/2 positive | Moderate growth |
| 2 | 1/2 positive | Mixed |
| 1 | 0/2 positive | Declining |

**NOT hard filters.** Every stock gets scored. Thresholds stored here for easy tweaking.

## Data Pipeline
1. `finviz_sync.py` fetches P/S (from FinViz) + quarterly revenue (from yfinance) → stores in DB
2. `final_report.py` reads from DB → computes scores → displays in table
3. `analyze.py --finviz-screener` passes PS + revenue to FormulaEngine

## Files Modified
- `finviz_db.py` — DB schema + store + get_tickers_with_metadata
- `finviz_sync.py` — sync script (adds yfinance + P/S fetch)
- `formulas.py` — `price_to_sales_score()` + `qoq_revenue_growth_score()`
- `analyze.py` — CLI args + passes new data to FormulaEngine
- `final_report.py` — new columns in output table

## Key Implementation Notes
- Quarterly revenue stored as strings (scientific notation OK)
- Revenue values are from yfinance `income_stmt.loc['Total Revenue']` — most recent first
- QoQ computed as `(curr - prev) / prev * 100` for each adjacent pair
- Only 2 QoQ changes from 3 quarters (not 3)
- If fewer than 3 revenue values → returns "N/A"
