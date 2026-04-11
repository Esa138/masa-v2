"""
MASA QUANT — AI Reports Engine V2
Powered by Google Gemini

Deep analysis — discovers hidden patterns, contradictions, and secrets
"""

import streamlit as st
import json
import requests
from datetime import datetime

# Gemini API configuration
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def _get_api_key():
    # Support both GEMINI_API_KEY and GOOGLE_API_KEY naming
    return st.secrets.get("GEMINI_API_KEY", "") or st.secrets.get("GOOGLE_API_KEY", "")


def _call_sonnet(system_prompt: str, user_prompt: str, max_tokens: int = 6000) -> str:
    """Call Google Gemini API."""
    api_key = _get_api_key()
    if not api_key:
        return "مفتاح API غير موجود. أضف GEMINI_API_KEY في Secrets."
    try:
        headers = {"Content-Type": "application/json"}
        params = {"key": api_key}
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.7,
            },
        }
        resp = requests.post(
            GEMINI_BASE_URL,
            headers=headers,
            params=params,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract text from response
        candidates = data.get("candidates", [])
        if not candidates:
            return "لم يتم إرجاع أي رد من النموذج."
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return "الرد فارغ من النموذج."
        return "".join(p.get("text", "") for p in parts)
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 401 or resp.status_code == 403:
            return "مفتاح API غير صحيح أو منتهي."
        elif resp.status_code == 429:
            return "تم تجاوز حد الاستخدام. حاول بعد دقيقة."
        return f"خطأ: {resp.status_code} — {resp.text[:200]}"
    except Exception as e:
        return f"خطأ: {str(e)}"


# ══════════════════════════════════════════
# EXPERT SYSTEM PROMPTS
# ══════════════════════════════════════════

SYSTEM_MARKET = """أنت محلل أسواق مالية خبير — مستوى hedge fund.
تكتب بالعربية (سعودي مهني). تحلل Order Flow بعمق وتكتشف ما لا يراه المتداول العادي.

## مهمتك:
اكتب تقرير يومي **مترابط ومتسق** — كل قسم يبني على اللي قبله. لا تناقض نفسك أبداً.

## قواعد حاسمة (لا تكسرها):
1. **لا تعطي فرصة في قطاع نسبة نجاحه تحت 40%** — شوف sector_performance في البيانات
2. **لا تعطي فرصة وتحذير على نفس السهم** — إما فرصة أو خطر
3. **لو 70%+ من الأسهم "تجنب"** = السوق خطير — لا تعطي أكثر من فرصة واحدة
4. **كل فرصة لازم تكون من قطاع نسبة نجاحه فوق 50%**
5. **اربط كل نقطة باللي قبلها** — التقرير قصة واحدة مو أقسام منفصلة

## البيانات المرفقة تشمل:
- sector_performance: نسبة نجاح كل قطاع تاريخياً (من Performance Tracker) — اعتمد عليها!
- golden_stats: أداء الفلتر الذهبي vs العادي — استخدمها في التوصيات
- market_type: سعودي أو أمريكي — لكل سوق خصائص مختلفة

## الهيكل المطلوب:

### 🔥 الخلاصة (3 أسطر)
- السطر الأول: حالة السوق اليوم بجملة واحدة
- السطر الثاني: أهم فرصة (لو موجودة) أو أهم تحذير
- السطر الثالث: التوصية المباشرة (ادخل/انتظر/اخرج)

### 📊 صورة السوق
اربط بين:
- نسبة التجميع vs التصريف (كم % من الأسهم تجميع؟)
- المؤشر المركب (صاعد/هابط؟)
- أداء النظام التاريخي (sector_performance)
- **خلص بحكم واحد متسق**

### 🔍 الاكتشافات (3 أسرار فقط — الأقوى)
لكل سر:
- وش اكتشفت بالضبط (سهم + أرقام)
- ليش هذا مهم (وش يعني للمتداول)
- وش الإجراء (ادخل/راقب/ابتعد)
**مهم: لا تذكر سهم هنا وتناقضه في قسم الفرص أو المخاطر**

### ⚡ الفرص (2 فقط — الأقوى)
**شروط الفرصة:**
- القطاع نسبة نجاحه **فوق 50%** (من sector_performance)
- السهم عنده flow إيجابي + CDV صاعد
- صفر أسباب حذر أو سبب واحد فقط
- مو نفس السهم اللي ذكرته في المخاطر

لكل فرصة جدول:
| السهم | الدخول | الوقف | الهدف | R:R | الثقة |
نسبة نجاح القطاع: X%

### 🔴 المخاطر (2 فقط — الأخطر)
**مهم: لا تذكر سهم هنا لو ذكرته في الفرص**
لكل خطر: اسم السهم + السبب + وش يصير لو دخلت

### 🎯 التوصية النهائية
جملة واحدة تربط كل اللي فوق — متسقة ما تناقض أي قسم.

### 🎯 التوصية النهائية
| العنصر | القيمة |
|--------|--------|
| حالة السوق | شراء / انتظار / بيع |
| درجة الثقة | X/100 |
| الأفق الزمني | هذا الأسبوع / هذا الشهر |
| أفضل قطاع للدخول | اسم القطاع + السبب |
| أسوأ قطاع | اسم القطاع + السبب |

### ⚡ أقوى 3 فرص (بالأرقام)
لكل فرصة:
| العنصر | القيمة |
|--------|--------|
| السهم | الاسم (الرمز) — السعر |
| الدخول | السعر بالضبط |
| الوقف | السعر + النسبة |
| الهدف | السعر + النسبة |
| R:R | X:1 |
| الثقة | X/100 |
| السبب | جملتين |

## قواعد صارمة:
- لا تكرر الأرقام بدون تحليل. "flow_bias 34" وحدها لا تعني شي — قل "تدفق قوي يعني المشترين عدوانيين".
- كل سهم تذكره اربطه بسبب — ليش هو فرصة أو خطر
- اكتشف الأنماط بين الأسهم — هل فيه مجموعة تتحرك مع بعض؟
- كل رقم من البيانات — لا تخترع. لو ما عندك الرقم قل "غير متوفر"
- لا تتجاوز 1500 كلمة"""

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

SYSTEM_STOCK = """أنت محلل فني ومالي خبير — مستوى hedge fund.
تكتب بالعربية (سعودي مهني).

## مهمتك:
حلل السهم بعمق كأنك تقدم توصية لمدير محفظة بمليارات. كل كلمة لازم تكون مدعومة بدليل.

## الهيكل الإلزامي:

### 🎯 القرار + درجة الثقة
| العنصر | القيمة |
|--------|--------|
| القرار | ادخل / راقب / تجنب |
| درجة الثقة | X/100 (اشرح ليش هالرقم مو أعلى أو أقل) |
| الأفق الزمني | قصير (1-5 أيام) / متوسط (1-4 أسابيع) / طويل (1-6 أشهر) |
| المخاطرة | منخفضة / متوسطة / عالية |

### 📊 بطاقة التنفيذ
| العنصر | القيمة |
|--------|--------|
| سعر الدخول | الرقم بالضبط (مو "عند الدعم") |
| وقف الخسارة | الرقم + النسبة من الدخول |
| الهدف الأول | الرقم + النسبة |
| الهدف الثاني | الرقم + النسبة (لو موجود) |
| R:R | X:1 — هل يستاهل المخاطرة |

### 🔬 تحليل Order Flow (الأدلة)
- **CDV**: صاعد/هابط/مستقر — هل يتوافق مع اتجاه السعر؟ لو تناقض = خطر أو فرصة.
- **المهاجم**: مشتري/بائع/متوازن — مين يسيطر فعلياً + aggressive_ratio
- **Divergence**: رقمه + تفسيره. لو فوق +25 = تجميع خفي مؤكد. لو تحت -25 = تصريف خفي.
- **Absorption**: الدرجة + الاتجاه (شرائي عند دعم = ممتاز. بيعي عند مقاومة = خطر).

### 🔄 مرحلة وايكوف + النضج
- المرحلة: accumulation/spring/markup/distribution/markdown
- عمر التجميع: X أيام (أقل من 3 = مبكر جداً. 3-7 = مبكر. 7-15 = ناضج. 15+ = متأخر)
- مرحلة النضج: stage_label

### 📍 موقع القطاع
- القطاع: اسمه
- حالة القطاع: هل القطاع قائد/متزامن/تابع بناءً على بيانات القطاع
- هل السهم يتوافق مع اتجاه القطاع أو يتناقض؟ (سهم يتجمع في قطاع يُصرَّف = حذر. سهم يتجمع في قطاع قائد = قوة)

### 📅 الموسمية (لو البيانات متوفرة)
- أداء الشهر الحالي تاريخياً: متوسط العائد + نسبة النجاح
- هل الموسمية متوافقة أو متناقضة مع Order Flow؟
- لو تناقض (مثل: OF يقول اشتر لكن الشهر تاريخياً سلبي) = نبّه!

### ⚠️ التناقضات والمخاطر
ابحث عن أي تناقض:
1. CDV يصعد لكن السعر ينزل = تجميع خفي (إيجابي)
2. CDV ينزل لكن السعر يصعد = صعود كاذب (خطير!)
3. RSI منخفض + كسر دعم + CDV هابط = سكين ساقطة (لا تلمس!)
4. المشتري مهاجم + السعر ثابت = امتصاص (فرصة)
5. أسباب الدخول كثيرة لكن R:R أقل من 1.5 = مخاطرة أعلى من العائد
6. Veto موجود = لا تدخل مهما كان

### 🤔 السر
شي واحد ما يشوفه المتداول العادي. ممكن يكون:
- تناقض بين Order Flow والسعر
- نمط تكرر تاريخياً في هالقطاع
- إشارة مبكرة على تحول (من تجميع لانطلاق أو من تصريف لانهيار)
- ربط مع حدث خارجي (توزيعات، نتائج، أوبك)

## قواعد صارمة:
- كل رقم تذكره لازم يكون من البيانات — لا تخترع
- لا تقول "قريب من الدعم" قل "السعر 115.9 والدعم 112.5 (بُعد 3%)"
- لا تقول "R:R جيد" قل "R:R 2.5:1 (وقف 3.5% مقابل هدف 8.7%)"
- درجة الثقة لازم تعكس قوة الأدلة: 90+ = أدلة قاطعة. 70-89 = أدلة قوية مع تحفظ. 50-69 = متوازنة. تحت 50 = ضعيفة.
- لا تتجاوز 800 كلمة."""

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

    # Add historical sector performance from Performance Tracker
    try:
        import sqlite3, os
        _db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "masa_v2_seed.db")
        if not os.path.exists(_db):
            _db = "masa_v2.db"
        conn = sqlite3.connect(_db)
        _sec_perf = conn.execute("""
            SELECT sector, COUNT(*) as cnt,
                   SUM(CASE WHEN outcome_10d='win' THEN 1 ELSE 0 END) as wins,
                   ROUND(AVG(return_10d), 2) as avg_ret
            FROM signals WHERE outcome_10d IS NOT NULL AND decision='enter'
            GROUP BY sector ORDER BY AVG(return_10d) DESC
        """).fetchall()
        summary["sector_performance"] = {
            "description": "نسبة نجاح كل قطاع تاريخياً (10 أيام) — لا تعطي فرصة في قطاع تحت 40%",
            "data": [
                {"sector": s, "signals": c, "win_rate": round(w/c*100) if c > 0 else 0,
                 "avg_return": a, "verdict": "🟢 موثوق" if w/c >= 0.6 else "🟡 متوسط" if w/c >= 0.4 else "🔴 كارثي — لا تدخل"}
                for s, c, w, a in _sec_perf
            ]
        }

        # Golden vs Normal stats
        import re
        _all_sigs = conn.execute("""
            SELECT reasons_for, reasons_against, accum_level, outcome_10d, return_10d
            FROM signals WHERE outcome_10d IS NOT NULL AND decision='enter'
        """).fetchall()
        _g, _n = 0, 0
        _gw, _nw = 0, 0
        for rf, ra, al, o, r in _all_sigs:
            rf, ra = rf or "", ra or ""
            ia = al in ("accumulation", "spring")
            hb = "المشتري هو المهاجم" in rf
            dv = 0
            if "دايفرجنس" in rf:
                m = re.search(r'\+(\d+)', rf.split("دايفرجنس")[1][:20])
                if m: dv = int(m.group(1))
            za = len(ra.strip()) == 0
            if ia and hb and dv >= 25 and za:
                _g += 1
                if o == "win": _gw += 1
            else:
                _n += 1
                if o == "win": _nw += 1

        summary["golden_stats"] = {
            "description": "الفلتر الذهبي (تجميع + مهاجم + div≥25 + صفر حذر) — أفضل بـ 33% من العادي",
            "golden": {"total": _g, "wins": _gw, "win_rate": round(_gw/_g*100) if _g > 0 else 0},
            "normal": {"total": _n, "wins": _nw, "win_rate": round(_nw/_n*100) if _n > 0 else 0},
        }

        # Avoid percentage
        summary["avoid_pct"] = round(len(avoids) / total * 100, 1) if total > 0 else 0
        summary["market_danger"] = summary["avoid_pct"] > 70

        conn.close()
    except Exception:
        pass

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


