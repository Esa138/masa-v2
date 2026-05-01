"""
MASA QUANT — Smart Chatbot
Context-aware Arabic chatbot for Saudi market analysis.
Uses Gemini + live data from scan results, DB history, seasonality, news.
"""

import json
import datetime
import sqlite3


# ══════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """أنت مساعد ذكي متخصص في السوق السعودي ومنصة MASA QUANT.

## شخصيتك:
- محلل مالي محترف بمستوى hedge fund
- تتكلم بالعربي السعودي المهني (مختصر، واضح، بدون مبالغة)
- صريح ومباشر — لو السهم خطر تقولها بدون تجميل
- تستخدم Markdown للترتيب والإيموجي للتوضيح فقط

## قواعد صارمة:
1. **استخدم البيانات المرفقة فقط** — لا تخترع أرقام أو أسماء شركات
2. **لو السؤال محتاج بيانات مو موجودة** — قول: "ما عندي بيانات حديثة عن X — اعمل مسح أولاً"
3. **لا تعطي نصائح استثمارية مباشرة** ("اشتري") — استخدم "الإشارة تشير لـ" أو "تاريخياً ينجح"
4. **اربط الأرقام بالسياق** — مثلاً "RSI 58 = منطقة الزخم (67.7% نجاح تاريخياً)"
5. **اختصر** — جواب قصير ودقيق أفضل من فقرة طويلة

## معرفتك بالمنصة:

### القرارات (decision):
- `enter` ✅ — ادخل
- `watch` ⚠️ — راقب (إشارات مختلطة)
- `avoid` ❌ — تجنب

### المراحل (phase):
- `accumulation` — تجميع (شراء)
- `spring` — كسر مؤكد
- `markup` — صعود (احذر RSI>70)
- `distribution` — تصريف (بيع)
- `markdown` — هبوط

### مناطق RSI (من بيانات V3 — 2,356 صفقة):
- `RSI < 30` + accumulation → 77-79% نجاح ✅ (تجميع مبكر)
- `RSI 30-50` → 60% نجاح (متعافي)
- `RSI 50-70` → **67.7% نجاح** ⭐ (منطقة الزخم — الأفضل)
- `RSI > 70` + markup → **0% نجاح** ❌ (فيتو تلقائي)

### الفلتر الذهبي:
الإشارة الذهبية = accumulation/spring + المشتري مهاجم + Divergence ≥ 25 + صفر أسباب حذر

### الاختراقات (`breakouts`):
- 🚀 اختراق سقف ZR — السهم اخترق المقاومة الرئيسية
- 🔵 سماء زرقا — السعر فوق ZR (لا مقاومة فوقه)
- اختراق فوق القناة — في location=above مع flow قوي
- اختراق بسيولة عالية — markup مع volume_ratio > 1.5

**ملاحظة مهمة:** الاختراقات قد تظهر مع decision=enter/watch/avoid — استخدم حقل `breakouts` مباشرة لما المستخدم يسأل "وش الأسهم اللي فيها اختراقات؟"

### الارتدادات (`bounces`):
- 🪲 ارتداد مبكر — early bounce signal
- ارتداد من قاع ZR — zr_floor مع flow إيجابي
- سبرنق — phase spring
- ارتداد قاعي — flow_type bottom

