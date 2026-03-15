"""
MASA V2 — Database Layer
SQLite for signal tracking and performance measurement.
"""

import sqlite3
import os

DB_FILE = "masa_v2.db"


def init_database():
    """Create tables if they don't exist."""
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


def log_signal(signal: dict) -> bool:
    """Log a signal to the database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO signals
                (date_logged, ticker, company, sector, decision,
                 accum_level, accum_days, location, cmf,
                 entry_price, stop_loss, target, rr_ratio,
                 reasons_for, reasons_against)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
