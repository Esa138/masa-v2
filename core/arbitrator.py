"""
MASA QUANT V95 — Signal Arbitrator (الحَكَم)
Resolves contradictions between VIP, Wolf, and Accumulation systems.
Produces a unified verdict with signal quality classification.

Timeframe hierarchy: Accumulation (weeks) > VIP (days) > Wolf (hours)
"""


# ── Signal Quality Constants ─────────────────────────────────
QUALITY_GOLD = "gold"        # 🥇 All systems agree — highest confidence
QUALITY_SILVER = "silver"    # 🥈 Strong accumulation + VIP — good confidence
QUALITY_BRONZE = "bronze"    # 🥉 VIP/Wolf only, no accumulation backing
QUALITY_BLOCKED = "blocked"  # 🚫 Distribution detected — blocked from VIP

QUALITY_LABELS = {
    "gold":    "🥇 ذهب — كل الأنظمة متفقة",
    "silver":  "🥈 فضة — تجميع + تقنية قوية",
    "bronze":  "🥉 برونز — زخم بدون تجميع",
    "blocked": "🚫 محظور — تصريف مؤسساتي",
}

QUALITY_COLORS = {
    "gold":    "#FFD700",
    "silver":  "#C0C0C0",
    "bronze":  "#CD7F32",
    "blocked": "#FF5252",
}


# ── Phase Multipliers ────────────────────────────────────────
PHASE_MULTIPLIERS = {
    "late":          1.15,    # Strong boost: institutions loaded, ready to go
    "strong":        1.08,    # Moderate boost: active institutional buying
    "mid":           1.02,    # Slight boost: building positions
    "early":         1.00,    # Neutral: too early to tell
    "neutral":       0.97,    # Slight penalty: no institutional signal
    "distribute":    0.75,    # Heavy penalty: institutions selling
    # ── Lifecycle phases ──
    "breakout":      1.05,    # Active breakout: slight boost
    "pullback_buy":  1.10,    # Healthy retest: quality setup, boost
    "pullback_wait": 0.95,    # Uncertain pullback: slight penalty
    "exhausted":     0.80,    # Failed move: heavy penalty
}


