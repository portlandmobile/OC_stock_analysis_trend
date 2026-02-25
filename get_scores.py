
import os
import sys
import json

# Add skill directory to path for imports
skill_dir = "/Users/peekay/.nanobot/workspace/skills/OC_stock_analysis_trend"
sys.path.append(skill_dir)

from sec_api import SECClient
from formulas import FormulaEngine

def get_buffett_score(ticker):
    try:
        client = SECClient()
        cik = client.resolve_ticker(ticker)
        if not cik:
            return "0/0*"
        facts = client.get_companyfacts(cik)
        if not facts:
            return "0/0*"
        
        # Extract facts (simplified for this script, but using real tags)
        # In a real scenario, we'd use the extract_fact method
        # For brevity, let's just try to get the pass count from FormulaEngine
        
        # We need a facts_dict for FormulaEngine
        # FormulaEngine expects a dict of extracted values
        # This part is complex to replicate exactly without the full analyze.py logic
        # So I will just use a shell command to run analyze.py and grep the score
        return None
    except:
        return "0/0*"

tickers = ["XYF", "YRD", "GSL", "FINV", "COHN", "HRB", "HG", "SGU", "ENR", "OMF", "FNLC", "KEN", "NWG", "NRT", "CIG", "PRU", "BBD", "UBCP", "LTM", "MARPS"]

results = {}
for t in tickers:
    # Use the existing analyze.py to get the score
    cmd = f"python3 analyze.py --ticker {t} --format telegram"
    output = os.popen(f"cd {skill_dir} && {cmd}").read()
    # Find the line: "Score: X/10 Buffett Criteria"
    import re
    match = re.search(r"Score: ([\d/]+)\*? Buffett Criteria", output)
    if match:
        results[t] = match.group(1)
    else:
        results[t] = "0/0*"

print(json.dumps(results))
