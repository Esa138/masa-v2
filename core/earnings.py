"""
MASA QUANT — Earnings Calendar + Pre-Earnings Accumulation Detector

يكتشف:
1. إعلان نتائج قريب (خلال 14 يوم) → تحذير
2. تجميع مؤسسي قبل النتائج → فرصة
3. توزيعات قريبة → معلومة مهمة
"""

import yfinance as yf
import streamlit as st
from datetime import datetime, timedelta


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_earnings_info(ticker):
    """Fetch earnings + dividend dates from yfinance. Cached 24h."""
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        if cal is None or (hasattr(cal, 'empty') and cal.empty):
            return None

        result = {}

        # Earnings date
        earnings_dates = cal.get("Earnings Date", [])
        if isinstance(earnings_dates, list) and earnings_dates:
            # Take the nearest future date
            for ed in earnings_dates:
                if hasattr(ed, 'year'):
                    result["earnings_date"] = ed.strftime("%Y-%m-%d") if hasattr(ed, 'strftime') else str(ed)
                    result["earnings_eps_est"] = cal.get("Earnings Average", None)
                    result["earnings_eps_high"] = cal.get("Earnings High", None)
                    result["earnings_eps_low"] = cal.get("Earnings Low", None)
                    result["earnings_rev_est"] = cal.get("Revenue Average", None)
                    break

        # Ex-dividend date
        ex_div = cal.get("Ex-Dividend Date")
        if ex_div and hasattr(ex_div, 'strftime'):
            result["ex_dividend_date"] = ex_div.strftime("%Y-%m-%d")

        # Dividend date
        div_date = cal.get("Dividend Date")
        if div_date and hasattr(div_date, 'strftime'):
            result["dividend_date"] = div_date.strftime("%Y-%m-%d")

        return result if result else None

    except Exception:
        return None


def check_earnings_proximity(ticker, days_warning=14):
    """
    Check if stock has earnings announcement within X days.

    Returns:
        dict or None: {
            "days_to_earnings": int,
            "earnings_date": str,
            "warning_level": "imminent" | "near" | "upcoming" | None,
            "eps_estimate": float or None,
            "message": str
        }
    """
    info = _fetch_earnings_info(ticker)
    if not info or "earnings_date" not in info:
        return None

    try:
        earnings_dt = datetime.strptime(info["earnings_date"], "%Y-%m-%d")
        today = datetime.now()
        days_diff = (earnings_dt - today).days

        if days_diff < -7:  # Past earnings, not relevant
            return None

        eps = info.get("earnings_eps_est")
        eps_str = f" | تقدير EPS: {eps:.2f}" if eps else ""

        if days_diff <= 3:
            return {
                "days_to_earnings": days_diff,
                "earnings_date": info["earnings_date"],
                "warning_level": "imminent",
                "eps_estimate": eps,
                "message": f"🔴 إعلان نتائج خلال {days_diff} يوم ({info['earnings_date']}){eps_str} — تذبذب عالي متوقع!",
            }
        elif days_diff <= 7:
            return {
                "days_to_earnings": days_diff,
                "earnings_date": info["earnings_date"],
                "warning_level": "near",
                "eps_estimate": eps,
                "message": f"🟡 إعلان نتائج خلال {days_diff} أيام ({info['earnings_date']}){eps_str} — حذر",
            }
        elif days_diff <= days_warning:
            return {
                "days_to_earnings": days_diff,
                "earnings_date": info["earnings_date"],
                "warning_level": "upcoming",
                "eps_estimate": eps,
                "message": f"📅 إعلان نتائج خلال {days_diff} يوم ({info['earnings_date']}){eps_str}",
            }

    except Exception:
        pass

    return None