def _prepare_stock_data(result, sector_info=None, seasonality_info=None):
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

    # Contradictions pre-computed
    contradictions = []
    if result.get("cdv_trend") == "rising" and result.get("change_pct", 0) < -0.5:
        contradictions.append("CDV صاعد لكن السعر ينزل = تجميع خفي محتمل")
    if result.get("cdv_trend") == "falling" and result.get("change_pct", 0) > 0.5:
        contradictions.append("CDV هابط لكن السعر يرتفع = صعود كاذب محتمل")
    if result.get("aggressor") == "buyers" and result.get("change_pct", 0) < 0:
        contradictions.append("المشتري مهاجم لكن السعر ينزل = امتصاص شرائي")
    if result.get("rsi", 50) < 30 and result.get("flow_bias", 0) > 15:
        contradictions.append("RSI منخفض جداً + تدفق إيجابي = ارتداد محتمل")
    if result.get("rsi", 50) < 25 and result.get("cdv_trend") == "falling":
        contradictions.append("RSI متطرف + CDV هابط = سكين ساقطة - خطر!")

    data["contradictions"] = contradictions

    # Sector context
    if sector_info:
        data["sector_health"] = sector_info.get("health", 0)
        data["sector_accum"] = sector_info.get("n_accum", 0)
        data["sector_dist"] = sector_info.get("n_dist", 0)
        data["sector_total"] = sector_info.get("n", 0)

    # Seasonality — supports both formats: stats dict or current_month dict
    if seasonality_info:
        from datetime import datetime
        mo = datetime.now().month
        ms = None

        # Format 1: from build_seasonality_for_sectors (has "stats" key)
        if mo in seasonality_info.get("stats", {}):
            ms = seasonality_info["stats"][mo]

        # Format 2: from _fetch_stock_seasonality (has "current_month" key)
        elif seasonality_info.get("current_month"):
            ms = seasonality_info["current_month"]

        if ms:
            _avg_ret = ms.get("avg_return", 0)
            _win_rate = ms.get("win_rate", 0)
            _phase = ms.get("phase", "")
            _month_name = ms.get("month_ar", ms.get("name", ""))

            data["seasonality"] = {
                "month": _month_name,
                "avg_return": _avg_ret,
                "win_rate": _win_rate,
                "phase": _phase,
                "sharpe": ms.get("sharpe", 0),
                "profit_factor": ms.get("profit_factor", 0),
                "best": ms.get("best", 0),
                "worst": ms.get("worst", 0),
                "n_years": seasonality_info.get("n_years", 0),
                "years_range": f"{min(seasonality_info.get('years_covered', [0]))}—{max(seasonality_info.get('years_covered', [0]))}" if seasonality_info.get("years_covered") else "",
            }

            # Add catalysts if available
            _cat = seasonality_info.get("catalysts", {})
            if isinstance(_cat, dict) and _cat:
                data["seasonality"]["catalyst"] = _cat.get("note", "")
                data["seasonality"]["catalyst_events"] = _cat.get("events", [])

            # Seasonality vs OF contradiction
            if _avg_ret < -1 and result.get("flow_bias", 0) > 15:
                data["contradictions"].append(
                    f"تناقض موسمي: {_month_name} تاريخياً سلبي ({_avg_ret:+.1f}%) لكن OF إيجابي — حذر!"
                )
            elif _avg_ret > 1 and result.get("flow_bias", 0) < -10:
                data["contradictions"].append(
                    f"تناقض موسمي: {_month_name} تاريخياً إيجابي ({_avg_ret:+.1f}%) لكن OF سلبي — غريب!"
                )

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


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_stock_seasonality(ticker, sector=""):
    """Fetch seasonality from yfinance — cached 24h. Tries multiple periods."""
    try:
        import yfinance as yf
        from core.seasonality import compute_monthly_returns, compute_seasonality_stats, get_current_month_insight, _get_sector_catalysts
        from datetime import datetime

        t = yf.Ticker(ticker)
        df = None
        for p in ["max", "10y", "5y", "2y"]:
            try:
                df = t.history(period=p, interval="1d")
                if df is not None and not df.empty and len(df) >= 200:
                    break
            except Exception:
                continue

        if df is None or df.empty or len(df) < 200:
            return {"error": "no_data"}

        dates = [d.strftime("%Y-%m-%d") for d in df.index]
        closes = [float(v) for v in df["Close"]]

        monthly = compute_monthly_returns(dates, closes)
        if not monthly or len(monthly) < 6:
            return {"error": "insufficient_monthly"}

        stats = compute_seasonality_stats(monthly)
        market_key = "saudi" if ".SR" in ticker else "us"
        catalysts = _get_sector_catalysts(sector, market_key)
        insight = get_current_month_insight(stats, catalysts)

        current_month = datetime.now().month
        current_stats = stats.get(current_month)

        return {
            "years_covered": sorted(set(m["year"] for m in monthly)),
            "n_years": len(set(m["year"] for m in monthly)),
            "current_month": {
                "name": current_stats["month_ar"] if current_stats else "",
                "avg_return": current_stats["avg_return"] if current_stats else 0,
                "win_rate": current_stats["win_rate"] if current_stats else 0,
                "sharpe": current_stats.get("sharpe", 0) if current_stats else 0,
                "phase": current_stats["phase"] if current_stats else "",
                "best": current_stats["best"] if current_stats else 0,
                "worst": current_stats["worst"] if current_stats else 0,
                "profit_factor": current_stats.get("profit_factor", 0) if current_stats else 0,
            } if current_stats else None,
            "insight": insight,
            "catalysts": catalysts.get(current_month, {}),
            "source": f"yfinance_{len(df)}_bars",
        }
    except Exception as e:
        return {"error": str(e)}


