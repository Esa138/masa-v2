"""
MASA QUANT — Performance Diagnostics Engine
Deep analysis of historical signals to discover golden patterns and trap patterns.

Methodology:
- Univariate: each feature alone (sector, RSI, location, day, etc.)
- Bivariate: pairs of features (sector × RSI, flow × RSI, etc.)
- Per-market: Saudi vs US analyzed separately

Statistical safeguards:
- Min sample size: n >= 4
- Highlight strong signals (n >= 8) vs weak (4 <= n < 8)
"""

import sqlite3
import pandas as pd
import numpy as np


DB_PATH = "masa_v2.db"


# ══════════════════════════════════════════════════════════════
# DATA PREPARATION
# ══════════════════════════════════════════════════════════════

def load_signals_df(db_path: str = DB_PATH) -> pd.DataFrame:
    """Load all completed signals with derived columns."""
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql(
                "SELECT * FROM signals WHERE decision='enter' AND outcome_20d IS NOT NULL",
                conn,
            )
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    # Derived columns
    df['is_saudi'] = df['ticker'].str.contains('.SR', regex=False, na=False)
    df['market'] = df['is_saudi'].map({True: 'السعودي', False: 'الأمريكي'})
    df['win'] = (df['outcome_20d'] == 'win').astype(int)
    df['date_logged'] = pd.to_datetime(df['date_logged'], errors='coerce')
    df['day_en'] = df['date_logged'].dt.day_name()
    _day_map = {
        'Sunday': 'الأحد', 'Monday': 'الإثنين', 'Tuesday': 'الثلاثاء',
        'Wednesday': 'الأربعاء', 'Thursday': 'الخميس',
        'Friday': 'الجمعة', 'Saturday': 'السبت',
    }
    df['day'] = df['day_en'].map(_day_map)
    df['month'] = df['date_logged'].dt.month

    # RSI zones
    def _rsi_zone(r):
        if pd.isna(r):
            return 'غير معروف'
        if r < 30:
            return 'منخفض (<30)'
        if r < 50:
            return 'متوسط (30-50)'
        if r < 70:
            return 'زخم (50-70)'
        return 'تشبع (>70)'
    df['rsi_zone'] = df['rsi'].apply(_rsi_zone)

    # Flow zones
    def _flow_zone(f):
        if pd.isna(f):
            return 'غير معروف'
        if f >= 50:
            return 'قوي جداً (50+)'
        if f >= 25:
            return 'قوي (25-50)'
        if f >= 10:
            return 'متوسط (10-25)'
        return 'ضعيف (<10)'
    df['flow_zone'] = df['cmf'].apply(_flow_zone)

    # R:R zones
    def _rr_zone(r):
        if pd.isna(r):
            return 'غير معروف'
        if r < 1.5:
            return 'R:R<1.5'
        if r < 2:
            return 'R:R 1.5-2'
        if r < 3:
            return 'R:R 2-3'
        return 'R:R 3+'
    df['rr_zone'] = df['rr_ratio'].apply(_rr_zone)

    # Accumulation days bins
    def _days_bin(d):
        if pd.isna(d):
            return 'غير معروف'
        if d < 10:
            return 'أقل من 10 أيام'
        if d < 20:
            return '10-20 يوم'
        if d < 40:
            return '20-40 يوم'
        return '40+ يوم'
    df['days_bin'] = df['accum_days'].apply(_days_bin)

    # Industry (sub-sector) — mapped from data/markets
    try:
        from data.markets import US_INDUSTRIES
        df['industry'] = df.apply(
            lambda r: US_INDUSTRIES.get(r['ticker'], r.get('sector', '')) if not r['is_saudi']
            else r.get('sector', ''),
            axis=1,
        )
    except Exception:
        df['industry'] = df.get('sector', '')

    return df


# ══════════════════════════════════════════════════════════════
# ANALYSIS FUNCTIONS
# ══════════════════════════════════════════════════════════════

