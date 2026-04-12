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
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# ── Argaam RSS feeds — only fresh/active feeds ──────────────
ARGAAM_FEEDS = {
    "الأخبار الرئيسية": "https://www.argaam.com/ar/rss/ho-main-news?sectionid=1523",
    "نبض السوق": "https://www.argaam.com/ar/rss/ho-market-pulse?sectionid=70",
}

# ── Saudi relevance keywords (filter out international noise) ──
SAUDI_KEYWORDS = [
    "تاسي", "تداول", "السعودي", "السعودية", "سابك", "أرامكو", "الراجحي",
    "الإنماء", "الأهلي", "بنك", "أسمنت", "اتصالات", "stc", "زين",
    "أرباح", "توزيعات", "نتائج", "ربع", "سهم", "أسهم", "مؤشر",
    "ريال", "هيئة السوق", "ساما", "نمو", "طرح", "اكتتاب",
    "قطاع", "شركة", "المالية", "الاستثمار", "صندوق", "عقاري",
    "تأمين", "بتروكيم", "طاقة", "نفط", "معادن", "ذهب",
    "موبايلي", "تبوك", "مكة", "المدينة", "الرياض", "جدة",
    "دار الأركان", "جرير", "المراعي", "ملكية", "أجنبي",
    "تجميع", "تصريف", "اختراق", "دعم", "مقاومة",
]

# News validity window — drop anything older than this
FRESHNESS_HOURS = 24

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _parse_pub_date(pub_str: str):
    """Parse RSS pubDate (RFC 822) to datetime. Returns None on failure."""
    if not pub_str:
        return None
    try:
        dt = parsedate_to_datetime(pub_str)
        # Normalize to naive UTC for comparison
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _is_fresh(pub_str: str, hours: int = FRESHNESS_HOURS) -> bool:
    """Check if pub_date is within the last N hours."""
    dt = _parse_pub_date(pub_str)
    if dt is None:
        return False
    now_utc = datetime.datetime.utcnow()
    age = now_utc - dt
    return age <= datetime.timedelta(hours=hours)


def _parse_rss(xml_bytes: bytes, only_fresh: bool = True) -> list:
    """Parse RSS 2.0 feed and return list of items, optionally filtered by freshness."""
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

            if not title:
                continue
            # Drop stale items (older than FRESHNESS_HOURS)
            if only_fresh and not _is_fresh(pub_date):
                continue

            items.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "description": description[:300],
                "_parsed_date": _parse_pub_date(pub_date),
            })
        # Sort newest first, then drop internal key
        items.sort(key=lambda x: x.get("_parsed_date") or datetime.datetime.min, reverse=True)
        for it in items:
            it.pop("_parsed_date", None)
        return items
    except Exception:
        return []


def fetch_argaam_feed(feed_url: str, limit: int = 15) -> list:
    """Fetch a single Argaam RSS feed (fresh items only)."""
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        items = _parse_rss(resp.content, only_fresh=True)
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


def _is_saudi_relevant(title: str, desc: str = "") -> bool:
    """Check if a news item is relevant to Saudi market/stocks."""
    text = f"{title} {desc}".lower()
    return any(kw in text for kw in SAUDI_KEYWORDS)


def fetch_maaal_news(limit: int = 15) -> list:
    """Scrape recent articles from Maaal.com — Saudi-focused financial news."""
    try:
        resp = requests.get("https://maaal.com/", headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'html.parser')
        seen = set()
        items = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            if len(text) < 25 or text in seen:
                continue
            if 'maaal.com' not in href and not href.startswith('/'):
                continue
            # Only keep Saudi-relevant
            if not _is_saudi_relevant(text):
                continue
            seen.add(text)
            link = href if href.startswith('http') else f"https://maaal.com{href}"
            items.append({
                "title": text[:150],
                "link": link,
                "pub_date": "",
                "description": "",
            })
        return items[:limit]
    except Exception:
        return []


def fetch_argaam_page_news(limit: int = 15) -> list:
    """Scrape Argaam main page for Saudi-relevant articles."""
    try:
        resp = requests.get("https://www.argaam.com/ar", headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, 'html.parser')
        seen = set()
        items = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a['href']
            if len(text) < 20 or '/ar/article/' not in href or text in seen:
                continue
            if not _is_saudi_relevant(text):
                continue
            seen.add(text)
            link = f"https://www.argaam.com{href}" if href.startswith('/') else href
            items.append({
                "title": text[:150],
                "link": link,
                "pub_date": "",
                "description": "",
            })
        return items[:limit]
    except Exception:
        return []


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
    Unified news fetch from all sources (Saudi-focused).
    Returns:
      {
        "argaam": {category: [items]},
        "argaam_page": [items],
        "maaal": [items],
        "fetched_at": str
      }
    """
    argaam_rss = fetch_all_argaam_news(limit_per_feed=limit_per_source)
    argaam_page = fetch_argaam_page_news(limit=limit_per_source)
    maaal = fetch_maaal_news(limit=limit_per_source)

    # Filter RSS results for Saudi relevance too
    for cat in list(argaam_rss.keys()):
        argaam_rss[cat] = [
            it for it in argaam_rss[cat]
            if _is_saudi_relevant(it.get("title", ""), it.get("description", ""))
        ]
        if not argaam_rss[cat]:
            del argaam_rss[cat]

    return {
        "argaam": argaam_rss,
        "argaam_page": argaam_page,
        "maaal": maaal,
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
    for it in news_data.get("argaam_page", []):
        flat.append({
            "source": "أرقام/الموقع",
            "title": it["title"],
            "date": "",
            "desc": "",
        })
    for it in news_data.get("maaal", []):
        flat.append({
            "source": "مال",
            "title": it["title"],
            "date": "",
            "desc": "",
        })
    # Deduplicate by title similarity
    seen = set()
    unique = []
    for it in flat:
        key = it["title"][:40]
        if key not in seen:
            seen.add(key)
            unique.append(it)
    return unique[:max_items]


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
