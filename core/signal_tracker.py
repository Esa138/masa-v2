"""
MASA QUANT V95 — Live Signal Tracker
Records accumulation/distribution signals, tracks outcomes over 5/10/20 days,
and computes live win-rate statistics.
"""

import sqlite3
import datetime
import pandas as pd
import numpy as np
import yfinance as yf

from core.utils import DB_FILE, SAUDI_TZ, get_today_str


# ═══════════════════════════════════════════════════════
# 1. Schema Initialization
# ═══════════════════════════════════════════════════════

def init_signal_log():
    """Create signal_log table if it doesn't exist."""
    with sqlite3.connect(DB_FILE) as conn:
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


# ═══════════════════════════════════════════════════════
# 2. Auto-Log Signals from Scan
# ═══════════════════════════════════════════════════════

def log_signals_from_scan(df_ai_picks: pd.DataFrame, market_name: str) -> int:
    """
    Log accumulation/distribution signals from scan results.
    Filters for non-neutral phases and non-none v2 signals.
    Returns count of newly inserted signals.
    """
    if df_ai_picks is None or df_ai_picks.empty:
        return 0

    today = get_today_str()
    count = 0

    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            for _, row in df_ai_picks.iterrows():
                phase = str(row.get('accum_phase', 'neutral'))
                v2_signal = str(row.get('accum_v2_signal', 'none'))

                # Skip neutral/none — only track real signals
                if phase == 'neutral' and v2_signal == 'none':
                    continue

                ticker = str(row.get('الرمز', ''))
                if not ticker:
                    continue

                entry_price = float(row.get('raw_price', 0))
                if entry_price <= 0:
                    continue

                company = str(row.get('الشركة', ''))
                accum_score = float(row.get('accum_score', 0))
                v2_confidence = int(row.get('accum_v2_confidence', 0))
                cmf = float(row.get('accum_cmf', 0))
                obv_slope = float(row.get('accum_obv_slope', 0))

                # Use v2_signal if available, else use phase as signal type
                effective_signal = v2_signal if v2_signal != 'none' else f"phase_{phase}"

                try:
                    c.execute(
                        """INSERT OR IGNORE INTO signal_log
                           (date_logged, ticker, company, market, accum_phase,
                            v2_signal, v2_confidence, accum_score, entry_price,
                            cmf, obv_slope)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (today, ticker, company, market_name, phase,
                         effective_signal, v2_confidence, accum_score,
                         entry_price, cmf, obv_slope)
                    )
                    if c.rowcount > 0:
                        count += 1
                except sqlite3.IntegrityError:
                    continue

            conn.commit()
    except Exception:
        pass

    return count


# ═══════════════════════════════════════════════════════
# 3. Update Outcomes (Follow-Up Price Tracking)
# ═══════════════════════════════════════════════════════

def _trading_days_elapsed(date_logged_str: str) -> int:
    """Count approximate trading days since signal date."""
    try:
        logged = datetime.datetime.strptime(date_logged_str, "%Y-%m-%d")
        today = datetime.datetime.now(SAUDI_TZ).replace(tzinfo=None)
        count = 0
        current = logged
        while current < today:
            current += datetime.timedelta(days=1)
            if current.weekday() < 5:  # Mon-Fri
                count += 1
        return count
    except Exception:
        return 0


def _classify_outcome(v2_signal: str, ret: float) -> str:
    """
    Classify win/loss based on signal type and return.
    Buy signals: win if return > 0 (price went up)
    Sell signals: win if return < 0 (price went down = signal was correct)
    """
    is_sell = v2_signal in ('sell_confirmed', 'sell_warning', 'phase_distribute')
    if is_sell:
        return 'win' if ret < 0 else 'loss'
    else:
        return 'win' if ret > 0 else 'loss'


def _fetch_current_price(ticker: str) -> float:
    """Fetch latest close price for a ticker."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period='5d')
        if hist is not None and not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception:
        pass
    return 0.0


def update_signal_outcomes(max_signals: int = 50) -> int:
    """
    Update follow-up prices and outcomes for signals that need it.
    Returns count of signals updated.
    """
    now_str = datetime.datetime.now(SAUDI_TZ).strftime("%Y-%m-%d %H:%M")
    updated = 0

    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()

            # Get signals that still have NULL outcomes to fill
            c.execute("""
                SELECT id, date_logged, ticker, v2_signal, entry_price,
                       price_5d, price_10d, price_20d
                FROM signal_log
                WHERE (outcome_5d IS NULL OR outcome_10d IS NULL OR outcome_20d IS NULL)
                  AND entry_price > 0
                ORDER BY date_logged DESC
                LIMIT ?
            """, (max_signals,))

            rows = c.fetchall()
            if not rows:
                return 0

            # Group by ticker to minimize API calls
            ticker_prices = {}

            for row_id, date_logged, ticker, v2_signal, entry_price, p5, p10, p20 in rows:
                days = _trading_days_elapsed(date_logged)
                if days < 3:
                    continue  # Too early for any outcome

                # Fetch price if not cached
                if ticker not in ticker_prices:
                    price = _fetch_current_price(ticker)
                    if price <= 0:
                        continue
                    ticker_prices[ticker] = price

                current_price = ticker_prices[ticker]
                ret = (current_price / entry_price - 1) * 100

                updates = {}

                # 5-day outcome
                if p5 is None and days >= 5:
                    outcome = _classify_outcome(v2_signal, ret)
                    updates['price_5d'] = current_price
                    updates['return_5d'] = round(ret, 2)
                    updates['outcome_5d'] = outcome

                # 10-day outcome
                if p10 is None and days >= 10:
                    outcome = _classify_outcome(v2_signal, ret)
                    updates['price_10d'] = current_price
                    updates['return_10d'] = round(ret, 2)
                    updates['outcome_10d'] = outcome

                # 20-day outcome
                if p20 is None and days >= 20:
                    outcome = _classify_outcome(v2_signal, ret)
                    updates['price_20d'] = current_price
                    updates['return_20d'] = round(ret, 2)
                    updates['outcome_20d'] = outcome

                if updates:
                    updates['last_updated'] = now_str
                    set_clause = ', '.join(f"{k} = ?" for k in updates)
                    values = list(updates.values()) + [row_id]
                    c.execute(f"UPDATE signal_log SET {set_clause} WHERE id = ?", values)
                    updated += 1

            conn.commit()
    except Exception:
        pass

    return updated


# ═══════════════════════════════════════════════════════
# 4. Compute Statistics
# ═══════════════════════════════════════════════════════

def compute_signal_stats(
    phase_filter: str = None,
    v2_filter: str = None,
    market_filter: str = None,
) -> dict:
    """
    Compute win-rate statistics from signal log.
    Returns dict with overall, by_v2, and by_phase breakdowns.
    """
    default = {
        'total': 0, 'active': 0, 'completed': 0,
        'by_v2': {}, 'by_phase': {},
        'overall': {'win_5d': 0, 'win_10d': 0, 'win_20d': 0},
    }

    try:
        with sqlite3.connect(DB_FILE) as conn:
            query = "SELECT * FROM signal_log WHERE 1=1"
            params = []

            if phase_filter and phase_filter != "الكل":
                query += " AND accum_phase = ?"
                params.append(phase_filter)
            if v2_filter and v2_filter != "الكل":
                query += " AND v2_signal = ?"
                params.append(v2_filter)
            if market_filter and market_filter != "الكل":
                query += " AND market = ?"
                params.append(market_filter)

            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return default

        total = len(df)
        completed = int(df['outcome_20d'].notna().sum())
        active = total - completed

        stats = {
            'total': total,
            'active': active,
            'completed': completed,
            'by_v2': {},
            'by_phase': {},
            'overall': _calc_win_rates(df),
        }

        # By V2 signal type
        for sig in df['v2_signal'].unique():
            if sig and sig != 'none':
                sub = df[df['v2_signal'] == sig]
                stats['by_v2'][sig] = {
                    'count': len(sub),
                    **_calc_win_rates(sub),
                }

        # By accumulation phase
        for phase in df['accum_phase'].unique():
            if phase and phase != 'neutral':
                sub = df[df['accum_phase'] == phase]
                stats['by_phase'][phase] = {
                    'count': len(sub),
                    **_calc_win_rates(sub),
                }

        return stats

    except Exception:
        return default


def _calc_win_rates(df: pd.DataFrame) -> dict:
    """Calculate win rates for 5d/10d/20d from a DataFrame subset."""
    result = {'win_5d': 0.0, 'win_10d': 0.0, 'win_20d': 0.0,
              'n_5d': 0, 'n_10d': 0, 'n_20d': 0}

    for period in ['5d', '10d', '20d']:
        col = f'outcome_{period}'
        if col in df.columns:
            valid = df[col].dropna()
            n = len(valid)
            if n > 0:
                wins = (valid == 'win').sum()
                result[f'win_{period}'] = round(wins / n * 100, 1)
                result[f'n_{period}'] = n

    return result


# ═══════════════════════════════════════════════════════
# 5. Get Signal Log DataFrame for Display
# ═══════════════════════════════════════════════════════

# Signal display labels
_V2_LABELS = {
    'buy_confirmed': '🟢 شراء مؤكد',
    'buy_breakout': '🔵 كسر مؤكد',
    'sell_confirmed': '🔴 بيع مؤكد',
    'sell_warning': '🟠 تحذير تصريف',
    'watch': '👁️ مراقبة',
    'phase_early': '⚪ تجميع مبكر',
    'phase_mid': '🟡 تجميع متوسط',
    'phase_strong': '🔵 تجميع قوي',
    'phase_late': '🟢 نهاية تجميع',
    'phase_distribute': '🔴 تصريف',
}

_PHASE_LABELS = {
    'early': 'مبكر',
    'mid': 'متوسط',
    'strong': 'قوي',
    'late': 'نهاية',
    'distribute': 'تصريف',
}


def get_signal_log_df(
    phase_filter: str = None,
    v2_filter: str = None,
    market_filter: str = None,
    limit: int = 200,
) -> pd.DataFrame:
    """
    Fetch signal log as a display-ready DataFrame with Arabic column names.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            query = "SELECT * FROM signal_log WHERE 1=1"
            params = []

            if phase_filter and phase_filter != "الكل":
                query += " AND accum_phase = ?"
                params.append(phase_filter)
            if v2_filter and v2_filter != "الكل":
                query += " AND v2_signal = ?"
                params.append(v2_filter)
            if market_filter and market_filter != "الكل":
                query += " AND market = ?"
                params.append(market_filter)

            query += " ORDER BY date_logged DESC, accum_score DESC LIMIT ?"
            params.append(limit)

            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame()

        # Format for display
        display = pd.DataFrame()
        display['التاريخ'] = df['date_logged']
        display['الرمز'] = df['ticker']
        display['الشركة'] = df['company']
        display['المرحلة'] = df['accum_phase'].map(lambda x: _PHASE_LABELS.get(x, x))
        display['الإشارة'] = df['v2_signal'].map(lambda x: _V2_LABELS.get(x, x))
        display['السكور'] = df['accum_score'].round(0).astype(int)
        display['سعر الدخول'] = df['entry_price'].round(2)

        # Returns with formatting
        for period, label in [('5d', '5 أيام'), ('10d', '10 أيام'), ('20d', '20 يوم')]:
            ret_col = f'return_{period}'
            outcome_col = f'outcome_{period}'
            if ret_col in df.columns:
                display[label] = df.apply(
                    lambda r: (
                        f"{'✅' if r[outcome_col] == 'win' else '❌'} "
                        f"{r[ret_col]:+.1f}%"
                        if pd.notna(r[ret_col])
                        else '⏳'
                    ),
                    axis=1
                )
            else:
                display[label] = '⏳'

        return display

    except Exception:
        return pd.DataFrame()


def clear_signal_log():
    """Delete all records from signal_log table."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM signal_log")
            conn.commit()
        return True
    except Exception:
        return False