def analyze_univariate(df: pd.DataFrame, group_col: str, min_n: int = 4) -> list:
    """Single-feature analysis. Returns sorted list of dicts."""
    if df.empty or group_col not in df.columns:
        return []

    grp = df.groupby(group_col)
    rows = []
    for k, g in grp:
        if len(g) < min_n:
            continue
        rows.append({
            'category': str(k) if pd.notna(k) else 'غير معروف',
            'n': len(g),
            'wins': int(g['win'].sum()),
            'win_rate': round(g['win'].mean() * 100, 1),
            'avg_return': round(g['return_20d'].mean(), 2),
            'best_return': round(g['return_20d'].max(), 2),
            'worst_return': round(g['return_20d'].min(), 2),
            'is_strong_sample': len(g) >= 8,
        })
    return sorted(rows, key=lambda x: -x['win_rate'])


def analyze_bivariate(df: pd.DataFrame, col1: str, col2: str, min_n: int = 4) -> list:
    """Two-feature combination analysis."""
    if df.empty or col1 not in df.columns or col2 not in df.columns:
        return []

    grp = df.groupby([col1, col2])
    rows = []
    for (k1, k2), g in grp:
        if len(g) < min_n:
            continue
        rows.append({
            'pattern': f"{k1} + {k2}",
            'col1_value': str(k1),
            'col2_value': str(k2),
            'n': len(g),
            'win_rate': round(g['win'].mean() * 100, 1),
            'avg_return': round(g['return_20d'].mean(), 2),
            'is_strong_sample': len(g) >= 8,
        })
    return sorted(rows, key=lambda x: -x['win_rate'])


def find_golden_patterns(df: pd.DataFrame, min_win_rate: float = 65, min_n: int = 4) -> list:
    """Find combinations with high win rate."""
    if df.empty:
        return []

    candidates = []

    # Sector × RSI Zone
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'sector', 'rsi_zone', min_n),
        "sector_rsi"
    ))
    # Sector × Flow Zone
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'sector', 'flow_zone', min_n),
        "sector_flow"
    ))
    # Industry × RSI Zone (sub-sector granular)
    if 'industry' in df.columns:
        candidates.extend(_label_patterns(
            analyze_bivariate(df, 'industry', 'rsi_zone', min_n),
            "industry_rsi"
        ))
        # Industry × Flow Zone
        candidates.extend(_label_patterns(
            analyze_bivariate(df, 'industry', 'flow_zone', min_n),
            "industry_flow"
        ))
    # Phase × RSI Zone
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'accum_level', 'rsi_zone', min_n),
        "phase_rsi"
    ))
    # Location × Days bin
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'location', 'days_bin', min_n),
        "loc_days"
    ))
    # R:R × Flow
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'rr_zone', 'flow_zone', min_n),
        "rr_flow"
    ))

    # Filter golden
    golden = [c for c in candidates if c['win_rate'] >= min_win_rate]
    # Sort by combination of win rate and sample size
    golden.sort(key=lambda x: (-x['win_rate'], -x['n']))
    return golden


def find_trap_patterns(df: pd.DataFrame, max_win_rate: float = 25, min_n: int = 4) -> list:
    """Find combinations with low win rate (traps)."""
    if df.empty:
        return []

    candidates = []
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'sector', 'rsi_zone', min_n), "sector_rsi"))
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'sector', 'flow_zone', min_n), "sector_flow"))
    if 'industry' in df.columns:
        candidates.extend(_label_patterns(
            analyze_bivariate(df, 'industry', 'rsi_zone', min_n), "industry_rsi"))
        candidates.extend(_label_patterns(
            analyze_bivariate(df, 'industry', 'flow_zone', min_n), "industry_flow"))
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'accum_level', 'rsi_zone', min_n), "phase_rsi"))
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'location', 'days_bin', min_n), "loc_days"))
    candidates.extend(_label_patterns(
        analyze_bivariate(df, 'rr_zone', 'flow_zone', min_n), "rr_flow"))

    traps = [c for c in candidates if c['win_rate'] <= max_win_rate]
    traps.sort(key=lambda x: (x['win_rate'], -x['n']))
    return traps


