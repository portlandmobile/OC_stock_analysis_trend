#!/bin/bash
cd /home/openclaw/.openclaw/skills/OC_stock_analysis_trend
python3 finviz_sync.py --screener "dividend and new low" --url "https://finviz.com/screener.ashx?v=111&f=fa_div_pos,fa_salesqoq_o5,geo_usa,ta_highlow52w_a0to5h&o=pe" --force-refresh