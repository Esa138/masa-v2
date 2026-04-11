"""
MASA V2 — Order Flow Decision Engine
One decision: Enter / Watch / Avoid
Based on Order Flow evidence — who is initiating?

Principles:
- No score /100 — just a clear decision with reasons
- Veto is absolute — nothing overrides it
- Every reason traces back to Order Flow data
"""

import pandas as pd
import numpy as np
from core.indicators import compute_atr


# ── Decision Types ────────────────────────────────────────────

DECISIONS = {
    "enter": {
        "label": "✅ ادخل",
        "color": "#00E676",
        "description": "الأوردر فلو يدعم الدخول — المشترون يسيطرون",
    },
    "watch": {
        "label": "⚠️ راقب",
        "color": "#FFD700",
        "description": "إشارات متضاربة — انتظر تأكيد من الأوردر فلو",
    },
    "avoid": {
        "label": "❌ تجنب",
        "color": "#FF5252",
        "description": "البائعون يسيطرون — لا تدخل",
    },
}


def score_stock(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    orderflow_data: dict,
    market_health: float = 50.0,
    institutional_data: dict = None,
) -> dict:
    """
    Score a stock based on Order Flow evidence.

    Args:
        close, high, low: Price data
        orderflow_data: Output from accumulation.detect_orderflow()
        market_health: Market breadth 0-100 (50 = neutral)
        institutional_data: Output from institutional.py (optional)

    Returns:
        decision:       str (enter/watch/avoid)
        decision_info:  dict (label, color, description)
        reasons_for:    list[str] — why enter
        reasons_against: list[str] — why not
        veto:           str or None — if blocked, why
        stop_loss:      float
        target:         float
        rr_ratio:       float
    """
    last_close = float(close.iloc[-1])
    atr = compute_atr(high, low, close, 14)
    last_atr = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else last_close * 0.02

    phase = orderflow_data.get("phase", "neutral")
    flow_bias = orderflow_data.get("flow_bias", 0)
    cdv_trend = orderflow_data.get("cdv_trend", "flat")
    aggressor = orderflow_data.get("aggressor", "balanced")
    absorption_score = orderflow_data.get("absorption_score", 0)
    absorption_bias = orderflow_data.get("absorption_bias", 0)
    divergence = orderflow_data.get("divergence", 0)
    aggressive_ratio = orderflow_data.get("aggressive_ratio", 0)
    rsi = orderflow_data.get("rsi", 50)
    location = orderflow_data.get("location", "middle")
    ma200 = orderflow_data.get("ma200", last_close)
    days = orderflow_data.get("days", 0)

    reasons_for = []
    reasons_against = []

    # ── VETO CHECK (absolute — nothing overrides) ──────────
    veto = _check_veto(last_close, ma200, rsi, phase, flow_bias, market_health)
    if veto:
        return {
            "decision": "avoid",
            "decision_info": DECISIONS["avoid"],
            "reasons_for": reasons_for,
            "reasons_against": [veto],
            "veto": veto,
            "stop_loss": 0,
            "target": 0,
            "rr_ratio": 0,
        }

    # ── EVIDENCE FROM ORDER FLOW ──────────────────────────

    # 1. Wyckoff Phase
    if phase in ("accumulation", "spring"):
        reasons_for.append(f"مرحلة وايكوف: {orderflow_data['phase_info']['label']}")
    elif phase in ("distribution", "markdown", "upthrust"):
        reasons_against.append(f"مرحلة وايكوف: {orderflow_data['phase_info']['label']}")
    elif phase == "markup":
        reasons_for.append("ترند صاعد مع أوردر فلو إيجابي")

    # 2. Flow Bias
    if flow_bias > 30:
        reasons_for.append(f"أوردر فلو قوي ({flow_bias:+.0f}) — المشترون يسيطرون")
    elif flow_bias > 10:
        reasons_for.append(f"أوردر فلو إيجابي ({flow_bias:+.0f})")
    elif flow_bias < -30:
        reasons_against.append(f"أوردر فلو سلبي قوي ({flow_bias:+.0f}) — البائعون يسيطرون")
    elif flow_bias < -10:
        reasons_against.append(f"أوردر فلو سلبي ({flow_bias:+.0f})")

    # 3. Aggressor
    if aggressor == "buyers":
        reasons_for.append("المشتري هو المهاجم — يرفع السعر بعدوانية")
    elif aggressor == "sellers":
        reasons_against.append("البائع هو المهاجم — يضغط السعر للأسفل")

    # 4. Absorption at key levels
    if absorption_score > 70:
        if absorption_bias > 0.2 and location in ("bottom", "support"):
            reasons_for.append("امتصاص شرائي عند الدعم — سمارت مني يجمّع")
        elif absorption_bias < -0.2 and location in ("resistance", "above"):
            reasons_against.append("امتصاص بيعي عند المقاومة — سمارت مني يصرّف")

    # 5. Divergence
    if divergence > 25:
        reasons_for.append(f"دايفرجنس شرائي ({divergence:+.0f}) — تجميع خفي")
    elif divergence < -25:
        reasons_against.append(f"دايفرجنس بيعي ({divergence:+.0f}) — تصريف خفي")

    # 6. Location context — WITH SUPPORT BREAK DETECTION
    # Check if price is BREAKING support vs BOUNCING off support
    _zr_low = orderflow_data.get("zr_low", 0)
    _prev_close = float(close.iloc[-2]) if len(close) >= 2 else last_close
    _today_change = (last_close - _prev_close) / _prev_close * 100 if _prev_close > 0 else 0
    _breaking_support = (
        location in ("support", "bottom")
        and _today_change < -1.0  # falling >1% today
        and cdv_trend == "falling"  # CDV confirms selling
    )
    _broke_below_support = (
        _zr_low > 0
        and last_close < _zr_low  # price below support level
        and _today_change < -0.5  # still falling
    )

    if _breaking_support or _broke_below_support:
        reasons_against.append("⚠️ كسر دعم — السعر يكسر الدعم مع ضغط بيعي (لا تلتقط السكين)")
    elif location == "bottom":
        reasons_for.append("موقع ممتاز — قريب من قاع القناة التاريخية")
    elif location == "support":
        reasons_for.append("قريب من منطقة دعم رئيسية")
    elif location == "above":
        # V3: Check for failed breakout (above + CDV falling = upthrust trap)
        if cdv_trend == "falling" and _today_change < -0.5:
            reasons_against.append("⚠️ اختراق فاشل — فوق المقاومة لكن CDV هابط + السعر ينزل (upthrust)")
        else:
            reasons_for.append("كسر المقاومة — سماء مفتوحة")
    elif location == "resistance":
        reasons_against.append("قريب من سقف المقاومة — خطر الارتداد")

    # 7. Trend (MA200)
    if last_close > ma200:
        reasons_for.append("فوق متوسط 200 — الاتجاه العام صاعد")
    elif last_close < ma200 * 0.95:
        reasons_against.append("تحت متوسط 200 بأكثر من 5% — اتجاه هابط")

    # 8. Market health
    if market_health >= 60:
        reasons_for.append(f"صحة السوق جيدة ({market_health:.0f}%)")
    elif market_health <= 30:
        reasons_against.append(f"السوق ضعيف جداً ({market_health:.0f}%)")

    # 9. RSI extremes — V3: phase-aware + falling knife protection
    if rsi > 75:
        reasons_against.append(f"RSI مرتفع ({rsi:.0f}) — تشبع شرائي")
    elif rsi > 70:
        # V3 backtest: RSI 70-75 + buy phases = lower win rate (data-driven)
        if phase in ("markup", "spring"):
            reasons_against.append(
                f"⚠️ RSI {rsi:.0f} في مرحلة {phase} — تاريخياً هذي المنطقة 0-25% نجاح فقط"
            )
        elif phase == "accumulation":
            reasons_against.append(
                f"⚠️ RSI {rsi:.0f} — قريب من تشبع، انتظر تهدئة قبل الدخول"
            )
    elif rsi < 28:
        # V3: RSI low in markdown/distribution = crash continuing, NOT bounce
        if phase in ("markdown", "distribution"):
            reasons_against.append(
                f"⚠️ RSI منخفض ({rsi:.0f}) في مرحلة {phase} — هبوط مستمر مو ارتداد!"
            )
        elif _breaking_support or _broke_below_support or cdv_trend == "falling":
            reasons_against.append(
                f"⚠️ RSI منخفض ({rsi:.0f}) لكن مع كسر دعم + CDV هابط — سكين ساقطة لا ارتداد!"
            )
        else:
            reasons_for.append(f"RSI منخفض ({rsi:.0f}) — احتمال ارتداد")

    # 10. Institutional data
    if institutional_data:
        foreign_change = institutional_data.get("foreign_change_pct", 0)
        if foreign_change > 0.1:
            reasons_for.append(
                f"ملكية الأجانب زادت +{foreign_change:.1f}% — تجميع مؤسساتي"
            )
        elif foreign_change < -0.1:
            reasons_against.append(
                f"ملكية الأجانب نقصت {foreign_change:.1f}% — تصريف مؤسساتي"
            )

    # 11. CDV Contradiction — buy signals but CDV falling = DANGER
    if cdv_trend == "falling" and flow_bias > 0:
        reasons_against.append(
            "⚠️ تناقض: أوردر فلو إيجابي لكن CDV هابط — البائعون يتسللون"
        )
    # 12. Falling knife veto — extreme oversold + broken support + falling CDV
    if rsi < 20 and cdv_trend == "falling" and (_breaking_support or _broke_below_support):
        reasons_against.append(
            "🔴 سكين ساقطة — RSI متطرف + كسر دعم + CDV هابط = لا تلمسه"
        )

    # ── STOP LOSS & TARGET (V3: min 2% floor, max 8% cap) ──
    stop_loss = round(last_close - (last_atr * 1.5), 2)
    stop_pct = (last_close - stop_loss) / last_close * 100

    # V3: Floor — stop can't be tighter than 2% (prevents noise exits)
    if stop_pct < 2.0:
        stop_loss = round(last_close * 0.98, 2)
        stop_pct = 2.0
    # Cap — stop can't be wider than 8%
    if stop_pct > 8:
        stop_loss = round(last_close * 0.92, 2)
        stop_pct = 8.0

    risk = last_close - stop_loss
    if risk <= 0:
        risk = last_close * 0.03  # fallback 3%
        stop_loss = round(last_close - risk, 2)

    target = round(last_close + (risk * 2.5), 2)
    rr_ratio = 2.5

    # Adjust target if near resistance — V3: validate zr_high > entry
    zr_h = orderflow_data.get("zr_high", 0)
    if zr_h > last_close and location != "above":
        if target > zr_h:
            target = round(zr_h * 0.98, 2)
            rr_ratio = round((target - last_close) / risk, 1) if risk > 0 else 0

    # ── V3: VALIDATE TARGET > ENTRY ─────────────────────────
    if target <= last_close:
        # ZR_high was stale or below entry — recalculate without cap
        target = round(last_close + (risk * 2.5), 2)
        rr_ratio = 2.5

    # ── FINAL DECISION (V3: stricter, flow-aware) ──────────
    if rr_ratio < 1.0:
        reasons_against.append(f"R:R سيء ({rr_ratio:.1f}) — المخاطرة أعلى من العائد")
        decision = "avoid"
    elif rr_ratio < 1.5:
        reasons_against.append(f"R:R ضعيف ({rr_ratio:.1f}) — أقل من 1.5")
        decision = "avoid"  # V3: R:R < 1.5 = avoid (was just a warning)

    n_for = len(reasons_for)
    n_against = len(reasons_against)

    if rr_ratio < 1.5:
        decision = "avoid"
    elif phase in ("spring",) and n_for >= 3 and flow_bias > 15:
        # V3: Spring needs 3 reasons + meaningful flow (was 2 reasons, no flow check)
        decision = "enter"
    elif phase in ("accumulation",) and n_for >= 4 and flow_bias > 20:
        # V3: Accumulation needs 4 reasons + strong flow (was 3 reasons, no flow check)
        decision = "enter"
    elif phase == "markup" and flow_bias > 25 and n_for > n_against + 1:
        # V3: Markup needs stronger flow (was 15) and clearer advantage (was n_for > n_against)
        decision = "enter"
    elif phase in ("accumulation", "markup") and n_for > n_against + 2 and flow_bias > 10:
        # V3: Need 3+ more reasons_for than against + positive flow (was just n_for > n_against)
        decision = "enter"
    elif phase in ("distribution", "markdown"):
        decision = "avoid"
    elif phase == "upthrust":
        decision = "avoid"
    elif n_against >= n_for:
        # V3: Equal or more against = avoid (was n_against > n_for + 1)
        decision = "avoid"
    elif n_for > n_against:
        decision = "watch"
    else:
        decision = "watch"

    # ── V3: RSI overbought downgrade ──
    # Even if all other conditions met, if RSI > 70 in any buy phase,
    # downgrade enter→watch (data-driven: V3 backtest shows low win rates)
    if decision == "enter" and rsi > 70 and phase in ("accumulation", "spring", "markup"):
        decision = "watch"
        if not any("RSI" in r and "تشبع" in r for r in reasons_against):
            reasons_against.append(
                f"⚠️ RSI {rsi:.0f} — انتظر تهدئة (تاريخياً منطقة تشبع تعطي نتائج ضعيفة)"
            )

    return {
        "decision": decision,
        "decision_info": DECISIONS[decision],
        "reasons_for": reasons_for,
        "reasons_against": reasons_against,
        "veto": None,
        "stop_loss": stop_loss,
        "target": target,
        "rr_ratio": rr_ratio,
    }


