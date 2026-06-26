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

    def extract_quarterly_data(self, ticker, limit=4):
        """Extract quarterly (10-Q) EPS and revenue data from SEC EDGAR.
        
        Returns dict with:
        - net_income: list of dicts with period_end, value, form, fy, qf
        - revenue: list of dicts with period_end, value, form, fy, qf
        - shares_outstanding: list of dicts with period_end, value, form, fy, qf
        - taxonomy: 'us-gaap' or 'ifrs-full'
        """
        cik = self.resolve_ticker(ticker)
        if not cik:
            return None
        
        companyfacts = self.get_companyfacts(cik, force_refresh=True)
        if not companyfacts:
            return None
        
        result = {
            'ticker': ticker,
            'cik': cik,
            'net_income': [],
            'revenue': [],
            'shares_outstanding': [],
            'eps_diluted': [],
            'taxonomy': None,
        }
        
        # Determine taxonomy (us-gaap or ifrs-full)
        taxonomy = None
        if 'us-gaap' in companyfacts.get('facts', {}) and 'NetIncomeLoss' in companyfacts['facts']['us-gaap']:
            taxonomy = 'us-gaap'
        elif 'ifrs-full' in companyfacts.get('facts', {}) and 'ProfitLoss' in companyfacts['facts']['ifrs-full']:
            taxonomy = 'ifrs-full'
        
        if not taxonomy:
            return None
        
        result['taxonomy'] = taxonomy
        facts = companyfacts['facts'][taxonomy]
        
        def extract_entries(tag, forms=('10-Q', '10-K')):
            """Extract entries for a given tag, filtering by form and currency."""
            if tag not in facts:
                return []
            entries = []
            tag_data = facts[tag]
            units = tag_data.get('units', {})
            
            # For US GAAP, prefer USD currency (or USD/shares for EPS)
            if taxonomy == 'us-gaap':
                if 'USD' in units:
                    unit_keys = ['USD']
                elif any('USD' in k for k in units.keys()):
                    # Find USD-related units (e.g., USD/shares)
                    unit_keys = [k for k in units.keys() if 'USD' in k]
                else:
                    unit_keys = list(units.keys())
            else:
                unit_keys = list(units.keys())
            
            for unit_name in unit_keys:
                for e in units[unit_name]:
                    if e.get('form') in forms:
                        entries.append({
                            'period_end': e.get('end'),
                            'fy': e.get('fy'),
                            'qf': e.get('qf'),
                            'form': e.get('form'),
                            'val': e.get('val'),
                            'unit': unit_name
                        })
            
            # Sort by period_end descending and deduplicate
            entries = sorted(entries, key=lambda x: x.get('period_end', ''), reverse=True)
            # Remove duplicates (same period_end + form)
            seen = set()
            unique = []
            for e in entries:
                key = (e['period_end'], e['form'])
                if key not in seen:
                    seen.add(key)
                    unique.append(e)
            return unique[:limit]
        
        # Extract Net Income / Profit Loss
        ni_tag = 'NetIncomeLoss' if taxonomy == 'us-gaap' else 'ProfitLoss'
        result['net_income'] = extract_entries(ni_tag)
        
        # Extract Revenue - use newer IFRS17-compliant tag first, fallback to legacy
        if taxonomy == 'us-gaap':
            rev_tag = 'RevenueFromContractWithCustomerExcludingAssessedTax'
            result['revenue'] = extract_entries(rev_tag)
            # If primary tag doesn't have recent data (within last 2 years), try legacy
            if result['revenue']:
                from datetime import datetime, timedelta
                cutoff = datetime.now() - timedelta(days=730)
                try:
                    latest_end = datetime.strptime(result['revenue'][0]['period_end'], '%Y-%m-%d')
                    if latest_end < cutoff:
                        result['revenue'] = extract_entries('Revenues')
                except (ValueError, IndexError):
                    result['revenue'] = extract_entries('Revenues')
            else:
                result['revenue'] = extract_entries('Revenues')
        else:
            result['revenue'] = extract_entries('Revenue')
        
        # Extract Shares Outstanding (for EPS calculation)
        shares_tag = 'CommonStockSharesOutstanding' if taxonomy == 'us-gaap' else 'NumberOfSharesOutstanding'
        result['shares_outstanding'] = extract_entries(shares_tag)
        
        # Extract Diluted EPS directly from SEC (uses same unit filtering as other fields)
        eps_tag = 'EarningsPerShareDiluted' if taxonomy == 'us-gaap' else 'DilutedEarningsLossPerShare'
        result['eps_diluted'] = extract_entries(eps_tag)
        
        return result

    def get_quarterly_eps_from_sec(self, ticker, limit=4):
        """Get quarterly EPS from SEC data (uses direct EPS field when available)."""
        data = self.extract_quarterly_data(ticker, limit)
        if not data:
            return None
        
        results = []
        for ni in data['net_income']:
            # Try to get direct EPS from SEC
            eps = None
            for e in data.get('eps_diluted', []):
                if e['period_end'] == ni['period_end']:
                    eps = e['val']
                    break
            
            # Fallback to calculated EPS if direct EPS not available
            if eps is None:
                shares = None
                for s in data['shares_outstanding']:
                    if s['period_end'] == ni['period_end']:
                        shares = s['val']
                        break
                
                if shares and shares > 0 and ni['val'] is not None:
                    eps = ni['val'] / shares
            
            results.append({
                'period_end': ni['period_end'],
                'fy': ni['fy'],
                'form': ni['form'],
                'net_income': ni['val'],
                'shares': None,
                'eps_calculated': eps,
                'revenue': None,
                'eps_source': 'direct' if any(e['period_end'] == ni['period_end'] for e in data.get('eps_diluted', [])) else 'calculated',
            })
        
        # Add revenue to matching periods
        for rev in data['revenue']:
            for r in results:
                if r['period_end'] == rev['period_end']:
                    r['revenue'] = rev['val']
                    break
        
        return results
