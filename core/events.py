"""
MASA V2 — Event Classifier (Bounces, Breakouts, Breakdowns)
Classifies scanned stocks into events with strength scoring.
No new API calls — works entirely from existing scanner results.
"""

from datetime import datetime


def classify_events(results: list) -> dict:
    """
    Classify all scanned stocks into bounce/breakout/breakdown events.

    Args:
        results: List of dicts from scan_market()

    Returns:
        {"bounces": [...], "breakouts": [...], "breakdowns": [...]}
        Each item = original result dict + event_* fields
    """
    bounces = []
    breakouts = []
    breakdowns = []

    for r in results:
        phase = r.get("phase", "neutral")
        flow_bias = r.get("flow_bias", 0)
        location = r.get("location", "middle")
        change_pct = r.get("change_pct", 0)
        zr_status = r.get("zr_status", "normal")
        flow_type = r.get("flow_type", "none")
        cdv_trend = r.get("cdv_trend", "flat")
        volume_ratio = r.get("volume_ratio", 1.0)
        early_bounce = r.get("early_bounce", False)

        # ── Priority: breakout > bounce > breakdown ──
        # Check breakout first
        is_breakout, bo_label = _detect_breakout(
            zr_status, location, flow_bias, change_pct, phase, volume_ratio
        )
        if is_breakout:
            event = _build_event(r, "breakout", bo_label)
            breakouts.append(event)
            continue

        # Check bounce
        is_bounce, bn_label = _detect_bounce(
            early_bounce, zr_status, flow_bias, location, phase, change_pct, flow_type
        )
        if is_bounce:
            event = _build_event(r, "bounce", bn_label)
            bounces.append(event)
            continue

        # Check breakdown
        is_breakdown, bd_label = _detect_breakdown(
            phase, change_pct, flow_bias, location, cdv_trend, zr_status
        )
        if is_breakdown:
            event = _build_event(r, "breakdown", bd_label)
            breakdowns.append(event)
            continue

    # Sort each list by strength (strongest first)
    bounces.sort(key=lambda x: x["event_strength"], reverse=True)
    breakouts.sort(key=lambda x: x["event_strength"], reverse=True)
    breakdowns.sort(key=lambda x: x["event_strength"], reverse=True)

    return {"bounces": bounces, "breakouts": breakouts, "breakdowns": breakdowns}


# ── Detection Rules ──────────────────────────────────────────

def _detect_bounce(early_bounce, zr_status, flow_bias, location, phase, change_pct, flow_type):
    """Check if stock qualifies as a bounce event."""
    if early_bounce:
        return True, "⚡ ارتداد حاد من القاع"

    if zr_status == "zr_floor" and flow_bias > 0:
        return True, "ارتداد من قاع ZR"

    if location in ("bottom", "support") and phase in ("accumulation", "spring") and change_pct > 0:
        lbl = "سبرنق — كسر كاذب + ارتداد" if phase == "spring" else "ارتداد من منطقة دعم"
        return True, lbl

    if flow_type in ("bottom", "spring"):
        lbl = "سبرنق" if flow_type == "spring" else "ارتداد قاعي"
        return True, lbl

    return False, ""


def _detect_breakout(zr_status, location, flow_bias, change_pct, phase, volume_ratio):
    """Check if stock qualifies as a breakout event."""
    if zr_status == "zr_breakout":
        return True, "🚀 اختراق سقف ZR"

    if zr_status == "zr_bluesky":
        return True, "🔵 سماء زرقا — فوق ZR"

    if location == "above" and flow_bias > 15 and change_pct > 1:
        return True, "اختراق فوق القناة"

    if phase == "markup" and volume_ratio > 1.3 and change_pct > 2:
        return True, "اختراق بسيولة عالية"

    return False, ""


def _detect_breakdown(phase, change_pct, flow_bias, location, cdv_trend, zr_status):
    """Check if stock qualifies as a breakdown event."""
    if phase in ("markdown", "upthrust") and change_pct < -2:
        lbl = "أبثرست — كسر كاذب للقمة" if phase == "upthrust" else "كسر هابط مؤكد"
        return True, lbl

    if flow_bias < -30 and location in ("support", "bottom") and change_pct < -1:
        return True, "كسر دعم بتدفق بيعي"

    if phase == "distribution" and cdv_trend == "falling" and change_pct < -1.5:
        return True, "تصريف مع هبوط"

    if zr_status == "zr_floor" and flow_bias < -20 and change_pct < 0:
        return True, "فشل في الثبات عند قاع ZR"

    return False, ""


