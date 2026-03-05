"""
MASA QUANT V95 — Live Signal Tracker
Records accumulation/distribution signals, tracks outcomes over 5/10/20 days,
and computes live win-rate statistics.
Supports Supabase (cloud) with SQLite fallback (local).
"""

import datetime
import pandas as pd
import numpy as np
import yfinance as yf

from core.database import (
    db_insert, db_select, db_select_where, db_update,
    db_delete, db_count, is_cloud,
)
from core.utils import SAUDI_TZ, get_today_str


# ═══════════════════════════════════════════════════════
# 1. Schema Initialization
# ═══════════════════════════════════════════════════════

def init_signal_log():
    """Tables are created by init_database() in core/database.py — nothing to do here."""
    pass


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

    for _, row in df_ai_picks.iterrows():
        phase = str(row.get('accum_phase', 'neutral'))
        v2_signal = str(row.get('accum_v2_signal', 'none'))

        if phase == 'neutral' and v2_signal == 'none':
            continue

        ticker = str(row.get('\u0627\u0644\u0631\u0645\u0632', ''))
        if not ticker:
            continue

        entry_price = float(row.get('raw_price', 0))
        if entry_price <= 0:
            continue

        company = str(row.get('\u0627\u0644\u0634\u0631\u0643\u0629', ''))
        accum_score = float(row.get('accum_score', 0))
        v2_confidence = int(row.get('accum_v2_confidence', 0))
        cmf = float(row.get('accum_cmf', 0))
        obv_slope = float(row.get('accum_obv_slope', 0))
        effective_signal = v2_signal if v2_signal != 'none' else f"phase_{phase}"

        # Check for duplicate
        existing = db_select("signal_log", {
            "date_logged": today,
            "ticker": ticker,
            "v2_signal": effective_signal,
        })
        if not existing:
            ok = db_insert("signal_log", {
                "date_logged": today,
                "ticker": ticker,
                "company": company,
                "market": market_name,
                "accum_phase": phase,
                "v2_signal": effective_signal,
                "v2_confidence": v2_confidence,
                "accum_score": accum_score,
                "entry_price": entry_price,
                "cmf": cmf,
                "obv_slope": obv_slope,
            })
            if ok:
                count += 1

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
            if current.weekday() < 5:
                count += 1
        return count
    except Exception:
        return 0


def _classify_outcome(v2_signal: str, ret: float) -> str:
    """Classify win/loss based on signal type and return."""
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

    # Get signals with NULL outcomes
    rows = db_select_where(
        "signal_log",
        where_sql="(outcome_5d IS NULL OR outcome_10d IS NULL OR outcome_20d IS NULL) AND entry_price > 0",
        order_by="-date_logged",
        limit=max_signals,
    )

    if not rows:
        return 0

    ticker_prices = {}

    for row in rows:
        row_id = row.get('id')
        date_logged = row.get('date_logged', '')
        ticker = row.get('ticker', '')
        v2_signal = row.get('v2_signal', '')
        entry_price = row.get('entry_price', 0)
        p5 = row.get('price_5d')
        p10 = row.get('price_10d')
        p20 = row.get('price_20d')

        days = _trading_days_elapsed(date_logged)
        if days < 3:
            continue

        if ticker not in ticker_prices:
            price = _fetch_current_price(ticker)
            if price <= 0:
                continue
            ticker_prices[ticker] = price

        current_price = ticker_prices[ticker]
        ret = (current_price / entry_price - 1) * 100

        updates = {}

        if p5 is None and days >= 5:
            outcome = _classify_outcome(v2_signal, ret)
            updates['price_5d'] = current_price
            updates['return_5d'] = round(ret, 2)
            updates['outcome_5d'] = outcome

        if p10 is None and days >= 10:
            outcome = _classify_outcome(v2_signal, ret)
            updates['price_10d'] = current_price
            updates['return_10d'] = round(ret, 2)
            updates['outcome_10d'] = outcome

        if p20 is None and days >= 20:
            outcome = _classify_outcome(v2_signal, ret)
            updates['price_20d'] = current_price
            updates['return_20d'] = round(ret, 2)
            updates['outcome_20d'] = outcome

        if updates:
            updates['last_updated'] = now_str
            if row_id:
                db_update("signal_log", {"id": row_id}, updates)
                updated += 1

    return updated


# ═══════════════════════════════════════════════════════
# 4. Compute Statistics
# ═══════════════════════════════════════════════════════

def compute_signal_stats(
    phase_filter: str = None,
    v2_filter: str = None,
    market_filter: str = None,
) -> dict:
    """Compute win-rate statistics from signal log."""
    default = {
        'total': 0, 'active': 0, 'completed': 0,
        'by_v2': {}, 'by_phase': {},
        'overall': {'win_5d': 0, 'win_10d': 0, 'win_20d': 0},
    }

    try:
        filters = {}
        if phase_filter and phase_filter != "\u0627\u0644\u0643\u0644":
            filters["accum_phase"] = phase_filter
        if v2_filter and v2_filter != "\u0627\u0644\u0643\u0644":
            filters["v2_signal"] = v2_filter
        if market_filter and market_filter != "\u0627\u0644\u0643\u0644":
            filters["market"] = market_filter

        rows = db_select("signal_log", filters if filters else None)
        if not rows:
            return default

        df = pd.DataFrame(rows)
        if df.empty:
            return default

        total = len(df)
        completed = int(df['outcome_20d'].notna().sum()) if 'outcome_20d' in df.columns else 0
        active = total - completed

        stats = {
            'total': total,
            'active': active,
            'completed': completed,
            'by_v2': {},
            'by_phase': {},
            'overall': _calc_win_rates(df),
        }

        for sig in df['v2_signal'].unique():
            if sig and sig != 'none':
                sub = df[df['v2_signal'] == sig]
                stats['by_v2'][sig] = {'count': len(sub), **_calc_win_rates(sub)}

        for phase in df['accum_phase'].unique():
            if phase and phase != 'neutral':
                sub = df[df['accum_phase'] == phase]
                stats['by_phase'][phase] = {'count': len(sub), **_calc_win_rates(sub)}

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

