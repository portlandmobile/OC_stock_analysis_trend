import sqlite3
import pandas as pd
DB_PATH = "data/finviz_screeners.db"
conn = sqlite3.connect(DB_PATH)
query = f"SELECT ticker, Company, Industry, PE FROM screener_stocks WHERE screener_name = ?"
df = pd.read_sql_query(query, conn, params=("dividend and new low",))
print(df)
conn.close()
