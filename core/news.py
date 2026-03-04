"""
MASA QUANT V95 — News Sentiment + TASI Keyword Scanner
Fetches news from yfinance, scans for killer/rocket keywords,
analyzes with Gemini AI, returns sentiment + keyword hits + adjustment.
"""

import time
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf


# ══════════════════════════════════════════════════════════════
#  TASI Killer & Rocket Keywords
#  Source: Saudi market behavioral analysis
# ══════════════════════════════════════════════════════════════

# 💣 Killer keywords — destroy stocks instantly
# Each: (keyword_ar, keyword_en, impact_weight 1-10, effect_description)
KILLER_KEYWORDS = [
    ("خسائر متراكمة",      "accumulated losses",           10, "هروب جماعي فوري"),
    ("خسائر",              "losses",                        6, "ضغط بيعي"),
    ("تعثر في السداد",     "default",                       9, "انهيار الثقة الائتمانية"),
    ("تعثر",               "default",                       7, "مخاطر ائتمانية"),
    ("إفلاس",              "bankruptcy",                    10, "الحد الأدنى في ساعات"),
    ("تصفية",              "liquidation",                   10, "إنهاء الشركة"),
    ("تحقيق رقابي",        "regulatory investigation",      8, "بيع مذعور"),
    ("تحقيق",              "investigation",                 5, "قلق تنظيمي"),
    ("إيقاف الإنتاج",      "production halt",               8, "تشكيك في استمرارية الأعمال"),
    ("إيقاف",              "suspension",                    6, "توقف مؤقت"),
    ("دون التوقعات",       "below expectations",            7, "خيبة أمل وتصحيح حاد"),
    ("أقل من التوقعات",    "below expectations",            7, "خيبة أمل"),
    ("سحب الترخيص",        "license revocation",            9, "شبه توقف للشركة"),
    ("استقالة الرئيس",     "ceo resignation",               7, "ضبابية قيادية"),
    ("استقالة",            "resignation",                   5, "تغيير إداري"),
    ("رفع دعوى",          "lawsuit filed",                 6, "مخاطر قانونية مفتوحة"),
    ("دعوى قضائية",        "lawsuit",                       6, "مخاطر قانونية"),
    ("توقف توزيع",         "dividend suspension",           8, "طرد حاملي الدخل الثابت"),
    ("تخفيض التوزيعات",    "dividend cut",                  6, "خيبة أمل للمستثمرين"),
    ("انخفاض الأرباح",     "profit decline",                6, "ضعف تشغيلي"),
    ("تراجع الإيرادات",    "revenue decline",               5, "تباطؤ النمو"),
    ("غرامة",              "fine",                          5, "مخاطر تنظيمية"),
    ("مخالفة",             "violation",                     5, "مخاطر تنظيمية"),
    ("احتيال",             "fraud",                         9, "انهيار الثقة"),
    ("تلاعب",              "manipulation",                  8, "فقدان المصداقية"),
    ("إعادة هيكلة ديون",   "debt restructuring",            7, "ضغط مالي شديد"),
    ("تخفيض التصنيف",      "downgrade",                     6, "تراجع الثقة المؤسسية"),
    # --- Arabic market action keywords (common in news headlines) ---
    ("تهوي",               "plunge",                        7, "انهيار حاد"),
    ("تهبط",               "drop",                          5, "ضغط بيعي"),
    ("هبوط حاد",           "sharp drop",                    7, "بيع مذعور"),
    ("هبوط",               "drop",                          4, "تراجع السعر"),
    ("انهيار",             "crash",                         9, "ذعر في السوق"),
    ("تراجع حاد",          "sharp decline",                 7, "بيع قوي"),
    ("تراجع",              "decline",                       3, "اتجاه هابط"),
    ("يتراجع",             "declining",                     3, "اتجاه هابط"),
    ("متراجع",             "declining",                     3, "ضعف عام"),
    ("انخفاض",             "decrease",                      3, "ضغط سعري"),
    ("ينخفض",              "decreasing",                    3, "ضغط سعري"),
    ("تنخفض",              "decreasing",                    3, "ضغط سعري"),
    ("يتكبد",              "incurs",                        5, "تحمل خسائر"),
    ("تكبد",               "incurred",                      5, "تحمل خسائر"),
    ("ركود",               "recession",                     6, "تباطؤ اقتصادي"),
    ("أزمة",               "crisis",                        7, "مخاطر عالية"),
    ("ضغوط",               "pressure",                      4, "بيئة سلبية"),
    ("عجز",                "deficit",                       5, "ضعف مالي"),
    ("خسارة",              "loss",                          5, "أداء سلبي"),
    ("ضغط بيعي",           "selling pressure",              6, "هروب السيولة"),
    ("بيع مكثف",           "heavy selling",                 6, "هروب جماعي"),
    ("خفض التوصية",        "recommendation cut",            6, "فقدان ثقة المحللين"),
    ("أدنى مستوى",         "lowest level",                  5, "ضعف تاريخي"),
    ("تخفيض رأس المال",    "capital reduction",             8, "تآكل القيمة"),
    ("حرب",                "war",                           7, "مخاطر جيوسياسية"),
    ("صراع",               "conflict",                      6, "عدم استقرار"),
    ("عقوبات",             "sanctions",                     7, "مخاطر تجارية"),
    ("تصحيح",              "correction",                    4, "جني أرباح"),
    # --- English keywords ---
    ("downgrade",          "downgrade",                     6, "تراجع الثقة"),
    ("lawsuit",            "lawsuit",                       5, "مخاطر قانونية"),
    ("bankruptcy",         "bankruptcy",                    10, "إفلاس"),
    ("fraud",              "fraud",                         9, "احتيال"),
    ("loss",               "loss",                          4, "خسارة"),
    ("decline",            "decline",                       4, "تراجع"),
    ("suspend",            "suspend",                       6, "إيقاف"),
    ("default",            "default",                       8, "تعثر"),
    ("plunge",             "plunge",                        7, "انهيار"),
    ("crash",              "crash",                         8, "انهيار"),
    ("war",                "war",                           6, "حرب"),
]

