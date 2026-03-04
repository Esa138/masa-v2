"""
MASA QUANT V95 — Wolf V2 Breakout Detection (Smart Filters)
Detects institutional momentum breakouts using 9 weighted filters.
Soft-pass system: allows 1 weak filter (weight <= 1) to fail.
All indicators are pre-computed in scanner.py — this module is pure logic.
"""

import pandas as pd
import numpy as np

# ── Wolf V2 Configuration ──────────────────────────────────────
WOLF_MIN_CHANGE = 2.0       # Filter 1: Min daily change %
WOLF_MIN_RVOL = 0.35        # Filter 2: Min volume acceleration
WOLF_RSI_MAX = 72           # Filter 4: RSI overbought cap
WOLF_MOM_MIN = 50           # Filter 8: Min momentum score
WOLF_SL_CAP = 0.08          # 8% max loss cap on stop-loss
WOLF_MIN_RR = 1.5           # Min R:R ratio or signal rejected

# ── Filter Weights ────────────────────────────────────────────
# Weight 3 = critical (blocks soft pass)
# Weight 2 = important (blocks soft pass)
# Weight 1 = soft (can be bypassed if only 1 fails)
FILTER_WEIGHTS = {
    "التغير اليومي ≥ 2%":    3,   # Critical
    "تسارع السيولة ≥ 0.35":  2,   # Important
    "درع الماكرو":           3,   # Critical
    "RSI ≤ 72":              1,   # Soft
    "السعر ≥ VWAP":          1,   # Soft
    "فوق MA50":              2,   # Important
    "لا مقاومة زيرو":        1,   # Soft
    "الزخم ≥ 50":            2,   # Important
    "ترند 5 أيام إيجابي":    1,   # Soft
}


