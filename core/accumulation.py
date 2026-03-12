"""
MASA V2 — Wyckoff Order Flow Engine
Detects accumulation/distribution using the REAL question:
"Who is initiating — the buyer or the seller?"

Built on:
1. Cumulative Delta Volume (CDV) — the #1 indicator
2. Absorption (Effort vs Result) — smart money footprint
3. Aggressive Order Flow — who is attacking
4. Wyckoff Phases — the complete framework

No more indirect proxies. This goes straight to the source.
"""

import pandas as pd
import numpy as np
from core.indicators import (
    compute_cdv, compute_cdv_slope, compute_rolling_delta,
    compute_delta_volume, compute_absorption, compute_absorption_bias,
    compute_aggressive_ratio, compute_divergence,
    compute_rsi, compute_volume_ratio, compute_range_contraction,
    compute_zero_reflection, compute_zr_status, compute_ma, compute_atr,
)


# ── Wyckoff Phases ──────────────────────────────────────────

PHASES = {
    "accumulation": {
        "label": "🟢 تدفق شرائي + امتصاص",
        "description": "CDV صاعد + المشتري مهاجم + امتصاص عرض عند الدعم",
        "color": "#00E676",
    },
    "markup": {
        "label": "🚀 تدفق صاعد مؤكد",
        "description": "CDV يؤكد الترند — المشتري مسيطر",
        "color": "#4FC3F7",
    },
    "distribution": {
        "label": "🔴 تدفق بيعي + تصريف",
        "description": "CDV هابط + البائع مهاجم + امتصاص طلب عند المقاومة",
        "color": "#FF5252",
    },
    "markdown": {
        "label": "📉 تدفق هابط مؤكد",
        "description": "CDV يؤكد الهبوط — البائع مسيطر",
        "color": "#FF8A80",
    },
    "spring": {
        "label": "🎯 سبرنق — كسر كاذب + تدفق يرتد",
        "description": "كسر كاذب للقاع + CDV يرتد + امتصاص شرائي — أقوى إشارة",
        "color": "#00E676",
    },
    "upthrust": {
        "label": "⚠️ أبثرست — كسر كاذب + تدفق يضعف",
        "description": "كسر كاذب للقمة + CDV يهبط + امتصاص بيعي",
        "color": "#FF9800",
    },
    "transition": {
        "label": "🔄 تحول في التدفق",
        "description": "CDV يتغير اتجاهه — مراقبة المهاجم",
        "color": "#FFD700",
    },
    "neutral": {
        "label": "⚪ تدفق متوازن",
        "description": "لا سيطرة واضحة — CDV مسطح + لا مهاجم",
        "color": "#808080",
    },
}


# ── Location Assessment ──────────────────────────────────────

LOCATIONS = {
    "bottom": {
        "label": "🎯 قاع القناة",
        "description": "أفضل موقع — إذا كان الأوردر فلو إيجابي = تجميع حقيقي",
        "color": "#00E676",
        "rank": 1,
    },
    "support": {
        "label": "💎 منطقة دعم",
        "description": "قريب من MA200 أو دعم رئيسي",
        "color": "#4CAF50",
        "rank": 2,
    },
    "middle": {
        "label": "⚪ منتصف القناة",
        "description": "بين الدعم والمقاومة",
        "color": "#FFD700",
        "rank": 3,
    },
    "resistance": {
        "label": "⚠️ منطقة مقاومة",
        "description": "قريب من سقف القناة — مراقبة الأوردر فلو حرجة",
        "color": "#FF9800",
        "rank": 4,
    },
    "above": {
        "label": "🌌 فوق القناة",
        "description": "كسر المقاومة — يحتاج تأكيد من الأوردر فلو",
        "color": "#2196F3",
        "rank": 2,
    },
}