# ── Strength Scoring ─────────────────────────────────────────

def _score_event(r: dict, event_type: str) -> tuple:
    """
    Score event strength (0-100) using 7 weighted factors.
    Returns (score, factors_list).
    """
    phase = r.get("phase", "neutral")
    flow_bias = r.get("flow_bias", 0)
    volume_ratio = r.get("volume_ratio", 1.0)
    location = r.get("location", "middle")
    divergence = r.get("divergence", 0)
    absorption = r.get("absorption_score", 0)
    maturity_stage = r.get("maturity_stage", "none")
    dist_maturity_stage = r.get("dist_maturity_stage", "none")

    factors = []
    total = 0

    # 1. Order Flow Alignment (max 25)
    max_w = 25
    raw = min(abs(flow_bias), 60) / 60 * max_w
    # Penalize if flow opposes event direction
    if event_type in ("bounce", "breakout") and flow_bias < 0:
        raw *= 0.3
    elif event_type == "breakdown" and flow_bias > 0:
        raw *= 0.3
    s = round(raw)
    factors.append({"name": "أوردر فلو", "score": s, "max": max_w})
    total += s

    # 2. Volume Confirmation (max 20)
    max_w = 20
    vr = max(volume_ratio, 0)
    if vr <= 0.5:
        s = 0
    elif vr >= 2.0:
        s = max_w
    else:
        s = round((vr - 0.5) / 1.5 * max_w)
    factors.append({"name": "سيولة", "score": s, "max": max_w})
    total += s

    # 3. Phase Backing (max 20)
    max_w = 20
    if event_type in ("bounce", "breakout"):
        phase_scores = {
            "accumulation": 20, "spring": 20, "markup": 15,
            "transition": 8, "neutral": 5,
            "distribution": 0, "upthrust": 0, "markdown": 0,
        }
    else:  # breakdown
        phase_scores = {
            "distribution": 20, "markdown": 20, "upthrust": 18,
            "transition": 8, "neutral": 5,
            "accumulation": 0, "spring": 0, "markup": 0,
        }
    s = phase_scores.get(phase, 5)
    factors.append({"name": "دعم المرحلة", "score": s, "max": max_w})
    total += s

    # 4. Location Quality (max 10) — enhanced with Volume Profile
    max_w = 10
    if event_type == "bounce":
        loc_scores = {"bottom": 10, "support": 8, "middle": 4, "resistance": 1, "above": 0}
    elif event_type == "breakout":
        loc_scores = {"above": 10, "resistance": 7, "middle": 4, "support": 2, "bottom": 1}
    else:  # breakdown
        loc_scores = {"above": 10, "resistance": 8, "middle": 4, "support": 5, "bottom": 2}
    s = loc_scores.get(location, 4)

    # Volume Profile bonus/penalty
    vp_loc = r.get("vp_location", "none")
    if event_type in ("bounce", "breakout") and vp_loc in ("vol_support", "poc", "pivot_support"):
        s = min(s + 2, max_w)  # bonus for bouncing at volume support
    elif event_type in ("bounce", "breakout") and vp_loc in ("vol_resistance", "pivot_resistance"):
        s = max(s - 1, 0)  # penalty for bouncing into resistance
    elif event_type == "breakdown" and vp_loc in ("vol_gap", "vol_resistance"):
        s = min(s + 2, max_w)  # breakdown in volume gap = stronger

    factors.append({"name": "الموقع", "score": s, "max": max_w})
    total += s

    # 5. Divergence Signal (max 10)
    max_w = 10
    if event_type in ("bounce", "breakout"):
        s = round(min(max(divergence, 0), 40) / 40 * max_w)
    else:
        s = round(min(max(-divergence, 0), 40) / 40 * max_w)
    factors.append({"name": "دايفرجنس", "score": s, "max": max_w})
    total += s

    # 6. Absorption Score (max 10)
    max_w = 10
    s = min(round(absorption / 10), max_w)
    factors.append({"name": "امتصاص", "score": s, "max": max_w})
    total += s

    # 7. Maturity Stage (max 5)
    max_w = 5
    if event_type in ("bounce", "breakout"):
        m = maturity_stage
    else:
        m = dist_maturity_stage
    mat_scores = {"late": 5, "mid": 3, "early": 1, "none": 0}
    s = mat_scores.get(m, 0)
    factors.append({"name": "نضج", "score": s, "max": max_w})
    total += s

    return total, factors