## أسلوب الجواب:
- إجابات مختصرة (3-6 أسطر) بدون مبالغة
- استخدم Bullet points للقوائم
- اربط دائماً بالبيانات المرفقة
- لو المستخدم يسأل عن سهم محدد — استخرج بياناته من الـ scan_results
"""


# ══════════════════════════════════════════════════════════════
# CONTEXT BUILDER
# ══════════════════════════════════════════════════════════════

def _is_golden_signal(r: dict) -> bool:
    """Same formula as Golden Filter page: accumulation/spring + buyer aggressor + div>=25 + 0 against."""
    is_accum = r.get("phase") in ("accumulation", "spring")
    is_buyer = r.get("aggressor") == "buyers"
    has_div = abs(r.get("divergence", 0)) >= 25
    zero_against = len(r.get("reasons_against", []) or []) == 0
    return is_accum and is_buyer and has_div and zero_against


def _detect_breakout(r: dict) -> tuple:
    """Detect breakout type from scan result. Returns (is_breakout, label) or (False, '')."""
    zr_status = r.get("zr_status", "")
    flow_type = r.get("flow_type", "")
    flow_bias = r.get("flow_bias", 0)
    location = r.get("location", "")
    phase = r.get("phase", "")
    change_pct = r.get("change_pct", 0)
    volume_ratio = r.get("volume_ratio", 1)

    if zr_status == "zr_breakout":
        return True, "🚀 اختراق سقف ZR"
    if zr_status == "zr_bluesky":
        return True, "🔵 سماء زرقا — فوق ZR"
    if location == "above" and flow_bias > 20 and change_pct > 1:
        return True, "اختراق فوق القناة"
    if phase == "markup" and change_pct > 2 and volume_ratio > 1.5:
        return True, "اختراق بسيولة عالية"
    return False, ""


def _detect_bounce(r: dict) -> tuple:
    """Detect bounce/spring type. Returns (is_bounce, label) or (False, '')."""
    zr_status = r.get("zr_status", "")
    flow_type = r.get("flow_type", "")
    flow_bias = r.get("flow_bias", 0)
    early_bounce = r.get("early_bounce", False)

    if early_bounce:
        return True, "🪲 ارتداد مبكر"
    if zr_status == "zr_floor" and flow_bias > 0:
        return True, "ارتداد من قاع ZR"
    if flow_type in ("bottom", "spring"):
        return True, "سبرنق" if flow_type == "spring" else "ارتداد قاعي"
    return False, ""


def _summarize_scan(scan_results: list, max_items: int = 30) -> dict:
    """Summarize scan results into compact dict for AI context."""
    if not scan_results:
        return {}

    decisions = {"enter": 0, "watch": 0, "avoid": 0}
    sectors = {}
    enters = []
    golden = []
    breakouts = []
    bounces = []

    for r in scan_results:
        dec = r.get("decision", "")
        decisions[dec] = decisions.get(dec, 0) + 1
        sec = r.get("sector", "")
        if sec:
            if sec not in sectors:
                sectors[sec] = {"flow_sum": 0, "n": 0, "enters": 0}
            sectors[sec]["flow_sum"] += r.get("flow_bias", 0)
            sectors[sec]["n"] += 1
            if dec == "enter":
                sectors[sec]["enters"] += 1

        # Detect breakouts and bounces (independent of decision)
        is_bo, bo_label = _detect_breakout(r)
        if is_bo:
            breakouts.append({
                "name": r.get("name", r.get("ticker", "")),
                "ticker": r.get("ticker", ""),
                "sector": sec,
                "type": bo_label,
                "phase": r.get("phase", ""),
                "flow": r.get("flow_bias", 0),
                "rsi": r.get("rsi", 50),
                "change_pct": r.get("change_pct", 0),
                "price": r.get("price", r.get("last_close", 0)),
                "decision": dec,
            })

        is_bn, bn_label = _detect_bounce(r)
        if is_bn:
            bounces.append({
                "name": r.get("name", r.get("ticker", "")),
                "ticker": r.get("ticker", ""),
                "sector": sec,
                "type": bn_label,
                "phase": r.get("phase", ""),
                "flow": r.get("flow_bias", 0),
                "rsi": r.get("rsi", 50),
                "price": r.get("price", r.get("last_close", 0)),
                "decision": dec,
            })

        if dec == "enter":
            is_g = _is_golden_signal(r)
            enters.append({
                "ticker": r.get("ticker", ""),
                "name": r.get("name", ""),
                "sector": sec,
                "phase": r.get("phase", ""),
                "flow": r.get("flow_bias", 0),
                "divergence": r.get("divergence", 0),
                "rsi": r.get("rsi", 50),
                "days": r.get("days", 0),
                "price": r.get("price", r.get("last_close", 0)),
                "stop": r.get("stop_loss", 0),
                "target": r.get("target", 0),
                "rr": r.get("rr_ratio", 0),
                "is_golden": is_g,
                "aggressor": r.get("aggressor", ""),
            })
            if is_g:
                golden.append({
                    "name": r.get("name", r.get("ticker", "")),
                    "ticker": r.get("ticker", ""),
                    "sector": sec,
                    "rsi": r.get("rsi", 50),
                    "flow": r.get("flow_bias", 0),
                    "divergence": r.get("divergence", 0),
                    "price": r.get("price", r.get("last_close", 0)),
                })

    # Top sectors by avg flow
    sector_ranks = sorted(
        sectors.items(),
        key=lambda x: x[1]["flow_sum"] / x[1]["n"] if x[1]["n"] else 0,
        reverse=True,
    )

    # Sort breakouts/bounces by flow strength
    breakouts.sort(key=lambda x: -x.get("flow", 0))
    bounces.sort(key=lambda x: -x.get("flow", 0))

    return {
        "total_scanned": len(scan_results),
        "decisions": decisions,
        "top_sectors": [
            {"sector": s, "avg_flow": round(d["flow_sum"] / d["n"], 1), "enters": d["enters"]}
            for s, d in sector_ranks[:5]
        ],
        "weak_sectors": [
            {"sector": s, "avg_flow": round(d["flow_sum"] / d["n"], 1)}
            for s, d in sector_ranks[-3:]
        ],
        "enter_signals": enters[:max_items],
        "golden_signals": golden,
        "golden_count": len(golden),
        "breakouts": breakouts[:20],
        "breakouts_count": len(breakouts),
        "bounces": bounces[:15],
        "bounces_count": len(bounces),
    }


def _get_historical_performance(db_path: str = "masa_v2.db") -> dict:
    """Quick performance summary from DB."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT outcome_20d, return_20d, sector, accum_level FROM signals "
                "WHERE decision='enter' AND outcome_20d IS NOT NULL"
            ).fetchall()
            if not rows:
                return {}
            data = [dict(r) for r in rows]
            total = len(data)
            wins = sum(1 for r in data if r["outcome_20d"] == "win")
            avg = sum((r.get("return_20d") or 0) for r in data) / total if total else 0
            return {
                "total_completed": total,
                "win_rate": round(wins / total * 100, 1) if total else 0,
                "avg_return_20d": round(avg, 2),
            }
    except Exception:
        return {}


