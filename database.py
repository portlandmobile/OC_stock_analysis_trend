import os
import sqlite3
import json
import pandas as pd
import io
from datetime import datetime, timedelta

def _ensure_db_dir(db_path):
    """Create parent directory for DB file if it doesn't exist."""
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

class PriceCache:
    def __init__(self, db_path):
        self.db_path = db_path
        _ensure_db_dir(db_path)
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db_path, timeout=15) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_cache (
                    ticker TEXT PRIMARY KEY,
                    data TEXT,
                    cached_at TIMESTAMP
                )
            """)

    def get(self, ticker, days=1):
        try:
            with sqlite3.connect(self.db_path, timeout=15) as conn:
                cursor = conn.execute("SELECT data, cached_at FROM price_cache WHERE ticker = ?", (ticker,))
                row = cursor.fetchone()
                if row:
                    data, cached_at = row
                    if datetime.fromisoformat(cached_at) > datetime.now() - timedelta(days=days):
                        return pd.read_json(io.StringIO(data))
        except sqlite3.OperationalError as e:
            print(f"DEBUG: sqlite3.OperationalError in get for {ticker}: {e} (path: {self.db_path})")
            raise
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            # Corrupt cache or incompatible format — treat as miss
            print(f"DEBUG: Price cache read failed for {ticker}: {e}")
        return None

    def store(self, ticker, df):
        if df is None or df.empty:
            return
        with sqlite3.connect(self.db_path, timeout=15) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO price_cache (ticker, data, cached_at)
                VALUES (?, ?, ?)
            """, (ticker, df.to_json(), datetime.now().isoformat()))

class SECCache:
    def __init__(self, db_path):
        self.db_path = db_path
        _ensure_db_dir(db_path)
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db_path, timeout=15) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sec_cache (
                    cik TEXT PRIMARY KEY,
                    data TEXT,
                    cached_at TIMESTAMP
                )
            """)

    def get(self, cik, days=7):
        try:
            with sqlite3.connect(self.db_path, timeout=15) as conn:
                cursor = conn.execute("SELECT data, cached_at FROM sec_cache WHERE cik = ?", (cik,))
                row = cursor.fetchone()
                if row:
                    data, cached_at = row
                    if datetime.fromisoformat(cached_at) > datetime.now() - timedelta(days=days):
                        return json.loads(data)
        except (sqlite3.OperationalError, json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"DEBUG: SEC cache read failed for CIK {cik}: {e}")
        return None

    def store(self, cik, data):
        if not data:
            return
        with sqlite3.connect(self.db_path, timeout=15) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sec_cache (cik, data, cached_at)
                VALUES (?, ?, ?)
            """, (cik, json.dumps(data), datetime.now().isoformat()))