def _check_veto(close, ma200, rsi, phase, flow_bias, market_health) -> str:
    """
    Absolute veto — if triggered, decision is ALWAYS avoid.
    Nothing overrides a veto. Not news, not hope, nothing.
    """
    # Veto 1: Deep downtrend + no recovery
    if close < ma200 * 0.88:
        return "❌ فيتو: السعر أقل من MA200 بأكثر من 12% — انهيار"

    # Veto 2: Distribution phase + weak market
    if phase in ("distribution", "markdown") and market_health < 40:
        return "❌ فيتو: تصريف في سوق ضعيف — لا تدخل"

    # Veto 3: Extreme overbought
    if rsi > 85:
        return f"❌ فيتو: RSI {rsi:.0f} — تشبع شرائي شديد"

    # Veto 4: Strong negative flow + seller aggression
    if flow_bias < -60 and market_health < 45:
        return "❌ فيتو: أوردر فلو سلبي شديد + سوق ضعيف"

    # Veto 5: Extreme RSI + deep below MA200 = crash in progress
    if rsi < 15 and close < ma200 * 0.92:
        return f"❌ فيتو: RSI {rsi:.0f} + تحت MA200 بـ {((close/ma200-1)*100):.0f}% — انهيار نشط"

    # Veto 6: markup breakout + RSI>70 = 0% historical win rate (V3 data, 92 trades)
    if phase == "markup" and rsi > 70:
        return f"❌ فيتو: اختراق + RSI {rsi:.0f} — تاريخياً 0% نجاح (فخ مؤكد)"

    return None
