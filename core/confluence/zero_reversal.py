"""
Zero Reversal levels (ZR1, ZR2) for any timeframe.
Matches Pine Script f_get_structural_zr semantics.
"""
import pandas as pd
import numpy as np
from typing import Tuple


def find_pivots(df: pd.DataFrame, left: int, right: int) -> Tuple[pd.Series, pd.Series]:
    """Detect pivot highs/lows (same as ta.pivothigh/pivotlow in Pine)."""
    if 'high' not in df.columns or 'low' not in df.columns:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    highs = df['high'].values
    lows = df['low'].values
    n = len(df)

    ph = np.full(n, np.nan)
    pl = np.full(n, np.nan)

    for i in range(left, n - right):
        window_high = highs[i - left:i + right + 1]
        window_low = lows[i - left:i + right + 1]

        if highs[i] == window_high.max() and (window_high == highs[i]).sum() == 1:
            ph[i] = highs[i]

        if lows[i] == window_low.min() and (window_low == lows[i]).sum() == 1:
            pl[i] = lows[i]

    return pd.Series(ph, index=df.index), pd.Series(pl, index=df.index)


def compute_zero_reversal(
    df: pd.DataFrame,
    bars: int = 400,
    confirm_len: int = 25,
) -> dict:
    """Compute ZR ceiling/floor for one timeframe."""
    if df.empty or len(df) < confirm_len * 2:
        return {'ceiling': np.nan, 'floor': np.nan, 'bars_analyzed': 0,
                'pivots_found': {'highs': 0, 'lows': 0}}

    ph, pl = find_pivots(df, confirm_len, confirm_len)
    recent_window = df.tail(bars)

    ph_in_window = ph.loc[recent_window.index].dropna()
    pl_in_window = pl.loc[recent_window.index].dropna()

    if len(ph_in_window) > 0:
        ceiling = float(ph_in_window.max())
    else:
        ceiling = float(recent_window['high'].iloc[:-1].max()) if len(recent_window) > 1 else np.nan

    if len(pl_in_window) > 0:
        floor = float(pl_in_window.min())
    else:
        floor = float(recent_window['low'].iloc[:-1].min()) if len(recent_window) > 1 else np.nan

    return {
        'ceiling': ceiling,
        'floor': floor,
        'bars_analyzed': bars,
        'pivots_found': {
            'highs': len(ph_in_window),
            'lows': len(pl_in_window),
        },
    }


def compute_zr1_zr2(df: pd.DataFrame) -> dict:
    """Compute both ZR1 and ZR2 levels (matches Pine defaults)."""
    zr1 = compute_zero_reversal(df, bars=400, confirm_len=25)
    zr2 = compute_zero_reversal(df, bars=300, confirm_len=30)
    return {
        'z1h': zr1['ceiling'],
        'z1l': zr1['floor'],
        'z2h': zr2['ceiling'],
        'z2l': zr2['floor'],
    }
