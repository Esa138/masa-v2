"""
MASA QUANT — Telegram Notifications
Send alerts to user via Telegram Bot.

Setup:
1. Create bot via @BotFather → get TELEGRAM_BOT_TOKEN
2. Get Chat ID via @userinfobot → TELEGRAM_CHAT_ID
3. Add both to Streamlit secrets

Functions:
- send_message(text): basic text message
- send_signal_alert(signal): formatted signal notification
- send_breakout_alert(stock): ZR breakout alert
- send_news_alert(news): breaking news alert
- send_daily_summary(stats): morning/evening summary
"""

import requests
import os
from typing import Optional


def _get_credentials():
    """Get bot token and chat ID from streamlit secrets or env vars."""
    try:
        import streamlit as st
        token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
    except Exception:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    return token, str(chat_id) if chat_id else ""


def is_configured() -> bool:
    """Check if Telegram is properly configured."""
    token, chat_id = _get_credentials()
    return bool(token and chat_id)


def send_message(text: str, parse_mode: str = "HTML",
                 disable_preview: bool = True,
                 silent: bool = False) -> bool:
    """
    Send a text message via Telegram Bot.

    Args:
        text: message body (supports HTML or Markdown)
        parse_mode: "HTML" or "Markdown" or None
        disable_preview: don't expand link previews
        silent: send without notification sound

    Returns: True if delivered successfully
    """
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_preview,
            "disable_notification": silent,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def send_signal_alert(signal: dict, signal_type: str = "golden") -> bool:
    """
    Format and send a trading signal alert.

    signal: dict with keys: name, ticker, sector, price, target,
            stop_loss, rr, flow, rsi, phase
    signal_type: "golden", "enter", "watch", "breakout"
    """
    icon = {
        "golden": "🥇",
        "enter": "✅",
        "watch": "⚠️",
        "breakout": "🚀",
    }.get(signal_type, "📊")

    type_label = {
        "golden": "إشارة ذهبية",
        "enter": "إشارة دخول",
        "watch": "مراقبة",
        "breakout": "اختراق ZR",
    }.get(signal_type, "إشارة")

    name = signal.get("name", "")
    ticker = signal.get("ticker", "")
    sector = signal.get("sector", "")
    price = signal.get("price", 0)
    target = signal.get("target", 0)
    stop = signal.get("stop_loss", 0)
    rr = signal.get("rr", signal.get("rr_ratio", 0))
    flow = signal.get("flow", signal.get("flow_bias", 0))
    rsi = signal.get("rsi", 0)
    phase = signal.get("phase", signal.get("accum_level", ""))

    # RSI label
    rsi_lbl = "تجميع" if rsi < 30 else "متعافي" if rsi < 50 else "زخم ✨" if rsi < 70 else "تشبع ⚠️"

    # Build message
    text = f"""<b>{icon} {type_label}</b>

📊 <b>{name}</b> ({ticker})
🏭 {sector}

💰 <b>السعر:</b> {price:.2f}
🎯 <b>الهدف:</b> {target:.2f}
🛑 <b>الوقف:</b> {stop:.2f}
📐 <b>R:R:</b> {rr:.1f}

📈 <b>Flow:</b> {flow:+.0f}
🔋 <b>RSI:</b> {rsi:.0f} ({rsi_lbl})
🌀 <b>المرحلة:</b> {phase}

⏰ {_now_str()}
"""

    return send_message(text, parse_mode="HTML")


def send_breakout_alert(stock: dict) -> bool:
    """Alert for ZR breakout."""
    name = stock.get("name", "")
    ticker = stock.get("ticker", "")
    price = stock.get("price", 0)
    zr_high = stock.get("zr_high", 0)
    flow = stock.get("flow", 0)
    change = stock.get("change_pct", 0)

    text = f"""<b>🚀 اختراق ZR</b>

<b>{name}</b> ({ticker})

💰 السعر: <b>{price:.2f}</b> ({change:+.1f}%)
⛰ سقف ZR: {zr_high:.2f}
📈 Flow: {flow:+.0f}

📊 السعر تجاوز سقف Zero Reflection لأول مرة

⏰ {_now_str()}
"""
    return send_message(text, parse_mode="HTML")


def send_news_alert(news: dict) -> bool:
    """Alert for breaking news."""
    title = news.get("title", "")
    sentiment = news.get("sentiment", "neutral")
    sectors = news.get("sectors", [])
    link = news.get("link", "")

    icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(sentiment, "📰")

    text = f"""<b>{icon} خبر مهم</b>

{title}
"""
    if sectors:
        text += f"\n📊 القطاعات: {' • '.join(sectors[:3])}\n"
    if link:
        text += f"\n🔗 {link}\n"
    text += f"\n⏰ {_now_str()}"

    return send_message(text, parse_mode="HTML")


def send_daily_summary(stats: dict, period: str = "morning") -> bool:
    """
    Send morning/evening summary.

    stats: dict with: enter_count, watch_count, golden_count,
                      top_sector, breakouts_count
    period: "morning" or "evening"
    """
    icon = "🌅" if period == "morning" else "🌙"
    title = "ملخص الصباح" if period == "morning" else "ملخص الإقفال"

    text = f"""<b>{icon} {title}</b>

<b>📊 المسح اليومي:</b>
✅ ادخل: <b>{stats.get('enter_count', 0)}</b>
⚠️ راقب: <b>{stats.get('watch_count', 0)}</b>
🥇 ذهبية: <b>{stats.get('golden_count', 0)}</b>
🚀 اختراقات ZR: <b>{stats.get('breakouts_count', 0)}</b>

<b>🏆 أقوى قطاع:</b> {stats.get('top_sector', '—')}

⏰ {_now_str()}
"""
    return send_message(text, parse_mode="HTML")


def send_test_notification() -> bool:
    """Send a test message to verify setup."""
    text = """<b>✅ MASA QUANT — اختبار</b>

تم ربط البوت بنجاح! 🎉

سيصلك إشعار عند:
🥇 إشارة ذهبية جديدة
🚀 اختراق ZR قوي
🚨 خبر عاجل
🎯 وصول هدف من قائمة المتابعة

<i>هذي رسالة اختبار، الإشعارات الفعلية ستبدأ قريباً.</i>
"""
    return send_message(text, parse_mode="HTML")


def _now_str() -> str:
    """Current Saudi time string."""
    import datetime
    try:
        from core.utils import SAUDI_TZ
        now = datetime.datetime.now(SAUDI_TZ)
    except Exception:
        now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M")


# ── Bulk operations for scan integration ────────────────────

def send_signals_batch(signals: list, signal_type: str = "golden",
                       max_alerts: int = 5) -> int:
    """
    Send multiple signals in one batch (rate-limit friendly).
    Returns count of successful sends.
    """
    if not signals:
        return 0

    sent = 0
    for sig in signals[:max_alerts]:
        if send_signal_alert(sig, signal_type):
            sent += 1
        # Telegram rate limit: 30 messages per second to different chats,
        # but only 1 message per second to the same chat
        import time
        time.sleep(1.1)
    return sent
