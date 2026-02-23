import os
import json
import time
import requests
from database import SECCache

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(SKILL_DIR, "data", "askten.db")
CIK_MAP_FILE = os.path.join(SKILL_DIR, "data", "cik_map.json")
USER_AGENT = 'nanobot/1.0 (peekay@example.com)'

class SECClient:
    def __init__(self, cache_db=DEFAULT_DB):
        self.cache = SECCache(cache_db)
        self.cik_map = self.get_cik_map()

    def get_cik_map(self):
        # Check cache
        if os.path.exists(CIK_MAP_FILE):
            mtime = os.path.getmtime(CIK_MAP_FILE)
            if time.time() - mtime < 30 * 24 * 3600: # 30 days
                try:
                    with open(CIK_MAP_FILE, 'r') as f:
                        return json.load(f)
                except Exception:
                    pass

        # Fetch from SEC
        try:
            headers = {'User-Agent': USER_AGENT}
            response = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Map ticker -> CIK
            cik_map = {}
            for item in data.values():
                ticker = item['ticker'].upper()
                cik = str(item['cik_str']).zfill(10)
                cik_map[ticker] = cik

            os.makedirs(os.path.dirname(CIK_MAP_FILE), exist_ok=True)
            with open(CIK_MAP_FILE, 'w') as f:
                json.dump(cik_map, f)
            return cik_map
        except Exception as e:
            print(f"Error fetching CIK map: {e}")
            if os.path.exists(CIK_MAP_FILE):
                with open(CIK_MAP_FILE, 'r') as f:
                    return json.load(f)
            return {}

    def get_companyfacts(self, cik, force_refresh=False):
        if not force_refresh:
            cached = self.cache.get(cik)
            if cached:
                return cached

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        headers = {'User-Agent': USER_AGENT}
        
        for delay in [2, 4, 8]:
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    self.cache.store(cik, data)
                    return data
                elif response.status_code == 404:
                    return None
            except Exception:
                pass
            time.sleep(delay)
        return None

    def resolve_ticker(self, ticker):
        ticker = ticker.upper().replace('.', '-')
        return self.cik_map.get(ticker)

    def extract_fact(self, companyfacts, tags, period='annual'):
        if not companyfacts or 'facts' not in companyfacts:
            return None, None

        for taxonomy in ['us-gaap', 'dei']:
            if taxonomy not in companyfacts['facts']:
                continue
            
            for tag in tags:
                if tag in companyfacts['facts'][taxonomy]:
                    units = companyfacts['facts'][taxonomy][tag].get('units', {})
                    # Prefer USD for monetary facts
                    unit_keys = list(units.keys())
                    if 'USD' in unit_keys:
                        unit_keys = ['USD'] + [k for k in unit_keys if k != 'USD']
                    for unit_name in unit_keys:
                        entries = units[unit_name]
                        # Sort by end date descending
                        sorted_entries = sorted(entries, key=lambda x: x.get('end', ''), reverse=True)
                        
                        for entry in sorted_entries:
                            if period == 'annual':
                                if entry.get('form') == '10-K':
                                    return entry.get('val'), {
                                        'tag': tag,
                                        'label': companyfacts['facts'][taxonomy][tag].get('label'),
                                        'period_end': entry.get('end'),
                                        'fiscal_year': entry.get('fy'),
                                        'unit': unit_name,
                                        'form': entry.get('form')
                                    }
                            # Could add 'quarterly' logic here if needed
                            
        return None, None

    def extract_historical_facts(self, companyfacts, tag, limit=10):
        if not companyfacts or 'facts' not in companyfacts:
            return []

        results = []
        for taxonomy in ['us-gaap', 'dei']:
            if taxonomy in companyfacts['facts'] and tag in companyfacts['facts'][taxonomy]:
                units = companyfacts['facts'][taxonomy][tag].get('units', {})
                for unit_name, entries in units.items():
                    # Get all 10-K entries
                    ten_ks = [e for e in entries if e.get('form') == '10-K']
                    # Sort by end date descending
                    ten_ks = sorted(ten_ks, key=lambda x: x.get('end', ''), reverse=True)
                    
                    seen_years = set()
                    for entry in ten_ks:
                        fy = entry.get('fy')
                        if fy not in seen_years:
                            results.append(entry.get('val'))
                            seen_years.add(fy)
                            if len(results) >= limit:
                                break
                    if results: break
            if results: break
        return results