def detect_orderflow(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    open_: pd.Series,
    volume: pd.Series,
) -> dict:
    """
    Main Order Flow + Wyckoff detection engine.

    Returns dict with:
        phase:              str (accumulation/markup/distribution/markdown/spring/upthrust/transition/neutral)
        phase_info:         dict (label, description, color)
        evidence:           list of dicts
        flow_bias:          float (-100 to +100) — net order flow
        cdv_trend:          str (rising/falling/flat)
        absorption_score:   float (0-100) — how much absorption
        absorption_bias:    float (-1 to +1) — bullish vs bearish absorption
        aggressor:          str (buyers/sellers/balanced)
        aggressive_ratio:   float (-1 to +1)
        divergence:         float (-100 to +100) — price-CDV divergence
        rsi:                float
        volume_ratio:       float
        days:               int — consecutive days of positive/negative flow
        location:           str
        location_info:      dict
        zr_high:            float
        zr_low:             float
        # Chart data
        delta_series:       list — for CDV chart
        cdv_series:         list — for CDV chart
        absorption_series:  list — for absorption chart
    """
    n = len(close)
    if n < 50:
        return _empty_result()

    # ── Compute Order Flow indicators ─────────────────────
    delta = compute_delta_volume(high, low, close, volume)
    cdv = compute_cdv(high, low, close, volume)
    cdv_slope = compute_cdv_slope(high, low, close, volume, 10)
    rolling_delta = compute_rolling_delta(high, low, close, volume, 20)
    absorption = compute_absorption(high, low, close, volume, 20)
    abs_bias = compute_absorption_bias(high, low, close, open_, volume, 20)
    agg_ratio = compute_aggressive_ratio(high, low, close, open_, volume, 20)
    divergence = compute_divergence(close, cdv, 20)

    # Supporting
    rsi = compute_rsi(close, 14)
    vol_ratio = compute_volume_ratio(volume, 20)
    contraction = compute_range_contraction(high, low, 20)
    ma50 = compute_ma(close, 50)
    ma200 = compute_ma(close, min(200, n - 1)) if n >= 50 else ma50

    # Current values
    last_delta = float(delta.iloc[-1])
    last_cdv_slope = float(cdv_slope.iloc[-1])
    last_rolling_delta = float(rolling_delta.iloc[-1])
    last_absorption = float(absorption.iloc[-1])
    last_abs_bias = float(abs_bias.iloc[-1])
    last_agg_ratio = float(agg_ratio.iloc[-1])
    last_divergence = float(divergence.iloc[-1])
    last_rsi = float(rsi.iloc[-1])
    last_vol_ratio = float(vol_ratio.iloc[-1])
    last_contraction = float(contraction.iloc[-1])
    last_close = float(close.iloc[-1])
    last_ma50 = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else last_close
    last_ma200 = float(ma200.iloc[-1]) if pd.notna(ma200.iloc[-1]) else last_close

    # ── CDV Trend ─────────────────────────────────────────
    cdv_5d = float(cdv.iloc[-1]) - float(cdv.iloc[-6]) if n >= 6 else 0
    cdv_10d = float(cdv.iloc[-1]) - float(cdv.iloc[-11]) if n >= 11 else 0

    if cdv_5d > 0 and cdv_10d > 0:
        cdv_trend = "rising"
    elif cdv_5d < 0 and cdv_10d < 0:
        cdv_trend = "falling"
    else:
        cdv_trend = "flat"

    # ── Aggressor Detection ───────────────────────────────
    if last_agg_ratio > 0.25:
        aggressor = "buyers"
    elif last_agg_ratio < -0.25:
        aggressor = "sellers"
    else:
        aggressor = "balanced"

    # ── Flow Bias (composite score -100 to +100) ─────────
    # Weighted combination of all order flow signals
    flow_components = [
        (last_agg_ratio * 35),       # Aggressive ratio: 35% weight
        (last_abs_bias * 25),         # Absorption bias: 25% weight
        (last_divergence * 0.2),      # Divergence: 20% weight
        (1 if cdv_trend == "rising" else -1 if cdv_trend == "falling" else 0) * 20,
    ]
    flow_bias = sum(flow_components)
    flow_bias = max(-100, min(100, flow_bias))

    # ── Consecutive flow days ─────────────────────────────
    days = _count_flow_days(rolling_delta)

    # ── Location ──────────────────────────────────────────
    zr_high, zr_low = compute_zero_reflection(high, low, bars=400, confirm_len=25)
    location = _classify_location(last_close, zr_high, zr_low, last_ma200, last_ma50)
    zr_stat = compute_zr_status(close, zr_high, zr_low)

    # ── Build Evidence ────────────────────────────────────
    evidence = []

    # Evidence 1: Cumulative Delta Volume trend
    if cdv_trend == "rising":
        evidence.append({
            "factor": "📈 CDV صاعد",
            "type": "positive",
            "meaning": "المشترون يسيطرون — تدفق أوامر صافي شرائي",
            "weight": 3,
        })
    elif cdv_trend == "falling":
        evidence.append({
            "factor": "📉 CDV هابط",
            "type": "negative",
            "meaning": "البائعون يسيطرون — تدفق أوامر صافي بيعي",
            "weight": 3,
        })

    # Evidence 2: Aggressive ratio
    if last_agg_ratio > 0.3:
        evidence.append({
            "factor": f"🔥 مشتري عدواني ({last_agg_ratio:+.2f})",
            "type": "positive",
            "meaning": "المشترون يهاجمون — يرفعون السعر بعنف",
            "weight": 3,
        })
    elif last_agg_ratio > 0.1:
        evidence.append({
            "factor": f"🟢 ميل شرائي ({last_agg_ratio:+.2f})",
            "type": "positive",
            "meaning": "المشترون أكثر عدوانية من البائعين",
            "weight": 2,
        })
    elif last_agg_ratio < -0.3:
        evidence.append({
            "factor": f"🔥 بائع عدواني ({last_agg_ratio:+.2f})",
            "type": "negative",
            "meaning": "البائعون يهاجمون — يضغطون السعر للأسفل",
            "weight": 3,
        })
    elif last_agg_ratio < -0.1:
        evidence.append({
            "factor": f"🔴 ميل بيعي ({last_agg_ratio:+.2f})",
            "type": "negative",
            "meaning": "البائعون أكثر عدوانية من المشترين",
            "weight": 2,
        })

    # Evidence 3: Absorption
    if last_absorption > 70 and last_abs_bias > 0.3:
        evidence.append({
            "factor": f"🛡️ امتصاص شرائي ({last_absorption:.0f}/100)",
            "type": "positive",
            "meaning": "حجم كبير + حركة صغيرة = سمارت مني يمتص العرض",
            "weight": 3,
        })
    elif last_absorption > 70 and last_abs_bias < -0.3:
        evidence.append({
            "factor": f"⚡ امتصاص بيعي ({last_absorption:.0f}/100)",
            "type": "negative",
            "meaning": "حجم كبير + حركة صغيرة = سمارت مني يمتص الطلب",
            "weight": 3,
        })
    elif last_absorption > 60:
        evidence.append({
            "factor": f"👁️ امتصاص نشط ({last_absorption:.0f}/100)",
            "type": "neutral",
            "meaning": "حجم مرتفع نسبياً — مراقبة الاتجاه",
            "weight": 1,
        })

    # Evidence 4: Divergence (THE most powerful signal)
    if last_divergence > 30:
        evidence.append({
            "factor": f"⭐ دايفرجنس شرائي ({last_divergence:+.0f})",
            "type": "positive",
            "meaning": "السعر يهبط لكن التدفق يصعد — تجميع خفي",
            "weight": 4,
        })
    elif last_divergence > 15:
        evidence.append({
            "factor": f"↗️ دايفرجنس إيجابي ({last_divergence:+.0f})",
            "type": "positive",
            "meaning": "التدفق أقوى من حركة السعر",
            "weight": 2,
        })
    elif last_divergence < -30:
        evidence.append({
            "factor": f"⭐ دايفرجنس بيعي ({last_divergence:+.0f})",
            "type": "negative",
            "meaning": "السعر يصعد لكن التدفق يهبط — تصريف خفي",
            "weight": 4,
        })
    elif last_divergence < -15:
        evidence.append({
            "factor": f"↘️ دايفرجنس سلبي ({last_divergence:+.0f})",
            "type": "negative",
            "meaning": "التدفق أضعف من حركة السعر",
            "weight": 2,
        })

    # Evidence 5: Rolling delta duration
    if days >= 15:
        evidence.append({
            "factor": f"💪 تدفق شرائي مستمر {days} يوم",
            "type": "positive",
            "meaning": "سيطرة شرائية طويلة — تجميع منظم",
            "weight": 2,
        })
    elif days >= 7:
        evidence.append({
            "factor": f"🟢 تدفق شرائي {days} أيام",
            "type": "positive",
            "meaning": "سيطرة شرائية متواصلة",
            "weight": 1,
        })
    elif days <= -15:
        evidence.append({
            "factor": f"📉 تدفق بيعي مستمر {abs(days)} يوم",
            "type": "negative",
            "meaning": "سيطرة بيعية طويلة — تصريف",
            "weight": 2,
        })
    elif days <= -7:
        evidence.append({
            "factor": f"🔴 تدفق بيعي {abs(days)} أيام",
            "type": "negative",
            "meaning": "سيطرة بيعية متواصلة",
            "weight": 1,
        })

    # Evidence 6: Volume + Contraction
    if last_vol_ratio >= 1.5:
        evidence.append({
            "factor": f"📊 حجم مرتفع ({last_vol_ratio:.1f}x)",
            "type": "neutral",
            "meaning": "نشاط غير عادي — تحقق من الاتجاه",
            "weight": 1,
        })

    if last_contraction >= 75:
        evidence.append({
            "factor": f"🔋 ضغط سعري ({last_contraction:.0f}/100)",
            "type": "neutral",
            "meaning": "السعر مضغوط — انفجار قادم",
            "weight": 1,
        })

    # ── Determine Wyckoff Phase ───────────────────────────
    phase = _determine_phase(
        flow_bias=flow_bias,
        cdv_trend=cdv_trend,
        aggressor=aggressor,
        last_absorption=last_absorption,
        last_abs_bias=last_abs_bias,
        last_divergence=last_divergence,
        last_close=last_close,
        last_ma50=last_ma50,
        last_ma200=last_ma200,
        location=location,
        last_rsi=last_rsi,
        last_contraction=last_contraction,
        evidence=evidence,
    )

    # ── Chart data (last 90 days) ─────────────────────────
    chart_days = 90
    delta_list = [round(float(v), 2) for v in delta.iloc[-chart_days:]]
    cdv_list = [round(float(v), 2) for v in cdv.iloc[-chart_days:]]
    abs_list = [round(float(v), 1) for v in absorption.iloc[-chart_days:]]

    return {
        "phase": phase,
        "phase_info": PHASES[phase],
        "evidence": evidence,
        "flow_bias": round(flow_bias, 1),
        "cdv_trend": cdv_trend,
        "absorption_score": round(last_absorption, 1),
        "absorption_bias": round(last_abs_bias, 3),
        "aggressor": aggressor,
        "aggressive_ratio": round(last_agg_ratio, 3),
        "divergence": round(last_divergence, 1),
        "rsi": round(last_rsi, 1),
        "volume_ratio": round(last_vol_ratio, 2),
        "contraction": round(last_contraction, 1),
        "days": days,
        "ma50": round(last_ma50, 2),
        "ma200": round(last_ma200, 2),
        "location": location,
        "location_info": LOCATIONS[location],
        "zr_high": round(zr_high, 2) if pd.notna(zr_high) else None,
        "zr_low": round(zr_low, 2) if pd.notna(zr_low) else None,
        "zr_status": zr_stat["status"],
        "zr_status_label": zr_stat["label"],
        "zr_status_color": zr_stat["color"],
        # Chart series
        "delta_series": delta_list,
        "cdv_series": cdv_list,
        "absorption_series": abs_list,
    }


