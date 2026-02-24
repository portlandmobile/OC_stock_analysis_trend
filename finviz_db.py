"""
SQLite layer for FinViz screener results.
Stores (screener_name, ticker, updated_at) with 1-day TTL.
"""
import os
import sqlite3
import time
from datetime import datetime, timedelta

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(SKILL_DIR, "data", "finviz_screeners.db")
TTL_DAYS = 1


def _ensure_db_dir(db_path):
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


class ScreenerCache:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = db_path
        self.ttl_days = TTL_DAYS
        _ensure_db_dir(db_path)
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db_path, timeout=15) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screener_stocks (
                    screener_name TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    Company TEXT,
                    Sector TEXT,
                    Industry TEXT,
                    Country TEXT,
                    PE TEXT,
                    MarketCap TEXT,
                    PRIMARY KEY (screener_name, ticker)
                )
            """)
            self._add_columns_if_missing(conn)

    def _add_columns_if_missing(self, conn):
        """Add Company, Sector, Industry, Country, PE, MarketCap to existing tables."""
        for col in ["Company", "Sector", "Industry", "Country", "PE", "MarketCap"]:
            try:
                conn.execute(f"ALTER TABLE screener_stocks ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass

    def is_fresh(self, screener_name):
        """Return True if screener has data and updated_at is within TTL."""
        try:
            with sqlite3.connect(self.db_path, timeout=15) as conn:
                cursor = conn.execute(
                    "SELECT updated_at FROM screener_stocks WHERE screener_name = ? LIMIT 1",
                    (screener_name,),
                )
                row = cursor.fetchone()
                if not row:
                    return False
                updated_at = datetime.fromisoformat(row[0])
                return updated_at > datetime.now() - timedelta(days=self.ttl_days)
        except (sqlite3.OperationalError, ValueError, TypeError) as e:
            print(f"DEBUG: ScreenerCache is_fresh failed for {screener_name}: {e}")
            return False

    def get_tickers(self, screener_name):
        """
        Return list of tickers for screener_name if data is within TTL.
        Otherwise return None (stale or missing).
        """
        try:
            with sqlite3.connect(self.db_path, timeout=15) as conn:
                cursor = conn.execute(
                    "SELECT ticker, updated_at FROM screener_stocks WHERE screener_name = ?",
                    (screener_name,),
                )
                rows = cursor.fetchall()
                if not rows:
                    return None
                # All rows share same updated_at; check TTL using first row
                updated_at = datetime.fromisoformat(rows[0][1])
                if updated_at <= datetime.now() - timedelta(days=self.ttl_days):
                    return None
                return [r[0] for r in rows]
        except (sqlite3.OperationalError, ValueError, TypeError) as e:
            print(f"DEBUG: ScreenerCache get_tickers failed for {screener_name}: {e}")
            return None

    def get_tickers_for_date(self, screener_name, on_date):
        """
        Return list of tickers where updated_at date equals on_date.
        on_date: str "YYYY-MM-DD".
        screener_name: specific name, or "all" for distinct tickers from any screener.
        """
        try:
            with sqlite3.connect(self.db_path, timeout=15) as conn:
                if screener_name.strip().lower() == "all":
                    cursor = conn.execute(
                        "SELECT DISTINCT ticker FROM screener_stocks WHERE date(updated_at) = ?",
                        (on_date,),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT ticker FROM screener_stocks WHERE screener_name = ? AND date(updated_at) = ?",
                        (screener_name, on_date),
                    )
                return [r[0] for r in cursor.fetchall()]
        except (sqlite3.OperationalError, ValueError, TypeError) as e:
            print(f"DEBUG: ScreenerCache get_tickers_for_date failed: {e}")
            return []

    def store(self, screener_name, rows):
        """
        Replace all rows for this screener.
        rows: list of dicts, each with 'ticker' and optionally Company, Sector, Industry, Country, PE, MarketCap.
        """
        if not rows:
            return
        updated_at = datetime.now().isoformat()
        cols = ["screener_name", "ticker", "updated_at", "Company", "Sector", "Industry", "Country", "PE", "MarketCap"]
        placeholders = ", ".join("?" * len(cols))
        for _ in range(3):
            try:
                with sqlite3.connect(self.db_path, timeout=15) as conn:
                    conn.execute(
                        "DELETE FROM screener_stocks WHERE screener_name = ?",
                        (screener_name,),
                    )
                    for r in rows:
                        ticker = r.get("ticker") or r.get("Ticker")
                        if not ticker:
                            continue
                        vals = (
                            screener_name,
                            str(ticker).strip(),
                            updated_at,
                            r.get("Company"),
                            r.get("Sector"),
                            r.get("Industry"),
                            r.get("Country"),
                            r.get("PE"),
                            r.get("MarketCap"),
                        )
                        conn.execute(
                            f"INSERT INTO screener_stocks ({', '.join(cols)}) VALUES ({placeholders})",
                            vals,
                        )
                break
            except sqlite3.OperationalError as e:
                if "unable to open database file" in str(e):
                    time.sleep(0.5)
                    continue
                raise
