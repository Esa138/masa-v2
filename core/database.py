"""
MASA V2 — Database Layer
SQLite for signal tracking and performance measurement.
"""

import sqlite3
import os

DB_FILE = "masa_v2.db"
SEED_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "masa_v2_seed.db")


def _ensure_db():
    """Copy seed if no DB exists. Never overwrite — preserve new signals."""
    if not os.path.exists(SEED_FILE):
        return
    if not os.path.exists(DB_FILE):
        import shutil
        shutil.copy2(SEED_FILE, DB_FILE)


def init_database():
    """Create tables if they don't exist."""
    _ensure_db()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_logged TEXT NOT NULL,
                ticker TEXT NOT NULL,
                company TEXT,
                sector TEXT,
                decision TEXT NOT NULL,
                accum_level TEXT,
                accum_days INTEGER DEFAULT 0,
                location TEXT,
                cmf REAL DEFAULT 0,
                entry_price REAL DEFAULT 0,
                stop_loss REAL DEFAULT 0,
                target REAL DEFAULT 0,
                rr_ratio REAL DEFAULT 0,
                reasons_for TEXT,
                reasons_against TEXT,
                -- Outcomes (filled later)
                price_5d REAL,
                price_10d REAL,
                price_20d REAL,
                return_5d REAL,
                return_10d REAL,
                return_20d REAL,
                outcome_5d TEXT,
                outcome_10d TEXT,
                outcome_20d TEXT,
                last_updated TEXT,
                UNIQUE(date_logged, ticker, decision)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                total_signals INTEGER DEFAULT 0,
                wins_5d INTEGER DEFAULT 0,
                wins_10d INTEGER DEFAULT 0,
                wins_20d INTEGER DEFAULT 0,
                total_completed INTEGER DEFAULT 0,
                win_rate_10d REAL DEFAULT 0,
                UNIQUE(date, signal_type)
            )
        """)


def compute_signal_quality(signal: dict) -> int:
    """
    Compute signal quality score 0-100 based on:
    - flow_bias (0-25 pts)
    - CDV trend (0-20 pts)
    - divergence (0-20 pts)
    - location (0-20 pts)
    - RSI zone (0-15 pts)
    """
    score = 0

    # Flow bias (0-25)
    flow = abs(signal.get("flow_bias", 0))
    if flow >= 40:
        score += 25
    elif flow >= 25:
        score += 20
    elif flow >= 15:
        score += 15
    elif flow >= 5:
        score += 8

    # CDV trend (0-20)
    cdv = signal.get("cdv_trend", "")
    if cdv == "rising":
        score += 20
    elif cdv == "flat":
        score += 10
    # falling = 0

    # Divergence (0-20)
    div = abs(signal.get("divergence", 0))
    if div >= 30:
        score += 20
    elif div >= 20:
        score += 15
    elif div >= 10:
        score += 8

    # Location (0-20)
    loc = signal.get("location", "")
    if loc in ("bottom", "support"):
        score += 20
    elif loc == "middle":
        score += 10
    elif loc in ("resistance", "above"):
        score += 5

    # RSI zone (0-15)
    rsi = signal.get("rsi", 50)
    if 30 <= rsi <= 50:
        score += 15  # ideal buying zone
    elif 25 <= rsi < 30 or 50 < rsi <= 60:
        score += 10
    elif rsi < 25:
        score += 5  # oversold — risky
    # overbought = 0

    return min(score, 100)


def _get_platform_tag():
    """Detect if running on V3-TEST or V2."""
    try:
        import streamlit as st
        # Check if V3-TEST badge exists in session or app title
        app_url = os.environ.get("STREAMLIT_SERVER_ADDRESS", "")
        if "v3-test" in app_url or "v3-test" in os.environ.get("HOSTNAME", ""):
            return "V3"
    except Exception:
        pass
    # Check git branch
    try:
        import subprocess
        branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
        if "v3" in branch:
            return "V3"
    except Exception:
        pass
    # Check for V3-TEST marker file or env
    if os.path.exists(".v3_test_marker"):
        return "V3"
    return "V2"


def log_signal(signal: dict) -> bool:
    """Log a signal to the database with quality score + platform tag."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # Add new columns if not exists
            for col, typ in [("quality_score", "INTEGER DEFAULT 0"), ("platform", "TEXT DEFAULT 'V2'")]:
                try:
                    conn.execute(f"ALTER TABLE signals ADD COLUMN {col} {typ}")
                except Exception:
                    pass

            quality = compute_signal_quality(signal)
            platform = signal.get("platform", _get_platform_tag())

            conn.execute("""
                INSERT OR IGNORE INTO signals
                (date_logged, ticker, company, sector, decision,
                 accum_level, accum_days, location, cmf,
                 entry_price, stop_loss, target, rr_ratio,
                 reasons_for, reasons_against, quality_score, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.get("date_logged", ""),
                signal.get("ticker", ""),
                signal.get("company", ""),
                signal.get("sector", ""),
                signal.get("decision", ""),
                signal.get("accum_level", ""),
                signal.get("accum_days", 0),
                signal.get("location", ""),
                signal.get("cmf", 0),
                signal.get("entry_price", 0),
                signal.get("stop_loss", 0),
                signal.get("target", 0),
                signal.get("rr_ratio", 0),
                "|".join(signal.get("reasons_for", [])),
                "|".join(signal.get("reasons_against", [])),
                quality,
                platform,
            ))
            return True
    except Exception:
        return False


def get_signals(limit: int = 200) -> list:
    """Get recent signals."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM signals ORDER BY date_logged DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def get_win_rates() -> dict:
    """
    Compute actual win rates per decision type.
    This is THE source of truth for the platform.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT decision, accum_level,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome_10d = 'win' THEN 1 ELSE 0 END) as wins,
                    COUNT(outcome_10d) as completed
                FROM signals
                WHERE outcome_10d IS NOT NULL
                GROUP BY decision, accum_level
            """).fetchall()

            result = {}
            for r in rows:
                key = f"{r['decision']}_{r['accum_level']}"
                completed = r["completed"]
                wins = r["wins"]
                result[key] = {
                    "total": r["total"],
                    "completed": completed,
                    "wins": wins,
                    "win_rate": round(wins / completed * 100, 1) if completed > 0 else 0,
                }
            return result
    except Exception:
        return {}


