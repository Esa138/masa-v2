"""
MASA QUANT — التحليل الموسمي للقطاعات
seasonality.py

يحلل أداء القطاعات شهرياً على مدى سنوات ويكتشف:
- الأشهر الإيجابية والسلبية + Sharpe Ratio
- أشهر التجميع والتصريف
- أشهر التحسن (التحول من سلبي لإيجابي)
- Win/Loss Ratio و Profit Factor
- ربط بمحفزات أساسية (توزيعات، نتائج، رمضان)
"""

import pandas as pd
import numpy as np
from datetime import datetime


MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

# ══════════════════════════════════════════
# المحفزات الأساسية — خاصة بكل قطاع
# ══════════════════════════════════════════

# محفزات عامة للسوق (تُستخدم كأساس + تُدمج مع المحفزات القطاعية)
_SAUDI_BASE = {
    1:  {"events": ["بداية السنة المالية"], "impact": "محايد", "note": "تدفقات صناديق + إعادة تخصيص محافظ"},
    2:  {"events": ["نتائج Q4 السنوية"], "impact": "إيجابي", "note": "موسم النتائج السنوية"},
    3:  {"events": ["نهاية Q1", "رمضان (متغير)"], "impact": "محايد", "note": "نهاية الربع الأول + رمضان"},
    4:  {"events": ["نتائج Q1", "عيد الفطر (متغير)"], "impact": "إيجابي", "note": "موسم نتائج Q1 + سيولة ما بعد العيد"},
    5:  {"events": ["Sell in May"], "impact": "سلبي", "note": "جني أرباح + Sell in May عالمياً"},
    6:  {"events": ["عيد الأضحى (متغير)", "إجازة صيفية"], "impact": "سلبي", "note": "انخفاض السيولة — إجازات"},
    7:  {"events": ["نتائج Q2 النصف سنوية"], "impact": "محايد", "note": "نتائج نصف سنوية — سيولة منخفضة"},
    8:  {"events": ["عودة السيولة"], "impact": "محايد", "note": "بداية عودة المتداولين"},
    9:  {"events": ["عودة السيولة الكاملة"], "impact": "إيجابي", "note": "عودة قوية للسيولة"},
    10: {"events": ["نتائج Q3"], "impact": "إيجابي", "note": "نتائج Q3"},
    11: {"events": ["ميزانية الحكومة", "Window Dressing"], "impact": "إيجابي", "note": "ترقب ميزانية + تجميل محافظ"},
    12: {"events": ["إعلان الميزانية", "نهاية السنة"], "impact": "محايد", "note": "ميزانية + تذبذب نهاية السنة"},
}