# 🚀 Rocket keywords — send stocks flying
ROCKET_KEYWORDS = [
    ("توزيعات استثنائية",  "special dividend",              10, "تدفق شرائي هائل"),
    ("توزيعات نقدية",      "cash dividend",                 6, "جاذبية للمستثمرين"),
    ("توزيعات أرباح",      "profit distribution",           6, "عائد مباشر"),
    ("توزيع أرباح",        "distributes profit",            6, "عائد مباشر"),
    ("توزيعات",            "dividend",                      5, "عائد للمستثمرين"),
    ("عقد بمليارات",       "billion contract",              9, "تسعير فوري لنمو مستقبلي"),
    ("عقد بملايين",        "million contract",              7, "نمو الإيرادات"),
    ("فاز بعقد",           "won contract",                  7, "إيرادات جديدة"),
    ("ترسية",              "contract award",                7, "فوز بعقد"),
    ("رؤية 2030",          "vision 2030",                   8, "ارتباط بالدعم الحكومي"),
    ("مشروع نيوم",         "neom",                          8, "مشاريع ضخمة"),
    ("صفقة استراتيجية",    "strategic deal",                8, "توقعات بتوسع ونمو"),
    ("صفقة",               "deal",                          4, "اتفاقية تجارية"),
    ("أرباح قياسية",       "record profits",                9, "تأكيد القوة التشغيلية"),
    ("ارتفاع الأرباح",     "profit increase",               7, "نمو الربحية"),
    ("ارتفاع أرباح",       "profit increase",               7, "نمو الربحية"),
    ("نمو الأرباح",        "profit growth",                 7, "تحسن الأداء"),
    ("نمو أرباح",          "profit growth",                 7, "تحسن الأداء"),
    ("ترتفع",              "rises",                         4, "اتجاه صاعد"),
    ("يرتفع",              "rises",                         4, "اتجاه صاعد"),
    ("اندماج",             "merger",                        8, "علاوة سعرية فورية"),
    ("استحواذ",            "acquisition",                   8, "توسع وقيمة مضافة"),
    ("طرح عام",            "ipo",                           7, "اكتشاف قيمة خفية"),
    ("شراكة دولية",        "international partnership",     8, "انفتاح على أسواق جديدة"),
    ("شراكة",              "partnership",                   5, "تعاون استراتيجي"),
    ("تطوير أراضي",        "land development",              7, "إعادة تقييم الأصول"),
    ("نمو الإيرادات",      "revenue growth",                7, "رقم يكسر التوقعات"),
    ("نمو إيرادات",        "revenue growth",                7, "نمو الإيرادات"),
    ("فوق التوقعات",       "above expectations",            8, "مفاجأة إيجابية"),
    ("أعلى من التوقعات",   "beat expectations",             8, "تفوق على التوقعات"),
    ("نتائج قياسية",       "record results",                8, "أداء تاريخي"),
    ("إيرادات تاريخية",    "historic revenue",              8, "قوة تشغيلية استثنائية"),
    ("رفع التصنيف",        "upgrade",                       6, "ثقة مؤسسية"),
    ("سعر مستهدف",         "target price",                  5, "توقعات إيجابية"),
    ("رفع السعر المستهدف", "target price raise",            7, "ثقة المحللين"),
    ("توصي بشراء",         "buy recommendation",            7, "ثقة المحللين"),
    ("زيادة رأس المال",    "capital increase",              5, "توسع"),
    ("أسهم مجانية",        "bonus shares",                  6, "مكافأة للملاك"),
    ("منحة أسهم",          "stock grant",                   5, "مكافأة للملاك"),
    ("تصدير",              "export",                        5, "أسواق جديدة"),
    ("أعلى مستوى",         "highest level",                 5, "قوة السهم"),
    # --- Arabic market action keywords (common in news headlines) ---
    ("يقفز",               "jumps",                         6, "صعود مفاجئ"),
    ("تقفز",               "jumps",                         6, "صعود مفاجئ"),
    ("قفزة",               "leap",                          6, "ارتفاع حاد"),
    ("صعود",               "rise",                          4, "اتجاه صاعد"),
    ("يصعد",               "rising",                        4, "اتجاه صاعد"),
    ("مكاسب",              "gains",                         4, "أداء إيجابي"),
    ("ارتفاع",             "increase",                      3, "اتجاه صاعد"),
    ("انتعاش",             "recovery",                      5, "تعافي السوق"),
    ("تعافي",              "recovering",                    5, "عودة الثقة"),
    ("توسع",               "expansion",                     5, "نمو الأعمال"),
    ("إعادة شراء",         "buyback",                       6, "ثقة الإدارة"),
    ("تمويل",              "financing",                     4, "دعم مالي"),
    # --- English keywords ---
    ("record",             "record",                        6, "قياسي"),
    ("upgrade",            "upgrade",                       6, "رفع تصنيف"),
    ("acquisition",        "acquisition",                   7, "استحواذ"),
    ("merger",             "merger",                        7, "اندماج"),
    ("partnership",        "partnership",                   5, "شراكة"),
    ("growth",             "growth",                        4, "نمو"),
    ("profit",             "profit",                        4, "أرباح"),
    ("beat",               "beat expectations",             6, "تفوق"),
    ("dividend",           "dividend",                      5, "توزيعات"),
    ("rally",              "rally",                         5, "صعود قوي"),
    ("surge",              "surge",                         6, "ارتفاع حاد"),
]


