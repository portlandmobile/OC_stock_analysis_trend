class FormulaEngine:
    def __init__(self, facts, historical_facts=None):
        self.facts = facts
        self.historical_facts = historical_facts or {}

    def evaluate_all(self):
        results = []
        results.append(self.cash_test())
        results.append(self.debt_to_equity())
        results.append(self.free_cash_flow())
        results.append(self.return_on_equity())
        results.append(self.current_ratio())
        results.append(self.operating_margin())
        results.append(self.asset_turnover())
        results.append(self.interest_coverage())
        results.append(self.earnings_stability())
        results.append(self.capital_allocation())
        return results

    def _result(self, name, status, value, target, description, provenance=None):
        return {
            "name": name,
            "status": status,
            "value": value,
            "target": target,
            "description": description,
            "provenance": provenance
        }

    def cash_test(self):
        cash = self.facts.get('cash')
        investments = self.facts.get('investments') or 0
        debt = self.facts.get('debt')
        
        if cash is None or debt is None:
            return self._result("Cash Test", "NA", None, "> 1.0", "Cash & equivalents / Total Debt")
        
        val = (cash + investments) / debt if debt > 0 else float('inf')
        status = "PASS" if val > 1.0 else "FAIL"
        return self._result("Cash Test", status, round(val, 2), "> 1.0", "Cash & equivalents / Total Debt")

    def debt_to_equity(self):
        liabilities = self.facts.get('liabilities')
        equity = self.facts.get('equity')
        
        if liabilities is None or equity is None:
            return self._result("Debt-to-Equity", "NA", None, "< 0.5", "Total Liabilities / Stockholders Equity")
        
        val = liabilities / equity if equity != 0 else float('inf')
        status = "PASS" if val < 0.5 else "FAIL"
        return self._result("Debt-to-Equity", status, round(val, 2), "< 0.5", "Total Liabilities / Stockholders Equity")

    def free_cash_flow(self):
        ocf = self.facts.get('ocf')
        capex = self.facts.get('capex')
        debt = self.facts.get('debt')
        
        if ocf is None or capex is None or debt is None:
            return self._result("Free Cash Flow Test", "NA", None, "> 0.25", "(OCF - CapEx) / Total Debt")
        
        fcf = ocf - abs(capex)
        val = fcf / debt if debt > 0 else float('inf')
        status = "PASS" if val > 0.25 else "FAIL"
        return self._result("Free Cash Flow Test", status, round(val, 2), "> 0.25", "(OCF - CapEx) / Total Debt")

    def return_on_equity(self):
        income = self.facts.get('income')
        equity = self.facts.get('equity')
        
        if income is None or equity is None:
            return self._result("Return on Equity", "NA", None, "> 15%", "Net Income / Stockholders Equity")
        
        val = income / equity if equity != 0 else 0
        status = "PASS" if val > 0.15 else "FAIL"
        return self._result("Return on Equity", status, f"{round(val*100, 1)}%", "> 15%", "Net Income / Stockholders Equity")

    def current_ratio(self):
        assets = self.facts.get('current_assets')
        liabilities = self.facts.get('current_liabilities')
        
        if assets is None or liabilities is None:
            return self._result("Current Ratio", "NA", None, "> 1.5", "Current Assets / Current Liabilities")
        
        val = assets / liabilities if liabilities != 0 else float('inf')
        status = "PASS" if val > 1.5 else "FAIL"
        return self._result("Current Ratio", status, round(val, 2), "> 1.5", "Current Assets / Current Liabilities")

    def operating_margin(self):
        oi = self.facts.get('oi')
        revenue = self.facts.get('revenue')
        
        if oi is None or revenue is None:
            return self._result("Operating Margin", "NA", None, "> 12%", "Operating Income / Revenue")
        
        val = oi / revenue if revenue != 0 else 0
        status = "PASS" if val > 0.12 else "FAIL"
        return self._result("Operating Margin", status, f"{round(val*100, 1)}%", "> 12%", "Operating Income / Revenue")

    def asset_turnover(self):
        revenue = self.facts.get('revenue')
        assets = self.facts.get('assets')
        
        if revenue is None or assets is None:
            return self._result("Asset Turnover", "NA", None, "> 0.5", "Revenue / Total Assets")
        
        val = revenue / assets if assets != 0 else 0
        status = "PASS" if val > 0.5 else "FAIL"
        return self._result("Asset Turnover", status, round(val, 2), "> 0.5", "Revenue / Total Assets")

    def interest_coverage(self):
        oi = self.facts.get('oi')
        interest = self.facts.get('interest')
        
        if oi is None:
            return self._result("Interest Coverage", "NA", None, "> 3.0", "Operating Income / Interest Expense")
        
        if interest is None or interest == 0:
            return self._result("Interest Coverage", "PASS", "No Interest", "> 3.0", "Operating Income / Interest Expense")
        
        val = oi / abs(interest)
        status = "PASS" if val > 3.0 else "FAIL"
        return self._result("Interest Coverage", status, round(val, 2), "> 3.0", "Operating Income / Interest Expense")

    def earnings_stability(self):
        history = self.historical_facts.get('NetIncomeLoss', [])
        if not history:
            return self._result("Earnings Stability", "NA", None, ">= 8/10", "Positive Net Income years (last 10)")
        
        positives = len([v for v in history[:10] if v > 0])
        status = "PASS" if positives >= 8 else "FAIL"
        return self._result("Earnings Stability", status, f"{positives}/10", ">= 8/10", "Positive Net Income years (last 10)")

    def capital_allocation(self):
        # Same as ROE for this simplified version
        res = self.return_on_equity()
        res['name'] = "Capital Allocation"
        return res
