"""
MASA QUANT — Post-Earnings Price Tracker

يتابع أداء الأسهم قبل وبعد إعلان النتائج:
- كم ارتفع/انخفض قبل الإعلان (5 أيام)
- كم ارتفع/انخفض بعد الإعلان (1/5/10 أيام)
- هل فيه نمط تجميع قبل النتائج
- إحصائيات عامة: كم سهم يرتفع بعد النتائج وكم ينزل
"""

import yfinance as yf
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@st.cache_data(ttl=86400, show_spinner=False)
def get_earnings_history(ticker, max_events=12):
    """
    Get past earnings dates and price reactions.

    Returns: list of {
        date, price_before_5d, price_on_day, price_after_1d, price_after_5d,
        return_pre_5d, return_post_1d, return_post_5d,
        gap_pct (overnight gap), volume_ratio
    }
    """
    try:
        t = yf.Ticker(ticker)

        # Get earnings dates
        ed = t.earnings_dates
        if ed is None or ed.empty:
            return []

        # Get price history
        df = t.history(period="max", interval="1d")
        if df is None or df.empty or len(df) < 30:
            return []

        results = []
        now = datetime.now()
        past_dates = []
        for d in ed.index:
            try:
                d_naive = d.tz_localize(None) if hasattr(d, 'tz_localize') and d.tzinfo else d
                if d_naive <= now:
                    past_dates.append(d)
            except Exception:
                pass

        for earn_dt in past_dates[:max_events]:
            try:
                # Normalize datetime
                if hasattr(earn_dt, 'tz_localize'):
                    earn_naive = earn_dt.tz_localize(None) if earn_dt.tzinfo else earn_dt
                else:
                    earn_naive = earn_dt

                if earn_naive > datetime.now():
                    continue

                # Find nearest trading days
                df_naive = df.copy()
                df_naive.index = df_naive.index.tz_localize(None) if df_naive.index.tzinfo else df_naive.index

                # Day of/nearest to earnings
                mask_on = df_naive.index >= earn_naive - timedelta(days=3)
                mask_on2 = df_naive.index <= earn_naive + timedelta(days=3)
                candidates = df_naive.index[mask_on & mask_on2]
                if len(candidates) == 0:
                    continue

                # Find closest date
                idx_on = min(candidates, key=lambda x: abs((x - earn_naive).total_seconds()))
                pos = df_naive.index.get_loc(idx_on)

                # Need at least 5 bars before and 10 after
                if pos < 5 or pos >= len(df_naive) - 10:
                    continue

                p_before_5d = float(df_naive.iloc[pos - 5]["Close"])
                p_before_1d = float(df_naive.iloc[pos - 1]["Close"])
                p_on_day = float(df_naive.iloc[pos]["Close"])
                p_after_1d = float(df_naive.iloc[pos + 1]["Close"])
                p_after_5d = float(df_naive.iloc[pos + 5]["Close"])
                p_after_10d = float(df_naive.iloc[min(pos + 10, len(df_naive) - 1)]["Close"])

                # Volume ratio
                vol_on = float(df_naive.iloc[pos]["Volume"])
                vol_avg = float(df_naive.iloc[max(0, pos - 20):pos]["Volume"].mean())
                vol_ratio = round(vol_on / vol_avg, 1) if vol_avg > 0 else 1.0

                # Gap (overnight)
                p_prev_close = float(df_naive.iloc[pos - 1]["Close"])
                p_open = float(df_naive.iloc[pos]["Open"])
                gap_pct = round((p_open - p_prev_close) / p_prev_close * 100, 2)

                results.append({
                    "date": idx_on.strftime("%Y-%m-%d"),
                    "price_before_5d": round(p_before_5d, 2),
                    "price_before_1d": round(p_before_1d, 2),
                    "price_on_day": round(p_on_day, 2),
                    "price_after_1d": round(p_after_1d, 2),
                    "price_after_5d": round(p_after_5d, 2),
                    "price_after_10d": round(p_after_10d, 2),
                    "return_pre_5d": round((p_on_day - p_before_5d) / p_before_5d * 100, 2),
                    "return_pre_1d": round((p_on_day - p_before_1d) / p_before_1d * 100, 2),
                    "return_post_1d": round((p_after_1d - p_on_day) / p_on_day * 100, 2),
                    "return_post_5d": round((p_after_5d - p_on_day) / p_on_day * 100, 2),
                    "return_post_10d": round((p_after_10d - p_on_day) / p_on_day * 100, 2),
                    "gap_pct": gap_pct,
                    "volume_ratio": vol_ratio,
                    "pre_accum": p_on_day > p_before_5d,  # Was price rising before?
                })

            except Exception:
                continue

        return results

    except Exception:
        return []