def _determine_phase(
    flow_bias, cdv_trend, aggressor, last_absorption, last_abs_bias,
    last_divergence, last_close, last_ma50, last_ma200,
    location, last_rsi, last_contraction, evidence,
) -> str:
    """
    Determine the Wyckoff phase from Order Flow evidence.

    Priority logic:
    1. Spring / Upthrust (highest priority — specific patterns)
    2. Accumulation / Distribution (confirmed phase)
    3. Markup / Markdown (trending)
    4. Transition / Neutral (unclear)
    """
    positive_weight = sum(e["weight"] for e in evidence if e["type"] == "positive")
    negative_weight = sum(e["weight"] for e in evidence if e["type"] == "negative")

    is_above_ma200 = last_close > last_ma200
    is_above_ma50 = last_close > last_ma50

    # ── Spring Detection ──────────────────────────────────
    # Price near bottom/support + strong bullish divergence + absorption
    if (location in ("bottom", "support")
            and last_divergence > 20
            and last_abs_bias > 0.2
            and cdv_trend == "rising"):
        return "spring"

    # ── Upthrust Detection ────────────────────────────────
    # Price near resistance/above + bearish divergence + absorption
    if (location in ("resistance", "above")
            and last_divergence < -20
            and last_abs_bias < -0.2
            and cdv_trend == "falling"):
        return "upthrust"

    # ── Accumulation ──────────────────────────────────────
    # Strong positive flow + buyer aggression + location makes sense
    if (flow_bias > 25
            and positive_weight >= 6
            and aggressor in ("buyers", "balanced")
            and location not in ("resistance",)):
        return "accumulation"

    # Moderate positive + strong divergence (hidden accumulation)
    if (flow_bias > 10
            and last_divergence > 25
            and location in ("bottom", "support", "middle")):
        return "accumulation"

    # ── Distribution ──────────────────────────────────────
    # Strong negative flow + seller aggression
    if (flow_bias < -25
            and negative_weight >= 6
            and aggressor in ("sellers", "balanced")):
        return "distribution"

    # Moderate negative + bearish divergence (hidden distribution)
    if (flow_bias < -10
            and last_divergence < -25
            and location in ("resistance", "above", "middle")):
        return "distribution"

    # ── Markup (trending up) ──────────────────────────────
    if (is_above_ma50 and is_above_ma200
            and cdv_trend == "rising"
            and flow_bias > 10):
        return "markup"

    # ── Markdown (trending down) ──────────────────────────
    if (not is_above_ma50 and not is_above_ma200
            and cdv_trend == "falling"
            and flow_bias < -10):
        return "markdown"

    # ── Transition ────────────────────────────────────────
    if abs(flow_bias) > 15 or abs(positive_weight - negative_weight) >= 3:
        return "transition"

    # ── Neutral ───────────────────────────────────────────
    return "neutral"


