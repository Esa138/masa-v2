import pandas as pd
import numpy as np
from core.utils import safe_div


def get_ai_analysis(
    last_close, ma50, ma200, rsi, counter, zr_low, zr_high,
    event_text, bo_score_add, mom_score, vol_accel_ratio, pct_1d,
    macro_status, is_forex, is_crypto, last_vwap, rr_ratio,
    daily_trend, interval
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

    tech_score = int(max(0, min(100, tech_score)))
    final_score = int((tech_score * 0.4) + (mom_score * 0.6))

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
        elif (veto_max_79 or (pd.notna(rsi) and rsi > 72)) and not is_blue_sky:
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