_V2_LABELS = {
    'buy_confirmed': '\U0001f7e2 شراء مؤكد',
    'buy_breakout': '\U0001f535 كسر مؤكد',
    'sell_confirmed': '\U0001f534 بيع مؤكد',
    'sell_warning': '\U0001f7e0 تحذير تصريف',
    'watch': '\U0001f441\ufe0f مراقبة',
    'phase_early': '\u26aa تجميع مبكر',
    'phase_mid': '\U0001f7e1 تجميع متوسط',
    'phase_strong': '\U0001f535 تجميع قوي',
    'phase_late': '\U0001f7e2 نهاية تجميع',
    'phase_distribute': '\U0001f534 تصريف',
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
    """Fetch signal log as a display-ready DataFrame with Arabic column names."""
    try:
        filters = {}
        if phase_filter and phase_filter != "\u0627\u0644\u0643\u0644":
            filters["accum_phase"] = phase_filter
        if v2_filter and v2_filter != "\u0627\u0644\u0643\u0644":
            filters["v2_signal"] = v2_filter
        if market_filter and market_filter != "\u0627\u0644\u0643\u0644":
            filters["market"] = market_filter

        rows = db_select(
            "signal_log",
            filters if filters else None,
            order_by="-date_logged",
            limit=limit,
        )

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame()

        display = pd.DataFrame()
        display['\u0627\u0644\u062a\u0627\u0631\u064a\u062e'] = df['date_logged']
        display['\u0627\u0644\u0631\u0645\u0632'] = df['ticker']
        display['\u0627\u0644\u0634\u0631\u0643\u0629'] = df['company']
        display['\u0627\u0644\u0645\u0631\u062d\u0644\u0629'] = df['accum_phase'].map(lambda x: _PHASE_LABELS.get(x, x))
        display['\u0627\u0644\u0625\u0634\u0627\u0631\u0629'] = df['v2_signal'].map(lambda x: _V2_LABELS.get(x, x))
        display['\u0627\u0644\u0633\u0643\u0648\u0631'] = df['accum_score'].round(0).astype(int)
        display['\u0633\u0639\u0631 \u0627\u0644\u062f\u062e\u0648\u0644'] = df['entry_price'].round(2)

        for period, label in [('5d', '5 أيام'), ('10d', '10 أيام'), ('20d', '20 يوم')]:
            ret_col = f'return_{period}'
            outcome_col = f'outcome_{period}'
            if ret_col in df.columns:
                display[label] = df.apply(
                    lambda r: (
                        f"{'✅' if r.get(outcome_col) == 'win' else '❌'} "
                        f"{r[ret_col]:+.1f}%"
                        if pd.notna(r.get(ret_col))
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
    return db_delete("signal_log")


def get_ticker_signal_history(ticker: str) -> dict:
    """Get signal history for a specific ticker."""
    default = {'total': 0, 'wins': 0, 'win_pct': 0, 'last_signal': '', 'last_date': ''}
    try:
        rows = db_select("signal_log", {"ticker": ticker}, order_by="-date_logged")
        if not rows:
            return default

        total = len(rows)
        completed = [(r['v2_signal'], r.get('outcome_20d')) for r in rows if r.get('outcome_20d')]
        wins = sum(1 for _, o in completed if o == 'win')
        win_pct = round(wins / len(completed) * 100, 0) if completed else 0

        return {
            'total': total,
            'wins': wins,
            'completed': len(completed),
            'win_pct': win_pct,
            'last_signal': rows[0].get('v2_signal', ''),
            'last_date': rows[0].get('date_logged', ''),
        }
    except Exception:
        return default


def get_distribution_summary() -> list:
    """Get active distribution signals for summary banner."""
    try:
        rows = db_select("signal_log", {"accum_phase": "distribute"}, order_by="-date_logged")
        # Filter last 3 days
        cutoff = (datetime.datetime.now(SAUDI_TZ) - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        seen = set()
        result = []
        for r in rows:
            tk = r.get('ticker', '')
            if r.get('date_logged', '') >= cutoff and tk not in seen:
                seen.add(tk)
                result.append({
                    'ticker': tk,
                    'company': r.get('company', ''),
                    'score': r.get('accum_score', 0),
                    'v2_signal': r.get('v2_signal', ''),
                    'date': r.get('date_logged', ''),
                })
        return result
    except Exception:
        return []


def get_signal_count() -> int:
    """Get total number of signals in the log."""
    return db_count("signal_log")