def _neutral_sentiment():
    """Default neutral sentiment when no news or analysis fails."""
    return {
        "sentiment": "محايد",
        "confidence": 0,
        "summary_ar": "لا توجد أخبار",
        "headlines": [],
        "keyword_hits": [],
        "keyword_score": 0,
    }


def scan_tasi_keywords(headlines_text: str) -> dict:
    """
    Scan text for TASI killer/rocket keywords.

    Returns:
        {
            "hits": [(keyword, type, weight, effect), ...],
            "killer_hits": [...],
            "rocket_hits": [...],
            "net_score": int (-100 to +100),
            "verdict": "💣 خطر" | "🚀 إيجابي" | "⚖️ محايد",
            "killer_count": int,
            "rocket_count": int,
        }
    """
    if not headlines_text:
        return {
            "hits": [], "killer_hits": [], "rocket_hits": [],
            "net_score": 0, "verdict": "⚖️ محايد",
            "killer_count": 0, "rocket_count": 0,
        }

    text_lower = headlines_text.lower()
    killer_hits = []
    rocket_hits = []
    seen_keywords = set()

    # Scan for killer keywords (negative)
    for kw_ar, kw_en, weight, effect in KILLER_KEYWORDS:
        # Check Arabic keyword
        if kw_ar and kw_ar in headlines_text and kw_ar not in seen_keywords:
            killer_hits.append((kw_ar, "💣", weight, effect))
            seen_keywords.add(kw_ar)
        # Check English keyword
        if kw_en and kw_en.lower() in text_lower and kw_en not in seen_keywords:
            killer_hits.append((kw_en, "💣", weight, effect))
            seen_keywords.add(kw_en)

    # Scan for rocket keywords (positive)
    for kw_ar, kw_en, weight, effect in ROCKET_KEYWORDS:
        if kw_ar and kw_ar in headlines_text and kw_ar not in seen_keywords:
            rocket_hits.append((kw_ar, "🚀", weight, effect))
            seen_keywords.add(kw_ar)
        if kw_en and kw_en.lower() in text_lower and kw_en not in seen_keywords:
            rocket_hits.append((kw_en, "🚀", weight, effect))
            seen_keywords.add(kw_en)

    # Sort by weight (strongest hits first)
    killer_hits.sort(key=lambda x: x[2], reverse=True)
    rocket_hits.sort(key=lambda x: x[2], reverse=True)

    # Calculate net score
    # Rule: Fear hits 1.5x harder than greed (market psychology)
    killer_score = sum(w for _, _, w, _ in killer_hits) * 1.5
    rocket_score = sum(w for _, _, w, _ in rocket_hits)
    net_score = int(rocket_score - killer_score)
    net_score = max(-100, min(100, net_score))

    # Verdict
    if net_score <= -5:
        verdict = "💣 خطر"
    elif net_score >= 5:
        verdict = "🚀 إيجابي"
    else:
        verdict = "⚖️ محايد"

    all_hits = killer_hits + rocket_hits

    return {
        "hits": all_hits,
        "killer_hits": killer_hits,
        "rocket_hits": rocket_hits,
        "net_score": net_score,
        "verdict": verdict,
        "killer_count": len(killer_hits),
        "rocket_count": len(rocket_hits),
    }


