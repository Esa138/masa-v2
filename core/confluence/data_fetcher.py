"""
Multi-timeframe OHLCV fetcher for the Confluence engine.
Uses yfinance with caching and column normalization.
"""
import pandas as pd
import yfinance as yf
from typing import Dict, Optional


# TF name -> (yfinance interval, period)
TF_CONFIG = {
    'D':   {'interval': '1d',  'period': '2y'},
    '240': {'interval': '1h',  'period': '730d'},  # resampled to 4h
    '60':  {'interval': '1h',  'period': '730d'},
    '15':  {'interval': '15m', 'period': '60d'},
    '5':   {'interval': '5m',  'period': '60d'},
}


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase columns, ensure OHLCV cols exist."""
    if df is None or df.empty:
        return pd.DataFrame()

    # Handle yfinance multi-index columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns={
        'Open': 'open', 'High': 'high', 'Low': 'low',
        'Close': 'close', 'Adj Close': 'adj_close', 'Volume': 'volume',
    })
    df.columns = [str(c).lower() for c in df.columns]

    needed = {'open', 'high', 'low', 'close'}
    if not needed.issubset(df.columns):
        return pd.DataFrame()

    if 'volume' not in df.columns:
        df['volume'] = 0.0

    return df.dropna(subset=['close'])


def _resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """Resample 1h OHLCV into 4h bars."""
    if df is None or df.empty:
        return df
    agg = {
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum',
    }
    cols = {k: v for k, v in agg.items() if k in df.columns}
    return df.resample('4h').agg(cols).dropna(subset=['close'])


def fetch_single_tf(ticker: str, tf: str) -> pd.DataFrame:
    """Fetch one timeframe of OHLCV data."""
    if tf not in TF_CONFIG:
        return pd.DataFrame()

    cfg = TF_CONFIG[tf]
    try:
        df = yf.download(
            ticker,
            period=cfg['period'],
            interval=cfg['interval'],
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception:
        return pd.DataFrame()

    df = _normalize_df(df)

    if tf == '240' and not df.empty:
        df = _resample_to_4h(df)

    return df


def fetch_multi_tf_data(
    ticker: str,
    timeframes: Optional[list] = None,
) -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV for multiple timeframes. Returns dict {tf_name: df}."""
    if timeframes is None:
        timeframes = ['D', '240', '60', '15', '5']

    out: Dict[str, pd.DataFrame] = {}
    for tf in timeframes:
        df = fetch_single_tf(ticker, tf)
        if df is not None and not df.empty:
            out[tf] = df
    return out
