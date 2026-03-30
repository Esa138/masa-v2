"""
MASA QUANT — AI Reports Engine V2
Powered by Claude Sonnet

Deep analysis — discovers hidden patterns, contradictions, and secrets
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
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _call_sonnet(system_prompt: str, user_prompt: str, max_tokens: int = 6000) -> str:
    client = _get_client()
    if not client:
        return "مفتاح API غير موجود. أضف ANTHROPIC_API_KEY في Secrets."
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except anthropic.AuthenticationError:
        return "مفتاح API غير صحيح."
    except anthropic.RateLimitError:
        return "تم تجاوز حد الاستخدام. حاول بعد دقيقة."
    except Exception as e:
        return f"خطأ: {str(e)}"


# ══════════════════════════════════════════
# EXPERT SYSTEM PROMPTS
# ══════════════════════════════════════════

SYSTEM_MARKET = """أنت محلل أسواق مالية خبير — مستوى hedge fund.
تكتب بالعربية (سعودي مهني). تحلل Order Flow بعمق وتكتشف ما لا يراه المتداول العادي.

## مهمتك:
اكتب تقرير يومي يكشف **الأسرار** — ليس ملخص أرقام.

## الهيكل المطلوب:

### 🔥 الخلاصة (جملة واحدة)
أهم شي اليوم — الرسالة اللي لو المتداول ما قرأ غيرها يكفيه.

### 🔍 الأسرار المكتشفة
ابحث في البيانات عن:
1. **تناقض CDV vs السعر**: سهم ينزل لكن CDV صاعد = تجميع خفي (سمارت مني يشتري والعامة تبيع)
2. **تناقض CDV vs السعر (عكسي)**: سهم يرتفع لكن CDV هابط = تصريف خفي (سمارت مني تبيع والعامة تشتري)
3. **المهاجم vs الاتجاه**: المشتري مهاجم لكن السعر ينزل = امتصاص (absorption) — فرصة ذهبية
4. **RSI متطرف + تدفق عكسي**: RSI تحت 30 لكن flow_bias إيجابي = ارتداد قادم
5. **تسارع تجميع**: أسهم عندها days > 5 مع flow_bias فوق 20 = انفجار وشيك
6. **سبرنق (Spring)**: مرحلة spring = كسر كاذب تحت الدعم ثم ارتداد — أقوى إشارة وايكوف
7. **القطاع vs السهم**: قطاع يصعد لكن سهم فيه يتخلف مع تجميع = فرصة
8. **Divergence قوي**: divergence فوق 30 أو تحت -30 = إشارة قوية جداً
9. **Veto أو كسر دعم**: أي سهم عنده veto أو reasons_against فيها "كسر دعم" = خطر حقيقي
10. **نسبة تجميع vs تصريف**: لو 70%+ تجميع = السوق يتحضر لصعود. لو 70%+ تصريف = هروب مؤسسي.

### ⚡ أقوى 3 فرص
لكل فرصة: اسم السهم، السعر، السبب بالتفصيل، نقطة الدخول، وقف الخسارة، الهدف.
ركز على الأسهم اللي عندها تجميع خفي أو سبرنق أو divergence قوي.

### 🔴 أخطر 3 مخاطر
لكل خطر: اسم السهم، السبب، وش يصير لو دخلت.
ركز على الأسهم اللي عندها صعود كاذب أو كسر دعم مع RSI منخفض.

### 📊 نبض القطاعات
أي قطاع يقود؟ أي قطاع يتأخر؟ أي قطاع فيه تناقض (يبان قوي لكنه ضعيف من الداخل)؟

### 🎯 التوصية
هل السوق مناسب للشراء اليوم أم الانتظار؟ ولماذا؟
درجة الثقة من 1-10.

## قواعد صارمة:
- لا تكرر الأرقام بدون تحليل. "flow_bias 34" وحدها لا تعني شي — قل "تدفق قوي يعني المشترين عدوانيين".
- كل سهم تذكره اربطه بسبب — ليش هو فرصة أو خطر
- اكتشف الأنماط بين الأسهم — هل فيه مجموعة تتحرك مع بعض؟
- لا تعطي أكثر من 1200 كلمة"""

SYSTEM_SECTOR = """أنت محلل قطاعات مالية خبير — مستوى institutional.
تكتب بالعربية.