def get_total_performance() -> dict:
    """Get overall platform performance summary."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN decision = 'enter' THEN 1 ELSE 0 END) as enter_count,
                    SUM(CASE WHEN decision = 'enter' AND outcome_10d = 'win' THEN 1 ELSE 0 END) as enter_wins,
                    SUM(CASE WHEN decision = 'enter' AND outcome_10d IS NOT NULL THEN 1 ELSE 0 END) as enter_completed,
                    AVG(CASE WHEN decision = 'enter' AND return_10d IS NOT NULL THEN return_10d END) as avg_return,
                    SUM(CASE WHEN decision = 'enter' AND outcome_5d = 'win' THEN 1 ELSE 0 END) as wins_5d,
                    SUM(CASE WHEN decision = 'enter' AND outcome_5d IS NOT NULL THEN 1 ELSE 0 END) as completed_5d,
                    AVG(CASE WHEN decision = 'enter' AND return_5d IS NOT NULL THEN return_5d END) as avg_return_5d
                FROM signals
            """).fetchone()

            if row is None:
                return {"total": 0, "enter_count": 0, "win_rate": 0, "avg_return": 0}

            completed = row["enter_completed"] or 0
            wins = row["enter_wins"] or 0
            completed_5d = row["completed_5d"] or 0
            wins_5d = row["wins_5d"] or 0

            return {
                "total": row["total"] or 0,
                "enter_count": row["enter_count"] or 0,
                "enter_completed": completed,
                "enter_wins": wins,
                "win_rate": round(wins / completed * 100, 1) if completed > 0 else 0,
                "avg_return": round(row["avg_return"] or 0, 2),
                "completed_5d": completed_5d,
                "wins_5d": wins_5d,
                "win_rate_5d": round(wins_5d / completed_5d * 100, 1) if completed_5d > 0 else 0,
                "avg_return_5d": round(row["avg_return_5d"] or 0, 2),
            }
    except Exception:
        return {"total": 0, "enter_count": 0, "win_rate": 0, "avg_return": 0}