# ── Event Date Detection ─────────────────────────────────────

def _find_event_date(r: dict, event_type: str) -> str:
    """
    Find the approximate date when the event started.
    - Bounce: date of the recent low (bottom before the bounce)
    - Breakout: date when price first crossed above ZR high
    - Breakdown: date when the decline streak started
    """
    chart_dates = r.get("chart_dates", [])
    chart_close = r.get("chart_close", [])
    chart_low = r.get("chart_low", [])

    if not chart_dates or not chart_close:
        return "—"

    n = len(chart_close)

    if event_type == "bounce":
        # Find the date of the lowest low in last 20 days = the bounce point
        lookback = min(20, n)
        lows = chart_low[-lookback:] if chart_low else chart_close[-lookback:]
        if lows:
            min_idx = 0
            min_val = lows[0]
            for i, v in enumerate(lows):
                if v <= min_val:
                    min_val = v
                    min_idx = i
            date_idx = n - lookback + min_idx
            if 0 <= date_idx < len(chart_dates):
                return chart_dates[date_idx]

    elif event_type == "breakout":
        # Find when price first crossed above ZR high (scan backwards)
        zr_high = r.get("zr_high", 0)
        if zr_high > 0 and n >= 2:
            for i in range(n - 1, 0, -1):
                if chart_close[i] > zr_high and chart_close[i - 1] <= zr_high:
                    return chart_dates[i]
            # If no crossover found, use maturity start date
            timeline = r.get("maturity_timeline", [])
            if timeline:
                return timeline[0].get("date", chart_dates[-1])

    elif event_type == "breakdown":
        # Find when the current decline streak started (scan backwards)
        if n >= 2:
            for i in range(n - 1, 0, -1):
                if chart_close[i - 1] >= chart_close[i]:
                    # Still declining, keep going back
                    continue
                else:
                    # Found the start of the decline
                    return chart_dates[i]

    # Fallback: use maturity timeline date or last date
    timeline = r.get("maturity_timeline", [])
    if timeline:
        return timeline[0].get("date", chart_dates[-1])

    return chart_dates[-1]


# ── Event Builder ────────────────────────────────────────────

def _build_event(r: dict, event_type: str, event_label: str) -> dict:
    """Augment a result dict with event classification fields."""
    strength, factors = _score_event(r, event_type)

    # Grade
    if strength >= 65:
        grade, grade_label, grade_color = "strong", "قوي", "#00E676"
    elif strength >= 40:
        grade, grade_label, grade_color = "moderate", "متوسط", "#FFD700"
    else:
        grade, grade_label, grade_color = "weak", "ضعيف", "#9ca3af"

    # Backing
    phase = r.get("phase", "neutral")
    if phase in ("accumulation", "spring"):
        backing, backing_label = "accumulation", "مدعوم بتجميع"
    elif phase in ("distribution", "upthrust", "markdown"):
        backing, backing_label = "distribution", "مدعوم بتصريف"
    else:
        backing, backing_label = "neutral", "بدون دعم واضح"

    # Event type display
    type_labels = {
        "bounce": ("⚡ ارتداد", "#00E676"),
        "breakout": ("🚀 اختراق", "#FFD700"),
        "breakdown": ("📉 كسر", "#FF5252"),
    }
    type_display, type_color = type_labels[event_type]

    # Date — find when the event actually started + scan time
    event_date = _find_event_date(r, event_type)
    scan_time = datetime.now().strftime("%H:%M")

    return {
        **r,
        "event_type": event_type,
        "event_type_display": type_display,
        "event_type_color": type_color,
        "event_label": event_label,
        "event_strength": strength,
        "event_grade": grade,
        "event_grade_label": grade_label,
        "event_grade_color": grade_color,
        "event_backing": backing,
        "event_backing_label": backing_label,
        "event_date": event_date,
        "event_scan_time": scan_time,
        "event_factors": factors,
    }
