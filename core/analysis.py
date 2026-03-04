import pandas as pd
import numpy as np
from core.utils import safe_div


# ── Adaptive Weight Regime Detection ─────────────────────────
def _detect_market_regime(last_close, ma50, ma200):
    """
    Detect market regime for adaptive scoring weights.
    Returns: (tech_weight, mom_weight, regime_name)
    """
    if pd.isna(ma50) or pd.isna(ma200):
        return 0.40, 0.60, "unknown"

    if last_close > ma50 and ma50 > ma200:
        return 0.45, 0.55, "uptrend"      # صاعد: تقنية أهم
    elif last_close < ma50 and ma50 < ma200:
        return 0.55, 0.45, "downtrend"     # هابط: تقنية أكثر أهمية للحماية
    else:
        return 0.35, 0.65, "sideways"      # تذبذب: الزخم يقود


# ── Confluence Stars Calculator ──────────────────────────────
def compute_confluence_stars(
    is_wolf=False, keyword_verdict="", is_blue_sky=False,
    vol_accel_ratio=0.0, final_score=0, news_adjustment=0,
    accum_phase="neutral"
) -> dict:
    """
    Calculate confluence stars (0-6) based on cross-signal agreement.
    Returns: {stars, display, signals[], multiplier}
    """
    stars = 0
    signals = []

    # ⭐ Wolf institutional breakout
    if is_wolf:
        stars += 1
        signals.append("🐺 وولف مؤسساتي")

    # ⭐ Rocket keywords positive
    if keyword_verdict == "🚀 إيجابي":
        stars += 1
        signals.append("🚀 كلمات صاروخية")

    # ⭐ Blue sky (no resistance)
    if is_blue_sky:
        stars += 1
        signals.append("🌌 سماء زرقاء")

    # ⭐ Volume explosion (2x+)
    if vol_accel_ratio >= 2.0:
        stars += 1
        signals.append("🌊 انفجار سيولة")

    # ⭐ Positive news + strong score
    if news_adjustment >= 5 and final_score >= 70:
        stars += 1
        signals.append("📰 أخبار داعمة")

    # ⭐ Institutional accumulation (strong, late, or healthy pullback)
    if accum_phase in ("strong", "late", "pullback_buy"):
        stars += 1
        signals.append("🏗️ تجميع مؤسساتي")

    # Multiplier based on star count (max 6 stars)
    if stars >= 6:
        multiplier = 1.18
    elif stars >= 5:
        multiplier = 1.15
    elif stars >= 4:
        multiplier = 1.10
    elif stars >= 3:
        multiplier = 1.05
    else:
        multiplier = 1.0

    display = "⭐" * stars if stars > 0 else ""

    return {
        "stars": stars,
        "display": display,
        "signals": signals,
        "multiplier": multiplier,
    }