def _fetch_yfinance_news(ticker, max_items=5):
    """Fetch latest news headlines from yfinance for a ticker."""
    try:
        tk = yf.Ticker(ticker)
        raw_news = tk.news
        if not raw_news:
            return []

        headlines = []
        for item in raw_news[:max_items]:
            title = item.get("title", "")
            if not title:
                continue
            headlines.append({
                "title": title,
                "publisher": item.get("publisher", ""),
                "link": item.get("link", ""),
                "time": item.get("providerPublishTime", 0),
            })
        return headlines
    except Exception:
        return []


def _get_stock_arabic_name(ticker):
    """Get Arabic name for a Saudi stock ticker."""
    try:
        from data.markets import SAUDI_NAMES
        return SAUDI_NAMES.get(ticker, "")
    except Exception:
        return ""


def _is_headline_relevant(title, ticker, stock_name):
    """
    Check if a news headline is actually about the target stock.
    Prevents showing news about 'المطاحن الحديثة' for 'السيف غاليري'.

    Strategy:
    1. Full stock name match → relevant
    2. Ticker number (e.g. "4192") in title → relevant
    3. Significant name parts (≥3 chars, non-stop) in title → relevant
    4. Otherwise → NOT relevant (discard)
    """
    if not title or not stock_name:
        return False

    # Normalize: remove extra whitespace
    title_clean = title.strip()
    name_clean = stock_name.strip()

    # 1. Full stock name in title
    if name_clean in title_clean:
        return True

    # 2. Ticker number in title (e.g., "4192" from "4192.SR")
    ticker_num = ticker.replace(".SR", "").replace(".sr", "")
    if ticker_num in title_clean:
        return True

    # 3. Partial name matching — check significant parts
    # Arabic stop words commonly found in stock names
    _stop = {
        "شركة", "مجموعة", "للتأمين", "السعودية", "العربية",
        "الوطنية", "المتحدة", "القابضة", "التجارية", "الصناعية",
        "ال", "و", "في", "من", "إلى", "على", "عن",
    }
    name_parts = name_clean.split()
    significant = [p for p in name_parts if len(p) > 2 and p not in _stop]

    # For short names like "الراجحي" or "السيف", the whole name IS the significant part
    if not significant and len(name_clean) > 2:
        significant = [name_clean]

    for part in significant:
        if part in title_clean:
            return True

    # 4. Also try without "ال" prefix (e.g. "السيف" → "سيف")
    for part in significant:
        if part.startswith("ال") and len(part) > 3:
            bare = part[2:]  # Remove "ال"
            if bare in title_clean:
                return True

    return False