def _fallback_seasonality_from_scan(result):
    """Fallback: compute seasonality from scan's chart_dates/chart_close if yfinance fails."""
    try:
        from core.seasonality import compute_monthly_returns, compute_seasonality_stats, get_current_month_insight, _get_sector_catalysts
        from datetime import datetime

        dates = result.get("chart_dates", [])
        closes = result.get("chart_close", [])
        if not dates or len(dates) < 60:
            return None

        monthly = compute_monthly_returns(dates, closes)
        if not monthly or len(monthly) < 6:
            return None

        stats = compute_seasonality_stats(monthly)
        sector = result.get("sector", "")
        market_key = "saudi" if ".SR" in result.get("ticker", "") else "us"
        catalysts = _get_sector_catalysts(sector, market_key)
        insight = get_current_month_insight(stats, catalysts)

        mo = datetime.now().month
        cs = stats.get(mo)

        return {
            "years_covered": sorted(set(m["year"] for m in monthly)),
            "n_years": len(set(m["year"] for m in monthly)),
            "current_month": {
                "name": cs["month_ar"] if cs else "",
                "avg_return": cs["avg_return"] if cs else 0,
                "win_rate": cs["win_rate"] if cs else 0,
                "sharpe": cs.get("sharpe", 0) if cs else 0,
                "phase": cs["phase"] if cs else "",
                "best": cs["best"] if cs else 0,
                "worst": cs["worst"] if cs else 0,
                "profit_factor": cs.get("profit_factor", 0) if cs else 0,
            } if cs else None,
            "insight": insight,
            "catalysts": catalysts.get(mo, {}),
            "source": "scan_data",
        }
    except Exception:
        return None


