"""
MASA V2 — Institutional Ownership Data
Fetches real foreign ownership data from Saudi Exchange (Tadawul).

Sources (in priority order):
1. Argaam API — per-stock foreign ownership %
2. Local cache (SQLite) — avoids repeated fetches
3. Manual CSV import — for offline use

Honest approach:
- If we have ownership data → use it
- If we don't → say "no institutional data available"
- NEVER fabricate institutional labels without real data
"""

import sqlite3
import csv
import os
import json
import datetime
import requests
import time
from typing import Optional

DB_FILE = "masa_v2.db"

# ── Cache TTL ────────────────────────────────────────────────
CACHE_HOURS = 12  # Ownership data updates once daily after market close


def init_institutional_tables():
    """Create institutional data tables if they don't exist."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ownership (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                foreign_pct REAL DEFAULT 0,
                foreign_limit REAL DEFAULT 0,
                foreign_change_pct REAL DEFAULT 0,
                source TEXT DEFAULT '',
                last_updated TEXT,
                UNIQUE(ticker, date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ownership_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                foreign_pct REAL DEFAULT 0,
                source TEXT DEFAULT '',
                UNIQUE(ticker, date)
            )
        """)


# ══════════════════════════════════════════════════════════════
# CACHE LAYER
# ══════════════════════════════════════════════════════════════

def _get_cached(ticker: str) -> Optional[dict]:
    """Get cached ownership data if fresh enough."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM ownership
                WHERE ticker = ?
                ORDER BY date DESC LIMIT 1
            """, (ticker,)).fetchone()

            if row is None:
                return None

            # Check freshness
            last_updated = row["last_updated"]
            if last_updated:
                updated_dt = datetime.datetime.fromisoformat(last_updated)
                age_hours = (datetime.datetime.now() - updated_dt).total_seconds() / 3600
                if age_hours > CACHE_HOURS:
                    return None  # Stale cache

            return dict(row)
    except Exception:
        return None


def _save_to_cache(ticker: str, data: dict):
    """Save ownership data to cache."""
    try:
        now = datetime.datetime.now().isoformat()
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ownership
                (ticker, date, foreign_pct, foreign_limit, foreign_change_pct, source, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                today,
                data.get("foreign_pct", 0),
                data.get("foreign_limit", 0),
                data.get("foreign_change_pct", 0),
                data.get("source", ""),
                now,
            ))

            # Also save to history
            conn.execute("""
                INSERT OR IGNORE INTO ownership_history
                (ticker, date, foreign_pct, source)
                VALUES (?, ?, ?, ?)
            """, (
                ticker,
                today,
                data.get("foreign_pct", 0),
                data.get("source", ""),
            ))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# DATA FETCHERS
# ══════════════════════════════════════════════════════════════

# Track if Argaam API is reachable this session
_argaam_available = None


def _fetch_from_argaam(ticker: str) -> Optional[dict]:
    """
    Try to fetch foreign ownership from Argaam.
    Quick timeout — if API is unreachable, skip immediately for all tickers.
    """
    global _argaam_available

    # If we already know Argaam is down, don't retry
    if _argaam_available is False:
        return None

    try:
        symbol = ticker.replace(".SR", "")
        url = f"https://www.argaam.com/api/v1/json/ir-api/overview/{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
            "Referer": "https://www.argaam.com/",
        }

        resp = requests.get(url, headers=headers, timeout=3)

        if resp.status_code == 200:
            data = resp.json()
            foreign_pct = data.get("foreignOwnership", 0)
            foreign_limit = data.get("foreignOwnershipLimit", 49)

            if foreign_pct is not None:
                _argaam_available = True
                return {
                    "foreign_pct": float(foreign_pct),
                    "foreign_limit": float(foreign_limit or 49),
                    "foreign_change_pct": 0,
                    "source": "argaam",
                }

        # Non-200 response — mark as unavailable
        _argaam_available = False
    except Exception:
        _argaam_available = False

    return None