# محفزات خاصة بكل قطاع سعودي
SAUDI_SECTOR_CATALYSTS = {
    "البنوك": {
        2:  {"events": ["إعلان أرباح سنوية", "توزيعات سنوية"], "impact": "إيجابي قوي", "note": "البنوك تعلن أرباح قياسية + توزيعات سنوية — شراء مؤسسي قبل الاستحقاق"},
        3:  {"events": ["تاريخ استحقاق التوزيعات", "شراء قبل الاستحقاق"], "impact": "إيجابي قوي", "note": "شراء مكثف قبل تاريخ الاستحقاق — أقوى محفز للبنوك"},
        4:  {"events": ["صرف التوزيعات", "نتائج Q1"], "impact": "إيجابي", "note": "سيولة التوزيعات تُعاد استثمارها + نتائج Q1"},
        5:  {"events": ["جني أرباح ما بعد التوزيعات"], "impact": "سلبي", "note": "بيع ما بعد الاستحقاق — السهم يتراجع بمقدار التوزيع"},
        9:  {"events": ["توزيعات نصف سنوية (بعض البنوك)"], "impact": "إيجابي", "note": "الراجحي والأهلي يوزعون نصف سنوي"},
        10: {"events": ["نتائج Q3", "قرارات الفائدة"], "impact": "إيجابي", "note": "نتائج Q3 + تأثير قرارات الفائدة على هوامش البنوك"},
    },
    "الطاقة": {
        1:  {"events": ["اجتماع أوبك+", "تحديد حصص الإنتاج"], "impact": "محايد", "note": "ترقب قرارات أوبك — تأثير مباشر على أسعار النفط"},
        3:  {"events": ["أرامكو: نتائج سنوية + توزيعات"], "impact": "إيجابي قوي", "note": "أرامكو تعلن نتائج + توزيعات ضخمة — تحرك المؤشر العام"},
        5:  {"events": ["اجتماع أوبك+ منتصف السنة"], "impact": "محايد", "note": "مراجعة حصص الإنتاج"},
        6:  {"events": ["موسم القيادة الأمريكي (طلب بنزين)"], "impact": "إيجابي", "note": "ارتفاع الطلب العالمي على الوقود"},
        10: {"events": ["موسم الشتاء (طلب تدفئة)", "نتائج Q3"], "impact": "إيجابي", "note": "ارتفاع الطلب الموسمي + نتائج أرامكو Q3"},
    },
    "المواد الأساسية": {
        2:  {"events": ["نتائج البتروكيم السنوية"], "impact": "إيجابي", "note": "سابك وصناعات تعلن أرباح سنوية — محفز رئيسي"},
        4:  {"events": ["نتائج Q1", "أسعار المواد الخام عالمياً"], "impact": "محايد", "note": "ربط بأسعار النفط والإيثيلين عالمياً"},
        7:  {"events": ["نتائج نصف سنوية", "موسم بناء (طلب أسمنت)"], "impact": "محايد", "note": "نتائج H1 + طلب موسمي على مواد البناء"},
        9:  {"events": ["عودة مشاريع البناء"], "impact": "إيجابي", "note": "نشاط المقاولات يرتفع بعد الصيف"},
    },
    "السلع الكمالية": {
        1:  {"events": ["عودة المدارس (ملابس/أجهزة)"], "impact": "إيجابي", "note": "موسم تسوق — ملابس وأجهزة إلكترونية"},
        3:  {"events": ["رمضان (استهلاك مرتفع)"], "impact": "إيجابي قوي", "note": "رمضان أقوى موسم استهلاك — مبيعات قياسية"},
        4:  {"events": ["عيد الفطر (تسوق + هدايا)"], "impact": "إيجابي قوي", "note": "موسم العيد — أعلى مبيعات في السنة"},
        6:  {"events": ["عيد الأضحى", "موسم الحج"], "impact": "إيجابي", "note": "موسم الحج — طلب سياحي + هدايا"},
        9:  {"events": ["عودة المدارس"], "impact": "إيجابي", "note": "موسم العودة للمدارس — ملابس + قرطاسية"},
        11: {"events": ["White Friday", "موسم التخفيضات"], "impact": "إيجابي", "note": "تخفيضات نوفمبر — مبيعات أونلاين قياسية"},
        12: {"events": ["موسم نهاية السنة", "هدايا"], "impact": "إيجابي", "note": "تسوق نهاية السنة + الرياض سيزون"},
    },
    "السلع الاستهلاكية": {
        3:  {"events": ["رمضان (أغذية + مشروبات)"], "impact": "إيجابي قوي", "note": "أقوى شهر — ارتفاع الطلب على الأغذية والمشروبات والتمور"},
        4:  {"events": ["عيد الفطر"], "impact": "إيجابي", "note": "استمرار الطلب — ولائم وتجمعات العيد"},
        6:  {"events": ["موسم الحج", "عيد الأضحى"], "impact": "إيجابي", "note": "طلب حجاج + ولائم الأضحى"},
        7:  {"events": ["نتائج H1 — شركات الأغذية"], "impact": "محايد", "note": "نتائج المراعي + صافولا + المنجم"},
        12: {"events": ["موسم نهاية السنة"], "impact": "محايد", "note": "تسوق عائلي + رأس السنة"},
    },
    "الاتصالات": {
        2:  {"events": ["نتائج سنوية + توزيعات"], "impact": "إيجابي", "note": "STC + زين + موبايلي — توزيعات مجزية"},
        3:  {"events": ["استحقاق التوزيعات"], "impact": "إيجابي", "note": "شراء قبل الاستحقاق — قطاع دفاعي"},
        5:  {"events": ["موسم إجازة (ارتفاع بيانات)"], "impact": "محايد", "note": "ارتفاع استهلاك البيانات في الإجازات"},
        10: {"events": ["نتائج Q3", "5G expansion"], "impact": "إيجابي", "note": "نتائج Q3 + تطوير شبكات الجيل الخامس"},
    },
    "العقارات": {
        1:  {"events": ["بداية مشاريع جديدة"], "impact": "محايد", "note": "إطلاق مشاريع رؤية 2030 الجديدة"},
        3:  {"events": ["موسم الحج (سكن + فنادق)"], "impact": "إيجابي", "note": "ارتفاع إشغال فنادق مكة والمدينة"},
        6:  {"events": ["موسم الحج الفعلي"], "impact": "إيجابي قوي", "note": "ذروة الإشغال الفندقي + إيرادات الحج"},
        9:  {"events": ["عودة النشاط العقاري"], "impact": "إيجابي", "note": "نشاط بيع وإيجار بعد الصيف"},
        11: {"events": ["ميزانية + مشاريع حكومية"], "impact": "إيجابي", "note": "إعلانات مشاريع جديدة ضمن الميزانية"},
    },
    "الرعاية الصحية": {
        2:  {"events": ["نتائج سنوية"], "impact": "إيجابي", "note": "نتائج المستشفيات السنوية — نمو مستمر"},
        6:  {"events": ["موسم الحج (خدمات طبية)"], "impact": "إيجابي", "note": "عقود خدمات طبية لموسم الحج"},
        9:  {"events": ["عودة المدارس (فحوصات)"], "impact": "محايد", "note": "فحوصات طبية إلزامية + تأمين"},
        11: {"events": ["ميزانية الصحة"], "impact": "إيجابي", "note": "تخصيصات ميزانية للقطاع الصحي"},
    },
    "التأمين": {
        1:  {"events": ["تجديد وثائق التأمين السنوية"], "impact": "إيجابي", "note": "موسم تجديد — إيرادات أقساط"},
        3:  {"events": ["إلزام تأمين صحي (تحديثات)"], "impact": "إيجابي", "note": "تحديثات تنظيمية + توسع التغطية"},
        7:  {"events": ["نتائج H1"], "impact": "محايد", "note": "نتائج نصف سنوية — قطاع متذبذب"},
        9:  {"events": ["تأمين المركبات (موسم)"], "impact": "إيجابي", "note": "موسم تجديد تأمين المركبات"},
    },
    "التقنية": {
        1:  {"events": ["ميزانيات IT جديدة"], "impact": "إيجابي", "note": "شركات تبدأ إنفاق ميزانيات التقنية الجديدة"},
        4:  {"events": ["نتائج Q1", "مشاريع رقمنة"], "impact": "إيجابي", "note": "عقود حكومية للتحول الرقمي"},
        10: {"events": ["LEAP Conference", "نتائج Q3"], "impact": "إيجابي قوي", "note": "مؤتمر LEAP — إعلانات عقود ومشاريع ضخمة"},
        11: {"events": ["ميزانية التحول الرقمي"], "impact": "إيجابي", "note": "تخصيصات ميزانية لرؤية 2030 الرقمية"},
    },
    "المرافق العامة": {
        6:  {"events": ["ذروة استهلاك الكهرباء (صيف)"], "impact": "إيجابي", "note": "ارتفاع حاد في الطلب على الكهرباء والمياه"},
        7:  {"events": ["استمرار ذروة الصيف"], "impact": "إيجابي", "note": "أعلى إيرادات موسمية للكهرباء"},
        8:  {"events": ["ذروة الصيف الأخيرة"], "impact": "إيجابي", "note": "آخر شهر ذروة — فواتير مرتفعة"},
        12: {"events": ["شتاء (انخفاض طلب)"], "impact": "سلبي", "note": "انخفاض الطلب الموسمي على الكهرباء"},
    },
    "النقل": {
        3:  {"events": ["رمضان (عمرة)"], "impact": "إيجابي", "note": "ارتفاع الطلب على النقل — عمرة رمضان"},
        6:  {"events": ["موسم الحج"], "impact": "إيجابي قوي", "note": "أقوى موسم — نقل حجاج بري وجوي"},
        7:  {"events": ["إجازة صيفية + سفر"], "impact": "إيجابي", "note": "سفر عائلي + رحلات صيفية"},
        12: {"events": ["موسم الرياض + سياحة شتوية"], "impact": "إيجابي", "note": "سياحة داخلية + موسم الرياض"},
    },
    "الخدمات المالية": {
        1:  {"events": ["إعادة تخصيص محافظ"], "impact": "إيجابي", "note": "صناديق تعيد تخصيص أصولها — عمولات عالية"},
        3:  {"events": ["IPOs موسمية"], "impact": "إيجابي", "note": "موسم طرح اكتتابات جديدة"},
        4:  {"events": ["نتائج Q1 + أحجام تداول"], "impact": "إيجابي", "note": "ارتفاع أحجام التداول — عمولات أعلى"},
        11: {"events": ["Window Dressing"], "impact": "إيجابي", "note": "تجميل محافظ الصناديق نهاية السنة"},
    },
}