def generate_stock_report(result, sector_info=None, seasonality_info=None):
    # Always try to fetch independent seasonality
    if not seasonality_info or (isinstance(seasonality_info, dict) and not seasonality_info.get("stats") and not seasonality_info.get("current_month")):
        ticker = result.get("ticker", "")
        sector = result.get("sector", "")
        # Try 1: yfinance (cached 24h)
        fetched = _fetch_stock_seasonality(ticker, sector)
        if fetched and not fetched.get("error") and fetched.get("current_month"):
            seasonality_info = fetched
        else:
            # Try 2: fallback from scan data
            fallback = _fallback_seasonality_from_scan(result)
            if fallback and fallback.get("current_month"):
                seasonality_info = fallback

    data = _prepare_stock_data(result, sector_info, seasonality_info)
    name = result.get("name", result["ticker"])
    return _call_sonnet(SYSTEM_STOCK, f"حلل سهم {name} بعمق:\n\n{data}", 4000)


def generate_composite_report(composite_data, pfi_data=None):
    data = json.dumps({"composite": composite_data, "pfi": pfi_data}, ensure_ascii=False, indent=2)
    return _call_sonnet(SYSTEM_COMPOSITE, f"حلل المؤشر المركب وتدفق الأموال:\n\n{data}", 3000)


def generate_opportunities_report(results):
    data = _prepare_market_summary(results)
    return _call_sonnet(SYSTEM_OPPORTUNITIES, f"ابحث عن كل الأنماط المخفية:\n\n{data}", 6000)


def is_ai_available():
    return bool(st.secrets.get("GEMINI_API_KEY", "") or st.secrets.get("GOOGLE_API_KEY", ""))
