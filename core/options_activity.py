"""
Options activity analysis from free yfinance chains (US tickers).

Not real-time "flow" (sweeps/blocks need paid feeds like Barchart
Premier) — but daily aggregated volume/OI/IV covers the directional
bias signal: Call/Put ratio + unusual-volume detection.
"""
import time
from typing import Optional, Dict

import pandas as pd
import yfinance as yf


# Bias thresholds on the call/put volume ratio
CALL_BIAS_MIN = 1.3
PUT_BIAS_MAX = 0.7
# A contract is "unusual" when today's volume dwarfs standing OI
UNUSUAL_VOL_OI = 2.0
UNUSUAL_MIN_VOL = 100


def get_options_activity(ticker: str, max_expirations: int = 2) -> Optional[Dict]:
    """
    Aggregate options activity for a US ticker across the nearest
    expirations. Returns None when the ticker has no listed options.

    Returns dict:
      call_vol, put_vol, cp_ratio, bias ('call'/'put'/'neutral'),
      unusual_calls, unusual_puts  (counts),
      top_calls, top_puts          (list of {strike, volume, oi, iv}),
      expirations                  (list of str)
    """
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            return None
        exps = list(exps[:max_expirations])

        all_calls, all_puts = [], []
        for exp in exps:
            try:
                chain = t.option_chain(exp)
                all_calls.append(chain.calls)
                all_puts.append(chain.puts)
            except Exception:
                continue
        if not all_calls and not all_puts:
            return None

        calls = pd.concat(all_calls, ignore_index=True) if all_calls else pd.DataFrame()
        puts = pd.concat(all_puts, ignore_index=True) if all_puts else pd.DataFrame()

        def _vol(df):
            return float(df['volume'].fillna(0).sum()) if not df.empty else 0.0

        call_vol, put_vol = _vol(calls), _vol(puts)
        cp_ratio = call_vol / put_vol if put_vol > 0 else (99.0 if call_vol > 0 else 1.0)

        if cp_ratio >= CALL_BIAS_MIN:
            bias = 'call'
        elif cp_ratio <= PUT_BIAS_MAX:
            bias = 'put'
        else:
            bias = 'neutral'

        def _unusual(df):
            if df.empty:
                return 0
            v = df['volume'].fillna(0)
            oi = df['openInterest'].fillna(0).replace(0, 1)
            return int(((v >= UNUSUAL_MIN_VOL) & (v / oi >= UNUSUAL_VOL_OI)).sum())

        def _top(df, n=3):
            if df.empty:
                return []
            top = df.nlargest(n, 'volume')
            return [
                {
                    'strike': float(r['strike']),
                    'volume': int(r['volume'] or 0),
                    'oi': int(r['openInterest'] or 0),
                    'iv': round(float(r['impliedVolatility'] or 0) * 100, 1),
                }
                for _, r in top.iterrows()
            ]

        return {
            'call_vol': int(call_vol),
            'put_vol': int(put_vol),
            'cp_ratio': round(cp_ratio, 2),
            'bias': bias,
            'unusual_calls': _unusual(calls),
            'unusual_puts': _unusual(puts),
            'top_calls': _top(calls),
            'top_puts': _top(puts),
            'expirations': exps,
        }
    except Exception:
        return None


def bias_label(activity: Optional[Dict]) -> str:
    """Compact table label, e.g. '🟢 C/P 1.8 ⚡2'."""
    if not activity:
        return '—'
    icon = {'call': '🟢', 'put': '🔴', 'neutral': '⚪'}[activity['bias']]
    label = f"{icon} C/P {activity['cp_ratio']}"
    unusual = activity['unusual_calls'] + activity['unusual_puts']
    if unusual:
        label += f" ⚡{unusual}"
    return label


def fetch_activity_batch(tickers: list, cache: dict, ttl_sec: int = 600,
                          max_workers: int = 10) -> dict:
    """
    Fetch options activity for many tickers in parallel, reusing
    `cache` entries younger than ttl_sec. Mutates and returns cache.
    Cache shape: {ticker: (unix_ts, activity_dict_or_None)}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    now = time.time()
    stale = [tk for tk in tickers
             if tk not in cache or (now - cache[tk][0]) > ttl_sec]

    if stale:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(get_options_activity, tk): tk for tk in stale}
            for fut in as_completed(futures):
                tk = futures[fut]
                try:
                    cache[tk] = (now, fut.result())
                except Exception:
                    cache[tk] = (now, None)

    return cache