def _fetch_google_news_rss(ticker, max_items=5, max_age_days=1):
    """
    Fetch recent Arabic news from Google News RSS for Saudi stocks.
    Free, no API key needed, returns Arabic headlines.
    Only returns news from the last max_age_days.
    Applies RELEVANCE FILTER: only headlines mentioning the stock name/ticker.
    """
    try:
        stock_name = _get_stock_arabic_name(ticker)
        ticker_num = ticker.replace(".SR", "")

        # Build queries — use 'when:Xd' for freshness
        when_tag = f"when:{max_age_days}d" if max_age_days <= 7 else ""
        queries = []
        if stock_name:
            queries.append(f'"{stock_name}" سهم {when_tag}'.strip())
            queries.append(f'"{stock_name}" تداول {when_tag}'.strip())
        queries.append(f"سهم {ticker_num} تداول {when_tag}".strip())

        all_headlines = []
        seen_titles = set()

        # Calculate cutoff timestamp
        from datetime import datetime, timezone, timedelta
        cutoff_ts = int((datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)).timestamp())

        for query in queries[:1]:  # Only 1 query for speed (was 2)
            encoded_q = urllib.request.quote(query)
            url = (
                f"https://news.google.com/rss/search?"
                f"q={encoded_q}&hl=ar&gl=SA&ceid=SA:ar"
            )

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MASAQuant/1.0)"},
            )
            try:
                with urllib.request.urlopen(req, timeout=4) as resp:
                    xml_data = resp.read()
            except Exception:
                continue

            root = ET.fromstring(xml_data)
            items = root.findall(".//item")

            for item in items[:max_items * 3]:  # Scan more to find relevant ones
                title_el = item.find("title")
                link_el = item.find("link")
                source_el = item.find("source")
                pub_date_el = item.find("pubDate")

                title = title_el.text if title_el is not None else ""
                if not title or title in seen_titles:
                    continue

                publisher = ""
                if source_el is not None and source_el.text:
                    publisher = source_el.text

                link = link_el.text if link_el is not None else ""
                pub_time = 0
                if pub_date_el is not None and pub_date_el.text:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date_el.text)
                        pub_time = int(dt.timestamp())
                    except Exception:
                        pass

                # Skip old news
                if pub_time > 0 and pub_time < cutoff_ts:
                    continue

                # ✅ RELEVANCE FILTER — only headlines about THIS stock
                if stock_name and not _is_headline_relevant(title, ticker, stock_name):
                    continue

                seen_titles.add(title)
                all_headlines.append({
                    "title": title,
                    "publisher": publisher,
                    "link": link,
                    "time": pub_time,
                })

                if len(all_headlines) >= max_items:
                    break

            if len(all_headlines) >= max_items:
                break

        # Sort by time (newest first), limit to max_items
        all_headlines.sort(key=lambda x: x.get("time", 0), reverse=True)
        return all_headlines[:max_items]

    except Exception:
        return []


def _fetch_news_combined(ticker, max_items=5, max_age_days=1):
    """
    Fetch RECENT news from multiple sources with PROGRESSIVE FALLBACK:
    1. yfinance (works for global stocks)
    2. Google News RSS (works for Saudi/Arabic stocks)

    For Saudi stocks: if no relevant news in 1 day → try 3 days → 7 days.
    Returns combined, deduplicated, RELEVANT headlines only.
    """
    from datetime import datetime, timezone, timedelta

    is_saudi = ticker.endswith(".SR")
    stock_name = _get_stock_arabic_name(ticker) if is_saudi else ""

    headlines = []
    seen_titles = set()

    # ── yfinance (fast for global tickers) ──
    cutoff_ts = int((datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)).timestamp())
    yf_headlines = _fetch_yfinance_news(ticker, max_items=max_items)
    for h in yf_headlines:
        t = h.get("title", "")
        ts = h.get("time", 0)
        if ts > 0 and ts < cutoff_ts:
            continue
        # Apply relevance filter for Saudi stocks
        if is_saudi and stock_name and not _is_headline_relevant(t, ticker, stock_name):
            continue
        if t and t not in seen_titles:
            headlines.append(h)
            seen_titles.add(t)

    # ── Google News RSS for Saudi stocks — PROGRESSIVE FALLBACK ──
    if is_saudi and len(headlines) < max_items:
        # Try progressively wider date ranges: 1d → 3d → 7d
        fallback_days = [max_age_days, 3, 7]
        # Remove duplicates and ensure ascending order
        fallback_days = sorted(set(fallback_days))

        for days in fallback_days:
            gn_headlines = _fetch_google_news_rss(
                ticker, max_items=max_items, max_age_days=days
            )
            for h in gn_headlines:
                t = h.get("title", "")
                if t and t not in seen_titles:
                    headlines.append(h)
                    seen_titles.add(t)

            # If we found relevant news, stop fallback
            if headlines:
                break

    # Sort by time (newest first) and limit
    headlines.sort(key=lambda x: x.get("time", 0), reverse=True)
    return headlines[:max_items]