def get_ai_analysis(
    last_close, ma50, ma200, rsi, counter, zr_low, zr_high,
    event_text, bo_score_add, mom_score, vol_accel_ratio, pct_1d,
    macro_status, is_forex, is_crypto, last_vwap, rr_ratio,
    daily_trend, interval, news_adjustment=0, is_wolf=False,
    rsi_divergence=None, vol_price_divergence=None, atr_regime=None,
    accumulation_data=None
):
    if pd.isna(ma50) or pd.isna(ma200):
        return 0, "انتظار ⏳", "#808080", ["بيانات غير كافية للتحليل."]

    tech_score = 50
    reasons = []

    is_macro_bull_stock = last_close > ma200
    is_micro_bull = last_close > ma50
    is_bleeding = (
        counter < 0
        or any(kw in event_text for kw in ["كسر", "سلبي", "تصحيح", "هابط", "🔻"])
    )
    dist_ma50 = safe_div(abs(last_close - ma50) * 100, ma50, 0)

    veto_max_59 = False
    veto_max_79 = False
    golden_watch = False

    is_zero_breakout = any(kw in event_text for kw in ["زيرو 👑", "سماء 🌌"])
    is_zero_breakdown = any(kw in event_text for kw in [
        "كسر زيرو 🩸", "انهيار سحيق 🔻", "سقوط 🩸"
    ])
    is_blue_sky = pd.notna(zr_high) and last_close > zr_high
    is_zero_bottom = pd.notna(zr_low) and last_close <= zr_low * 1.05

    macro_reason = ""
    is_absolute_lockdown = False

    mtf_reason = ""
    is_mtf_veto = False
    if interval != "1d":
        if daily_trend == "هابط ⛈️":
            tech_score -= 25
            is_mtf_veto = True
            veto_max_59 = True
            mtf_reason = (
                "🔍 <b>[مصفوفة التوافق MTF]:</b> الفريم اليومي الأكبر يعاني من مسار "
                "هابط شرس. تم حظر الاختراق اللحظي لمنع السباحة ضد التيار الأكبر."
            )
        else:
            tech_score += 15
            mtf_reason = (
                "🔍 <b>[مصفوفة التوافق MTF]:</b> اصطفاف نجمي إيجابي! الفريم اللحظي "
                "مدعوم بمسار صاعد مستقر ومؤكد على الفريم اليومي الأكبر."
            )

    if rr_ratio < 1.5:
        tech_score -= 20
        veto_max_59 = True
        reasons.append(
            f"⚖️ <b>[إدارة المخاطر R:R]:</b> نسبة الربح للمخاطرة سيئة "
            f"({rr_ratio:.1f}:1). تم حظر الدخول."
        )
    else:
        tech_score += 10
        reasons.append(
            f"⚖️ <b>[إدارة المخاطر R:R]:</b> العائد ممتاز "
            f"({rr_ratio:.1f}:1) ومحمي بوقف ATR المطاطي."
        )

    if pd.notna(last_vwap) and not is_forex:
        if last_close < last_vwap:
            tech_score -= 20
            veto_max_59 = True
            reasons.append(
                "🐋 <b>[مؤشر الحقيقة VWAP]:</b> السعر يتداول تحت متوسط "
                "تكلفة الحيتان (تصريف خفي). تم حظر الدخول."
            )
        else:
            tech_score += 10
            reasons.append(
                "🐋 <b>[مؤشر الحقيقة VWAP]:</b> السعر يتداول فوق متوسط "
                "تكلفة الحيتان (تجميع إيجابي مستمر)."
            )

    if macro_status == "سلبي ⛈️" and not is_forex:
        if is_zero_bottom and not is_zero_breakdown:
            tech_score += 15
            macro_reason = (
                "🛡️ <b>[تكتيك دفاعي]:</b> السوق ينزف، وهذا الأصل في قاع "
                "زيرو السحيق (استثناء آمن للاصطياد)."
            )
        elif is_blue_sky and (vol_accel_ratio >= 1.2 or is_crypto):
            tech_score += 20
            macro_reason = (
                "🌌 <b>[استثناء المتمرد]:</b> الأصل يحلق في سماء زرقاء "
                "متمرداً على سلبية المؤشر العام!"
            )
        else:
            tech_score -= 30
            is_absolute_lockdown = True
            macro_reason = (
                "🛑 <b>[الإغلاق المطلق 🔒]:</b> المؤشر ينزف والأصل ليس في "
                "قاع زيرو ولا يحلق في سماء زرقاء. تم حظر الدخول."
            )
    elif macro_status == "إيجابي ☀️" and not is_forex:
        if "اختراق" in event_text or is_blue_sky:
            tech_score += 10
            macro_reason = (
                "☀️ <b>[دعم الماكرو]:</b> طقس السوق صاعد ويدعم نجاح "
                "هذه الاختراقات بقوة."
            )

    if is_macro_bull_stock:
        tech_score += 15
        reasons.append(
            "✅ <b>الاتجاه العام:</b> يتداول في أمان استثماري (أعلى من 200)."
        )
    else:
        if is_micro_bull and mom_score >= 70 and not is_bleeding:
            golden_watch = True
            tech_score += 5
            reasons.append(
                f"👀 <b>مرحلة تعافي:</b> يحاول الارتداد رغم كونه تحت MA200."
            )
        else:
            tech_score -= 25
            veto_max_59 = True
            reasons.append(
                "❌ <b>الاتجاه العام:</b> ينهار تحت متوسط 200 (مسار هابط)."
            )

    if is_forex or is_crypto:
        tech_score += 10
        if (
            veto_max_59 and mom_score >= 60
            and (macro_status != "سلبي ⛈️" or is_forex)
            and not is_mtf_veto
        ):
            veto_max_59 = False
            veto_max_79 = True
    else:
        if vol_accel_ratio >= 1.2 and pct_1d > 0 and not is_bleeding:
            tech_score += 15
            reasons.append("🌊 <b>السيولة:</b> تدفق سيولة مؤسساتية عالية.")
            if (
                veto_max_59 and mom_score >= 60
                and macro_status != "سلبي ⛈️"
                and not is_mtf_veto
            ):
                veto_max_59 = False
                veto_max_79 = True
        elif vol_accel_ratio < 0.7:
            tech_score -= 5
            reasons.append("❄️ <b>السيولة:</b> التداولات ضعيفة وجافة.")

    if is_micro_bull:
        if dist_ma50 <= 3.5 and not is_bleeding:
            tech_score += 15
            reasons.append(
                "💎 <b>الدعم:</b> ارتداد إيجابي آمن بالقرب من متوسط 50."
            )
        elif dist_ma50 <= 3.5 and is_bleeding:
            veto_max_79 = True
            reasons.append(
                "⏳ <b>الدعم:</b> السعر يختبر الدعم اللحظي، ننتظر توقف النزيف."
            )
        elif dist_ma50 > 8.0 and not is_blue_sky:
            tech_score -= 10
            veto_max_79 = True
            reasons.append(
                f"⚠️ <b>التضخم:</b> السعر ابتعد عن الدعم بنسبة {dist_ma50:.1f}%."
            )
    else:
        if not golden_watch:
            tech_score -= 20
            veto_max_59 = True
            reasons.append(
                "🔴 <b>المضاربة:</b> السعر سلبي ويكسر متوسط 50 اللحظي."
            )

    if is_zero_breakdown:
        tech_score -= 40
        veto_max_59 = True
        reasons.append(
            "🔻 <b>[انهيار تاريخي]:</b> السعر يكسر قاع 300 شمعة "
            "ويسقط في الهاوية. حظر دخول نهائي!"
        )
    elif any(e in event_text for e in ["🚀", "🟢", "💎", "📈", "🔥", "👑", "🌌"]):
        tech_score += 10
        reasons.append("⚡ <b>الحدث:</b> إشارة إيجابية داعمة في الشموع الأخيرة.")
    elif any(e in event_text for e in ["🩸", "🔴", "🛑", "⚠️", "📉"]):
        tech_score -= 15
        reasons.append("⚠️ <b>الحدث:</b> ضغط بيعي واضح.")
        if "كسر" in event_text:
            veto_max_59 = True

    if is_zero_bottom and macro_status != "سلبي ⛈️" and not is_zero_breakdown:
        tech_score += 10
        reasons.append(
            "🎯 <b>زيرو انعكاس:</b> السعر رخيص جداً ويختبر قاع القناة التاريخي."
        )

    if is_blue_sky:
        tech_score += 25
        if not is_zero_breakout:
            reasons.append(
                "🌌 <b>سماء زرقاء:</b> يواصل التحليق فوق قمة زيرو "
                "التاريخية بلا مقاومات."
            )
        else:
            reasons.append(
                "👑 <b>انفجار تاريخي:</b> يخترق سقف زيرو الآن وينطلق "
                "في سماء مفتوحة."
            )
    elif (
        pd.notna(zr_high) and last_close >= zr_high * 0.97
        and last_close <= zr_high
    ):
        tech_score -= 15
        veto_max_79 = True
        reasons.append(
            "🧱 <b>تحذير زيرو:</b> السعر متضخم ويصطدم بسقف القناة كمقاومة."
        )

    # ── Divergence Scoring ──────────────────────────────────
    if rsi_divergence and rsi_divergence.get("type") != "none":
        div_type = rsi_divergence["type"]
        div_strength = rsi_divergence.get("strength", 0)
        if div_type == "bearish" and div_strength >= 0.3:
            penalty = int(-10 * div_strength)
            tech_score += penalty
            veto_max_79 = True
            reasons.append(rsi_divergence.get("description_ar", "📉 تباين RSI هبوطي"))
        elif div_type == "bullish" and div_strength >= 0.3:
            bonus = int(8 * div_strength)
            tech_score += bonus
            reasons.append(rsi_divergence.get("description_ar", "📈 تباين RSI صعودي"))

    if vol_price_divergence and vol_price_divergence.get("type") != "none":
        vpd_type = vol_price_divergence["type"]
        if vpd_type == "bearish":
            tech_score -= 8
            veto_max_79 = True
            reasons.append(vol_price_divergence.get("description_ar", "📉 تباين حجم هبوطي"))
        elif vpd_type == "bullish":
            tech_score += 5
            reasons.append(vol_price_divergence.get("description_ar", "📈 تباين حجم صعودي"))
        elif vpd_type == "confirmed":
            tech_score += 3
            reasons.append(vol_price_divergence.get("description_ar", "✅ تأكيد حجم"))

    if atr_regime and atr_regime.get("score_modifier", 0) != 0:
        tech_score += atr_regime["score_modifier"]
        if atr_regime.get("description_ar"):
            reasons.append(atr_regime["description_ar"])

    # ── Accumulation Phase Scoring ────────────────────────────
    accum_veto_79 = False
    if accumulation_data and isinstance(accumulation_data, dict):
        a_phase = accumulation_data.get("phase", "neutral")
        a_score = accumulation_data.get("score", 0)
        a_days = accumulation_data.get("days", 0)
        a_zr_bonus = accumulation_data.get("zr_bonus", 0)
        a_cmf = accumulation_data.get("cmf", 0)

        if a_phase == "late":
            bonus = 12
            if a_zr_bonus > 0:
                bonus += 10
            tech_score += bonus
            zr_txt = " + 💎 قرب قاع زيرو" if a_zr_bonus > 0 else ""
            reasons.append(
                f"🏗️ <b>[نهاية تجميع 🟢]:</b> سكور التجميع {a_score}/100 "
                f"({a_days} يوم تراكم){zr_txt}. جاهز للانطلاق!"
            )
        elif a_phase == "strong":
            bonus = 8
            if a_zr_bonus > 0:
                bonus += 10
            tech_score += bonus
            zr_txt = " + 💎 قرب قاع زيرو" if a_zr_bonus > 0 else ""
            reasons.append(
                f"🏗️ <b>[تجميع قوي 🔵]:</b> سكور {a_score}/100 "
                f"({a_days} يوم تراكم){zr_txt}. ضغط شرائي مستمر."
            )
        elif a_phase == "mid":
            tech_score += 4
            reasons.append(
                f"🏗️ <b>[وسط التجميع 🟣]:</b> سكور {a_score}/100 "
                f"({a_days} يوم). مرحلة بناء المراكز."
            )
        elif a_phase == "distribute":
            tech_score -= 10
            accum_veto_79 = True
            reasons.append(
                f"🏗️ <b>[تصريف مؤسساتي 🔴]:</b> CMF سلبي ({a_cmf:+.3f}) "
                f"مع OBV هابط. المؤسسات تبيع!"
            )
        # ── Lifecycle phases (post-breakout) ──────────────
        elif a_phase == "breakout":
            tech_score += 5
            reasons.append(
                f"🏗️ <b>[انطلاق 🚀]:</b> السهم كسر بعد تجميع مؤسساتي. "
                f"اللحاق محفوف بالمخاطر — راقب التراجع."
            )
        elif a_phase == "pullback_buy":
            tech_score += 10
            reasons.append(
                f"🏗️ <b>[ارتداد صحي 🟢]:</b> السهم انطلق سابقاً وتراجع بشكل صحي. "
                f"CMF إيجابي ({a_cmf:+.3f}) — فرصة دخول ثانية!"
            )
        elif a_phase == "pullback_wait":
            tech_score += 0
            reasons.append(
                f"🏗️ <b>[ارتداد — انتظر 🟡]:</b> السهم انطلق سابقاً لكن التراجع غير مؤكد. "
                f"انتظر تأكيد CMF."
            )
        elif a_phase == "exhausted":
            tech_score -= 8
            accum_veto_79 = True
            reasons.append(
                f"🏗️ <b>[استنفاد 🔴]:</b> السهم انطلق وأعاد معظم حركته. "
                f"الفرصة انتهت — لا تدخل."
            )

    # ── Adaptive Weights ─────────────────────────────────────
    tech_score = int(max(0, min(100, tech_score)))
    tech_w, mom_w, _regime = _detect_market_regime(last_close, ma50, ma200)
    final_score = int((tech_score * tech_w) + (mom_score * mom_w))

    # --- News Sentiment Adjustment ---
    if news_adjustment != 0:
        final_score = final_score + news_adjustment
        final_score = max(0, min(100, final_score))
        if news_adjustment > 0:
            reasons.append(
                f"📰 <b>تأثير الأخبار:</b> أخبار إيجابية رفعت التقييم (+{news_adjustment})"
            )
        else:
            reasons.append(
                f"📰 <b>تأثير الأخبار:</b> أخبار سلبية خفضت التقييم ({news_adjustment})"
            )
        # Excellent news can override soft veto (veto_max_79 only)
        if news_adjustment >= 8 and veto_max_79 and not veto_max_59 and not is_absolute_lockdown:
            veto_max_79 = False
            reasons.append(
                "📰 <b>[تجاوز إخباري]:</b> أخبار ممتازة جداً تتجاوز الفيتو الخفيف!"
            )

    # --- Wolf V2 Confirmation Bonus ---
    if is_wolf:
        final_score = final_score + 10
        final_score = max(0, min(100, final_score))
        reasons.append(
            "🐺 <b>[تأكيد وولف]:</b> اختراق مؤسساتي مدعوم بـ 8 مرشحات "
            "(تغير يومي + سيولة + زخم + ترند + ماكرو)."
        )
        if veto_max_79 and not veto_max_59 and not is_absolute_lockdown:
            veto_max_79 = False
            reasons.append(
                "🐺 <b>[تجاوز وولف]:</b> قوة الاختراق المؤسساتي تتجاوز الفيتو الخفيف!"
            )

    reasons = [r for r in reasons if r]
    reasons.insert(
        0, f"📊 <b>الزخم التراكمي:</b> تقييم قوة الحركة هو <b>{mom_score}/100</b>."
    )

    if mtf_reason:
        reasons.insert(0, mtf_reason)

    if is_absolute_lockdown:
        final_score = min(final_score, 59)
        if macro_reason:
            reasons.insert(0, macro_reason)
    else:
        if macro_reason:
            reasons.insert(0, macro_reason)
        if golden_watch and not is_bleeding:
            final_score = min(max(final_score, 60), 79)
            reasons.insert(
                0,
                "🛡️ <b>[فيتو التعافي]:</b> تم تخفيض التقييم للمراقبة "
                "لأن الأصل ما زال تحت MA200."
            )
        elif not is_macro_bull_stock and not is_micro_bull and is_bleeding:
            final_score = min(final_score, 59)
            reasons.insert(
                0,
                "🛑 <b>[فيتو الانهيار]:</b> الأصل ضعيف جداً ومنهار، "
                "تم فرض حظر الدخول."
            )
        elif veto_max_59 and not golden_watch:
            final_score = min(final_score, 59)
            reasons.insert(
                0,
                "🛡️ <b>[فيتو المخاطر]:</b> تم فرض حظر الدخول بسبب "
                "العيوب القاتلة (الفيتو)."
            )
        elif (veto_max_79 or accum_veto_79 or (pd.notna(rsi) and rsi > 72)) and not is_blue_sky:
            final_score = min(final_score, 79)
            reasons.insert(
                0,
                "🛡️ <b>[فيتو الأمان]:</b> السعر متضخم (مؤشرات عالية)، "
                "تم منعه من الـ VIP لتجنب التعليقة."
            )

    if final_score >= 80:
        if is_blue_sky:
            dec, col = "سماء زرقاء 🌌", "#FFD700"
        else:
            dec, col = "دخول قوي 🟢", "#00E676"
    elif final_score >= 60:
        if is_blue_sky:
            dec, col = "مراقبة الانفجار 🌌", "#FFD700"
        else:
            dec, col = "مراقبة 🟡", "#FFD700"
    else:
        dec, col = "تجنب 🔴", "#FF5252"

    return final_score, dec, col, reasons
