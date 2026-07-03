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
    'W':   {'interval': '1wk', 'period': '10y'},   # ~520 bars — sovereign horizon
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
    Resample 1h OHLCV into 4h bars aligned to the market session,
    matching TradingView's bar boundaries:

    - TADAWUL (.SR): session opens 10:00 Riyadh = 07:00 UTC → offset 7h
    - US equities/ETFs/indices: session opens 09:30 ET; yfinance returns
      these with an America/New_York index → offset 9h30min from local
      midnight gives bars at 09:30 / 13:30 like TV
    - Crypto (24/7, -USD): TV aligns to UTC midnight → default bins
    """
    if df is None or df.empty:
        return df
    agg = {
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum',
    }
    cols = {k: v for k, v in agg.items() if k in df.columns}

    _t = ticker.upper()
    if _t.endswith('.SR'):
        return df.resample('4h', origin='start_day', offset='7h').agg(cols).dropna(subset=['close'])

    if _t.endswith('-USD') or _t.endswith('=X') or _t.endswith('=F'):
        # 24/7 or non-equity: default UTC-midnight bins (matches TV crypto)
        return df.resample('4h').agg(cols).dropna(subset=['close'])

    # US equities/ETFs/indices: align to the 09:30 ET session open.
    # yfinance may return the index in UTC — convert to New York first
    # so the 9h30 offset lands on the session open across DST changes.
    tz = getattr(df.index, 'tz', None)
    if tz is not None:
        try:
            df = df.tz_convert('America/New_York')
            out = df.resample('4h', origin='start_day', offset='9h30min').agg(cols).dropna(subset=['close'])
            return out
        except Exception:
            pass
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


def fetch_60_and_240(ticker: str):
    """
    Download 1h data ONCE and derive both the 60m and 4h frames from it.
    Halves the request count vs fetching '60' and '240' separately
    (the 4h frame was already resampled from 1h anyway).

    Returns (df_240, df_60) — either may be an empty DataFrame.
    """
    df_60 = fetch_single_tf(ticker, '60')
    if df_60 is None or df_60.empty:
        return pd.DataFrame(), pd.DataFrame()
    df_240 = _resample_to_4h(df_60, ticker=ticker)
    if not df_240.empty and len(df_240) > _MAX_BARS:
        df_240 = df_240.tail(_MAX_BARS).copy()
    return df_240, df_60


def fetch_multi_tf_data(
    ticker: str,
    timeframes: Optional[list] = None,
    parallel: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Fetch OHLCV for multiple timeframes. Returns dict {tf_name: df}.

    With parallel=True (default), fetches all TFs concurrently using a
    thread pool. When both '60' and '240' are requested, the 1h data is
    downloaded once and the 4h frame is resampled from it locally.
    """
    if timeframes is None:
        timeframes = ['D', '240', '60', '15', '5']

    out: Dict[str, pd.DataFrame] = {}

    # Dedup: serve 240 from the 60 download when both requested
    _pair_240_60 = '60' in timeframes and '240' in timeframes
    _fetch_list = [tf for tf in timeframes if not (_pair_240_60 and tf == '240')]

    def _job(tf):
        if _pair_240_60 and tf == '60':
            return fetch_60_and_240(ticker)  # (df_240, df_60)
        return fetch_single_tf(ticker, tf)

    if parallel and len(_fetch_list) > 1:
        with ThreadPoolExecutor(max_workers=min(5, len(_fetch_list))) as ex:
            futures = {ex.submit(_job, tf): tf for tf in _fetch_list}
            for fut in futures:
                tf = futures[fut]
                try:
                    result = fut.result(timeout=30)
                except Exception:
                    continue
                if _pair_240_60 and tf == '60':
                    df_240, df_60 = result
                    if df_240 is not None and not df_240.empty:
                        out['240'] = df_240
                    if df_60 is not None and not df_60.empty:
                        out['60'] = df_60
                elif result is not None and not result.empty:
                    out[tf] = result
    else:
        for tf in _fetch_list:
            result = _job(tf)
            if _pair_240_60 and tf == '60':
                df_240, df_60 = result
                if df_240 is not None and not df_240.empty:
                    out['240'] = df_240
                if df_60 is not None and not df_60.empty:
                    out['60'] = df_60
            elif result is not None and not result.empty:
                out[tf] = result

    return out


def fetch_daily_batch(tickers: list, period: str = '5y',
                      interval: str = '1d') -> Dict[str, pd.DataFrame]:
    """
    Bulk download OHLCV for many tickers in ONE yfinance call.
    Works for any interval — pass interval='1wk' for weekly batches.

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
            interval=interval,
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