def arbitrate_signals(
    ai_score,
    mom_score,
    is_wolf,
    wolf_details,
    accum_data,
    is_blue_sky=False,
    vol_accel_ratio=0.0,
):
    """
    Main arbitration function — resolves cross-system contradictions.

    Returns dict with:
        unified_score:    int 0-100  (replaces raw ai_score for VIP)
        signal_quality:   str        (gold/silver/bronze/blocked)
        quality_label:    str        (Arabic display label)
        quality_color:    str        (hex color)
        vip_allowed:      bool       (can this stock enter VIP?)
        wolf_allowed:     bool       (should wolf signal be shown?)
        wolf_downgraded:  bool       (wolf shown with warning?)
        contradictions:   list[str]  (Arabic warnings)
        adjustments:      list[str]  (Arabic explanations)
    """
    # Extract accumulation data
    a_phase = "neutral"
    a_score = 0
    a_days = 0
    a_pressure = 0
    a_cmf = 0
    if accum_data and isinstance(accum_data, dict):
        a_phase = accum_data.get("phase", "neutral")
        a_score = accum_data.get("score", 0)
        a_days = accum_data.get("days", 0)
        a_pressure = accum_data.get("pressure", 0)
        a_cmf = accum_data.get("cmf", 0)

    wolf_filters_count = wolf_details.get("filters_count", 0) if wolf_details else 0
    wolf_soft_pass = wolf_details.get("is_soft_pass", False) if wolf_details else False

    contradictions = []
    adjustments = []
    vip_allowed = True
    wolf_allowed = True
    wolf_downgraded = False

    # ── RULE 1: Distribution Hard Block ──────────────────────
    if a_phase == "distribute":
        vip_allowed = False
        contradictions.append(
            "🔴 تصريف مؤسساتي: CMF سلبي + OBV هابط — المؤسسات تبيع."
        )
        adjustments.append(
            "🚫 تم حظر الدخول في VIP بسبب التصريف."
        )

        # Exception: extreme blue sky + full wolf (9/9) = possible regime change
        if is_blue_sky and wolf_filters_count >= 9 and vol_accel_ratio >= 2.0:
            vip_allowed = False  # Still blocked, but wolf can show with warning
            wolf_downgraded = True
            contradictions.append(
                "⚠️ سماء زرقاء مع تصريف — قد يكون تغيير نظام. راقب فقط."
            )
        else:
            # Wolf during distribution is unreliable
            if is_wolf:
                wolf_downgraded = True
                contradictions.append(
                    "⚠️ اختراق وولف أثناء تصريف — إشارة غير موثوقة!"
                )

    # ── RULE 1b: Exhausted Block ──────────────────────────────
    if a_phase == "exhausted":
        contradictions.append(
            "🔴 استنفاد: السهم انطلق وأعاد معظم حركته — الفرصة انتهت."
        )

    # ── RULE 2: Wolf in Wrong Phase ──────────────────────────
    if is_wolf and a_phase in ("distribute", "neutral", "exhausted"):
        wolf_downgraded = True
        if a_phase == "exhausted":
            contradictions.append(
                "⚠️ اختراق وولف بعد استنفاد — إشارة ضعيفة!"
            )
        elif a_phase != "distribute":  # Already warned above for distribute
            contradictions.append(
                "⚠️ اختراق وولف بدون دعم تجميع مؤسساتي."
            )

    # ── RULE 3: Compute Unified Score ────────────────────────
    base = ai_score
    phase_mult = PHASE_MULTIPLIERS.get(a_phase, 1.0)

    # Wolf synergy bonus (replaces the simple +10 already in ai_score)
    # We don't add +10 again, we adjust based on phase alignment
    wolf_adjustment = 0
    if is_wolf:
        if a_phase in ("strong", "late", "pullback_buy"):
            wolf_adjustment = 10  # Extra synergy on top of existing +10
            adjustments.append(
                "🐺🏗️ تآزر وولف + تجميع = بونص +10 إضافي."
            )
        elif a_phase == "distribute":
            wolf_adjustment = -15  # Cancel the +10 wolf bonus and penalize
            adjustments.append(
                "🐺🔴 إلغاء بونص وولف + عقوبة بسبب التصريف."
            )
        elif a_phase in ("neutral", "exhausted"):
            wolf_adjustment = -5  # Reduce wolf bonus
            adjustments.append(
                "🐺⚠️ تخفيض بونص وولف — لا يوجد تجميع مؤسساتي."
            )
        elif a_phase == "breakout":
            wolf_adjustment = 5  # Mild synergy during active breakout
            adjustments.append(
                "🐺🚀 وولف أثناء انطلاق — تأكيد إضافي."
            )

    # Pressure bonus for loaded spring
    pressure_bonus = 0
    if a_phase in ("strong", "late") and a_pressure >= 60:
        pressure_bonus = int(a_pressure / 10)  # 6-10 points
        adjustments.append(
            f"🏗️ بونص ضغط التجميع +{pressure_bonus} (ضغط {a_pressure:.0f}/100)."
        )

    # Blue sky partially overrides distribution penalty
    if is_blue_sky and a_phase == "distribute":
        phase_mult = max(phase_mult, 0.88)

    unified = int(base * phase_mult) + wolf_adjustment + pressure_bonus
    unified = max(0, min(100, unified))

    # ── RULE 4: Classify Signal Quality ──────────────────────
    if a_phase == "distribute":
        quality = QUALITY_BLOCKED
    elif a_phase == "exhausted":
        quality = QUALITY_BLOCKED
    elif a_phase in ("late",) and is_wolf and unified >= 70:
        quality = QUALITY_GOLD
    elif a_phase == "pullback_buy" and is_wolf and unified >= 70:
        quality = QUALITY_GOLD  # Wolf + healthy pullback = gold
    elif a_phase in ("strong", "late", "pullback_buy") and unified >= 65:
        quality = QUALITY_SILVER
    elif a_phase in ("strong", "late", "pullback_buy"):
        quality = QUALITY_SILVER
    elif a_phase == "breakout" and unified >= 70:
        quality = QUALITY_SILVER
    elif is_wolf and a_phase in ("mid", "early") and unified >= 75:
        quality = QUALITY_BRONZE
    elif unified >= 80 and a_phase not in ("strong", "late"):
        quality = QUALITY_BRONZE
    else:
        quality = QUALITY_BRONZE

    # Override: distribution & exhausted are always blocked
    if a_phase in ("distribute", "exhausted"):
        quality = QUALITY_BLOCKED
        vip_allowed = False

    # ── RULE 5: VIP threshold adjustment for late accumulation ─
    # This is communicated as a flag, the actual threshold is applied in app.py
    vip_threshold_reduction = 0
    if a_phase == "late" and a_pressure >= 50 and mom_score >= 40:
        vip_threshold_reduction = 10
        adjustments.append(
            "🟢 تخفيض عتبة VIP بـ 10 نقاط — نهاية تجميع مع ضغط عالي."
        )

    return {
        "unified_score": unified,
        "signal_quality": quality,
        "quality_label": QUALITY_LABELS.get(quality, ""),
        "quality_color": QUALITY_COLORS.get(quality, "#808080"),
        "vip_allowed": vip_allowed,
        "wolf_allowed": wolf_allowed,
        "wolf_downgraded": wolf_downgraded,
        "contradictions": contradictions,
        "adjustments": adjustments,
        "vip_threshold_reduction": vip_threshold_reduction,
    }
