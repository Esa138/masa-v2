import pandas as pd
import numpy as np
from core.utils import safe_div


def calculate_zero_reflection(
    high_col: pd.Series,
    low_col: pd.Series,
    bars: int = 400,
    confirm_len: int = 25
) -> tuple[pd.Series, pd.Series]:
    try:
        n = len(high_col)
        ph_val = np.full(n, np.nan)
        pl_val = np.full(n, np.nan)

        window_size = int(2 * confirm_len + 1)
        if n > window_size:
            roll_max = high_col.rolling(window=window_size, min_periods=1, center=True).max().values
            roll_min = low_col.rolling(window=window_size, min_periods=1, center=True).min().values

            shifted_high = high_col.shift(int(confirm_len)).values
            shifted_low = low_col.shift(int(confirm_len)).values

            with np.errstate(invalid='ignore'):
                is_ph = (shifted_high == roll_max) & ~np.isnan(shifted_high)
                is_pl = (shifted_low == roll_min) & ~np.isnan(shifted_low)

            ph_val[is_ph] = shifted_high[is_ph]
            pl_val[is_pl] = shifted_low[is_pl]

        ph_series = pd.Series(ph_val, index=high_col.index)
        pl_series = pd.Series(pl_val, index=low_col.index)

        ph_filled = ph_series.ffill()
        pl_filled = pl_series.ffill()

        ceiling = ph_filled.rolling(window=int(bars), min_periods=1).max()
        floor_s = pl_filled.rolling(window=int(bars), min_periods=1).min()

        fallback_ceiling = high_col.rolling(window=int(bars), min_periods=1).max()
        fallback_floor = low_col.rolling(window=int(bars), min_periods=1).min()

        ceiling = ceiling.where(ceiling.notna() & (ceiling > 0), fallback_ceiling)
        floor_s = floor_s.where(floor_s.notna() & (floor_s > 0), fallback_floor)

        return ceiling, floor_s

    except Exception:
        fallback_ceiling = high_col.rolling(window=int(bars), min_periods=1).max()
        fallback_floor = low_col.rolling(window=int(bars), min_periods=1).min()
        return fallback_ceiling, fallback_floor


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    diff = close.diff()
    up = diff.clip(lower=0)
    down = (-diff).clip(lower=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    ema_down_safe = ema_down.replace(0, np.nan)
    rs = ema_up / ema_down_safe
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def compute_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int = 20) -> pd.Series:
    if volume.sum() == 0:
        return close.rolling(window).mean()
    typical_price = (high + low + close) / 3
    vol_sum = volume.rolling(window).sum().replace(0, np.nan)
    return (typical_price * volume).rolling(window).sum() / vol_sum


def compute_direction_counter(close: pd.Series) -> list[int]:
    diff = close.diff()
    direction = np.where(diff > 0, 1, np.where(diff < 0, -1, 0))
    counters = []
    curr = 0
    for d in direction:
        if d == 1:
            curr = curr + 1 if curr > 0 else 1
        elif d == -1:
            curr = curr - 1 if curr < 0 else -1
        else:
            curr = 0
        counters.append(curr)
    return counters


def calc_momentum_score(
    pct_1d: float, pct_5d: float, pct_10d: float, vol_ratio: float
) -> int:
    def get_points(val, weights):
        if pd.isna(val) or val == 0:
            return weights[3]
        abs_val = abs(val)
        if val > 0:
            if abs_val >= 1.0:
                return weights[0]
            elif abs_val >= 0.1:
                return weights[1]
            return weights[2]
        else:
            if abs_val >= 1.0:
                return weights[6]
            elif abs_val >= 0.1:
                return weights[5]
            return weights[4]

    s5 = get_points(pct_5d, [40, 35, 28, 20, 12, 6, 0])
    s10 = get_points(pct_10d, [25, 22, 18, 12, 8, 4, 0])
    s1 = get_points(pct_1d, [15, 13, 10, 7, 4, 2, 0])

    if pd.isna(pct_1d) or pct_1d == 0:
        svol = 10
    elif pct_1d > 0:
        svol = 20 if vol_ratio > 1.0 else 16
    else:
        svol = 6 if vol_ratio <= 1.0 else 0

    return int(min(100, max(0, s5 + s10 + s1 + svol)))
