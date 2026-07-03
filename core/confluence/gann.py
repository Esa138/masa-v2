"""
Gann Box — price & time analysis anchored to confirmed pivots.

Mirrors the user's Pine v7.5 logic:
- Anchors: highest confirmed pivot-high and lowest confirmed pivot-low
  in the lookback window (pivot strength = bars each side).
- Price levels: fib fractions of the swing (25/38.2/50/61.8/75) plus
  extensions 138.2/161.8 used as targets after a break.
- Time: the swing duration (bars between the two anchors) projected
  forward at 50/61.8/100/138.2/161.8/200% from the later anchor —
  dates where reversals statistically cluster (Gann's square).
"""
from dataclasses import dataclass, field
from typing import Optional, List

import numpy as np
import pandas as pd

from .zero_reversal import find_pivots

# Price retracement fractions inside the box (gold = 50 / 61.8)
GANN_LEVELS = [0.25, 0.382, 0.5, 0.618, 0.75]
GOLD_LEVELS = {0.5, 0.618}
# Extension fractions for targets after a box break
GANN_EXTENSIONS = [1.382, 1.618]
# Time projection fractions of the swing duration
TIME_FRACTIONS = [0.5, 0.618, 1.0, 1.382, 1.618, 2.0]
GOLD_TIME = {0.5, 0.618}


@dataclass
class GannBox:
    low: float                 # box bottom (anchor pivot low)
    high: float                # box top (anchor pivot high)
    low_idx: int               # bar index of the low anchor
    high_idx: int              # bar index of the high anchor
    direction: str             # 'up' = low came first (upswing), 'down' otherwise
    levels: dict = field(default_factory=dict)       # {fraction: price}
    extensions: dict = field(default_factory=dict)   # {fraction: price}
    position_pct: float = 0.0  # current price position inside box (0-100+)
    exhausted: bool = False    # price passed the 161.8% extension
    time_windows: List[dict] = field(default_factory=list)  # projections
    active_time_window: Optional[dict] = None  # window within ±tolerance now


def compute_gann_box(df: pd.DataFrame, lookback: int = 200,
                     pivot_strength: int = 10,
                     time_tolerance_bars: int = 2) -> Optional[GannBox]:
    """
    Build the Gann box from the most significant confirmed swing in
    the lookback window. Returns None when the data is too short or
    no confirmed pivots exist.
    """
    if df is None or len(df) < pivot_strength * 2 + 5:
        return None

    window = df.tail(lookback)
    ph, pl = find_pivots(df, pivot_strength, pivot_strength)
    ph_w = ph.loc[window.index].dropna()
    pl_w = pl.loc[window.index].dropna()
    if ph_w.empty or pl_w.empty:
        return None

    # Anchors: extreme confirmed pivots in window
    high_price = float(ph_w.max())
    low_price = float(pl_w.min())
    if high_price <= low_price:
        return None
    high_ts = ph_w.idxmax()
    low_ts = pl_w.idxmin()
    # positional indices within the full df
    high_idx = int(df.index.get_loc(high_ts))
    low_idx = int(df.index.get_loc(low_ts))

    direction = 'up' if low_idx < high_idx else 'down'
    rng = high_price - low_price

    levels = {frac: low_price + rng * frac for frac in GANN_LEVELS}
    levels[0.0] = low_price
    levels[1.0] = high_price

    # Extensions in the direction of the swing
    if direction == 'up':
        extensions = {f: low_price + rng * f for f in GANN_EXTENSIONS}
    else:
        extensions = {f: high_price - rng * f for f in GANN_EXTENSIONS}

    current = float(df['close'].iloc[-1])
    position_pct = (current - low_price) / rng * 100 if rng > 0 else 0.0

    # Exhaustion: beyond the 161.8% extension in swing direction
    if direction == 'up':
        exhausted = current >= low_price + rng * 1.618
    else:
        exhausted = current <= high_price - rng * 1.618

    # ── Time projections ──
    duration = abs(high_idx - low_idx)
    swing_end = max(high_idx, low_idx)
    last_idx = len(df) - 1
    time_windows = []
    active = None
    if duration >= 3:
        for frac in TIME_FRACTIONS:
            target_idx = swing_end + int(round(duration * frac))
            bars_away = target_idx - last_idx
            try:
                # approximate date: extrapolate using median bar spacing
                if target_idx < len(df):
                    when = df.index[target_idx]
                else:
                    step = (df.index[-1] - df.index[0]) / max(1, len(df) - 1)
                    when = df.index[-1] + step * (target_idx - last_idx)
                when_str = str(when)[:10]  # date only — bar spacing is approximate
            except Exception:
                when_str = '—'
            w = {
                'fraction': frac,
                'is_gold': frac in GOLD_TIME,
                'bars_away': bars_away,
                'when': when_str,
            }
            time_windows.append(w)
            if abs(bars_away) <= time_tolerance_bars and active is None:
                active = w

    return GannBox(
        low=low_price, high=high_price,
        low_idx=low_idx, high_idx=high_idx,
        direction=direction,
        levels=levels, extensions=extensions,
        position_pct=round(position_pct, 1),
        exhausted=exhausted,
        time_windows=time_windows,
        active_time_window=active,
    )


def match_gann_level(zone_price: float, box: Optional[GannBox],
                     tolerance_pct: float = 1.0) -> Optional[str]:
    """
    Does a confluence-zone price coincide with a Gann level?
    Returns a label like '61.8% ⭐' / '50% ⭐' / '38.2%' or None.
    Gold levels get priority when several match.
    """
    if box is None or box.high <= box.low:
        return None
    tol = zone_price * tolerance_pct / 100
    best = None
    for frac, price in box.levels.items():
        if frac in (0.0, 1.0):
            continue
        if abs(zone_price - price) <= tol:
            label = f"{frac * 100:.1f}%".replace('.0%', '%')
            if frac in GOLD_LEVELS:
                return f"{label} ⭐"       # gold wins immediately
            best = best or label
    return best


def gann_targets(box: Optional[GannBox], side: str) -> list:
    """
    Profit targets for a signal. side='buy' → upward extensions,
    side='sell' → downward. Returns [(fraction, price), ...].
    """
    if box is None:
        return []
    rng = box.high - box.low
    if rng <= 0:
        return []
    if side == 'buy':
        return [(f, box.low + rng * f) for f in GANN_EXTENSIONS]
    return [(f, box.high - rng * f) for f in GANN_EXTENSIONS]
