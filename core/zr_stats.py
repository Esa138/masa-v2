"""
MASA QUANT — ZR (Zero Reflection) Breakout Statistics
Historical backtest of every ZR breakout over multiple years.

Detection: Price closes above ZR ceiling (zr_high) for the first time.
Outcomes: 5d / 10d / 20d forward returns.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings('ignore')


def backtest_ticker_zr(ticker: str, period: str = "5y") -> list:
    """Find all ZR breakouts for a ticker. Returns list of events with outcomes."""
    try:
        from core.indicators import compute_zero_reflection
        data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if data is None or data.empty or len(data) < 250:
            return []
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        high, low, close = data['High'], data['Low'], data['Close']
        events = []

        for i in range(250, len(close) - 25):
            past_high = high.iloc[:i+1]
            past_low = low.iloc[:i+1]
            zr_high, zr_low = compute_zero_reflection(past_high, past_low, bars=400, confirm_len=25)

            if pd.isna(zr_high) or zr_high == 0:
                continue

            cur = float(close.iloc[i])
            prev = float(close.iloc[i-1])

            if cur > zr_high and prev <= zr_high:
                p5 = float(close.iloc[min(i+5, len(close)-1)])
                p10 = float(close.iloc[min(i+10, len(close)-1)])
                p20 = float(close.iloc[min(i+20, len(close)-1)])
                events.append({
                    'ticker': ticker,
                    'date': close.index[i].strftime('%Y-%m-%d'),
                    'breakout_price': round(cur, 2),
                    'zr_high': round(zr_high, 2),
                    'breakout_pct': round((cur / zr_high - 1) * 100, 2),
                    'ret_5d': round((p5 / cur - 1) * 100, 2),
                    'ret_10d': round((p10 / cur - 1) * 100, 2),
                    'ret_20d': round((p20 / cur - 1) * 100, 2),
                    'win_5d': p5 > cur,
                    'win_10d': p10 > cur,
                    'win_20d': p20 > cur,
                })
        return events
    except Exception:
        return []


def run_zr_backtest(tickers: list, period: str = "5y", max_workers: int = 6,
                    progress_callback=None) -> pd.DataFrame:
    """Run ZR backtest on multiple tickers in parallel."""
    all_events = []
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(backtest_ticker_zr, t, period): t for t in tickers}
        for f in as_completed(futs):
            try:
                evs = f.result()
                all_events.extend(evs)
            except Exception:
                pass
            completed += 1
            if progress_callback:
                progress_callback(completed, len(tickers), len(all_events))

    if not all_events:
        return pd.DataFrame()

    df = pd.DataFrame(all_events)
    return df


def aggregate_stats(df: pd.DataFrame) -> dict:
    """Aggregate ZR breakout statistics."""
    if df.empty:
        return {}

    stats = {'total': len(df), 'periods': {}}
    for period in ['5d', '10d', '20d']:
        win_col = f'win_{period}'
        ret_col = f'ret_{period}'
        wins = int(df[win_col].sum())
        losses = len(df) - wins
        gains = df[df[ret_col] > 0][ret_col].sum()
        losses_sum = abs(df[df[ret_col] < 0][ret_col].sum())
        pf = round(gains / losses_sum, 2) if losses_sum > 0.01 else 0

        stats['periods'][period] = {
            'win_rate': round(df[win_col].mean() * 100, 1),
            'avg_return': round(df[ret_col].mean(), 2),
            'median_return': round(df[ret_col].median(), 2),
            'best': round(df[ret_col].max(), 2),
            'worst': round(df[ret_col].min(), 2),
            'std': round(df[ret_col].std(), 2),
            'wins': wins,
            'losses': losses,
            'profit_factor': pf,
        }

    return stats


def stats_by_sector(df: pd.DataFrame, period: str = "20d", min_n: int = 5) -> list:
    """Sector-level breakdown."""
    if df.empty or 'sector' not in df.columns:
        return []
    win_col = f'win_{period}'
    ret_col = f'ret_{period}'
    grp = df.groupby('sector')
    rows = []
    for sec, g in grp:
        if len(g) < min_n:
            continue
        rows.append({
            'sector': str(sec),
            'n': len(g),
            'win_rate': round(g[win_col].mean() * 100, 1),
            'avg_return': round(g[ret_col].mean(), 2),
            'best': round(g[ret_col].max(), 2),
            'worst': round(g[ret_col].min(), 2),
        })
    return sorted(rows, key=lambda x: -x['win_rate'])


def stats_by_magnitude(df: pd.DataFrame, period: str = "20d") -> list:
    """Stats by breakout magnitude bins."""
    if df.empty:
        return []
    df = df.copy()
    df['mag_bin'] = pd.cut(df['breakout_pct'], [0, 1, 3, 5, 100],
                           labels=['<1%', '1-3%', '3-5%', '5%+'])
    win_col = f'win_{period}'
    ret_col = f'ret_{period}'
    rows = []
    for mag, g in df.groupby('mag_bin', observed=True):
        if len(g) == 0:
            continue
        rows.append({
            'magnitude': str(mag),
            'n': len(g),
            'win_rate': round(g[win_col].mean() * 100, 1),
            'avg_return': round(g[ret_col].mean(), 2),
        })
    return rows


def stats_by_year(df: pd.DataFrame, period: str = "20d") -> list:
    """Stats by year."""
    if df.empty:
        return []
    df = df.copy()
    df['year'] = pd.to_datetime(df['date']).dt.year
    win_col = f'win_{period}'
    ret_col = f'ret_{period}'
    rows = []
    for yr, g in df.groupby('year'):
        rows.append({
            'year': int(yr),
            'n': len(g),
            'win_rate': round(g[win_col].mean() * 100, 1),
            'avg_return': round(g[ret_col].mean(), 2),
        })
    return sorted(rows, key=lambda x: x['year'])