def _count_flow_days(rolling_delta: pd.Series) -> int:
    """
    Count consecutive days of positive/negative rolling delta.
    Positive return = consecutive buying days
    Negative return = consecutive selling days
    """
    count = 0
    for val in reversed(rolling_delta.values):
        if pd.isna(val):
            break
        if count == 0:
            # First bar sets direction
            if val > 0:
                direction = 1
            elif val < 0:
                direction = -1
            else:
                return 0
            count = direction
        else:
            if (direction == 1 and val > 0) or (direction == -1 and val < 0):
                count += direction
            else:
                break
    return count


def _classify_location(close, zr_high, zr_low, ma200, ma50) -> str:
    """Classify where the stock is relative to its historical channel."""
    if pd.notna(zr_high) and close > zr_high:
        return "above"

    if pd.notna(zr_low) and close <= zr_low * 1.05:
        return "bottom"

    if pd.notna(ma200) and close <= ma200 * 1.03:
        return "support"

    if pd.notna(zr_high) and zr_high > 0:
        dist_to_top = (zr_high - close) / zr_high
        if dist_to_top <= 0.05:
            return "resistance"

    return "middle"


def compute_accumulation_maturity(
    dates: list,
    close: pd.Series,
    rolling_delta: pd.Series,
    cdv: pd.Series,
    absorption: pd.Series,
    contraction: pd.Series,
    rsi: pd.Series,
    volume: pd.Series,
) -> dict:
    """
    Detect accumulation maturity stage with dates.
    Uses BOTH duration (days) AND intensity (signal strength).

    Returns:
        stage: "early" | "mid" | "late" | "none"
        stage_label: Arabic label
        stage_color: color
        timeline: list of {stage, date, label}
        current_days: int — consecutive accumulation days
    """
    n = len(close)
    if n < 30:
        return {"stage": "none", "stage_label": "لا توجد بيانات كافية",
                "stage_color": "#808080", "timeline": [], "current_days": 0}

    # Walk through last 90 days to find phase transitions
    lookback = min(90, n)
    start_idx = n - lookback

    # Track daily accumulation signal
    daily_signals = []
    for i in range(start_idx, n):
        if i < 20:
            daily_signals.append({"idx": i, "accum": False})
            continue

        rd = float(rolling_delta.iloc[i]) if pd.notna(rolling_delta.iloc[i]) else 0
        cdv_5d = float(cdv.iloc[i]) - float(cdv.iloc[max(0, i - 5)]) if i >= 5 else 0
        abs_val = float(absorption.iloc[i]) if pd.notna(absorption.iloc[i]) else 0
        cont_val = float(contraction.iloc[i]) if pd.notna(contraction.iloc[i]) else 0
        rsi_val = float(rsi.iloc[i]) if pd.notna(rsi.iloc[i]) else 50

        # Is this day showing accumulation?
        is_accum = rd > 0 and cdv_5d > 0

        daily_signals.append({
            "idx": i,
            "accum": is_accum,
            "rd": rd,
            "cdv_5d": cdv_5d,
            "abs": abs_val,
            "cont": cont_val,
            "rsi": rsi_val,
        })

    # Find consecutive accumulation streak from the end
    streak = 0
    for sig in reversed(daily_signals):
        if sig["accum"]:
            streak += 1
        else:
            break

    if streak == 0:
        return {"stage": "none", "stage_label": "لا يوجد تجميع نشط",
                "stage_color": "#808080", "timeline": [], "current_days": 0}

    # ── Signal intensity (current values) ──
    last_sig = daily_signals[-1]
    last_rsi = last_sig.get("rsi", 50)
    last_cont = last_sig.get("cont", 50)
    last_cdv_5d = last_sig.get("cdv_5d", 0)

    # Compute divergence from close vs CDV (last 20 days)
    price_change_20d = 0
    if n >= 20:
        p_now = float(close.iloc[-1])
        p_20 = float(close.iloc[-20])
        if p_20 > 0:
            price_change_20d = (p_now - p_20) / p_20 * 100

    # Strong signal = price dropping but CDV rising
    has_strong_divergence = price_change_20d < -3 and last_cdv_5d > 0
    has_extreme_rsi = last_rsi < 30
    has_high_contraction = last_cont > 65

    # ── Intensity score (0-3) — how many strong signals ──
    intensity = 0
    if has_strong_divergence:
        intensity += 1
    if has_extreme_rsi:
        intensity += 1
    if has_high_contraction:
        intensity += 1

    # Determine stages with dates
    timeline = []
    accum_start_idx = len(daily_signals) - streak
    accum_start = daily_signals[accum_start_idx]

    # Map index back to date
    def idx_to_date(idx):
        offset = idx - start_idx
        if 0 <= offset < len(dates[start_idx:]):
            return dates[start_idx + offset] if start_idx + offset < len(dates) else "—"
        return "—"

    today_date = idx_to_date(daily_signals[-1]["idx"])

    # ── Stage determination: duration + intensity ──
    # Strong signals still need minimum duration for confirmation
    if intensity >= 2 and streak >= 3:
        # Very strong signals + enough duration → confirmed late
        timeline.append({"stage": "late", "date": today_date,
                          "label": "🟢 سبرنق — إشارات قوية", "action": "ادخل"})
        stage = "late"
        stage_label = "🟢 سبرنق — إشارات قوية جداً"
        stage_color = "#00E676"
    elif intensity >= 2 and streak < 3:
        # Strong signals but too early — needs confirmation
        timeline.append({"stage": "early", "date": today_date,
                          "label": "🟡 إشارات قوية — تحتاج تأكيد", "action": "راقب"})
        stage = "early"
        stage_label = "🟡 سبرنق مبكر — تحتاج تأكيد"
        stage_color = "#FFD700"
    elif intensity == 1 and streak >= 3:
        # Moderate signals + some duration → mid/late
        early_date = idx_to_date(accum_start["idx"])
        timeline.append({"stage": "early", "date": early_date,
                          "label": "🟡 بداية التجميع", "action": "انتظر"})
        timeline.append({"stage": "late", "date": today_date,
                          "label": "🟢 تسارع — إشارة قوية", "action": "ادخل"})
        stage = "late"
        stage_label = "🟢 تسارع في التجميع — إشارة قوية"
        stage_color = "#00E676"
    elif intensity == 1 or streak >= 5:
        # Some intensity OR decent duration → mid
        early_date = idx_to_date(accum_start["idx"])
        timeline.append({"stage": "early", "date": early_date,
                          "label": "🟡 بداية التجميع", "action": "انتظر"})
        if streak >= 5:
            mid_sig = daily_signals[accum_start_idx + min(4, streak - 1)]
            mid_date = idx_to_date(mid_sig["idx"])
        else:
            mid_date = today_date
        timeline.append({"stage": "mid", "date": mid_date,
                          "label": "🟠 منتصف التجميع", "action": "راقب وجهّز"})
        stage = "mid"
        stage_label = "🟠 منتصف التجميع — راقب"
        stage_color = "#FF9800"

        # Check if ready to graduate to late
        if streak >= 15 and (last_cont > 60 or last_rsi < 40):
            timeline.append({"stage": "late", "date": today_date,
                              "label": "🟢 نهاية التجميع", "action": "ادخل"})
            stage = "late"
            stage_label = "🟢 نهاية التجميع — جاهز ينطلق"
            stage_color = "#00E676"
    else:
        # Low intensity + short duration → early
        early_date = idx_to_date(accum_start["idx"])
        timeline.append({"stage": "early", "date": early_date,
                          "label": "🟡 بداية التجميع", "action": "انتظر"})
        stage = "early"
        stage_label = "🟡 بداية التجميع — انتظر"
        stage_color = "#FFD700"

    return {
        "stage": stage,
        "stage_label": stage_label,
        "stage_color": stage_color,
        "timeline": timeline,
        "current_days": streak,
    }


