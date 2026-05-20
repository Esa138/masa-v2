"""
Multi-timeframe OHLCV fetcher for the Confluence engine.
Uses yfinance with caching and column normalization.
"""
import pandas as pd
import yfinance as yf
from typing import Dict, Optional


# TF name -> (yfinance interval, period)
# Periods extended so ZR1 (400-bar) window captures historical highs/lows
# matching the Pine indicator on TradingView.
TF_CONFIG = {
    'D':   {'interval': '1d',  'period': '5y'},    # ~1250 bars
    '240': {'interval': '1h',  'period': '730d'},  # ~4380 1h → ~1095 4h bars
    '60':  {'interval': '1h',  'period': '730d'},  # ~4380 bars
    '15':  {'interval': '15m', 'period': '60d'},   # yfinance limit
    '5':   {'interval': '5m',  'period': '60d'},   # yfinance limit
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


def _resample_to_4h(df: pd.DataFrame, ticker: str = "") -> pd.DataFrame:
    """
    Resample 1h OHLCV into 4h bars aligned to the market session.

    Saudi market (TADAWUL) opens 10:00 Riyadh (07:00 UTC) and closes 15:00.
    TradingView's 4h Saudi bars start at session open, so we must align
    the resampling origin to 07:00 UTC instead of the default midnight.
    For US/crypto we use default alignment.
    """
    if df is None or df.empty:
        return df
    agg = {
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum',
    }
    cols = {k: v for k, v in agg.items() if k in df.columns}

    # Saudi tickers: align 4h bars to 07:00 UTC (10:00 Riyadh, market open)
    is_saudi = ticker.upper().endswith('.SR')
    if is_saudi:
        # offset='7h' shifts the 4h bin boundaries by 7 hours from midnight
        return df.resample('4h', origin='start_day', offset='7h').agg(cols).dropna(subset=['close'])

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
        df = _resample_to_4h(df, ticker=ticker)

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