def _analyze_with_gemini(headlines, ticker, api_key, keyword_context=""):
    """Send headlines to Gemini for sentiment analysis with keyword awareness."""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        titles_text = "\n".join(
            f"- {h['title']}" for h in headlines if h.get("title")
        )
        if not titles_text:
            return _neutral_sentiment()

        # Enhanced prompt with TASI keyword intelligence
        keyword_section = ""
        if keyword_context:
            keyword_section = (
                f"\n\n⚠️ تنبيه: الماسح الآلي اكتشف هذه الكلمات المؤثرة في العناوين:\n"
                f"{keyword_context}\n"
                "ضع هذه الكلمات في الاعتبار عند تحليلك — فهي محركات سعرية قوية في تاسي.\n"
            )

        prompt = (
            f"أنت محلل مالي محترف متخصص في السوق السعودي (تاسي). "
            f"حلل العناوين الإخبارية التالية للسهم ({ticker}).\n\n"
            f"العناوين:\n{titles_text}\n"
            f"{keyword_section}\n"
            "📌 قواعد التحليل:\n"
            "- الكلمات السلبية تضرب بقوة مضاعفة (الخوف أسرع من الطمع)\n"
            '- كلمات مثل "خسائر متراكمة" أو "إفلاس" أو "تحقيق رقابي" = سلبي 90+ ثقة\n'
            '- كلمات مثل "أرباح قياسية" أو "عقد بمليارات" أو "توزيعات استثنائية" = إيجابي 85+ ثقة\n'
            "- إذا وُجدت كلمات سلبية وإيجابية معاً، السلبي يغلب\n\n"
            "المطلوب: حلل التأثير على سعر السهم وأعطني:\n"
            '1. sentiment: "إيجابي" أو "سلبي" أو "محايد"\n'
            "2. confidence: رقم من 0 إلى 100 (مدى ثقتك بالتحليل)\n"
            "3. summary_ar: ملخص عربي في سطر واحد فقط\n"
            "4. detected_keywords: قائمة بأهم الكلمات المؤثرة التي وجدتها (عربي)\n\n"
            'أجب بـ JSON فقط بدون أي نص إضافي:\n'
            '{"sentiment": "...", "confidence": ..., "summary_ar": "...", '
            '"detected_keywords": ["...", "..."]}'
        )

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=300,
            ),
            request_options={"timeout": 15},
        )

        text = response.text.strip()
        # Clean potential markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()

        result = json.loads(text)

        # Validate fields
        sentiment = result.get("sentiment", "محايد")
        if sentiment not in ("إيجابي", "سلبي", "محايد"):
            sentiment = "محايد"

        confidence = int(result.get("confidence", 0))
        confidence = max(0, min(100, confidence))

        summary_ar = str(result.get("summary_ar", "لا يوجد ملخص"))
        gemini_keywords = result.get("detected_keywords", [])

        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "summary_ar": summary_ar,
            "gemini_keywords": gemini_keywords,
        }

    except Exception:
        return _neutral_sentiment()


