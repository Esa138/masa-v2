"""
MASA QUANT — AI Reports Engine
Powered by Claude Sonnet

يولّد تقارير ذكية شاملة:
1. تقرير السوق اليومي
2. تقرير القطاعات
3. تحليل سهم فردي
4. تقرير المؤشر المركب
5. اكتشاف الفرص والمخاطر
"""

import streamlit as st
import json
from datetime import datetime

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


def _get_client():
    """Get Anthropic client with API key from secrets."""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _call_sonnet(system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
    """Call Claude Sonnet and return response text."""
    client = _get_client()
    if not client:
        return "❌ مفتاح API غير موجود. أضف ANTHROPIC_API_KEY في Secrets."

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except anthropic.AuthenticationError:
        return "❌ مفتاح API غير صحيح. تأكد من ANTHROPIC_API_KEY."
    except anthropic.RateLimitError:
        return "⚠️ تم تجاوز حد الاستخدام. حاول بعد دقيقة."
    except Exception as e:
        return f"❌ خطأ: {str(e)}"


# ══════════════════════════════════════════
# System Prompts
# ══════════════════════════════════════════

SYSTEM_MARKET = """أنت محلل أسواق مالية محترف متخصص في السوق السعودي والأمريكي.
تكتب بالعربية (لهجة سعودية مهنية).
مهمتك: تحليل بيانات المسح وكتابة تقرير يومي شامل.

قواعد التقرير:
1. ابدأ بملخص تنفيذي (3 أسطر) — الرسالة الأهم اليوم
2. استخدم أرقام حقيقية من البيانات — لا تخترع
3. حدد أقوى 3 فرص وأخطر 3 مخاطر
4. اربط بين القطاعات — أي قطاع يقود وأيهم يتبع
5. أعطِ توصية واضحة: هل السوق مناسب للشراء اليوم أم الانتظار
6. استخدم إيموجي بشكل مهني (🟢 للإيجابي، 🔴 للسلبي، ⚠️ للتحذير)
7. لا تكتب أكثر من 800 كلمة
8. في النهاية أعطِ درجة ثقة من 1-10 في تحليلك ولماذا"""

SYSTEM_SECTOR = """أنت محلل قطاعات مالية محترف.
تكتب بالعربية.
مهمتك: تحليل قطاع محدد بعمق بناءً على بيانات Order Flow.

قواعد التقرير:
1. حلل كل سهم في القطاع — لا تتجاهل أي سهم
2. حدد أسهم التجميع وأسهم التصريف
3. اكتشف التناقضات (سهم يرتفع لكن يُصرَّف، أو ينزل لكن يُجمَّع)
4. أعطِ ترتيب الأسهم من الأفضل للأسوأ
5. حدد أفضل سهم للدخول ولماذا
6. حدد أخطر سهم ولماذا
7. اربط بالمحفزات الموسمية إن وجدت"""

SYSTEM_STOCK = """أنت محلل فني ومالي محترف.
تكتب بالعربية.
مهمتك: تحليل سهم واحد بعمق.

قواعد التقرير:
1. ملخص سريع: ادخل / راقب / تجنب — ولماذا
2. تحليل Order Flow: CDV، المهاجم، الدايفرجنس
3. تحليل فني: الموقع من الدعم/المقاومة، MA200، RSI
4. مرحلة وايكوف: تجميع، انطلاق، تصريف، هبوط
5. المخاطر: وقف الخسارة، أسوأ سيناريو
6. الهدف: متى تبيع ولماذا
7. درجة الثقة من 1-10"""

SYSTEM_COMPOSITE = """أنت محلل مؤشرات مالية محترف.
تكتب بالعربية.
مهمتك: تحليل المؤشر المركب للسوق.

قواعد التقرير:
1. حلل قيمة المؤشر الحالية ومعناها
2. قارن مع المؤشر المرجعي (تاسي أو S&P)
3. حلل الاتجاه: صاعد/هابط/عرضي ولماذا
4. حلل الدعم والمقاومة — هل قريب من مستوى حرج؟
5. حلل تدفق الأموال (PFI): تجميع أم تصريف
6. أعطِ توقع للأسبوع القادم بناءً على البيانات
7. حدد المخاطر الرئيسية"""

SYSTEM_OPPORTUNITIES = """أنت صائد فرص استثمارية محترف.
تكتب بالعربية.
مهمتك: اكتشاف الفرص المخفية والمخاطر الخفية من بيانات المسح.

ابحث عن:
1. تجميع خفي: سهم ينزل لكن Order Flow إيجابي (فرصة!)
2. صعود كاذب: سهم يرتفع لكن CDV هابط (خطر!)
3. سبرنق: كسر كاذب تحت الدعم ثم ارتداد (أقوى إشارة)
4. تناقض بين القطاع والسهم: القطاع يصعد لكن السهم يتخلف
5. تسارع تجميع: تجميع مستمر 5+ أيام (انفجار قادم)
6. RSI متطرف + تدفق عكسي (انعكاس محتمل)

لكل فرصة/خطر اذكر:
- اسم السهم والسعر
- نوع الإشارة
- القوة (ضعيفة/متوسطة/قوية)
- الإجراء المقترح
- وقف الخسارة والهدف"""


# ══════════════════════════════════════════
# Data Preparation
# ══════════════════════════════════════════

def _prepare_market_summary(results, composite_data=None, pfi_data=None):
    """Prepare market data summary for AI."""
    if not results:
        return "لا توجد بيانات مسح"

    total = len(results)
    enters = [r for r in results if r.get("decision") == "enter"]
    avoids = [r for r in results if r.get("decision") == "avoid"]
    watches = [r for r in results if r.get("decision") == "watch"]

    # Phase breakdown
    accum = sum(1 for r in results if r.get("phase") == "accumulation")
    dist = sum(1 for r in results if r.get("phase") == "distribution")
    markup = sum(1 for r in results if r.get("phase") == "markup")
    markdown = sum(1 for r in results if r.get("phase") == "markdown")

    # Top movers
    sorted_by_change = sorted(results, key=lambda r: r.get("change_pct", 0), reverse=True)
    top_gainers = sorted_by_change[:5]
    top_losers = sorted_by_change[-5:]

    # Top by flow
    sorted_by_flow = sorted(results, key=lambda r: r.get("flow_bias", 0), reverse=True)
    top_flow = sorted_by_flow[:5]
    worst_flow = sorted_by_flow[-5:]

    summary = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_stocks": total,
        "enter_count": len(enters),
        "avoid_count": len(avoids),
        "watch_count": len(watches),
        "accumulation": accum,
        "distribution": dist,
        "markup": markup,
        "markdown": markdown,
        "enter_stocks": [
            {"name": r.get("name", r["ticker"]), "ticker": r["ticker"],
             "price": r.get("last_close", 0), "change": r.get("change_pct", 0),
             "flow": r.get("flow_bias", 0), "phase": r.get("phase", ""),
             "rsi": r.get("rsi", 0), "reasons": r.get("reasons_for", [])}
            for r in enters[:10]
        ],
        "top_gainers": [
            {"name": r.get("name", r["ticker"]), "change": r.get("change_pct", 0),
             "flow": r.get("flow_bias", 0), "decision": r.get("decision", "")}
            for r in top_gainers
        ],
        "top_losers": [
            {"name": r.get("name", r["ticker"]), "change": r.get("change_pct", 0),
             "flow": r.get("flow_bias", 0), "decision": r.get("decision", "")}
            for r in top_losers
        ],
        "strongest_flow": [
            {"name": r.get("name", r["ticker"]), "flow": r.get("flow_bias", 0),
             "phase": r.get("phase", ""), "decision": r.get("decision", "")}
            for r in top_flow
        ],
        "weakest_flow": [
            {"name": r.get("name", r["ticker"]), "flow": r.get("flow_bias", 0),
             "phase": r.get("phase", ""), "decision": r.get("decision", "")}
            for r in worst_flow
        ],
    }

    if composite_data:
        summary["composite"] = composite_data
    if pfi_data:
        summary["pfi"] = pfi_data

    return json.dumps(summary, ensure_ascii=False, indent=2)


