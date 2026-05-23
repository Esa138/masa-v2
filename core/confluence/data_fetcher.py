"""
Multi-timeframe OHLCV fetcher for the Confluence engine.
Uses yfinance with caching and column normalization.
"""
import pandas as pd
import yfinance as yf
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import time


# TF name -> (yfinance interval, period)
# Aggressively trimmed for Streamlit Cloud (1GB memory ceiling).
TF_CONFIG = {
    'D':   {'interval': '1d',  'period': '5y'},    # ~1250 bars — matches TV history depth
    '240': {'interval': '1h',  'period': '365d'},  # ~2200 1h → ~550 4h
    '60':  {'interval': '1h',  'period': '365d'},  # ~2200 bars
    '15':  {'interval': '15m', 'period': '30d'},   # ~600 bars
    '5':   {'interval': '5m',  'period': '15d'},   # ~900 bars
}

# Hard cap per DataFrame — give Gamma enough history to match TV's HMA600.
_MAX_BARS = 1300


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

    # Trim to last _MAX_BARS to control memory
    if not df.empty and len(df) > _MAX_BARS:
        df = df.tail(_MAX_BARS).copy()

    return df


def fetch_multi_tf_data(
    ticker: str,
    timeframes: Optional[list] = None,
    parallel: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch OHLCV for multiple timeframes. Returns dict {tf_name: df}.

    With parallel=True (default), fetches all TFs concurrently using a
    thread pool — typically 3-5× faster for multi-TF requests.
    """
    if timeframes is None:
        timeframes = ['D', '240', '60', '15', '5']

    out: Dict[str, pd.DataFrame] = {}

    if parallel and len(timeframes) > 1:
        with ThreadPoolExecutor(max_workers=min(5, len(timeframes))) as ex:
            futures = {ex.submit(fetch_single_tf, ticker, tf): tf for tf in timeframes}
            for fut in futures:
                tf = futures[fut]
                try:
                    df = fut.result(timeout=30)
                    if df is not None and not df.empty:
                        out[tf] = df
                except Exception:
                    pass
    else:
        for tf in timeframes:
            df = fetch_single_tf(ticker, tf)
            if df is not None and not df.empty:
                out[tf] = df

    return out


def fetch_daily_batch(tickers: list, period: str = '5y') -> Dict[str, pd.DataFrame]:
    """
    Bulk download daily OHLCV for many tickers in ONE yfinance call.

    Much faster than per-ticker calls when scanning a market:
    250 tickers × individual = ~250 requests
    250 tickers batched     = ~1 request
    """
    if not tickers:
        return {}

    out: Dict[str, pd.DataFrame] = {}
    try:
        df_all = yf.download(
            tickers=' '.join(tickers),
            period=period,
            interval='1d',
            group_by='ticker',
            progress=False,
            auto_adjust=False,
            threads=True,
        )
    except Exception:
        return out

    if df_all is None or df_all.empty:
        return out

    # When >1 ticker, columns are MultiIndex (ticker, field)
    if isinstance(df_all.columns, pd.MultiIndex):
        for tk in tickers:
            try:
                if tk in df_all.columns.get_level_values(0):
                    sub = df_all[tk]
                    sub = _normalize_df(sub)
                    if not sub.empty:
                        out[tk] = sub
            except Exception:
                continue
    else:
        # Single ticker case
        sub = _normalize_df(df_all)
        if not sub.empty and tickers:
            out[tickers[0]] = sub

    return out


# ── Memory-aware cache (size-bounded, 5-min TTL) ──────────
# Previous unbounded cache held DataFrames for hundreds of tickers
# → OOM on Streamlit Cloud's 1GB limit. New version caps entries.
_CACHE: Dict[tuple, tuple] = {}
_CACHE_TTL_SEC = 300
_CACHE_MAX_ENTRIES = 20  # tighter cap for low-memory environments


def fetch_multi_tf_data_cached(
    ticker: str,
    timeframes: Optional[list] = None,
) -> Dict[str, pd.DataFrame]:
    """Cached multi-TF fetch — bounded LRU-style, 5-min TTL."""
    if timeframes is None:
        timeframes = ['D', '240', '60', '15', '5']
    key = (ticker, tuple(sorted(timeframes)))
    now = time.time()

    # Evict expired entries
    expired = [k for k, v in _CACHE.items() if (now - v[0]) >= _CACHE_TTL_SEC]
    for k in expired:
        _CACHE.pop(k, None)

    # Size cap — drop oldest if at capacity
    while len(_CACHE) >= _CACHE_MAX_ENTRIES:
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _CACHE.pop(oldest, None)

    cached = _CACHE.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SEC:
        return cached[1]

    data = fetch_multi_tf_data(ticker, timeframes=timeframes, parallel=True)
    _CACHE[key] = (now, data)
    return data


def clear_cache():
    """Free all cached data."""
    _CACHE.clear()