def get_ticker_signal_history(ticker: str) -> dict:
    """
    Get signal history for a specific ticker.
    Returns: {'total': 5, 'wins': 3, 'win_pct': 60.0, 'last_signal': 'sell_warning', 'last_date': '2026-03-01'}
    """
    default = {'total': 0, 'wins': 0, 'win_pct': 0, 'last_signal': '', 'last_date': ''}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT v2_signal, outcome_20d, date_logged FROM signal_log "
                "WHERE ticker = ? ORDER BY date_logged DESC",
                (ticker,)
            )
            rows = c.fetchall()
            if not rows:
                return default

            total = len(rows)
            completed = [(s, o) for s, o, _ in rows if o is not None]
            wins = sum(1 for _, o in completed if o == 'win')
            win_pct = round(wins / len(completed) * 100, 0) if completed else 0

            return {
                'total': total,
                'wins': wins,
                'completed': len(completed),
                'win_pct': win_pct,
                'last_signal': rows[0][0],
                'last_date': rows[0][2],
            }
    except Exception:
        return default


def get_distribution_summary() -> list:
    """
    Get active distribution signals for today's summary banner.
    Returns list of dicts: [{'ticker': '2222.SR', 'company': 'أرامكو', 'score': 35, 'v2_signal': 'sell_warning'}, ...]
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            # Get latest distribution signals (last 3 days to catch recent ones)
            c.execute("""
                SELECT ticker, company, accum_score, v2_signal, date_logged
                FROM signal_log
                WHERE accum_phase = 'distribute'
                  AND date_logged >= date('now', '-3 days')
                ORDER BY date_logged DESC, accum_score ASC
            """)
            rows = c.fetchall()
            # Deduplicate by ticker (keep latest)
            seen = set()
            result = []
            for tk, co, sc, v2, dt in rows:
                if tk not in seen:
                    seen.add(tk)
                    result.append({
                        'ticker': tk, 'company': co, 'score': sc,
                        'v2_signal': v2, 'date': dt,
                    })
            return result
    except Exception:
        return []


def get_signal_count() -> int:
    """Get total number of signals in the log."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            result = conn.execute("SELECT COUNT(*) FROM signal_log").fetchone()
            return result[0] if result else 0
    except Exception:
        return 0