def check_ex_dividend(ticker, days_warning=14):
    """Check if stock has ex-dividend date within X days."""
    info = _fetch_earnings_info(ticker)
    if not info or "ex_dividend_date" not in info:
        return None

    try:
        ex_dt = datetime.strptime(info["ex_dividend_date"], "%Y-%m-%d")
        today = datetime.now()
        days_diff = (ex_dt - today).days

        if days_diff < -1 or days_diff > days_warning:
            return None

        if days_diff <= 3:
            return {
                "days_to_ex": days_diff,
                "ex_date": info["ex_dividend_date"],
                "message": f"💰 تاريخ استحقاق التوزيع خلال {days_diff} يوم ({info['ex_dividend_date']}) — توقع ضغط بيعي بعده",
            }
        else:
            return {
                "days_to_ex": days_diff,
                "ex_date": info["ex_dividend_date"],
                "message": f"💰 توزيعات قادمة: استحقاق {info['ex_dividend_date']} (خلال {days_diff} يوم)",
            }

    except Exception:
        pass
    return None


def detect_pre_earnings_accumulation(ticker, flow_bias, cdv_trend, days, phase, rsi):
    """
    Detect institutional accumulation before earnings.

    The pattern:
    - Earnings within 60 days
    - flow_bias > 15 (institutions buying)
    - CDV rising (confirmed buying pressure)
    - Accumulation phase with 5+ days
    - RSI not extreme (not overbought)

    Returns dict or None
    """
    earnings = check_earnings_proximity(ticker, days_warning=60)
    if not earnings:
        return None

    days_to_earnings = earnings.get("days_to_earnings", 999)

    # Too close = don't enter (volatility risk)
    if days_to_earnings <= 5:
        return None

    # Check accumulation signals
    is_accumulating = (
        flow_bias > 15
        and cdv_trend in ("rising", "flat")
        and phase in ("accumulation", "spring")
        and days >= 5
        and rsi < 70
    )

    if not is_accumulating:
        return None

    # Score the accumulation
    score = 0
    signals = []

    if flow_bias > 30:
        score += 30
        signals.append(f"تدفق قوي ({flow_bias:+.0f})")
    elif flow_bias > 15:
        score += 15
        signals.append(f"تدفق إيجابي ({flow_bias:+.0f})")

    if cdv_trend == "rising":
        score += 25
        signals.append("CDV صاعد")

    if days >= 15:
        score += 25
        signals.append(f"تجميع ناضج ({days} يوم)")
    elif days >= 7:
        score += 15
        signals.append(f"تجميع متوسط ({days} يوم)")
    else:
        score += 5
        signals.append(f"تجميع مبكر ({days} يوم)")

    if phase == "spring":
        score += 20
        signals.append("سبرنق — أقوى إشارة")

    # Determine strength
    if score >= 70:
        strength = "قوي"
        icon = "🟢"
    elif score >= 40:
        strength = "متوسط"
        icon = "🟡"
    else:
        strength = "ضعيف"
        icon = "⚪"

    return {
        "detected": True,
        "score": score,
        "strength": strength,
        "icon": icon,
        "days_to_earnings": days_to_earnings,
        "earnings_date": earnings["earnings_date"],
        "eps_estimate": earnings.get("eps_estimate"),
        "signals": signals,
        "message": (
            f"{icon} تجميع مؤسسي قبل النتائج ({strength}) — "
            f"النتائج خلال {days_to_earnings} يوم ({earnings['earnings_date']}). "
            f"الإشارات: {' + '.join(signals)}"
        ),
    }


def get_stock_events(ticker, flow_bias=0, cdv_trend="flat", days=0, phase="neutral", rsi=50):
    """
    Get all upcoming events for a stock (earnings + dividends + pre-earnings accumulation).
    Call this from scanner or detail panel.

    Returns: list of event dicts
    """
    events = []

    # Earnings proximity
    earnings = check_earnings_proximity(ticker)
    if earnings:
        events.append({
            "type": "earnings",
            "level": earnings["warning_level"],
            "message": earnings["message"],
            "data": earnings,
        })

    # Ex-dividend
    ex_div = check_ex_dividend(ticker)
    if ex_div:
        events.append({
            "type": "dividend",
            "level": "info",
            "message": ex_div["message"],
            "data": ex_div,
        })

    # Pre-earnings accumulation
    pre_acc = detect_pre_earnings_accumulation(ticker, flow_bias, cdv_trend, days, phase, rsi)
    if pre_acc:
        events.append({
            "type": "pre_earnings_accumulation",
            "level": pre_acc["strength"],
            "message": pre_acc["message"],
            "data": pre_acc,
        })

    return events