def get_news_sentiment(ticker, api_key):
    """
    Full pipeline: fetch news → scan keywords → analyze with Gemini → return result.
    Returns dict with sentiment, confidence, summary_ar, headlines, keyword_hits, keyword_score.
    """
    try:
        headlines = _fetch_news_combined(ticker, max_items=5)
        if not headlines:
            result = _neutral_sentiment()
            return result

        # Step 1: Scan headlines for TASI keywords
        all_titles = " ".join(h.get("title", "") for h in headlines)
        kw_result = scan_tasi_keywords(all_titles)

        # Step 2: Build keyword context for Gemini
        keyword_context = ""
        if kw_result["hits"]:
            kw_lines = []
            for kw, ktype, weight, effect in kw_result["hits"][:5]:
                kw_lines.append(f"  {ktype} \"{kw}\" (وزن: {weight}/10) → {effect}")
            keyword_context = "\n".join(kw_lines)

        # Step 3: Analyze with Gemini (enhanced prompt)
        if api_key:
            analysis = _analyze_with_gemini(headlines, ticker, api_key, keyword_context)
        else:
            analysis = _neutral_sentiment()

        # Step 4: Merge results
        analysis["headlines"] = headlines
        analysis["keyword_hits"] = kw_result["hits"]
        analysis["keyword_score"] = kw_result["net_score"]
        analysis["keyword_verdict"] = kw_result["verdict"]
        analysis["killer_count"] = kw_result["killer_count"]
        analysis["rocket_count"] = kw_result["rocket_count"]
        analysis["killer_hits"] = kw_result["killer_hits"]
        analysis["rocket_hits"] = kw_result["rocket_hits"]

        return analysis

    except Exception:
        return _neutral_sentiment()


def _keyword_only_analysis(ticker):
    """Fetch news + scan keywords locally (no Gemini needed).
    Uses FAST batch mode: single 7-day search, no progressive fallback."""
    # ── FAST batch mode: one query, 7 days, relevance filter ──
    if ticker.endswith(".SR"):
        headlines = _fetch_google_news_rss(ticker, max_items=3, max_age_days=7)
    else:
        headlines = _fetch_news_combined(ticker, max_items=3, max_age_days=7)
    if not headlines:
        result = _neutral_sentiment()
        result["summary_ar"] = "لا توجد أخبار خاصة بالسهم"
        return ticker, result

    all_titles = " ".join(h.get("title", "") for h in headlines)
    kw_result = scan_tasi_keywords(all_titles)

    result = _neutral_sentiment()
    result["headlines"] = headlines
    result["keyword_hits"] = kw_result["hits"]
    result["keyword_score"] = kw_result["net_score"]
    result["keyword_verdict"] = kw_result["verdict"]
    result["killer_count"] = kw_result["killer_count"]
    result["rocket_count"] = kw_result["rocket_count"]
    result["killer_hits"] = kw_result["killer_hits"]
    result["rocket_hits"] = kw_result["rocket_hits"]

    # Set confidence based on keyword strength (local analysis)
    if kw_result["net_score"] != 0:
        strength = min(abs(kw_result["net_score"]), 30)
        result["confidence"] = int(20 + strength * 2)  # 20-80%
        result["summary_ar"] = (
            f"تحليل محلي: {kw_result['killer_count']} كلمة سلبية, "
            f"{kw_result['rocket_count']} كلمة إيجابية"
        )
        if kw_result["net_score"] <= -5:
            result["sentiment"] = "سلبي"
        elif kw_result["net_score"] >= 5:
            result["sentiment"] = "إيجابي"
    else:
        # Headlines found but no keyword hits
        result["summary_ar"] = f"أخبار محايدة ({len(headlines)} عنوان)"

    return ticker, result