def _label_patterns(patterns: list, pattern_type: str) -> list:
    """Add pattern_type and human-readable label to each pattern."""
    type_labels = {
        "sector_rsi": "🏭 قطاع × RSI",
        "sector_flow": "🏭 قطاع × Flow",
        "industry_rsi": "🔬 صناعة × RSI",
        "industry_flow": "🔬 صناعة × Flow",
        "phase_rsi": "📊 مرحلة × RSI",
        "loc_days": "📍 موقع × مدة التجميع",
        "rr_flow": "🎯 R:R × Flow",
    }
    for p in patterns:
        p['pattern_type'] = type_labels.get(pattern_type, pattern_type)
    return patterns


def simulate_golden_filter(df: pd.DataFrame, golden_patterns: list, top_n: int = 5) -> dict:
    """
    Simulate: what if we ONLY took signals matching top golden patterns?
    Returns before/after stats.
    """
    if df.empty or not golden_patterns:
        return {}

    # Build mask for top N golden patterns
    top_patterns = golden_patterns[:top_n]

    # Map pattern types to columns
    type_to_cols = {
        "🏭 قطاع × RSI": ('sector', 'rsi_zone'),
        "🏭 قطاع × Flow": ('sector', 'flow_zone'),
        "🔬 صناعة × RSI": ('industry', 'rsi_zone'),
        "🔬 صناعة × Flow": ('industry', 'flow_zone'),
        "📊 مرحلة × RSI": ('accum_level', 'rsi_zone'),
        "📍 موقع × مدة التجميع": ('location', 'days_bin'),
        "🎯 R:R × Flow": ('rr_zone', 'flow_zone'),
    }

    matched_idx = set()
    for p in top_patterns:
        cols = type_to_cols.get(p.get('pattern_type'))
        if not cols:
            continue
        c1, c2 = cols
        mask = (df[c1].astype(str) == p['col1_value']) & (df[c2].astype(str) == p['col2_value'])
        matched_idx.update(df[mask].index.tolist())

    filtered = df.loc[list(matched_idx)]

    return {
        'before': {
            'n': len(df),
            'win_rate': round(df['win'].mean() * 100, 1),
            'avg_return': round(df['return_20d'].mean(), 2),
            'wins': int(df['win'].sum()),
        },
        'after': {
            'n': len(filtered),
            'win_rate': round(filtered['win'].mean() * 100, 1) if len(filtered) > 0 else 0,
            'avg_return': round(filtered['return_20d'].mean(), 2) if len(filtered) > 0 else 0,
            'wins': int(filtered['win'].sum()) if len(filtered) > 0 else 0,
            'kept_pct': round(len(filtered) / len(df) * 100, 1) if len(df) > 0 else 0,
        },
    }


def get_market_summary(df: pd.DataFrame) -> dict:
    """Quick summary stats for a market."""
    if df.empty:
        return {'n': 0, 'win_rate': 0, 'avg_return': 0, 'wins': 0, 'losses': 0}
    return {
        'n': len(df),
        'win_rate': round(df['win'].mean() * 100, 1),
        'avg_return': round(df['return_20d'].mean(), 2),
        'wins': int(df['win'].sum()),
        'losses': int((df['win'] == 0).sum()),
        'best': round(df['return_20d'].max(), 2),
        'worst': round(df['return_20d'].min(), 2),
    }


def build_heatmap_data(df: pd.DataFrame, row_col: str, col_col: str) -> tuple:
    """
    Build pivot table for heatmap visualization.
    Returns: (z_matrix, x_labels, y_labels, n_matrix)
    """
    if df.empty:
        return [], [], [], []

    pivot = df.groupby([row_col, col_col])['win'].agg(['mean', 'count']).reset_index()
    pivot.columns = [row_col, col_col, 'win_rate', 'n']
    pivot['win_rate'] = pivot['win_rate'] * 100

    # Pivot to matrix
    wr_matrix = pivot.pivot(index=row_col, columns=col_col, values='win_rate')
    n_matrix = pivot.pivot(index=row_col, columns=col_col, values='n')

    return (
        wr_matrix.values.tolist(),
        wr_matrix.columns.tolist(),
        wr_matrix.index.tolist(),
        n_matrix.values.tolist(),
    )
