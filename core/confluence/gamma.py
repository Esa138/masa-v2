"""
Gamma (long-term trend MA) computation — multi-type.
Default: HMA 600 (Hull Moving Average).
"""
import pandas as pd
import numpy as np


def hma(series: pd.Series, period: int) -> pd.Series:
    """Hull Moving Average — matches Pine ta.hma()."""
    half = max(1, int(period / 2))
    sqrt_p = max(1, int(np.sqrt(period)))

    def _wma(x):
        n = len(x)
        if n == 0:
            return np.nan
        weights = np.arange(1, n + 1)
        return float(np.average(x, weights=weights))

    wma_half = series.rolling(half).apply(_wma, raw=True)
    wma_full = series.rolling(period).apply(_wma, raw=True)
    raw_hma = 2 * wma_half - wma_full
    return raw_hma.rolling(sqrt_p).apply(_wma, raw=True)


def compute_gamma(
    df: pd.DataFrame,
    length: int = 600,
    ma_type: str = "HMA",
) -> pd.Series:
    """Compute gamma series — supports EMA / SMA / WMA / HMA."""
    if 'close' not in df.columns or df.empty:
        return pd.Series(dtype=float)

    close = df['close']
    n = len(close)

    # HMA needs `period + sqrt(period)` valid bars to produce a non-NaN
    # last value (two stacked rolling WMAs). Reserve that overhead.
    if ma_type == "HMA":
        overhead = int(np.sqrt(length)) + 5
        actual_length = min(length, max(20, n - overhead))
    else:
        actual_length = min(length, max(20, n - 1))

    if ma_type == "EMA":
        return close.ewm(span=actual_length, adjust=False).mean()
    elif ma_type == "SMA":
        return close.rolling(actual_length).mean()
    elif ma_type == "WMA":
        return close.rolling(actual_length).apply(
            lambda x: float(np.average(x, weights=np.arange(1, len(x) + 1))),
            raw=True,
        )
    elif ma_type == "HMA":
        return hma(close, actual_length)
    else:
        raise ValueError(f"Unknown MA type: {ma_type}")


def gamma_slope(gamma_series: pd.Series, lookback: int = 5) -> str:
    """Determine slope direction: صاعد / هابط / جانبي / غير محدد."""
    if gamma_series.empty or len(gamma_series) < lookback + 1:
        return "غير محدد"

    current = gamma_series.iloc[-1]
    past = gamma_series.iloc[-1 - lookback]

    if pd.isna(current) or pd.isna(past) or past == 0:
        return "غير محدد"

    change_pct = (current - past) / past * 100

    if change_pct > 0.1:
        return "صاعد"
    elif change_pct < -0.1:
        return "هابط"
    return "جانبي"
