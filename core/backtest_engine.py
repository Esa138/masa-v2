"""
MASA QUANT V95 — Accumulation Signal Backtester
Tests historical accuracy of accumulation/distribution signals.
Includes market breadth filter for trend alignment.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.indicators import (
    compute_cmf, compute_obv, compute_linear_slope,
    compute_rsi, compute_range_contraction,
    compute_accumulation_score, detect_accumulation_phase,
)
from data.markets import get_stock_name

FORWARD_DAYS = [5, 10, 20, 40]
MIN_BARS = 60

# Breadth thresholds for market alignment (strict)
BREADTH_BULL = 55  # Buy signals require breadth >= this
BREADTH_BEAR = 40  # Sell signals require breadth <= this


def _compute_historical_breadth(tickers: list, period: str) -> pd.Series:
    """
    Batch-download all tickers and compute daily breadth %.
    Returns Series: index=dates, values=breadth % (0-100).
    """
    try:
        raw = yf.download(
            tickers=tickers,
            period=period,
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
        )
        if raw is None or raw.empty:
            return pd.Series(dtype=float)

        closes = {}
        for tk in tickers:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if tk in raw.columns.get_level_values(0):
                        s = raw[tk]["Close"].dropna()
                        if len(s) >= 20:
                            closes[tk] = s
                else:
                    if "Close" in raw.columns:
                        closes[tk] = raw["Close"].dropna()
            except (KeyError, TypeError):
                continue

        if not closes:
            return pd.Series(dtype=float)

        df_closes = pd.DataFrame(closes).sort_index()

        # Daily % change
        changes = df_closes.pct_change(1)
        winners = (changes > 0).sum(axis=1)
        total_valid = changes.notna().sum(axis=1)
        breadth_pct = (winners / total_valid.replace(0, np.nan) * 100).fillna(50)

        # Smooth with SMA-5 to reduce noise
        breadth_smooth = breadth_pct.rolling(window=5, min_periods=1).mean()

        return breadth_smooth

    except Exception:
        return pd.Series(dtype=float)


def _backtest_single_ticker(tk: str, period: str, breadth: pd.Series) -> list:
    """Backtest accumulation signals for a single ticker with breadth filter."""
    try:
        df = yf.Ticker(tk).history(period=period, interval="1d")
        if df is None or df.empty or len(df) < MIN_BARS:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # Compute indicators
        cmf = compute_cmf(high, low, close, volume, period=20)
        obv = compute_obv(close, volume)
        obv_slope = compute_linear_slope(obv, window=20)
        rsi = compute_rsi(close)
        range_ratio = compute_range_contraction(high, low)
        vol_sma = volume.rolling(20).mean().replace(0, np.nan)
        vol_ratio = (volume / vol_sma).fillna(1.0)
        price_slope = compute_linear_slope(close, window=20)

        # Accumulation score & phase
        score = compute_accumulation_score(
            cmf, obv_slope, rsi, vol_ratio, range_ratio, price_slope
        )
        phase = detect_accumulation_phase(score, cmf, obv_slope)

        # Detect signal transitions
        signals = []
        stock_name = get_stock_name(tk)
        close_arr = close.values
        dates = close.index

        has_breadth = not breadth.empty

        for i in range(1, len(phase)):
            curr_phase = phase.iloc[i]
            prev_phase = phase.iloc[i - 1]

            signal_type = None
            if curr_phase == "late" and prev_phase != "late":
                signal_type = "late"
            elif curr_phase == "strong" and prev_phase not in ("strong", "late"):
                signal_type = "strong"
            elif curr_phase == "distribute" and prev_phase != "distribute":
                signal_type = "distribute"

            if signal_type is None:
                continue

            entry_price = close_arr[i]
            entry_date = dates[i]
            entry_score = score.iloc[i]
            entry_cmf = cmf.iloc[i]

            # Look up market breadth on signal date
            entry_breadth = np.nan
            aligned = True  # Default: aligned if no breadth data
            if has_breadth:
                # Find closest breadth date (tz-naive match)
                sig_date = entry_date
                if hasattr(sig_date, 'tz') and sig_date.tz is not None:
                    sig_date = sig_date.tz_localize(None)

                breadth_idx = breadth.index
                if hasattr(breadth_idx, 'tz') and breadth_idx.tz is not None:
                    breadth_idx = breadth_idx.tz_localize(None)

                # Find nearest date
                diffs = abs(breadth_idx - sig_date)
                if len(diffs) > 0:
                    nearest_idx = diffs.argmin()
                    if diffs[nearest_idx].days <= 3:  # Within 3 days
                        entry_breadth = float(breadth.iloc[nearest_idx])

                        # Alignment logic (strict)
                        if signal_type in ("late", "strong"):
                            # Buy signal: only in bullish market
                            aligned = entry_breadth >= BREADTH_BULL
                        else:
                            # Sell signal: only in bearish market
                            aligned = entry_breadth <= BREADTH_BEAR

            sig = {
                "ticker": tk,
                "stock": stock_name,
                "date": entry_date,
                "phase": signal_type,
                "score": round(entry_score, 1),
                "cmf": round(entry_cmf, 3),
                "entry_price": round(entry_price, 2),
                "breadth": round(entry_breadth, 1) if not np.isnan(entry_breadth) else np.nan,
                "aligned": aligned,
            }

            # Forward returns
            for days in FORWARD_DAYS:
                if i + days < len(close_arr):
                    future = close_arr[i + days]
                    ret = (future / entry_price - 1) * 100
                    sig[f"ret_{days}d"] = round(ret, 2)
                else:
                    sig[f"ret_{days}d"] = np.nan

            signals.append(sig)

        return signals

    except Exception:
        return []


@st.cache_data(ttl=900, show_spinner=False)
def backtest_accumulation_signals(
    tickers: tuple, period: str = "2y"
) -> pd.DataFrame:
    """
    Run backtest across all tickers in parallel.
    First computes market breadth, then tags each signal with alignment.
    Returns DataFrame with all historical signals and their forward returns.
    """
    # Step 1: Compute historical market breadth
    breadth = _compute_historical_breadth(list(tickers), period)

    # Step 2: Run individual ticker backtests in parallel
    all_signals = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_backtest_single_ticker, tk, period, breadth): tk
            for tk in tickers
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_signals.extend(result)

    if not all_signals:
        return pd.DataFrame()

    df = pd.DataFrame(all_signals)
    df = df.sort_values("date", ascending=False).reset_index(drop=True)
    return df


def compute_backtest_summary(signals_df: pd.DataFrame, aligned_only: bool = False) -> dict:
    """
    Compute summary statistics from backtest signals.
    If aligned_only=True, only considers signals aligned with market trend.
    Returns dict with per-phase stats.
    """
    if signals_df.empty:
        return {}

    df_src = signals_df
    if aligned_only and "aligned" in df_src.columns:
        df_src = df_src[df_src["aligned"] == True]

    if df_src.empty:
        return {}

    summary = {}
    for phase in ["late", "strong", "distribute"]:
        df_p = df_src[df_src["phase"] == phase]
        if df_p.empty:
            continue

        stats = {"count": len(df_p), "periods": {}}

        for days in FORWARD_DAYS:
            col = f"ret_{days}d"
            valid = df_p[col].dropna()
            if valid.empty:
                continue

            if phase == "distribute":
                wins = (valid < 0).sum()
            else:
                wins = (valid > 0).sum()

            total = len(valid)
            win_rate = (wins / total * 100) if total > 0 else 0
            avg_ret = valid.mean()
            best = valid.max()
            worst = valid.min()

            gains = valid[valid > 0].sum()
            losses = abs(valid[valid < 0].sum())
            pf = (gains / losses) if losses > 0 else 99.9

            stats["periods"][days] = {
                "win_rate": round(win_rate, 1),
                "avg_return": round(avg_ret, 2),
                "best": round(best, 2),
                "worst": round(worst, 2),
                "profit_factor": round(pf, 2),
                "total": total,
            }

        # Overall 20d stats as headline
        col_20 = "ret_20d"
        valid_20 = df_p[col_20].dropna()
        if not valid_20.empty:
            if phase == "distribute":
                stats["headline_win"] = round(
                    (valid_20 < 0).sum() / len(valid_20) * 100, 1
                )
            else:
                stats["headline_win"] = round(
                    (valid_20 > 0).sum() / len(valid_20) * 100, 1
                )
            stats["headline_avg"] = round(valid_20.mean(), 2)
        else:
            stats["headline_win"] = 0
            stats["headline_avg"] = 0

        summary[phase] = stats

    return summary