## مهمتك:
حلل القطاع بعمق واكتشف الأسرار.

## الهيكل:

### 🏆 ملخص القطاع (3 أسطر)
الصورة الكاملة — هل القطاع يتجمع أو يُصرَّف؟

### 🔍 الأسرار
1. أي سهم فيه تجميع خفي (ينزل لكن CDV صاعد أو flow إيجابي)؟
2. أي سهم فيه صعود كاذب (يرتفع لكن CDV هابط)؟
3. أي سهم المهاجم فيه مشتري لكن السعر ما تحرك بعد؟ = امتصاص
4. أي سهم عنده divergence قوي (+30 أو -30)؟
5. هل فيه تناقض بين أسهم القطاع؟ (واحد يصعد والباقي ينزل)

### 📊 ترتيب الأسهم
رتب كل سهم من الأفضل للأسوأ مع سبب مختصر.
استخدم هالمعايير بالترتيب:
1. المرحلة (spring > accumulation > markup > neutral > distribution)
2. flow_bias (أعلى = أفضل)
3. CDV trend (صاعد > مستقر > هابط)
4. RSI (30-60 = أفضل منطقة)
5. الموقع (support/bottom > middle > resistance)

### 🎯 أفضل سهم للدخول ولماذا
بالتفصيل — وقف، هدف، شروط الدخول.

### ⚠️ أخطر سهم ولماذا
لا تدخله ولو يبان حلو — اشرح الفخ.

لا تتجاوز 800 كلمة."""

SYSTEM_STOCK = """أنت محلل فني ومالي خبير.
تكتب بالعربية.

## مهمتك:
حلل السهم بعمق كأنك تقدم توصية لمدير محفظة.

## الهيكل:

### 🎯 القرار (جملة واحدة)
ادخل / راقب / تجنب — والسبب الرئيسي.

### 🔬 تحليل Order Flow
- **CDV**: صاعد/هابط/مستقر — وش يعني للسهم
- **المهاجم**: مشتري/بائع/متوازن — مين يسيطر فعلياً
- **Divergence**: لو موجود، هل هو إشارة حقيقية أو فخ؟
- **Absorption**: هل فيه امتصاص عند الدعم/المقاومة؟

### 📐 التحليل الفني
- الموقع: فوق/تحت MA200، قريب من دعم/مقاومة
- RSI: تشبع شرائي/بيعي أو منطقة صحية
- ZR (Zero Reversal): وش يقول السقف والقاع

### 🔄 مرحلة وايكوف
أي مرحلة بالضبط وكم عمرها (أيام التجميع). هل ناضجة أو مبكرة؟

### ⚠️ المخاطر
- وقف الخسارة: كم ونسبته
- أسوأ سيناريو: وش يصير لو غلطت
- أسباب الحذر كاملة

### 💰 الفرصة
- الهدف: كم ونسبته
- R:R: هل يستاهل المخاطرة
- متى تدخل بالضبط (الشرط)

### 🤔 السر
شي واحد ما يشوفه المتداول العادي — تناقض، نمط خفي، إشارة مبكرة.

درجة الثقة: 1-10
لا تتجاوز 600 كلمة."""

SYSTEM_COMPOSITE = """أنت محلل مؤشرات مالية خبير.
تكتب بالعربية.

## مهمتك:
حلل المؤشر المركب + مؤشر تدفق الأموال (PFI) واكشف الصورة الحقيقية للسوق.

## الهيكل:

### 📊 قراءة المؤشر
- القيمة الحالية ومعناها (فوق 100 = صعود، تحت = هبوط)
- التغير اليومي — هل مستمر أو انعكاس
- الموقع من الدعم والمقاومة — هل قريب من مستوى حرج؟

### 💰 تدفق الأموال (PFI)
- نسبة التجميع vs التصريف — مين يسيطر
- لو التجميع فوق 50% = أموال تدخل. تحت = أموال تخرج.
- تفسير PFI: فوق 55 = شرائي، تحت 45 = بيعي، بينهم = حيادي

