"""
MASA QUANT — Database Abstraction Layer
Supports Supabase (cloud) with SQLite fallback (local).
"""

import os
import sqlite3
import streamlit as st

_supabase_client = None
_USE_SUPABASE = False

DB_FILE = "masa_database.db"


def _get_supabase_creds():
    """Get Supabase credentials from st.secrets or environment."""
    url = ""
    key = ""
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
    except Exception:
        pass
    if not url:
        url = os.environ.get("SUPABASE_URL", "")
    if not key:
        key = os.environ.get("SUPABASE_KEY", "")
    return url, key


def init_database():
    """Initialize database connection — Supabase if available, else SQLite."""
    global _supabase_client, _USE_SUPABASE

    url, key = _get_supabase_creds()
    if url and key:
        try:
            from supabase import create_client
            _supabase_client = create_client(url, key)
            _USE_SUPABASE = True
            return
        except Exception:
            pass

    # Fallback to SQLite
    _USE_SUPABASE = False
    _supabase_client = None
    _init_sqlite_tables()


def _init_sqlite_tables():
    """Create SQLite tables (fallback mode)."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracker (
                date_time TEXT, market TEXT, ticker TEXT, company TEXT,
                entry REAL, target REAL, stop_loss REAL, score TEXT,
                mom TEXT, date_only TEXT, timeframe TEXT DEFAULT '\u063a\u064a\u0631 \u0645\u062d\u062f\u062f'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signal_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_logged TEXT NOT NULL,
                ticker TEXT NOT NULL,
                company TEXT,
                market TEXT,
                accum_phase TEXT,
                v2_signal TEXT,
                v2_confidence INTEGER DEFAULT 0,
                accum_score REAL DEFAULT 0,
                entry_price REAL NOT NULL,
                cmf REAL DEFAULT 0,
                obv_slope REAL DEFAULT 0,
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
                UNIQUE(date_logged, ticker, v2_signal)
            )
        """)
        conn.commit()


def is_cloud():
    """Check if using Supabase (cloud) or SQLite (local)."""
    return _USE_SUPABASE


# ═══════════════════════════════════════════════════════
# CRUD Operations
# ═══════════════════════════════════════════════════════

def db_insert(table: str, data: dict) -> bool:
    """Insert a row. Returns True on success."""
    if _USE_SUPABASE and _supabase_client:
        try:
            _supabase_client.table(table).insert(data).execute()
            return True
        except Exception:
            return False
    else:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute(
                    f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})",
                    list(data.values()),
                )
                conn.commit()
            return True
        except Exception:
            return False


def db_upsert(table: str, data: dict) -> bool:
    """Insert or update a row. Returns True on success."""
    if _USE_SUPABASE and _supabase_client:
        try:
            _supabase_client.table(table).upsert(data).execute()
            return True
        except Exception:
            return False
    else:
        return db_insert(table, data)


def db_select(table: str, filters: dict = None, order_by: str = None,
              limit: int = None, columns: str = "*") -> list:
    """Select rows. Returns list of dicts."""
    if _USE_SUPABASE and _supabase_client:
        try:
            query = _supabase_client.table(table).select(columns)
            if filters:
                for k, v in filters.items():
                    query = query.eq(k, v)
            if order_by:
                desc = order_by.startswith("-")
                col = order_by.lstrip("-")
                query = query.order(col, desc=desc)
            if limit:
                query = query.limit(limit)
            result = query.execute()
            return result.data if result.data else []
        except Exception:
            return []
    else:
        try:
            where_clause = ""
            values = []
            if filters:
                conditions = [f"{k} = ?" for k in filters.keys()]
                where_clause = " WHERE " + " AND ".join(conditions)
                values = list(filters.values())

            sql = f"SELECT {columns} FROM {table}{where_clause}"
            if order_by:
                desc = order_by.startswith("-")
                col = order_by.lstrip("-")
                sql += f" ORDER BY {col} {'DESC' if desc else 'ASC'}"
            if limit:
                sql += f" LIMIT {limit}"

            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, values).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []


def db_select_where(table: str, where_sql: str, values: list = None,
                    order_by: str = None, limit: int = None) -> list:
    """Select with raw WHERE clause (SQLite) or filter chain (Supabase).
    For complex queries that need more than simple equality filters.
    Falls back to SQLite-style query for both backends.
    """
    if _USE_SUPABASE and _supabase_client:
        try:
            # Use RPC or direct query for complex filters
            query = _supabase_client.table(table).select("*")
            if order_by:
                desc = order_by.startswith("-")
                col = order_by.lstrip("-")
                query = query.order(col, desc=desc)
            if limit:
                query = query.limit(limit)
            result = query.execute()
            return result.data if result.data else []
        except Exception:
            return []
    else:
        try:
            sql = f"SELECT * FROM {table}"
            if where_sql:
                sql += f" WHERE {where_sql}"
            if order_by:
                desc = order_by.startswith("-")
                col = order_by.lstrip("-")
                sql += f" ORDER BY {col} {'DESC' if desc else 'ASC'}"
            if limit:
                sql += f" LIMIT {limit}"
            with sqlite3.connect(DB_FILE) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, values or []).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []


def db_update(table: str, filters: dict, data: dict) -> bool:
    """Update rows matching filters. Returns True on success."""
    if _USE_SUPABASE and _supabase_client:
        try:
            query = _supabase_client.table(table).update(data)
            for k, v in filters.items():
                query = query.eq(k, v)
            query.execute()
            return True
        except Exception:
            return False
    else:
        try:
            set_clause = ", ".join(f"{k} = ?" for k in data.keys())
            where_clause = " AND ".join(f"{k} = ?" for k in filters.keys())
            values = list(data.values()) + list(filters.values())
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute(
                    f"UPDATE {table} SET {set_clause} WHERE {where_clause}",
                    values,
                )
                conn.commit()
            return True
        except Exception:
            return False


def db_delete(table: str, filters: dict = None) -> bool:
    """Delete rows (all if no filters). Returns True on success."""
    if _USE_SUPABASE and _supabase_client:
        try:
            if filters:
                query = _supabase_client.table(table).delete()
                for k, v in filters.items():
                    query = query.eq(k, v)
                query.execute()
            else:
                # Delete all — Supabase needs at least one filter
                _supabase_client.table(table).delete().neq("id", -999).execute()
            return True
        except Exception:
            return False
    else:
        try:
            with sqlite3.connect(DB_FILE) as conn:
                if filters:
                    where_clause = " AND ".join(f"{k} = ?" for k in filters.keys())
                    conn.execute(f"DELETE FROM {table} WHERE {where_clause}",
                                 list(filters.values()))
                else:
                    conn.execute(f"DELETE FROM {table}")
                conn.commit()
            return True
        except Exception:
            return False


def db_count(table: str, filters: dict = None) -> int:
    """Count rows in table."""
    if _USE_SUPABASE and _supabase_client:
        try:
            query = _supabase_client.table(table).select("*", count="exact")
            if filters:
                for k, v in filters.items():
                    query = query.eq(k, v)
            result = query.execute()
            return result.count if result.count is not None else 0
        except Exception:
            return 0
    else:
        try:
            where_clause = ""
            values = []
            if filters:
                conditions = [f"{k} = ?" for k in filters.keys()]
                where_clause = " WHERE " + " AND ".join(conditions)
                values = list(filters.values())
            with sqlite3.connect(DB_FILE) as conn:
                row = conn.execute(
                    f"SELECT COUNT(*) FROM {table}{where_clause}", values
                ).fetchone()
                return row[0] if row else 0
        except Exception:
            return 0
