import sqlite3
from datetime import datetime

db_path = "/Users/peekay/.openclaw/skills/OC_stock_analysis_trend/data/finviz_screeners.db"
conn = sqlite3.connect(db_path)
cursor = conn.execute("SELECT screener_name, updated_at FROM screener_stocks")
for row in cursor.fetchall():
    print(f"{row[0]} - {row[1]}")
conn.close()