### 🔍 التناقض
هل المؤشر المركب يتوافق مع PFI؟
- مؤشر صاعد + PFI شرائي = تأكيد (قوي)
- مؤشر صاعد + PFI بيعي = صعود كاذب (خطر!)
- مؤشر هابط + PFI شرائي = تجميع خفي (فرصة!)
- مؤشر هابط + PFI بيعي = هبوط حقيقي (ابتعد)

### 📈 المقارنة مع المرجعي
هل المؤشر يسبق أو يتبع المرجعي؟ وش الدلالة؟

### 🎯 توقع الأسبوع القادم
بناءً على الاتجاه + PFI + الدعم/المقاومة.

لا تتجاوز 500 كلمة."""

SYSTEM_OPPORTUNITIES = """أنت صائد فرص — مثل detective مالي.
تكتب بالعربية.

## مهمتك:
ابحث في كل سهم عن الإشارات المخفية اللي ما يشوفها المتداول العادي.

## ابحث عن هذي الأنماط بالضبط:

### النمط 1: تجميع خفي 🟢
**الشرط**: السعر ينزل أو ثابت + flow_bias > 15 + CDV صاعد + aggressor = buyers
**المعنى**: سمارت مني يشتري بينما الناس خايفة
**الإجراء**: راقب وانتظر أول شمعة خضراء بحجم عالي

### النمط 2: صعود كاذب 🔴
**الشرط**: السعر يرتفع + flow_bias > 0 + CDV هابط + aggressor = sellers أو balanced
**المعنى**: السعر يُرفع بالتلاعب والسمارت مني تبيع
**الإجراء**: لا تدخل — فخ

### النمط 3: سبرنق (أقوى إشارة) 💎
**الشرط**: phase = spring
**المعنى**: كسر كاذب تحت الدعم ثم ارتداد فوري — المؤسسات صفّت الضعفاء وبدأت الشراء
**الإجراء**: ادخل فوراً

### النمط 4: انفجار قادم 🚀
**الشرط**: phase = accumulation + days > 7 + flow_bias > 25 + divergence > 20
**المعنى**: تجميع طويل ناضج — جاهز للانطلاق
**الإجراء**: ادخل مع أول اختراق فوق المقاومة

### النمط 5: تناقض القطاع 🔄
**الشرط**: معظم أسهم القطاع ترتفع لكن سهم واحد يتخلف مع flow إيجابي
**المعنى**: السهم المتخلف بيلحق — فرصة
**الإجراء**: ادخل السهم المتخلف

### النمط 6: سكين ساقطة ☠️
**الشرط**: RSI < 25 + CDV هابط + location = support + change < -1%
**المعنى**: السهم يكسر دعم — لا تلتقطه
**الإجراء**: ابتعد تماماً

### النمط 7: امتصاص عند الدعم 🧲
**الشرط**: absorption > 60 + absorption_bias > 0.2 + location = support أو bottom
**المعنى**: حجم كبير عند الدعم لكن السعر ما ينزل = مؤسسات تمتص البيع
**الإجراء**: ادخل مع وقف تحت الدعم

### النمط 8: Divergence مزدوج ⚡
**الشرط**: divergence > 30 + flow_bias > 20 + RSI < 40
**المعنى**: ثلاث إشارات تجميع متزامنة — قوة ثلاثية
**الإجراء**: إشارة قوية جداً — ادخل

## التنسيق لكل اكتشاف:
| العنصر | التفاصيل |
|--------|----------|
| السهم | الاسم (الرمز) — السعر |
| النمط | اسم النمط + الأيقونة |
| القوة | ضعيفة / متوسطة / قوية |
| الدليل | الأرقام اللي تثبت النمط |
| الإجراء | وش تسوي بالضبط |
| الوقف | رقم محدد |
| الهدف | رقم محدد |