def batch_news_analysis(tickers, api_key, max_calls=12):
    """
    Analyze news for multiple tickers with rate limiting.
    Phase 1: Parallel keyword scanning (all tickers, no API key needed)
    Phase 2: Sequential Gemini analysis (top tickers only, needs API key)
    Returns dict[ticker -> sentiment_result]
    """
    if not tickers:
        return {}

    results = {}

    # Phase 1: Parallel news fetching + keyword scanning (no API key needed)
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {
            executor.submit(_keyword_only_analysis, tk): tk
            for tk in tickers
        }
        for future in as_completed(futures):
            try:
                tk, result = future.result()
                results[tk] = result
            except Exception:
                results[futures[future]] = _neutral_sentiment()

    # Phase 2: Gemini deep analysis for tickers with keyword hits (needs API key)
    if api_key:
        # Prioritize tickers with keyword hits or headlines
        priority_tickers = [
            tk for tk in tickers
            if results.get(tk, {}).get("keyword_score", 0) != 0
            or results.get(tk, {}).get("headlines")
        ]
        # Limit Gemini calls
        calls_made = 0
        for ticker in priority_tickers:
            if calls_made >= max_calls:
                break
            try:
                existing = results.get(ticker, {})
                headlines = existing.get("headlines", [])
                if not headlines:
                    continue

                # Build keyword context
                keyword_context = ""
                kw_hits = existing.get("keyword_hits", [])
                if kw_hits:
                    kw_lines = [
                        f"  {ktype} \"{kw}\" (وزن: {w}/10) → {eff}"
                        for kw, ktype, w, eff in kw_hits[:5]
                    ]
                    keyword_context = "\n".join(kw_lines)

                analysis = _analyze_with_gemini(
                    headlines, ticker, api_key, keyword_context
                )

                # Merge Gemini analysis with existing keyword data
                if analysis.get("sentiment") != "محايد" or analysis.get("confidence", 0) > 0:
                    existing["sentiment"] = analysis.get("sentiment", existing.get("sentiment", "محايد"))
                    existing["confidence"] = analysis.get("confidence", existing.get("confidence", 0))
                    existing["summary_ar"] = analysis.get("summary_ar", existing.get("summary_ar", ""))
                    results[ticker] = existing

                calls_made += 1
                if calls_made < max_calls:
                    time.sleep(1)  # 1s delay (was 3s)
            except Exception:
                pass

    return results


def calculate_news_adjustment(sentiment_result, sector=""):
    """
    Convert Gemini sentiment + keyword scan to a score adjustment.

    Normal range: -15 to +10
    Critical event range (keyword weight >= 9): -20 to +15

    Calculation:
    1. Base: Gemini sentiment × confidence → -10 to +10
    2. Keyword amplifier: killer/rocket hits boost the effect
    3. Sector boost: sector-specific keywords get ×1.3-1.5 multiplier
    4. Critical override: weight >= 9 keywords widen the range
    5. Fear multiplier: negative keywords hit 1.5x harder

    Returns int adjustment to apply to AI Score.
    """
    if not sentiment_result:
        return 0

    sentiment = sentiment_result.get("sentiment", "محايد")
    confidence = sentiment_result.get("confidence", 0)
    kw_score = sentiment_result.get("keyword_score", 0)

    # Check for critical keywords (weight >= 9)
    has_critical = False
    max_killer_weight = 0
    max_rocket_weight = 0
    killer_hits = sentiment_result.get("killer_hits", [])
    rocket_hits = sentiment_result.get("rocket_hits", [])

    for _, _, weight, _ in killer_hits:
        max_killer_weight = max(max_killer_weight, weight)
        if weight >= 9:
            has_critical = True

    for _, _, weight, _ in rocket_hits:
        max_rocket_weight = max(max_rocket_weight, weight)
        if weight >= 9:
            has_critical = True

    # Base adjustment from Gemini
    if sentiment == "إيجابي":
        base_adj = int(min(10, confidence / 10))
    elif sentiment == "سلبي":
        base_adj = -int(min(10, confidence / 10))
    else:
        base_adj = 0

    # Keyword amplifier
    kw_adj = 0
    if kw_score <= -10:
        kw_adj = -5
    elif kw_score <= -5:
        kw_adj = -3
    elif kw_score >= 10:
        kw_adj = 3
    elif kw_score >= 5:
        kw_adj = 2

    # Sector-specific keyword boost
    if sector:
        from data.markets import SECTOR_KEYWORD_BOOST
        sector_multiplier = 1.0
        all_hits = killer_hits + rocket_hits
        for kw_text, _, _, _ in all_hits:
            kw_lower = kw_text.lower() if kw_text else ""
            for boost_key, boost_sectors in SECTOR_KEYWORD_BOOST.items():
                if boost_key in kw_text or boost_key.lower() in kw_lower:
                    if sector in boost_sectors:
                        sector_multiplier = max(sector_multiplier, boost_sectors[sector])
        if sector_multiplier > 1.0:
            kw_adj = int(kw_adj * sector_multiplier)

    # Combined adjustment
    total = base_adj + kw_adj

    # Clamp based on critical event presence
    if has_critical:
        # Critical events: wider range -20 to +15
        total = max(-20, min(15, total))
    else:
        # Normal: -15 to +10
        total = max(-15, min(10, total))

    return total