def compute_distribution_maturity(
    dates: list,
    close: pd.Series,
    rolling_delta: pd.Series,
    cdv: pd.Series,
    absorption: pd.Series,
    contraction: pd.Series,
    rsi: pd.Series,
    volume: pd.Series,
) -> dict:
    """
    Detect distribution maturity stage with dates.
    Mirror of accumulation maturity but for SELLING pressure.
    """
    n = len(close)
    if n < 30:
        return {"stage": "none", "stage_label": "لا توجد بيانات كافية",
                "stage_color": "#808080", "timeline": [], "current_days": 0}

    lookback = min(90, n)
    start_idx = n - lookback

    daily_signals = []
    for i in range(start_idx, n):
        if i < 20:
            daily_signals.append({"idx": i, "dist": False})
            continue

        rd = float(rolling_delta.iloc[i]) if pd.notna(rolling_delta.iloc[i]) else 0
        cdv_5d = float(cdv.iloc[i]) - float(cdv.iloc[max(0, i - 5)]) if i >= 5 else 0
        abs_val = float(absorption.iloc[i]) if pd.notna(absorption.iloc[i]) else 0
        cont_val = float(contraction.iloc[i]) if pd.notna(contraction.iloc[i]) else 0
        rsi_val = float(rsi.iloc[i]) if pd.notna(rsi.iloc[i]) else 50

        # Distribution = negative rolling delta + CDV falling
        is_dist = rd < 0 and cdv_5d < 0

        daily_signals.append({
            "idx": i, "dist": is_dist,
            "rd": rd, "cdv_5d": cdv_5d,
            "abs": abs_val, "cont": cont_val, "rsi": rsi_val,
        })

    # Consecutive distribution streak
    streak = 0
    for sig in reversed(daily_signals):
        if sig["dist"]:
            streak += 1
        else:
            break

    if streak == 0:
        return {"stage": "none", "stage_label": "لا يوجد تصريف نشط",
                "stage_color": "#808080", "timeline": [], "current_days": 0}

    # Signal intensity
    last_sig = daily_signals[-1]
    last_rsi = last_sig.get("rsi", 50)
    last_cont = last_sig.get("cont", 50)
    last_cdv_5d = last_sig.get("cdv_5d", 0)

    price_change_20d = 0
    if n >= 20:
        p_now = float(close.iloc[-1])
        p_20 = float(close.iloc[-20])
        if p_20 > 0:
            price_change_20d = (p_now - p_20) / p_20 * 100

    # Strong distribution = price rising but CDV falling (bearish divergence)
    has_bearish_div = price_change_20d > 3 and last_cdv_5d < 0
    has_overbought_rsi = last_rsi > 70
    has_high_contraction = last_cont > 65

    intensity = sum([has_bearish_div, has_overbought_rsi, has_high_contraction])

    timeline = []
    dist_start_idx = len(daily_signals) - streak
    dist_start = daily_signals[dist_start_idx]

    def idx_to_date(idx):
        offset = idx - start_idx
        if 0 <= offset < len(dates[start_idx:]):
            return dates[start_idx + offset] if start_idx + offset < len(dates) else "—"
        return "—"

    today_date = idx_to_date(daily_signals[-1]["idx"])

    if intensity >= 2:
        timeline.append({"stage": "late", "date": today_date,
                          "label": "🔴 أبثرست — تصريف حاد", "action": "اخرج فوراً"})
        stage = "late"
        stage_label = "🔴 أبثرست — تصريف حاد"
        stage_color = "#FF5252"
    elif intensity == 1 and streak >= 3:
        early_date = idx_to_date(dist_start["idx"])
        timeline.append({"stage": "early", "date": early_date,
                          "label": "🟠 بداية التصريف", "action": "حذر"})
        timeline.append({"stage": "late", "date": today_date,
                          "label": "🔴 تسارع التصريف", "action": "اخرج"})
        stage = "late"
        stage_label = "🔴 تسارع في التصريف — اخرج"
        stage_color = "#FF5252"
    elif intensity == 1 or streak >= 5:
        early_date = idx_to_date(dist_start["idx"])
        timeline.append({"stage": "early", "date": early_date,
                          "label": "🟠 بداية التصريف", "action": "حذر"})
        if streak >= 5:
            mid_sig = daily_signals[dist_start_idx + min(4, streak - 1)]
            mid_date = idx_to_date(mid_sig["idx"])
        else:
            mid_date = today_date
        timeline.append({"stage": "mid", "date": mid_date,
                          "label": "🔴 منتصف التصريف", "action": "لا تدخل"})
        stage = "mid"
        stage_label = "🔴 منتصف التصريف — لا تدخل"
        stage_color = "#FF5252"

        if streak >= 15:
            timeline.append({"stage": "late", "date": today_date,
                              "label": "⚫ نهاية التصريف", "action": "اخرج فوراً"})
            stage = "late"
            stage_label = "⚫ نهاية التصريف — انهيار محتمل"
            stage_color = "#FF1744"
    else:
        early_date = idx_to_date(dist_start["idx"])
        timeline.append({"stage": "early", "date": early_date,
                          "label": "🟠 بداية التصريف", "action": "حذر"})
        stage = "early"
        stage_label = "🟠 بداية التصريف — حذر"
        stage_color = "#FF9800"

    return {
        "stage": stage,
        "stage_label": stage_label,
        "stage_color": stage_color,
        "timeline": timeline,
        "current_days": streak,
    }


def _empty_result() -> dict:
    """Return empty result when data is insufficient."""
    return {
        "phase": "neutral",
        "phase_info": PHASES["neutral"],
        "evidence": [{"factor": "بيانات غير كافية", "type": "neutral",
                       "meaning": "يحتاج 50 شمعة على الأقل", "weight": 0}],
        "flow_bias": 0,
        "cdv_trend": "flat",
        "absorption_score": 0,
        "absorption_bias": 0,
        "aggressor": "balanced",
        "aggressive_ratio": 0,
        "divergence": 0,
        "rsi": 50,
        "volume_ratio": 1.0,
        "contraction": 50,
        "days": 0,
        "ma50": 0, "ma200": 0,
        "location": "middle",
        "location_info": LOCATIONS["middle"],
        "zr_high": None, "zr_low": None,
        "zr_status": "normal", "zr_status_label": "", "zr_status_color": "#808080",
        "delta_series": [],
        "cdv_series": [],
        "absorption_series": [],
    }
