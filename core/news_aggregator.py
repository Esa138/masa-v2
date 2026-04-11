"""
MASA QUANT — Saudi Market News Aggregator
Fetches news from Argaam RSS + Saudi Exchange, summarizes with Gemini.

Sources:
  1. Argaam RSS (breaking, market pulse, main news)
  2. Saudi Exchange (issuer announcements)

No database — in-memory cache per session.
"""

import requests
import xml.etree.ElementTree as ET
import re
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# ── Argaam RSS feeds ──────────────────────────────────────
ARGAAM_FEEDS = {
    "عاجل": "https://www.argaam.com/ar/rss/breaking-news?sectionid=1585",
    "نبض السوق": "https://www.argaam.com/ar/rss/ho-market-pulse?sectionid=70",
    "الأخبار الرئيسية": "https://www.argaam.com/ar/rss/ho-main-news?sectionid=1523",
    "الشركات": "https://www.argaam.com/ar/rss/companies?sectionid=1543",
    "المحللون": "https://www.argaam.com/ar/rss/analysts?sectionid=1545",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _parse_rss(xml_bytes: bytes) -> list:
    """Parse RSS 2.0 feed and return list of items."""
    try:
        root = ET.fromstring(xml_bytes)
        items = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            description = (item.findtext("description") or "").strip()
            # Clean HTML tags from description
            description = re.sub(r"<[^>]+>", "", description)
            description = re.sub(r"\s+", " ", description).strip()

            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "pub_date": pub_date,
                    "description": description[:300],
                })
        return items
    except Exception:
        return []


def fetch_argaam_feed(feed_url: str, limit: int = 15) -> list:
    """Fetch a single Argaam RSS feed."""
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        items = _parse_rss(resp.content)
        return items[:limit]
    except Exception:
        return []


def fetch_all_argaam_news(limit_per_feed: int = 10) -> dict:
    """
    Fetch all Argaam feeds in parallel.
    Returns dict: {category_name: [items]}
    """
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_argaam_feed, url, limit_per_feed): name
            for name, url in ARGAAM_FEEDS.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                items = future.result()
                if items:
                    results[name] = items
            except Exception:
                pass
    return results


def fetch_tadawul_news(limit: int = 20) -> list:
    """
    Fetch Saudi Exchange issuer announcements.
    Best-effort HTML scrape.
    """
    try:
        url = "https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/issuer-news?locale=ar"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return []
        # Saudi Exchange renders news dynamically — extract any visible news links
        from html.parser import HTMLParser

        items = []
        pattern = re.compile(r"newsDetails[^\"']*[\"']([^\"']+)", re.IGNORECASE)
        # Simple title extraction from anchor text near "news" keywords
        text = resp.text
        # Fallback: look for JSON-like news data in the page
        json_matches = re.findall(
            r'"title"\s*:\s*"([^"]{20,200})".*?"pubDate"\s*:\s*"([^"]*)"',
            text,
        )
        for title, pub in json_matches[:limit]:
            items.append({
                "title": title,
                "link": url,
                "pub_date": pub,
                "description": "",
            })
        return items
    except Exception:
        return []