US_CATALYSTS = {
    1:  {"events": ["بداية السنة", "نتائج Q4"], "impact": "إيجابي", "note": "January Effect + موسم نتائج"},
    2:  {"events": ["نتائج Q4 متأخرة"], "impact": "محايد", "note": "استمرار موسم النتائج"},
    3:  {"events": ["نهاية Q1", "قرار الفيدرالي"], "impact": "محايد", "note": "ترقب قرارات الفائدة"},
    4:  {"events": ["نتائج Q1", "Tax Season"], "impact": "إيجابي", "note": "موسم نتائج Q1 — تك كبيرة تعلن"},
    5:  {"events": ["Sell in May"], "impact": "سلبي", "note": "Sell in May and go away — نمط تاريخي"},
    6:  {"events": ["قرار الفيدرالي", "نهاية النصف الأول"], "impact": "محايد", "note": "ترقب الفائدة"},
    7:  {"events": ["نتائج Q2", "أرباح التك"], "impact": "إيجابي", "note": "موسم أرباح التك الكبيرة"},
    8:  {"events": ["Jackson Hole"], "impact": "سلبي", "note": "تذبذب — ترقب خطاب الفيدرالي"},
    9:  {"events": ["عودة من الإجازة", "September Effect"], "impact": "سلبي قوي", "note": "أسوأ شهر تاريخياً"},
    10: {"events": ["نتائج Q3", "October Surprise"], "impact": "محايد", "note": "تذبذب عالي + بداية ارتداد"},
    11: {"events": ["الانتخابات (كل 4 سنوات)", "Black Friday"], "impact": "إيجابي قوي", "note": "أقوى شهر تاريخياً"},
    12: {"events": ["Santa Rally", "Tax Loss Harvesting"], "impact": "إيجابي", "note": "ارتفاع نهاية السنة"},
}


