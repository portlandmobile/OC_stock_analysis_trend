
import subprocess
import json
import re

stocks = [{"ticker": "XYF", "pe": 0.8443316, "wr": -83.33336487018863, "intensity": "MODERATE"}, {"ticker": "QFIN", "pe": 2.0531645, "wr": -88.64286363854656, "intensity": "STRONG"}, {"ticker": "LIEN", "pe": 5.6875, "wr": -78.0701636974475, "intensity": "NEUTRAL"}, {"ticker": "OTF", "pe": 6.1833334, "wr": -95.07561297801954, "intensity": "EXTREME"}, {"ticker": "HPQ", "pe": 6.9874716, "wr": -83.67080867710764, "intensity": "MODERATE"}, {"ticker": "BCIC", "pe": 7.272436, "wr": -89.21568688560457, "intensity": "STRONG"}, {"ticker": "EIC", "pe": 7.8276563, "wr": -84.66408246447133, "intensity": "MODERATE"}, {"ticker": "GSBD", "pe": 7.9389567, "wr": -71.22037952995183, "intensity": "NEUTRAL"}, {"ticker": "HTGC", "pe": 8.129676, "wr": -99.73739802703226, "intensity": "EXTREME"}, {"ticker": "BXSL", "pe": 8.945283, "wr": -87.61754258199953, "intensity": "STRONG"}, {"ticker": "SCM", "pe": 9.541284, "wr": -94.53691026279934, "intensity": "VERY_STRONG"}, {"ticker": "CGBD", "pe": 9.74569, "wr": -86.47883676485837, "intensity": "STRONG"}, {"ticker": "GLAD", "pe": 11.398734, "wr": -99.60970004395224, "intensity": "EXTREME"}, {"ticker": "EHI", "pe": 12.020001, "wr": -55.07717540762766, "intensity": "NEUTRAL"}, {"ticker": "PMT", "pe": 12.085858, "wr": -86.34019224889123, "intensity": "STRONG"}, {"ticker": "WIW", "pe": 12.176058, "wr": -38.4602135528091, "intensity": "NEUTRAL"}, {"ticker": "WIA", "pe": 12.313433, "wr": -53.44362870203984, "intensity": "NEUTRAL"}, {"ticker": "PNNT", "pe": 12.589744, "wr": -93.12212313032855, "intensity": "VERY_STRONG"}, {"ticker": "OPRA", "pe": 13.400001, "wr": -88.92403802625623, "intensity": "STRONG"}, {"ticker": "OFS", "pe": 16.833334, "wr": -95.08197105754292, "intensity": "EXTREME"}]

results = []

for s in stocks:
    ticker = s['ticker']
    try:
        output = subprocess.check_output(["python3", "analyze.py", "--ticker", ticker, "--format", "telegram"], stderr=subprocess.STDOUT).decode()
        # Find Score: X/Y
        match = re.search(r"Score: (\d+/\d+)", output)
        score = match.group(1) if match else "N/A"
    except Exception as e:
        score = "N/A"
    
    results.append({
        'ticker': ticker,
        'pe': round(s['pe'], 2),
        'score': score,
        'wr': round(s['wr'], 1) if s['wr'] is not None else "N/A",
        'intensity': s['intensity']
    })

print(json.dumps(results))