def compute_earnings_stats(earnings_history):
    """
    Compute aggregate stats from earnings history.

    Returns: {
        total, rose_after, fell_after, avg_post_1d, avg_post_5d,
        avg_pre_5d, avg_gap, avg_volume_ratio,
        pre_accum_win_rate, no_accum_win_rate
    }
    """
    if not earnings_history:
        return None

    n = len(earnings_history)
    post_1d = [e["return_post_1d"] for e in earnings_history]
    post_5d = [e["return_post_5d"] for e in earnings_history]
    post_10d = [e["return_post_10d"] for e in earnings_history]
    pre_5d = [e["return_pre_5d"] for e in earnings_history]
    gaps = [e["gap_pct"] for e in earnings_history]
    vols = [e["volume_ratio"] for e in earnings_history]

    rose_1d = sum(1 for r in post_1d if r > 0)
    fell_1d = sum(1 for r in post_1d if r < 0)
    rose_5d = sum(1 for r in post_5d if r > 0)
    fell_5d = sum(1 for r in post_5d if r < 0)

    # Pre-accumulation analysis
    with_accum = [e for e in earnings_history if e["pre_accum"]]
    without_accum = [e for e in earnings_history if not e["pre_accum"]]

    accum_win_rate = 0
    no_accum_win_rate = 0
    if with_accum:
        accum_win_rate = round(sum(1 for e in with_accum if e["return_post_5d"] > 0) / len(with_accum) * 100, 1)
    if without_accum:
        no_accum_win_rate = round(sum(1 for e in without_accum if e["return_post_5d"] > 0) / len(without_accum) * 100, 1)

    return {
        "total": n,
        "rose_1d": rose_1d,
        "fell_1d": fell_1d,
        "rose_5d": rose_5d,
        "fell_5d": fell_5d,
        "win_rate_1d": round(rose_1d / n * 100, 1) if n else 0,
        "win_rate_5d": round(rose_5d / n * 100, 1) if n else 0,
        "avg_post_1d": round(float(np.mean(post_1d)), 2),
        "avg_post_5d": round(float(np.mean(post_5d)), 2),
        "avg_post_10d": round(float(np.mean(post_10d)), 2),
        "avg_pre_5d": round(float(np.mean(pre_5d)), 2),
        "avg_gap": round(float(np.mean(gaps)), 2),
        "avg_volume_ratio": round(float(np.mean(vols)), 1),
        "best_post_5d": round(max(post_5d), 2),
        "worst_post_5d": round(min(post_5d), 2),
        "pre_accum_count": len(with_accum),
        "pre_accum_win_rate": accum_win_rate,
        "no_accum_count": len(without_accum),
        "no_accum_win_rate": no_accum_win_rate,
    }


def get_market_earnings_stats(tickers, max_per_stock=8):
    """
    Get earnings stats for multiple stocks.
    Returns: {ticker: {history, stats}}
    """
    all_stats = {}
    for tk in tickers:
        history = get_earnings_history(tk, max_events=max_per_stock)
        if history and len(history) >= 3:
            stats = compute_earnings_stats(history)
            all_stats[tk] = {
                "history": history,
                "stats": stats,
            }
    return all_stats