def detect_wolf_signal(data: dict) -> tuple:
    """
    Evaluate Wolf V2 breakout criteria against pre-computed indicators.
    Now with weighted soft-pass system.

    Parameters:
        data: dict with keys:
            - last_close, pct_1d, pct_5d, vol_accel_ratio, vol_ratio,
              macro_status, is_forex, rsi, last_vwap, ma50,
              zr_high, momentum_score, last_atr

    Returns:
        (is_wolf: bool, wolf_details: dict)
        wolf_details includes: is_soft_pass (True if 8/9 soft pass)
    """
    last_close = data.get("last_close", 0)
    pct_1d = data.get("pct_1d", 0)
    pct_5d = data.get("pct_5d", 0)
    vol_accel = data.get("vol_accel_ratio", 0)
    macro = data.get("macro_status", "")
    is_forex = data.get("is_forex", False)
    rsi = data.get("rsi", 50)
    last_vwap = data.get("last_vwap", None)
    ma50 = data.get("ma50", None)
    zr_high = data.get("zr_high", None)
    mom_score = data.get("momentum_score", 0)
    last_atr = data.get("last_atr", 0)

    if last_close <= 0:
        return False, _empty_details()

    # ── 9 Sequential Filters (with weights) ───────────────────
    filters = []

    # Filter 1: Daily Change >= 2% (weight 3 - critical)
    f1 = pct_1d >= WOLF_MIN_CHANGE
    filters.append(("التغير اليومي ≥ 2%", f1))

    # Filter 2: Volume Acceleration >= 0.35 (weight 2)
    f2 = vol_accel >= WOLF_MIN_RVOL
    filters.append(("تسارع السيولة ≥ 0.35", f2))

    # Filter 3: Macro Shield (weight 3 - critical)
    f3 = is_forex or (macro != "سلبي ⛈️")
    filters.append(("درع الماكرو", f3))

    # Filter 4: RSI <= 72 (weight 1 - soft)
    f4 = pd.isna(rsi) or rsi <= WOLF_RSI_MAX
    filters.append(("RSI ≤ 72", f4))

    # Filter 5: Price >= VWAP (weight 1 - soft)
    f5 = pd.isna(last_vwap) or last_close >= last_vwap
    filters.append(("السعر ≥ VWAP", f5))

    # Filter 6: Price > MA50 (weight 2)
    f6 = pd.isna(ma50) or last_close > ma50
    filters.append(("فوق MA50", f6))

    # Filter 7: Not at ZR ceiling (weight 1 - soft)
    f7 = True
    if pd.notna(zr_high) and zr_high > 0:
        if last_close >= zr_high * 0.98 and last_close <= zr_high:
            f7 = False
    filters.append(("لا مقاومة زيرو", f7))

    # Filter 8: Momentum >= 50 (weight 2)
    f8 = mom_score >= WOLF_MOM_MIN
    filters.append(("الزخم ≥ 50", f8))

    # Filter 9: 5-day trend positive (weight 1 - soft)
    f9 = pd.isna(pct_5d) or pct_5d >= 0
    filters.append(("ترند 5 أيام إيجابي", f9))

    filters_count = sum(1 for _, passed in filters if passed)
    all_passed = all(passed for _, passed in filters)

    # ── Soft-Pass Logic ───────────────────────────────────────
    is_soft_pass = False
    failed_filters = [(name, passed) for name, passed in filters if not passed]
    num_failed = len(failed_filters)

    if not all_passed:
        # Check for soft-pass: exactly 1 failure with weight <= 1
        if num_failed == 1:
            failed_name = failed_filters[0][0]
            failed_weight = FILTER_WEIGHTS.get(failed_name, 3)
            if failed_weight <= 1:
                # Soft-pass allowed!
                is_soft_pass = True
                all_passed = True  # Override to continue

    if not all_passed:
        return False, {
            "wolf_sl": 0,
            "wolf_target": 0,
            "wolf_rr": 0,
            "filters_passed": filters,
            "filters_count": filters_count,
            "is_soft_pass": False,
            "reject_reason": next(
                (name for name, passed in filters if not passed),
                "Unknown"
            ),
        }

    # ── Compute Wolf SL/TP ─────────────────────────────────────

    # ATR-based SL with 8% max loss cap
    if pd.isna(last_atr) or last_atr <= 0:
        last_atr = last_close * 0.02

    wolf_sl = last_close - (last_atr * 1.5)
    wolf_sl = max(wolf_sl, last_close * (1 - WOLF_SL_CAP))
    if wolf_sl >= last_close:
        wolf_sl = last_close * 0.97

    risk = max(last_close - wolf_sl, last_close * 0.02)

    # Target: Blue sky → 3:1, Normal → 2:1 or ZR high
    is_blue_sky = pd.notna(zr_high) and last_close > zr_high
    if is_blue_sky:
        wolf_target = last_close + (risk * 3.0)
    elif pd.notna(zr_high) and zr_high > last_close:
        wolf_target = max(zr_high, last_close + (risk * 2.0))
    else:
        wolf_target = last_close + (risk * 2.0)

    wolf_rr = (wolf_target - last_close) / risk if risk > 0 else 0

    # R:R Veto: must be >= 1.5
    if wolf_rr < WOLF_MIN_RR:
        return False, {
            "wolf_sl": wolf_sl,
            "wolf_target": wolf_target,
            "wolf_rr": wolf_rr,
            "filters_passed": filters,
            "filters_count": filters_count,
            "is_soft_pass": False,
            "reject_reason": f"R:R ({wolf_rr:.1f}) < {WOLF_MIN_RR}",
        }

    return True, {
        "wolf_sl": wolf_sl,
        "wolf_target": wolf_target,
        "wolf_rr": round(wolf_rr, 2),
        "filters_passed": filters,
        "filters_count": filters_count,
        "is_soft_pass": is_soft_pass,
        "reject_reason": None,
    }


def classify_wolf_signal(is_wolf: bool, masa_score: int) -> str:
    """
    Classify wolf signal type based on MASA score crossover.
    - 'مؤكد' = MASA×Wolf cross-confirmed (masa_score >= 60)
    - 'فقط' = Wolf-only momentum breakout
    - '' = not a wolf signal
    """
    if not is_wolf:
        return ""
    if masa_score >= 60:
        return "مؤكد"
    return "فقط"


def _empty_details() -> dict:
    """Return empty wolf details for invalid data."""
    return {
        "wolf_sl": 0,
        "wolf_target": 0,
        "wolf_rr": 0,
        "filters_passed": [],
        "filters_count": 0,
        "is_soft_pass": False,
        "reject_reason": "Invalid data",
    }