def _fetch_from_rapidapi(ticker: str, api_key: str) -> Optional[dict]:
    """
    Fetch from RapidAPI Saudi Exchange endpoint.
    Requires RAPIDAPI_KEY environment variable.
    """
    try:
        symbol = ticker.replace(".SR", "")
        url = f"https://saudi-exchange-stocks-tadawul.p.rapidapi.com/api/stocks/{symbol}"
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "saudi-exchange-stocks-tadawul.p.rapidapi.com",
        }

        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            foreign_pct = data.get("foreignOwnership", data.get("foreign_ownership_pct", 0))
            if foreign_pct is not None:
                return {
                    "foreign_pct": float(foreign_pct),
                    "foreign_limit": float(data.get("foreignOwnershipLimit", 49)),
                    "foreign_change_pct": 0,
                    "source": "rapidapi",
                }
    except Exception:
        pass

    return None


# ══════════════════════════════════════════════════════════════
# CSV IMPORT
# ══════════════════════════════════════════════════════════════

def import_from_csv(csv_path: str) -> int:
    """
    Import ownership data from a CSV file.

    Expected CSV format:
    ticker,foreign_pct,foreign_limit
    2222.SR,5.2,49
    1120.SR,12.3,49
    ...

    Returns count of imported rows.
    """
    if not os.path.exists(csv_path):
        return 0

    count = 0
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = row.get("ticker", "")
                if not ticker:
                    continue

                data = {
                    "foreign_pct": float(row.get("foreign_pct", 0)),
                    "foreign_limit": float(row.get("foreign_limit", 49)),
                    "foreign_change_pct": float(row.get("foreign_change_pct", 0)),
                    "source": "csv",
                }
                _save_to_cache(ticker, data)
                count += 1
    except Exception:
        pass

    return count


# ══════════════════════════════════════════════════════════════
# MAIN PUBLIC API
# ══════════════════════════════════════════════════════════════

def get_ownership(ticker: str) -> Optional[dict]:
    """
    Get foreign ownership data for a single ticker.

    Returns dict with:
        - foreign_pct: float (e.g., 5.2 means 5.2%)
        - foreign_limit: float (max allowed, usually 49%)
        - foreign_change_pct: float (change from previous reading)
        - source: str (where the data came from)
        - available: bool (True if we have real data)

    Returns None if no data available.
    Honest: returns None rather than guessing.
    """
    init_institutional_tables()

    # 1. Check cache first
    cached = _get_cached(ticker)
    if cached:
        return {
            "foreign_pct": cached["foreign_pct"],
            "foreign_limit": cached["foreign_limit"],
            "foreign_change_pct": cached["foreign_change_pct"],
            "source": cached["source"],
            "available": True,
        }

    # 2. Try Argaam
    data = _fetch_from_argaam(ticker)
    if data:
        _save_to_cache(ticker, data)
        return {**data, "available": True}

    # 3. Try RapidAPI (if key available)
    api_key = os.environ.get("RAPIDAPI_KEY", "")
    if api_key:
        data = _fetch_from_rapidapi(ticker, api_key)
        if data:
            _save_to_cache(ticker, data)
            return {**data, "available": True}

    # 4. No data — be honest about it
    return None


def get_ownership_batch(tickers: list, delay: float = 0.1) -> dict:
    """
    Get ownership data for multiple tickers.
    Smart: tests first ticker, if API is down skips all remote fetches.

    Returns: dict of {ticker: ownership_data or None}
    """
    global _argaam_available
    init_institutional_tables()
    results = {}

    # Quick probe: try first ticker to check if API is reachable
    if tickers and _argaam_available is None:
        first = get_ownership(tickers[0])
        results[tickers[0]] = first
        # If Argaam failed on first attempt, it's flagged — rest will skip

    for tk in tickers:
        if tk in results:
            continue  # Already fetched
        results[tk] = get_ownership(tk)
        # Small delay only if we're actually hitting an API
        if _argaam_available is True:
            time.sleep(delay)

    return results


def compute_ownership_change(ticker: str) -> float:
    """
    Compute the change in foreign ownership over the last available readings.
    Requires at least 2 data points in ownership_history.

    Returns: change in percentage points (e.g., +0.5 means 0.5% increase)
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT foreign_pct FROM ownership_history
                WHERE ticker = ?
                ORDER BY date DESC LIMIT 2
            """, (ticker,)).fetchall()

            if len(rows) < 2:
                return 0.0

            current = rows[0]["foreign_pct"]
            previous = rows[1]["foreign_pct"]
            return round(current - previous, 3)
    except Exception:
        return 0.0