def _get_sector_catalysts(sector_name, market_key="saudi"):
    """يرجع المحفزات الخاصة بالقطاع — يدمج القطاعية مع العامة."""
    if market_key != "saudi":
        return US_CATALYSTS

    base = dict(_SAUDI_BASE)  # نسخة من العامة
    sector_specific = SAUDI_SECTOR_CATALYSTS.get(sector_name, {})

    # دمج: المحفزات القطاعية تتقدم على العامة
    merged = {}
    for mo in range(1, 13):
        if mo in sector_specific:
            # قطاعي — أضف أحداث عامة إذا ما تتعارض
            sec = sector_specific[mo]
            gen = base.get(mo, {})
            gen_events = gen.get("events", [])
            # أضف الأحداث العامة اللي مو مذكورة في القطاعي
            combined_events = list(sec["events"])
            for e in gen_events:
                if e not in combined_events:
                    combined_events.append(e)
            merged[mo] = {
                "events": combined_events,
                "impact": sec["impact"],  # القطاعي يتقدم
                "note": sec["note"],
            }
        elif mo in base:
            # عام فقط
            merged[mo] = dict(base[mo])

    return merged


def compute_monthly_returns(dates, vals):
    """
    يحسب العائد الشهري من بيانات يومية.
    Returns: list of {year, month, month_ar, return_pct, start_val, end_val}
    """
    if not dates or not vals or len(dates) < 20:
        return []

    df = pd.DataFrame({"date": dates, "val": vals})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    monthly = []
    for (yr, mo), grp in df.groupby(["year", "month"]):
        if len(grp) < 5:
            continue
        start_val = float(grp["val"].iloc[0])
        end_val = float(grp["val"].iloc[-1])
        if start_val <= 0:
            continue
        ret = (end_val - start_val) / start_val * 100
        monthly.append({
            "year": int(yr),
            "month": int(mo),
            "month_ar": MONTH_NAMES_AR.get(int(mo), str(mo)),
            "return_pct": round(ret, 2),
            "start_val": round(start_val, 2),
            "end_val": round(end_val, 2),
        })

    return monthly