لا تتجاوز 1500 كلمة. اذكر كل نمط تلقاه — لا تتجاهل أي شي."""


# ══════════════════════════════════════════
# Data Preparation — DEEP
# ══════════════════════════════════════════

def _prepare_market_summary(results, composite_data=None, pfi_data=None):
    if not results:
        return "لا توجد بيانات"

    total = len(results)
    enters = [r for r in results if r.get("decision") == "enter"]
    avoids = [r for r in results if r.get("decision") == "avoid"]
    watches = [r for r in results if r.get("decision") == "watch"]

    # Phase breakdown
    phases = {}
    for r in results:
        p = r.get("phase", "unknown")
        phases[p] = phases.get(p, 0) + 1

    # Sector breakdown
    sectors = {}
    for r in results:
        s = r.get("sector", "غير مصنف")
        if s not in sectors:
            sectors[s] = {"total": 0, "enter": 0, "avoid": 0, "avg_flow": 0, "flows": []}
        sectors[s]["total"] += 1
        if r.get("decision") == "enter":
            sectors[s]["enter"] += 1
        elif r.get("decision") == "avoid":
            sectors[s]["avoid"] += 1
        sectors[s]["flows"].append(r.get("flow_bias", 0))

    for s in sectors:
        flows = sectors[s]["flows"]
        sectors[s]["avg_flow"] = round(sum(flows) / len(flows), 1) if flows else 0
        del sectors[s]["flows"]

    # All enter stocks with FULL details
    enter_details = []
    for r in enters[:15]:
        enter_details.append({
            "name": r.get("name", r["ticker"]),
            "ticker": r["ticker"],
            "sector": r.get("sector", ""),
            "price": r.get("last_close", 0),
            "change_pct": r.get("change_pct", 0),
            "flow_bias": r.get("flow_bias", 0),
            "cdv_trend": r.get("cdv_trend", ""),
            "aggressor": r.get("aggressor", ""),
            "phase": r.get("phase", ""),
            "rsi": r.get("rsi", 0),
            "divergence": r.get("divergence", 0),
            "absorption_score": r.get("absorption_score", 0),
            "absorption_bias": r.get("absorption_bias", 0),
            "location": r.get("location", ""),
            "days": r.get("days", 0),
            "flow_type_label": r.get("flow_type_label", ""),
            "reasons_for": r.get("reasons_for", []),
            "reasons_against": r.get("reasons_against", []),
            "stop_loss": r.get("stop_loss", 0),
            "target": r.get("target", 0),
            "rr_ratio": r.get("rr_ratio", 0),
            "veto": r.get("veto"),
        })

    # Contradictions: price down + flow up
    hidden_accum = []
    for r in results:
        if r.get("change_pct", 0) < -0.3 and r.get("flow_bias", 0) > 10 and r.get("cdv_trend") == "rising":
            hidden_accum.append({
                "name": r.get("name", r["ticker"]),
                "change": r.get("change_pct", 0),
                "flow": r.get("flow_bias", 0),
                "phase": r.get("phase", ""),
                "divergence": r.get("divergence", 0),
            })

    # False rallies: price up + CDV falling
    false_rallies = []
    for r in results:
        if r.get("change_pct", 0) > 0.5 and r.get("cdv_trend") == "falling" and r.get("flow_bias", 0) < 10:
            false_rallies.append({
                "name": r.get("name", r["ticker"]),
                "change": r.get("change_pct", 0),
                "flow": r.get("flow_bias", 0),
                "cdv_trend": "هابط",
            })

    # Springs
    springs = [
        {"name": r.get("name", r["ticker"]), "price": r.get("last_close", 0),
         "flow": r.get("flow_bias", 0), "days": r.get("days", 0)}
        for r in results if r.get("phase") == "spring"
    ]

    # Strong divergence
    strong_div = [
        {"name": r.get("name", r["ticker"]), "divergence": r.get("divergence", 0),
         "flow": r.get("flow_bias", 0), "rsi": r.get("rsi", 0), "change": r.get("change_pct", 0)}
        for r in results if abs(r.get("divergence", 0)) > 25
    ]

    summary = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_stocks": total,
        "decisions": {"enter": len(enters), "watch": len(watches), "avoid": len(avoids)},
        "phases": phases,
        "sectors": sectors,
        "enter_stocks": enter_details,
        "hidden_accumulation": hidden_accum,
        "false_rallies": false_rallies,
        "springs": springs,
        "strong_divergence": strong_div,
        "accum_pct": round(phases.get("accumulation", 0) / total * 100, 1) if total else 0,
        "dist_pct": round(phases.get("distribution", 0) / total * 100, 1) if total else 0,
    }

    if composite_data:
        summary["composite"] = composite_data
    if pfi_data:
        summary["pfi"] = pfi_data

    return json.dumps(summary, ensure_ascii=False, indent=2)


def _prepare_sector_data(results, sector_name):
    sector_stocks = [r for r in results if r.get("sector") == sector_name]
    if not sector_stocks:
        return "لا توجد أسهم"

    stocks_data = []
    for r in sector_stocks:
        stocks_data.append({
            "name": r.get("name", r["ticker"]),
            "ticker": r["ticker"],
            "price": r.get("last_close", 0),
            "change_pct": r.get("change_pct", 0),
            "decision": r.get("decision", ""),
            "phase": r.get("phase", ""),
            "flow_bias": r.get("flow_bias", 0),
            "cdv_trend": r.get("cdv_trend", ""),
            "aggressor": r.get("aggressor", ""),
            "rsi": r.get("rsi", 0),
            "divergence": r.get("divergence", 0),
            "absorption_score": r.get("absorption_score", 0),
            "absorption_bias": r.get("absorption_bias", 0),
            "location": r.get("location", ""),
            "days": r.get("days", 0),
            "flow_type_label": r.get("flow_type_label", ""),
            "reasons_for": r.get("reasons_for", []),
            "reasons_against": r.get("reasons_against", []),
            "stop_loss": r.get("stop_loss", 0),
            "target": r.get("target", 0),
            "rr_ratio": r.get("rr_ratio", 0),
            "veto": r.get("veto"),
        })

    return json.dumps({"sector": sector_name, "total": len(stocks_data), "stocks": stocks_data}, ensure_ascii=False, indent=2)


def _prepare_stock_data(result):
    data = {
        "name": result.get("name", result["ticker"]),
        "ticker": result["ticker"],
        "sector": result.get("sector", ""),
        "price": result.get("last_close", 0),
        "change_pct": result.get("change_pct", 0),
        "decision": result.get("decision", ""),
        "decision_info": result.get("decision_info", {}),
        "phase": result.get("phase", ""),
        "phase_info": result.get("phase_info", {}),
        "flow_bias": result.get("flow_bias", 0),
        "cdv_trend": result.get("cdv_trend", ""),
        "aggressor": result.get("aggressor", ""),
        "aggressive_ratio": result.get("aggressive_ratio", 0),
        "rsi": result.get("rsi", 0),
        "divergence": result.get("divergence", 0),
        "absorption_score": result.get("absorption_score", 0),
        "absorption_bias": result.get("absorption_bias", 0),
        "location": result.get("location", ""),
        "ma200": result.get("ma200", 0),
        "days": result.get("days", 0),
        "flow_type_label": result.get("flow_type_label", ""),
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
        "maturity_stage": result.get("maturity", {}).get("stage", ""),
        "maturity_label": result.get("maturity", {}).get("stage_label", ""),
        "maturity_days": result.get("maturity", {}).get("current_days", 0),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════
# Report Generators
# ══════════════════════════════════════════

def generate_market_report(results, composite_data=None, pfi_data=None):
    data = _prepare_market_summary(results, composite_data, pfi_data)
    return _call_sonnet(SYSTEM_MARKET, f"حلل بيانات السوق واكتشف الأسرار:\n\n{data}", 6000)


def generate_sector_report(results, sector_name):
    data = _prepare_sector_data(results, sector_name)
    return _call_sonnet(SYSTEM_SECTOR, f"حلل قطاع {sector_name} واكتشف الأسرار:\n\n{data}", 4000)


def generate_stock_report(result):
    data = _prepare_stock_data(result)
    name = result.get("name", result["ticker"])
    return _call_sonnet(SYSTEM_STOCK, f"حلل سهم {name} بعمق:\n\n{data}", 3000)


def generate_composite_report(composite_data, pfi_data=None):
    data = json.dumps({"composite": composite_data, "pfi": pfi_data}, ensure_ascii=False, indent=2)
    return _call_sonnet(SYSTEM_COMPOSITE, f"حلل المؤشر المركب وتدفق الأموال:\n\n{data}", 3000)


def generate_opportunities_report(results):
    data = _prepare_market_summary(results)
    return _call_sonnet(SYSTEM_OPPORTUNITIES, f"ابحث عن كل الأنماط المخفية:\n\n{data}", 6000)


def is_ai_available():
    return HAS_ANTHROPIC and bool(st.secrets.get("ANTHROPIC_API_KEY", ""))