def get_ownership_summary(tickers: list) -> dict:
    """
    Get a summary of institutional data availability.
    Useful for the UI to show data coverage.
    """
    init_institutional_tables()

    try:
        with sqlite3.connect(DB_FILE) as conn:
            total = len(tickers)
            count = conn.execute("""
                SELECT COUNT(DISTINCT ticker) FROM ownership
            """).fetchone()[0]

            return {
                "total_stocks": total,
                "with_data": count,
                "coverage_pct": round(count / total * 100, 1) if total > 0 else 0,
                "last_update": _get_last_update_time(),
            }
    except Exception:
        return {
            "total_stocks": len(tickers),
            "with_data": 0,
            "coverage_pct": 0,
            "last_update": None,
        }


def _get_last_update_time() -> Optional[str]:
    """Get the most recent update timestamp."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute("""
                SELECT MAX(last_updated) FROM ownership
            """).fetchone()
            return row[0] if row else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
# INTERPRETATION — What does ownership data mean?
# ══════════════════════════════════════════════════════════════

def interpret_ownership(ownership_data: Optional[dict], phase: str) -> dict:
    """
    Combine ownership data with Order Flow phase detection.

    This is the HONEST interpretation:
    - Order Flow = "buying/selling pressure detected" (what we know)
    - Foreign ownership increasing = "institutional interest confirmed" (real data)
    - Both together = "institutional accumulation" (we can now say this honestly)

    Args:
        ownership_data: Foreign ownership dict or None
        phase: Wyckoff phase from detect_orderflow()

    Returns:
        label: str — what to call it
        confidence: str — how sure we are
        detail: str — explanation
    """
    has_accum = phase in ("accumulation", "spring", "markup")

    if ownership_data is None or not ownership_data.get("available"):
        # No institutional data — be honest
        if has_accum:
            return {
                "label": "ضغط شرائي",  # Buying pressure
                "confidence": "جزئي",  # Partial
                "detail": "أوردر فلو يشير لضغط شرائي — لكن لا نعرف من يشتري (لا بيانات ملكية)",
                "is_institutional": False,
            }
        return {
            "label": "لا يوجد تجميع",
            "confidence": "—",
            "detail": "لا ضغط شرائي ولا بيانات ملكية",
            "is_institutional": False,
        }

    foreign_pct = ownership_data.get("foreign_pct", 0)
    foreign_change = ownership_data.get("foreign_change_pct", 0)

    if has_accum and foreign_change > 0.1:
        # BOTH signals agree — this is real institutional accumulation
        return {
            "label": "تجميع مؤسساتي مؤكد",  # Confirmed institutional accumulation
            "confidence": "عالي",  # High
            "detail": (
                f"أوردر فلو إيجابي + ملكية أجانب زادت +{foreign_change:.2f}% "
                f"(الآن {foreign_pct:.1f}%) — تجميع مؤسساتي حقيقي"
            ),
            "is_institutional": True,
        }

    if has_accum and foreign_change <= 0.1 and foreign_change >= -0.1:
        # Buying pressure but no ownership change
        return {
            "label": "ضغط شرائي محلي",  # Local buying pressure
            "confidence": "متوسط",  # Medium
            "detail": (
                f"أوردر فلو إيجابي لكن ملكية الأجانب ثابتة ({foreign_pct:.1f}%) "
                f"— الشراء من محليين أو أفراد"
            ),
            "is_institutional": False,
        }

    if has_accum and foreign_change < -0.1:
        # Buying pressure but foreigners selling — contradiction
        return {
            "label": "ضغط شرائي + تصريف مؤسساتي",
            "confidence": "تحذير",  # Warning
            "detail": (
                f"أوردر فلو إيجابي لكن الأجانب يبيعون ({foreign_change:+.2f}%) "
                f"— حذر: المؤسسات تصرف"
            ),
            "is_institutional": False,
        }

    if not has_accum and foreign_change > 0.1:
        # No buying pressure but foreigners buying — early signal
        return {
            "label": "تجميع مؤسساتي مبكر",  # Early institutional
            "confidence": "مبكر",  # Early
            "detail": (
                f"لا ضغط شرائي واضح بعد، لكن الأجانب يزيدون ({foreign_change:+.2f}%) "
                f"— ممكن بداية تجميع"
            ),
            "is_institutional": True,
        }

    # Default: nothing interesting
    return {
        "label": "لا يوجد نشاط مؤسساتي",
        "confidence": "—",
        "detail": f"ملكية أجانب: {foreign_pct:.1f}% — بدون تغيير ملحوظ",
        "is_institutional": False,
    }