def get_all_market_news(limit_per_source: int = 10) -> dict:
    """
    Unified news fetch from all sources.
    Returns:
      {
        "argaam": {category: [items]},
        "tadawul": [items],
        "fetched_at": str
      }
    """
    argaam = fetch_all_argaam_news(limit_per_feed=limit_per_source)
    tadawul = fetch_tadawul_news(limit=limit_per_source)
    return {
        "argaam": argaam,
        "tadawul": tadawul,
        "fetched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def flatten_news_for_summary(news_data: dict, max_items: int = 40) -> list:
    """Flatten all news sources into a single list for Gemini."""
    flat = []
    for category, items in news_data.get("argaam", {}).items():
        for it in items:
            flat.append({
                "source": f"أرقام/{category}",
                "title": it["title"],
                "date": it.get("pub_date", "")[:16],
                "desc": it.get("description", ""),
            })
    for it in news_data.get("tadawul", []):
        flat.append({
            "source": "تداول",
            "title": it["title"],
            "date": it.get("pub_date", "")[:16],
            "desc": it.get("description", ""),
        })
    return flat[:max_items]


# ══════════════════════════════════════════════════════════
# AI Summarization (uses Gemini via core.ai_reports)
# ══════════════════════════════════════════════════════════

NEWS_SYSTEM_PROMPT = """أنت محلل مالي سعودي خبير — مستوى hedge fund analyst.
تكتب بالعربية الفصحى (لهجة مهنية سعودية).
مهمتك: تلخيص أخبار السوق السعودي وربطها بإشارات منصة MASA (Order Flow).

## قواعد صارمة:
1. **لا تخترع أخبار** — حلل فقط الأخبار المعطاة لك.
2. **لا تعطي نصائح استثمارية مباشرة** — حلل فقط.
3. **كن دقيقاً في الأسماء** — استخدم أسماء الشركات كما وردت.
4. **ركز على التأثير** — إيجابي/سلبي/محايد + القطاع المتأثر.
5. **اربط مع Order Flow** إذا توفرت بيانات المنصة.
"""


def build_news_summary_prompt(
    news_items: list,
    masa_context: dict = None,
) -> str:
    """Build the user prompt for Gemini news summarization."""
    news_text = "\n".join([
        f"- [{n['source']} | {n['date']}] {n['title']}"
        for n in news_items
    ])

    masa_section = ""
    if masa_context:
        masa_section = f"""

## بيانات منصة MASA الحالية (Order Flow):
- عدد الإشارات الذهبية: {masa_context.get('golden_count', 0)}
- نسبة نجاح المنصة (20 يوم): {masa_context.get('win_rate', 'غير متوفر')}
- أفضل القطاعات حالياً: {', '.join(masa_context.get('top_sectors', []))}
- أسوأ القطاعات حالياً: {', '.join(masa_context.get('weak_sectors', []))}
"""

    return f"""حلّل هذه الأخبار من السوق السعودي ولخّصها:

{news_text}
{masa_section}

## المطلوب بالضبط:

### 📊 ملخص اليوم (3 أسطر فقط)
ركّز على أهم 3 أحداث تأثيراً.

### 🎯 أهم الأخبار المؤثرة (حتى 5)
لكل خبر:
- **العنوان المختصر**
- **القطاع المتأثر**
- **الأسهم المتأثرة** (إن وُجدت بالاسم)
- **التأثير**: 🟢 إيجابي | 🔴 سلبي | ⚪ محايد
- **الأهمية**: عالية/متوسطة/منخفضة

### 🏭 تأثير القطاعات
جدول قصير: كل قطاع → حكم (إيجابي/سلبي/محايد) + سبب مختصر.

### 🔗 ربط مع MASA (إذا توفرت بيانات)
هل الأخبار تدعم إشارات المنصة أم تتناقض معها؟ مثال:
- "البنوك في Order Flow +36 وفيه إشارة ذهبية للإنماء — يتوافق مع نتائج Q1 القوية ✅"
- "الطاقة سلبية في MASA لكن أرامكو ثبّتت التوزيعات — تناقض، انتظر"

### ⚠️ تنبيهات (اختياري)
أي خبر يتطلب حذر فوري.

لا تتجاوز 600 كلمة. استخدم Markdown."""


def summarize_news_with_gemini(
    news_data: dict,
    masa_context: dict = None,
) -> str:
    """Summarize news using Gemini via ai_reports._call_sonnet."""
    items = flatten_news_for_summary(news_data, max_items=30)
    if not items:
        return "لا توجد أخبار متوفرة حالياً."

    from core.ai_reports import _call_sonnet
    prompt = build_news_summary_prompt(items, masa_context)
    return _call_sonnet(NEWS_SYSTEM_PROMPT, prompt, max_tokens=3000)
