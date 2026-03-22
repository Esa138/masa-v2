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
# المحفزات الأساسية — السوق السعودي
# ══════════════════════════════════════════
SAUDI_CATALYSTS = {
    1: {
        "events": ["بداية السنة المالية", "إعلان ميزانية Q4"],
        "impact": "محايد",
        "note": "تدفقات جديدة من صناديق + إعادة تخصيص المحافظ",
    },
    2: {
        "events": ["نتائج Q4 السنوية", "إعلان التوزيعات السنوية"],
        "impact": "إيجابي",
        "note": "موسم النتائج — البنوك والبتروكيم تعلن أرباح سنوية",
    },
    3: {
        "events": ["نهاية Q1", "رمضان (متغير)", "توزيعات البنوك"],
        "impact": "إيجابي",
        "note": "تاريخ استحقاق توزيعات البنوك — شراء قبل الاستحقاق",
    },
    4: {
        "events": ["نتائج Q1", "عيد الفطر (متغير)", "موسم التوزيعات"],
        "impact": "إيجابي قوي",
        "note": "موسم نتائج Q1 + توزيعات البنوك الكبرى + سيولة ما بعد العيد",
    },
    5: {
        "events": ["Sell in May", "نهاية موسم التوزيعات"],
        "impact": "سلبي",
        "note": "جني أرباح بعد موسم التوزيعات + Sell in May عالمياً",
    },
    6: {
        "events": ["عيد الأضحى (متغير)", "إجازة صيفية"],
        "impact": "سلبي",
        "note": "انخفاض السيولة — إجازات + عيد الأضحى",
    },
    7: {
        "events": ["نتائج Q2 النصف سنوية", "إجازة صيفية"],
        "impact": "محايد",
        "note": "نتائج نصف سنوية تبدأ — السيولة منخفضة",
    },
    8: {
        "events": ["نهاية الإجازات", "عودة السيولة"],
        "impact": "محايد",
        "note": "بداية عودة المتداولين — ترقب نتائج Q2 المتأخرة",
    },
    9: {
        "events": ["عودة السيولة الكاملة", "إعلان ميزانية نصف سنوية"],
        "impact": "إيجابي",
        "note": "عودة قوية للسيولة + بداية الموسم الثاني",
    },
    10: {
        "events": ["نتائج Q3", "موسم أرامكو"],
        "impact": "إيجابي",
        "note": "نتائج Q3 + أرامكو تعلن — تأثير على المؤشر العام",
    },
    11: {
        "events": ["ميزانية الحكومة (متوقعة)", "Window Dressing"],
        "impact": "إيجابي",
        "note": "ترقب ميزانية الحكومة + تجميل محافظ الصناديق",
    },
    12: {
        "events": ["إعلان الميزانية الحكومية", "Window Dressing نهاية السنة"],
        "impact": "محايد",
        "note": "إعلان الميزانية + تجميل نهاية السنة — تذبذب عالي",
    },
}

US_CATALYSTS = {
    1: {"events": ["بداية السنة", "نتائج Q4"], "impact": "إيجابي", "note": "January Effect + موسم نتائج"},
    2: {"events": ["نتائج Q4 متأخرة"], "impact": "محايد", "note": "استمرار موسم النتائج"},
    3: {"events": ["نهاية Q1", "قرار الفيدرالي"], "impact": "محايد", "note": "ترقب قرارات الفائدة"},
    4: {"events": ["نتائج Q1", "Tax Season"], "impact": "إيجابي", "note": "موسم نتائج Q1 — تك كبيرة تعلن"},
    5: {"events": ["Sell in May"], "impact": "سلبي", "note": "Sell in May and go away — نمط تاريخي"},
    6: {"events": ["قرار الفيدرالي", "نهاية النصف الأول"], "impact": "محايد", "note": "ترقب الفائدة"},
    7: {"events": ["نتائج Q2", "أرباح التك"], "impact": "إيجابي", "note": "موسم أرباح التك الكبيرة"},
    8: {"events": ["Jackson Hole"], "impact": "سلبي", "note": "تذبذب — ترقب خطاب الفيدرالي"},
    9: {"events": ["عودة من الإجازة", "September Effect"], "impact": "سلبي قوي", "note": "أسوأ شهر تاريخياً"},
    10: {"events": ["نتائج Q3", "October Surprise"], "impact": "محايد", "note": "تذبذب عالي + بداية ارتداد"},
    11: {"events": ["الانتخابات (كل 4 سنوات)", "Black Friday"], "impact": "إيجابي قوي", "note": "أقوى شهر تاريخياً"},
    12: {"events": ["Santa Rally", "Tax Loss Harvesting"], "impact": "إيجابي", "note": "ارتفاع نهاية السنة"},
}


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
    يبني التحليل الموسمي لكل القطاعات مع المحفزات.

    Parameters:
        sector_composites: dict {sector_name: {dates, vals, ret}}
        market_key: "saudi" or "us" — لتحديد المحفزات الأساسية
    """
    catalysts = SAUDI_CATALYSTS if market_key == "saudi" else US_CATALYSTS
    result = {}

    for sector_name, data in sector_composites.items():
        dates = data.get("dates", [])
        vals = data.get("vals", [])

        monthly = compute_monthly_returns(dates, vals)
        if not monthly:
            continue

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