def compute_seasonality_stats(monthly_returns):
    """
    يحسب إحصائيات موسمية لكل شهر مع Sharpe + Win/Loss Ratio + Profit Factor.
    """
    if not monthly_returns:
        return {}

    stats = {}
    for mo in range(1, 13):
        mo_data = [m for m in monthly_returns if m["month"] == mo]
        if not mo_data:
            continue

        returns = [m["return_pct"] for m in mo_data]
        years = [m["year"] for m in mo_data]

        positive = sum(1 for r in returns if r > 0)
        negative = sum(1 for r in returns if r < 0)
        total = len(returns)

        avg_ret = float(np.mean(returns))
        median_ret = float(np.median(returns))
        std_ret = float(np.std(returns)) if len(returns) > 1 else 0.01

        # ── Sharpe Ratio (شهري) ──
        sharpe = round(avg_ret / std_ret, 2) if std_ret > 0.01 else 0

        # ── Win/Loss Ratio + Profit Factor ──
        winning_returns = [r for r in returns if r > 0]
        losing_returns = [r for r in returns if r < 0]

        avg_win = float(np.mean(winning_returns)) if winning_returns else 0
        avg_loss = float(np.mean(losing_returns)) if losing_returns else 0
        # Win/Loss ratio: avg win ÷ |avg loss|
        win_loss_ratio = round(avg_win / abs(avg_loss), 2) if avg_loss != 0 else (
            99.0 if avg_win > 0 else 0
        )
        # Profit Factor: total gains ÷ |total losses|
        total_gains = sum(winning_returns) if winning_returns else 0
        total_losses = abs(sum(losing_returns)) if losing_returns else 0.01
        profit_factor = round(total_gains / total_losses, 2) if total_losses > 0.01 else (
            99.0 if total_gains > 0 else 0
        )

        # ── Classify month ──
        win_rate = positive / total * 100 if total > 0 else 0
        if win_rate >= 70 and avg_ret > 1:
            phase = "إيجابي قوي"
            phase_icon = "🟢"
            phase_color = "#00E676"
        elif win_rate >= 55 and avg_ret > 0:
            phase = "إيجابي"
            phase_icon = "🟢"
            phase_color = "#4CAF50"
        elif win_rate <= 30 and avg_ret < -1:
            phase = "سلبي قوي"
            phase_icon = "🔴"
            phase_color = "#F44336"
        elif win_rate <= 45 and avg_ret < 0:
            phase = "سلبي"
            phase_icon = "🔴"
            phase_color = "#E57373"
        else:
            phase = "محايد"
            phase_icon = "⚪"
            phase_color = "#9E9E9E"

        # ── Warning: high win rate but negative expectancy ──
        expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)
        misleading = win_rate > 60 and expectancy < 0

        stats[mo] = {
            "month": mo,
            "month_ar": MONTH_NAMES_AR.get(mo, str(mo)),
            "avg_return": round(avg_ret, 2),
            "median_return": round(median_ret, 2),
            "win_rate": round(win_rate, 1),
            "positive": positive,
            "negative": negative,
            "total_years": total,
            "best": round(max(returns), 2),
            "worst": round(min(returns), 2),
            "std": round(std_ret, 2),
            "sharpe": sharpe,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "win_loss_ratio": win_loss_ratio,
            "profit_factor": profit_factor,
            "expectancy": round(expectancy, 2),
            "misleading": misleading,
            "years": years,
            "returns_by_year": {m["year"]: m["return_pct"] for m in mo_data},
            "phase": phase,
            "phase_icon": phase_icon,
            "phase_color": phase_color,
        }

    return stats


