"""
MASA QUANT — التحليل الموسمي للقطاعات
seasonality.py

يحلل أداء القطاعات شهرياً على مدى سنوات ويكتشف:
- الأشهر الإيجابية والسلبية
- أشهر التجميع والتصريف
- أشهر التحسن (التحول من سلبي لإيجابي)
- متوسط العائد ونسبة النجاح لكل شهر
"""

import pandas as pd
import numpy as np
from datetime import datetime


MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}


def compute_monthly_returns(dates, vals):
    """
    يحسب العائد الشهري من بيانات يومية.
    Returns: list of {year, month, month_ar, return_pct, start_val, end_val}
    """
    if not dates or not vals or len(dates) < 20:
        return []

    # Build DataFrame
    df = pd.DataFrame({"date": dates, "val": vals})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    monthly = []
    for (yr, mo), grp in df.groupby(["year", "month"]):
        if len(grp) < 5:  # need at least 5 trading days
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
    يحسب إحصائيات موسمية لكل شهر.
    Returns: dict {month: {avg, median, win_rate, best, worst, years, ...}}
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

        avg_ret = np.mean(returns)
        median_ret = np.median(returns)

        # Classify month
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

        stats[mo] = {
            "month": mo,
            "month_ar": MONTH_NAMES_AR.get(mo, str(mo)),
            "avg_return": round(float(avg_ret), 2),
            "median_return": round(float(median_ret), 2),
            "win_rate": round(win_rate, 1),
            "positive": positive,
            "negative": negative,
            "total_years": total,
            "best": round(max(returns), 2),
            "worst": round(min(returns), 2),
            "std": round(float(np.std(returns)), 2) if len(returns) > 1 else 0,
            "years": years,
            "returns_by_year": {m["year"]: m["return_pct"] for m in mo_data},
            "phase": phase,
            "phase_icon": phase_icon,
            "phase_color": phase_color,
        }

    return stats


def detect_transitions(seasonality_stats):
    """
    يكتشف أشهر التحول (من سلبي لإيجابي والعكس).
    Returns: list of {from_month, to_month, type, description}
    """
    transitions = []
    months = sorted(seasonality_stats.keys())

    for i in range(len(months)):
        curr = months[i]
        prev = months[i - 1] if i > 0 else months[-1]  # wrap around

        curr_stats = seasonality_stats[curr]
        prev_stats = seasonality_stats[prev]

        prev_avg = prev_stats["avg_return"]
        curr_avg = curr_stats["avg_return"]

        # Transition from negative to positive
        if prev_avg < -0.5 and curr_avg > 0.5:
            transitions.append({
                "from_month": prev,
                "to_month": curr,
                "from_ar": prev_stats["month_ar"],
                "to_ar": curr_stats["month_ar"],
                "type": "تحسن",
                "icon": "📈",
                "color": "#00E676",
                "description": (
                    f"تحول إيجابي: {prev_stats['month_ar']} ({prev_avg:+.1f}%) → "
                    f"{curr_stats['month_ar']} ({curr_avg:+.1f}%)"
                ),
            })

        # Transition from positive to negative
        elif prev_avg > 0.5 and curr_avg < -0.5:
            transitions.append({
                "from_month": prev,
                "to_month": curr,
                "from_ar": prev_stats["month_ar"],
                "to_ar": curr_stats["month_ar"],
                "type": "تدهور",
                "icon": "📉",
                "color": "#F44336",
                "description": (
                    f"تحول سلبي: {prev_stats['month_ar']} ({prev_avg:+.1f}%) → "
                    f"{curr_stats['month_ar']} ({curr_avg:+.1f}%)"
                ),
            })

    return transitions


def get_current_month_insight(seasonality_stats):
    """
    يعطي نصيحة عن الشهر الحالي بناءً على التاريخ.
    """
    current_month = datetime.now().month
    if current_month not in seasonality_stats:
        return None

    s = seasonality_stats[current_month]
    next_month = (current_month % 12) + 1

    insight = {
        "month_ar": s["month_ar"],
        "avg_return": s["avg_return"],
        "win_rate": s["win_rate"],
        "phase": s["phase"],
        "phase_icon": s["phase_icon"],
    }

    # Add next month forecast
    if next_month in seasonality_stats:
        ns = seasonality_stats[next_month]
        insight["next_month_ar"] = ns["month_ar"]
        insight["next_avg"] = ns["avg_return"]
        insight["next_phase"] = ns["phase"]
        insight["next_icon"] = ns["phase_icon"]

    return insight


def build_seasonality_for_sectors(sector_composites):
    """
    يبني التحليل الموسمي لكل القطاعات.

    Parameters:
        sector_composites: dict {sector_name: {dates, vals, ret}}

    Returns:
        dict {sector_name: {monthly, stats, transitions, insight}}
    """
    result = {}

    for sector_name, data in sector_composites.items():
        dates = data.get("dates", [])
        vals = data.get("vals", [])

        monthly = compute_monthly_returns(dates, vals)
        if not monthly:
            continue

        stats = compute_seasonality_stats(monthly)
        transitions = detect_transitions(stats)
        insight = get_current_month_insight(stats)

        result[sector_name] = {
            "monthly": monthly,
            "stats": stats,
            "transitions": transitions,
            "insight": insight,
            "years_covered": sorted(set(m["year"] for m in monthly)),
        }

    return result
