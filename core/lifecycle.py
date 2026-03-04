"""
MASA QUANT V95 — Accumulation Lifecycle Engine (محرك دورة الحياة)
Tracks the full accumulation-breakout-pullback cycle per ticker.

Solves the "blind spot" problem: after a stock breaks out from late accumulation
and pulls back, the raw phase detection still shows "late" because CMF/OBV remain
positive. This engine adds memory — it knows the stock ALREADY launched.

Lifecycle states:
  neutral/early/mid/strong/late  →  pass-through from detect_accumulation_phase()
  breakout                       →  price rose ≥ threshold since entering "late"
  pullback_buy                   →  healthy retest (CMF+, pullback < 50%)
  pullback_wait                  →  uncertain pullback (CMF weak or too deep)
  exhausted                      →  gave back ≥ 75% of the move — opportunity gone
"""

import pandas as pd
import numpy as np


def apply_lifecycle(
    close: pd.Series,
    phase: pd.Series,
    cmf: pd.Series,
    obv_slope: pd.Series,
    atr_last: float = 0.0,
    breakout_pct: float = 0.10,
    healthy_max_retracement: float = 0.50,
    exhaustion_retracement: float = 0.75,
    zr_high: pd.Series = None,
) -> tuple:
    """
    Walk the phase series and overlay lifecycle states.

    Parameters:
        close:       daily close prices
        phase:       raw accumulation phase from detect_accumulation_phase()
        cmf:         Chaikin Money Flow series
        obv_slope:   OBV linear slope series
        atr_last:    last ATR value (for adaptive threshold)
        breakout_pct: min % gain from late-entry to declare breakout (default 10%)
        healthy_max_retracement: max retracement to still be "healthy" (default 50%)
        exhaustion_retracement: retracement level = exhausted (default 75%)
        zr_high:     Zero Reflection High series (preferred breakout reference)

    Returns:
        tuple: (lifecycle_phases: pd.Series, metadata: dict)
        The metadata uses the SAME entry/peak tracked by the forward walk,
        so there is no mismatch between phase classification and display.

    Breakout detection priority:
        1. ZR High: if price crosses above ZR High → breakout (real resistance break)
        2. ATR %:   if no ZR High available → fallback to % gain from entry
    """
    result = phase.copy()
    n = len(close)

    # Default metadata
    meta = {
        "lifecycle_phase": phase.iloc[-1] if n > 0 else "neutral",
        "is_post_breakout": False,
        "late_entry_price": 0.0,
        "breakout_price": 0.0,
        "peak_price": 0.0,
        "peak_gain_pct": 0.0,
        "current_retracement": 0.0,
        "bars_since_breakout": 0,
        "accum_start_date": "",
        "breakout_date": "",
        "peak_date": "",
    }

    if n < 5:
        return result, meta

    # ── Adaptive breakout threshold ────────────────────────
    # Use ATR-based threshold if available, bounded [5%, 18%]
    if atr_last > 0 and close.iloc[-1] > 0:
        atr_pct = (atr_last * 3) / close.iloc[-1]
        breakout_threshold = max(0.05, min(0.18, atr_pct))
    else:
        breakout_threshold = breakout_pct

    # ── State machine variables ────────────────────────────
    state = "raw"               # "raw" = pass-through, "tracking" = watching breakout
    late_entry_price = 0.0
    late_entry_bar = -1
    peak_price = 0.0
    peak_bar = -1
    first_breakout_bar = -1
    breakout_price = 0.0        # price at first breakout bar (actual entry for traders)

    for i in range(n):
        raw = phase.iloc[i]
        c = close.iloc[i]

        if state == "raw":
            # ── Looking for entry into "late" or "strong" phase ──
            # Track from "strong" too, since real accumulation starts there
            if raw in ("late", "strong"):
                if i == 0 or phase.iloc[i - 1] not in ("late", "strong"):
                    # Fresh entry into accumulation zone
                    late_entry_price = c
                    late_entry_bar = i
                    peak_price = c
                    peak_bar = i
                    state = "tracking"
                elif late_entry_price <= 0:
                    # Already in accumulation from the start of the series
                    late_entry_price = c
                    late_entry_bar = i
                    peak_price = c
                    peak_bar = i
                    state = "tracking"

        elif state == "tracking":
            # ── Track peak price ──────────────────────────
            if c > peak_price:
                peak_price = c
                peak_bar = i

            # ── Check for breakout ────────────────────────
            # Priority 1: ZR High crossing (real resistance break)
            # Priority 2: ATR % gain from entry (fallback)
            zr_h_val = np.nan
            if zr_high is not None and i < len(zr_high):
                zr_h_val = zr_high.iloc[i]

            gain = (peak_price - late_entry_price) / late_entry_price if late_entry_price > 0 else 0

            is_breakout = False
            if pd.notna(zr_h_val) and zr_h_val > 0:
                # ZR High available → breakout = price above ZR High
                is_breakout = c > zr_h_val
            else:
                # No ZR High → fallback to ATR percentage
                is_breakout = gain >= breakout_threshold

            if is_breakout:
                # Record first breakout bar + price
                if first_breakout_bar < 0:
                    first_breakout_bar = i
                    breakout_price = c

                # Breakout confirmed! Now classify current position
                retracement = (peak_price - c) / (peak_price - late_entry_price) if peak_price > late_entry_price else 0

                if c >= peak_price * 0.98:
                    # Still near peak — active breakout
                    result.iloc[i] = "breakout"

                elif retracement >= exhaustion_retracement:
                    # Gave back 75%+ of the move
                    result.iloc[i] = "exhausted"

                elif retracement < healthy_max_retracement:
                    # Pulled back less than 50% — check health
                    cmf_ok = cmf.iloc[i] > 0
                    obv_ok = obv_slope.iloc[i] > -0.001
                    if cmf_ok and obv_ok:
                        result.iloc[i] = "pullback_buy"
                    else:
                        result.iloc[i] = "pullback_wait"

                else:
                    # Between 50%-75% — uncertain
                    result.iloc[i] = "pullback_wait"

            else:
                # Not yet broken out — keep raw phase
                # But if phase dropped to non-accumulation, reset
                if raw in ("neutral", "distribute"):
                    state = "raw"
                    late_entry_price = 0.0
                    peak_price = 0.0
                    first_breakout_bar = -1
                    breakout_price = 0.0

            # ── Reset conditions ──────────────────────────
            # If price dropped BELOW late entry price → thesis failed
            if c < late_entry_price * 0.95:
                state = "raw"
                late_entry_price = 0.0
                peak_price = 0.0
                first_breakout_bar = -1
                breakout_price = 0.0
                result.iloc[i] = raw  # Revert to raw phase

            # If raw phase is "distribute" for this bar → reset
            if raw == "distribute":
                state = "raw"
                late_entry_price = 0.0
                peak_price = 0.0
                first_breakout_bar = -1
                breakout_price = 0.0
                result.iloc[i] = "distribute"  # Keep distribute

    # ── Build metadata from the SAME state machine ─────────
    final_phase = result.iloc[-1]
    is_post = final_phase in ("breakout", "pullback_buy", "pullback_wait", "exhausted")

    # ── Extract dates from the index (always, not just post-breakout) ──
    _accum_start_date = ""
    _breakout_date = ""
    _peak_date = ""
    try:
        idx = close.index
        if late_entry_bar >= 0 and late_entry_bar < n:
            _accum_start_date = str(idx[late_entry_bar])[:10]
        if first_breakout_bar >= 0 and first_breakout_bar < n:
            _breakout_date = str(idx[first_breakout_bar])[:10]
        if peak_bar >= 0 and peak_bar < n:
            _peak_date = str(idx[peak_bar])[:10]
    except Exception:
        pass

    if is_post and late_entry_price > 0:
        current_price = close.iloc[-1]
        peak_gain = (peak_price - late_entry_price) / late_entry_price if late_entry_price > 0 else 0
        retracement = (peak_price - current_price) / (peak_price - late_entry_price) if peak_price > late_entry_price else 0

        meta = {
            "lifecycle_phase": final_phase,
            "is_post_breakout": True,
            "late_entry_price": round(late_entry_price, 4),
            "breakout_price": round(breakout_price, 4),
            "peak_price": round(peak_price, 4),
            "peak_gain_pct": round(peak_gain * 100, 1),
            "current_retracement": round(max(0, min(1, retracement)), 2),
            "bars_since_breakout": max(0, n - 1 - first_breakout_bar) if first_breakout_bar >= 0 else 0,
            "accum_start_date": _accum_start_date,
            "breakout_date": _breakout_date,
            "peak_date": _peak_date,
        }
    else:
        # ── Pre-breakout: still return tracking data ──────
        meta["lifecycle_phase"] = final_phase
        if late_entry_price > 0:
            meta["late_entry_price"] = round(late_entry_price, 4)
            meta["accum_start_date"] = _accum_start_date

    return result, meta