def detect_transitions(seasonality_stats):
    """يكتشف أشهر التحول (من سلبي لإيجابي والعكس)."""
    transitions = []
    months = sorted(seasonality_stats.keys())

    for i in range(len(months)):
        curr = months[i]
        prev = months[i - 1] if i > 0 else months[-1]

        curr_stats = seasonality_stats[curr]
        prev_stats = seasonality_stats[prev]

        prev_avg = prev_stats["avg_return"]
        curr_avg = curr_stats["avg_return"]

        if prev_avg < -0.5 and curr_avg > 0.5:
            transitions.append({
                "from_month": prev, "to_month": curr,
                "from_ar": prev_stats["month_ar"], "to_ar": curr_stats["month_ar"],
                "type": "تحسن", "icon": "📈", "color": "#00E676",
                "description": (
                    f"تحول إيجابي: {prev_stats['month_ar']} ({prev_avg:+.1f}%) → "
                    f"{curr_stats['month_ar']} ({curr_avg:+.1f}%)"
                ),
            })
        elif prev_avg > 0.5 and curr_avg < -0.5:
            transitions.append({
                "from_month": prev, "to_month": curr,
                "from_ar": prev_stats["month_ar"], "to_ar": curr_stats["month_ar"],
                "type": "تدهور", "icon": "📉", "color": "#F44336",
                "description": (
                    f"تحول سلبي: {prev_stats['month_ar']} ({prev_avg:+.1f}%) → "
                    f"{curr_stats['month_ar']} ({curr_avg:+.1f}%)"
                ),
            })

    return transitions


def get_current_month_insight(seasonality_stats, catalysts=None):
    """يعطي نصيحة عن الشهر الحالي بناءً على التاريخ + المحفزات."""
    current_month = datetime.now().month
    if current_month not in seasonality_stats:
        return None

    s = seasonality_stats[current_month]
    next_month = (current_month % 12) + 1

    insight = {
        "month_ar": s["month_ar"],
        "avg_return": s["avg_return"],
        "win_rate": s["win_rate"],
        "sharpe": s.get("sharpe", 0),
        "profit_factor": s.get("profit_factor", 0),
        "phase": s["phase"],
        "phase_icon": s["phase_icon"],
        "misleading": s.get("misleading", False),
    }

    # Add catalyst info
    if catalysts and current_month in catalysts:
        cat = catalysts[current_month]
        insight["catalyst_events"] = cat["events"]
        insight["catalyst_note"] = cat["note"]
        insight["catalyst_impact"] = cat["impact"]

    # Next month
    if next_month in seasonality_stats:
        ns = seasonality_stats[next_month]
        insight["next_month_ar"] = ns["month_ar"]
        insight["next_avg"] = ns["avg_return"]
        insight["next_phase"] = ns["phase"]
        insight["next_icon"] = ns["phase_icon"]
        if catalysts and next_month in catalysts:
            insight["next_catalyst"] = catalysts[next_month]["note"]

    return insight


def build_seasonality_for_sectors(sector_composites, market_key="saudi"):
    """
    يبني التحليل الموسمي لكل القطاعات مع محفزات خاصة بكل قطاع.

    Parameters:
        sector_composites: dict {sector_name: {dates, vals, ret}}
        market_key: "saudi" or "us" — لتحديد المحفزات الأساسية
    """
    result = {}

    for sector_name, data in sector_composites.items():
        dates = data.get("dates", [])
        vals = data.get("vals", [])

        monthly = compute_monthly_returns(dates, vals)
        if not monthly:
            continue

        # محفزات خاصة بهذا القطاع
        catalysts = _get_sector_catalysts(sector_name, market_key)

        stats = compute_seasonality_stats(monthly)
        transitions = detect_transitions(stats)
        insight = get_current_month_insight(stats, catalysts)

        result[sector_name] = {
            "monthly": monthly,
            "stats": stats,
            "transitions": transitions,
            "insight": insight,
            "years_covered": sorted(set(m["year"] for m in monthly)),
            "catalysts": catalysts,
        }

    return result