def _prepare_sector_data(results, sector_name):
    """Prepare sector-specific data for AI."""
    sector_stocks = [r for r in results if r.get("sector") == sector_name]
    if not sector_stocks:
        return "لا توجد أسهم في هذا القطاع"

    data = {
        "sector": sector_name,
        "total": len(sector_stocks),
        "stocks": [
            {
                "name": r.get("name", r["ticker"]),
                "ticker": r["ticker"],
                "price": r.get("last_close", 0),
                "change": r.get("change_pct", 0),
                "decision": r.get("decision", ""),
                "phase": r.get("phase", ""),
                "flow_bias": r.get("flow_bias", 0),
                "cdv_trend": r.get("cdv_trend", ""),
                "aggressor": r.get("aggressor", ""),
                "rsi": r.get("rsi", 0),
                "divergence": r.get("divergence", 0),
                "absorption": r.get("absorption_score", 0),
                "location": r.get("location", ""),
                "days_accum": r.get("days", 0),
                "flow_type": r.get("flow_type_label", ""),
                "reasons_for": r.get("reasons_for", []),
                "reasons_against": r.get("reasons_against", []),
            }
            for r in sector_stocks
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _prepare_stock_data(result):
    """Prepare single stock data for AI."""
    data = {
        "name": result.get("name", result["ticker"]),
        "ticker": result["ticker"],
        "sector": result.get("sector", ""),
        "price": result.get("last_close", 0),
        "change": result.get("change_pct", 0),
        "decision": result.get("decision", ""),
        "decision_info": result.get("decision_info", {}),
        "phase": result.get("phase", ""),
        "phase_info": result.get("phase_info", {}),
        "flow_bias": result.get("flow_bias", 0),
        "cdv_trend": result.get("cdv_trend", ""),
        "aggressor": result.get("aggressor", ""),
        "rsi": result.get("rsi", 0),
        "divergence": result.get("divergence", 0),
        "absorption_score": result.get("absorption_score", 0),
        "absorption_bias": result.get("absorption_bias", 0),
        "location": result.get("location", ""),
        "ma200": result.get("ma200", 0),
        "days_accum": result.get("days", 0),
        "flow_type": result.get("flow_type_label", ""),
        "flow_scope": result.get("flow_scope", ""),
        "reasons_for": result.get("reasons_for", []),
        "reasons_against": result.get("reasons_against", []),
        "stop_loss": result.get("stop_loss", 0),
        "target": result.get("target", 0),
        "rr_ratio": result.get("rr_ratio", 0),
        "veto": result.get("veto"),
        "zr_high": result.get("zr_high", 0),
        "zr_low": result.get("zr_low", 0),
        "atr_pct": result.get("atr_pct", 0),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════
# Report Generators
# ══════════════════════════════════════════

def generate_market_report(results, composite_data=None, pfi_data=None):
    """Generate comprehensive daily market report."""
    data = _prepare_market_summary(results, composite_data, pfi_data)
    return _call_sonnet(
        SYSTEM_MARKET,
        f"حلل بيانات السوق اليوم وأعطني تقرير يومي شامل:\n\n{data}",
        max_tokens=4000,
    )


def generate_sector_report(results, sector_name):
    """Generate sector-specific analysis."""
    data = _prepare_sector_data(results, sector_name)
    return _call_sonnet(
        SYSTEM_SECTOR,
        f"حلل قطاع {sector_name} بالتفصيل:\n\n{data}",
        max_tokens=3000,
    )


def generate_stock_report(result):
    """Generate individual stock analysis."""
    data = _prepare_stock_data(result)
    name = result.get("name", result["ticker"])
    return _call_sonnet(
        SYSTEM_STOCK,
        f"حلل سهم {name} بالتفصيل:\n\n{data}",
        max_tokens=2500,
    )


def generate_composite_report(composite_data, pfi_data=None):
    """Generate composite index analysis."""
    data = json.dumps({
        "composite": composite_data,
        "pfi": pfi_data,
    }, ensure_ascii=False, indent=2)
    return _call_sonnet(
        SYSTEM_COMPOSITE,
        f"حلل المؤشر المركب:\n\n{data}",
        max_tokens=2500,
    )


def generate_opportunities_report(results):
    """Generate hidden opportunities and risks report."""
    data = _prepare_market_summary(results)
    return _call_sonnet(
        SYSTEM_OPPORTUNITIES,
        f"ابحث عن الفرص المخفية والمخاطر الخفية:\n\n{data}",
        max_tokens=4000,
    )


def is_ai_available():
    """Check if AI reports are available."""
    return HAS_ANTHROPIC and bool(st.secrets.get("ANTHROPIC_API_KEY", ""))