def _get_seasonality_context(month: str = None) -> dict:
    """Get seasonality info for current month."""
    try:
        from data.seasonality import (
            get_current_month_ar, MONTH_OVERVIEW,
            get_top_sectors, get_avoid_sectors,
        )
        if not month:
            month = get_current_month_ar()
        info = MONTH_OVERVIEW.get(month, {})
        return {
            "month": month,
            "verdict": info.get("verdict", ""),
            "expected_return": info.get("return", info.get("market_return", 0)),
            "win_rate": info.get("win_pct", info.get("win_rate", 0)),
            "catalyst": info.get("catalyst", ""),
            "top_sectors": [s["sector"] for s in get_top_sectors(month, 3)],
            "avoid_sectors": [s["sector"] for s in get_avoid_sectors(month)[:3]],
        }
    except Exception:
        return {}


def build_context(
    scan_results: list = None,
    include_history: bool = True,
    include_seasonality: bool = True,
) -> str:
    """Build context string to inject into chat."""
    ctx = {}

    if scan_results:
        ctx["latest_scan"] = _summarize_scan(scan_results)
    else:
        ctx["latest_scan"] = "لم يتم تشغيل مسح بعد"

    if include_history:
        perf = _get_historical_performance()
        if perf:
            ctx["historical_performance"] = perf

    if include_seasonality:
        seas = _get_seasonality_context()
        if seas:
            ctx["seasonality"] = seas

    ctx["current_date"] = datetime.datetime.now().strftime("%Y-%m-%d")

    return json.dumps(ctx, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════
# CHAT FUNCTION
# ══════════════════════════════════════════════════════════════

def chat(
    user_message: str,
    history: list = None,
    scan_results: list = None,
    max_tokens: int = 1500,
) -> str:
    """
    Send a message to the chatbot and get a response.

    Args:
        user_message: latest user message
        history: list of {"role": "user"|"assistant", "content": str}
        scan_results: optional scan results from session state
        max_tokens: response length cap

    Returns: assistant response text
    """
    import streamlit as st
    import requests

    api_key = st.secrets.get("GEMINI_API_KEY", "") or st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key:
        return "⚠️ مفتاح API غير موجود. أضف `GEMINI_API_KEY` في Settings → Secrets."

    # Build context
    context_str = build_context(scan_results=scan_results)

    # Convert history to Gemini format
    contents = []
    if history:
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    # Add context + new question
    user_text = f"""## بيانات المنصة الحية:
```json
{context_str}
```

## سؤال المستخدم:
{user_message}"""

    contents.append({"role": "user", "parts": [{"text": user_text}]})

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.6,
        },
    }

    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        resp = requests.post(url, params={"key": api_key}, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return "⚠️ لم يتم إرجاع رد."
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return "⚠️ الرد فارغ."
        return "".join(p.get("text", "") for p in parts)
    except requests.exceptions.HTTPError:
        if resp.status_code in (401, 403):
            return "⚠️ مفتاح API غير صحيح."
        elif resp.status_code == 429:
            return "⚠️ تم تجاوز حد الاستخدام. حاول بعد دقيقة."
        return f"⚠️ خطأ: {resp.status_code}"
    except Exception as e:
        return f"⚠️ خطأ: {str(e)}"


# ══════════════════════════════════════════════════════════════
# QUICK ACTION SUGGESTIONS
# ══════════════════════════════════════════════════════════════

QUICK_ACTIONS = [
    "وش أفضل 3 إشارات ذهبية اليوم؟",
    "كم نسبة نجاح المنصة الحالية؟",
    "وش أفضل قطاع هذا الشهر؟",
    "اشرح لي معنى accumulation",
    "وش الفرق بين spring و markup؟",
    "كيف أستخدم RSI مع الإشارات؟",
    "ما هي القطاعات اللي أتجنبها هذا الشهر؟",
    "وش معنى الفيتو في النظام؟",
]


def get_starter_prompts(scan_results: list = None) -> list:
    """Suggest contextual starter prompts based on data state."""
    if not scan_results:
        return [
            "كيف أستخدم المنصة؟",
            "وش أفضل قطاع هذا الشهر؟",
            "اشرح لي الفلتر الذهبي",
            "ما هي مناطق RSI الأفضل؟",
        ]

    suggestions = []
    enters = sum(1 for r in scan_results if r.get("decision") == "enter")
    if enters > 0:
        suggestions.append(f"حلل أفضل 3 إشارات من الـ {enters} الموجودة")
        suggestions.append("وش الإشارات الذهبية اليوم؟")
    suggestions.append("وش أقوى قطاع في المسح الحالي؟")
    suggestions.append("هل المسح الحالي يتوافق مع الموسمية؟")
    return suggestions
