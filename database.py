import os
import sqlite3
import json
import pandas as pd
import io
import time
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

    def _add_metadata_columns_if_missing(self, conn):
        """Add pe_ratio, sector, industry to existing tables (no-op if already present)."""
        for col, typ in [("pe_ratio", "REAL"), ("sector", "TEXT"), ("industry", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE price_cache ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass  # column already exists

    def _create_table(self):
        with sqlite3.connect(self.db_path, timeout=15) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_cache (
                    ticker TEXT PRIMARY KEY,
                    data TEXT,
                    cached_at TIMESTAMP,
                    pe_ratio REAL,
                    sector TEXT,
                    industry TEXT
                )
            """)
            self._add_metadata_columns_if_missing(conn)

    def get(self, ticker, days=1):
        for _ in range(3):
            try:
                with sqlite3.connect(self.db_path, timeout=15) as conn:
                    cursor = conn.execute(
                        "SELECT data, cached_at FROM price_cache WHERE ticker = ?", (ticker,)
                    )
                    row = cursor.fetchone()
                    if row:
                        data, cached_at = row
                        if datetime.fromisoformat(cached_at) > datetime.now() - timedelta(days=days):
                            return pd.read_json(io.StringIO(data))
                break
            except sqlite3.OperationalError as e:
                if "unable to open database file" in str(e):
                    time.sleep(0.5)
                    continue
                print(f"DEBUG: sqlite3.OperationalError in get for {ticker}: {e} (path: {self.db_path})")
                raise
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                # Corrupt cache or incompatible format — treat as miss
                print(f"DEBUG: Price cache read failed for {ticker}: {e}")
                break
        return None

    def get_metadata(self, ticker, days=1):
        """Return dict with pe_ratio, sector, industry or None if missing/expired."""
        try:
            with sqlite3.connect(self.db_path, timeout=15) as conn:
                cursor = conn.execute(
                    "SELECT pe_ratio, sector, industry, cached_at FROM price_cache WHERE ticker = ?",
                    (ticker,),
                )
                row = cursor.fetchone()
                if row:
                    pe_ratio, sector, industry, cached_at = row
                    if datetime.fromisoformat(cached_at) > datetime.now() - timedelta(days=days):
                        return {
                            "pe_ratio": pe_ratio,
                            "sector": sector,
                            "industry": industry,
                        }
        except (sqlite3.OperationalError, ValueError, TypeError):
            pass
        return None

    def store(self, ticker, df, metadata=None):
        if df is None or df.empty:
            return
        cached_at = datetime.now().isoformat()
        pe_ratio = None
        sector = None
        industry = None
        if metadata:
            pe_ratio = metadata.get("pe_ratio")
            sector = metadata.get("sector")
            industry = metadata.get("industry")
        for _ in range(3):
            try:
                with sqlite3.connect(self.db_path, timeout=15) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO price_cache
                        (ticker, data, cached_at, pe_ratio, sector, industry)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (ticker, df.to_json(), cached_at, pe_ratio, sector, industry))
                break
            except sqlite3.OperationalError as e:
                if "unable to open database file" in str(e):
                    time.sleep(0.5)
                    continue
                raise

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
