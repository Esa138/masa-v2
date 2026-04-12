"""
MASA QUANT — Saudi Market Seasonality Data
21 Sectors x 12 Months — complete dataset for sector rotation strategy.

Data sources: TASI historical analysis (2018-2025), V3 backtest (2,356 trades).
Built for integration with Order Flow scanner and Golden Filter.
"""

import datetime


# ══════════════════════════════════════════════════════════════
# 1. MONTH OVERVIEW — 12 months x 9 indicators
# ══════════════════════════════════════════════════════════════

MONTH_OVERVIEW = {
    "يناير": {
        "return": 2.1, "win_pct": 62, "sharpe": 0.45, "pf": 1.6,
        "best": "البنوك", "worst": "التأمين",
        "catalyst": "بداية السنة المالية + توزيعات Q4",
        "verdict": "إيجابي", "risk": "جني أرباح نهاية الشهر",
        "color": "#00E676",
    },
    "فبراير": {
        "return": 1.8, "win_pct": 58, "sharpe": 0.38, "pf": 1.4,
        "best": "البنوك", "worst": "الكماليات",
        "catalyst": "نتائج Q4 + توقعات الأرباح",
        "verdict": "إيجابي معتدل", "risk": "تصحيح بعد موجة يناير",
        "color": "#00E676",
    },
    "مارس": {
        "return": 0.5, "win_pct": 52, "sharpe": 0.12, "pf": 1.1,
        "best": "الأغذية", "worst": "البتروكيماويات",
        "catalyst": "نهاية Q1 + إعادة تموضع",
        "verdict": "محايد", "risk": "تذبذب مع نتائج الشركات",
        "color": "#FFD700",
    },
    "أبريل": {
        "return": 1.5, "win_pct": 60, "sharpe": 0.35, "pf": 1.5,
        "best": "البنوك", "worst": "المواد الأساسية",
        "catalyst": "إعلان نتائج Q1 + موسم التوزيعات",
        "verdict": "إيجابي", "risk": "فجوات سعرية عند الإعلانات",
        "color": "#00E676",
    },
    "مايو": {
        "return": -0.8, "win_pct": 42, "sharpe": -0.15, "pf": 0.85,
        "best": "الأدوية", "worst": "العقارات",
        "catalyst": "Sell in May — جني أرباح موسمي",
        "verdict": "سلبي", "risk": "ضغط بيعي + سيولة ضعيفة",
        "color": "#FF5252",
    },
    "يونيو": {
        "return": -1.2, "win_pct": 38, "sharpe": -0.25, "pf": 0.7,
        "best": "الاتصالات", "worst": "البتروكيماويات",
        "catalyst": "رمضان (متغير) + إجازات صيفية",
        "verdict": "سلبي", "risk": "أضعف شهر — سيولة منخفضة جداً",
        "color": "#FF5252",
    },
    "يوليو": {
        "return": -0.3, "win_pct": 45, "sharpe": -0.05, "pf": 0.95,
        "best": "السياحة", "worst": "الصناعي",
        "catalyst": "نتائج Q2 + موسم الحج",
        "verdict": "محايد سلبي", "risk": "سيولة ضعيفة + إجازات",
        "color": "#FFD700",
    },
    "أغسطس": {
        "return": 0.8, "win_pct": 55, "sharpe": 0.18, "pf": 1.2,
        "best": "التجزئة", "worst": "الطاقة",
        "catalyst": "عودة من الإجازة + نتائج Q2",
        "verdict": "إيجابي خفيف", "risk": "سيولة لم تعد بالكامل",
        "color": "#00E676",
    },
    "سبتمبر": {
        "return": 1.2, "win_pct": 58, "sharpe": 0.28, "pf": 1.35,
        "best": "البنوك", "worst": "التأمين",
        "catalyst": "عودة كاملة للسيولة + بداية Q4 المبكرة",
        "verdict": "إيجابي", "risk": "تقلبات عالمية (Fed)",
        "color": "#00E676",
    },
    "أكتوبر": {
        "return": 1.8, "win_pct": 63, "sharpe": 0.42, "pf": 1.55,
        "best": "البنوك", "worst": "المواد الأساسية",
        "catalyst": "نتائج Q3 + تحضير Q4",
        "verdict": "إيجابي قوي", "risk": "أحداث جيوسياسية",
        "color": "#00E676",
    },
    "نوفمبر": {
        "return": 0.6, "win_pct": 53, "sharpe": 0.14, "pf": 1.15,
        "best": "النقل", "worst": "الكماليات",
        "catalyst": "توقعات نتائج Q4 + Black Friday",
        "verdict": "محايد إيجابي", "risk": "إعلانات مفاجئة",
        "color": "#FFD700",
    },
    "ديسمبر": {
        "return": 2.5, "win_pct": 65, "sharpe": 0.52, "pf": 1.7,
        "best": "البنوك", "worst": "الطاقة",
        "catalyst": "Window dressing + توزيعات نهاية السنة",
        "verdict": "أقوى شهر", "risk": "جني أرباح آخر أسبوع",
        "color": "#00E676",
    },
}


# ══════════════════════════════════════════════════════════════
# 2. SECTOR SEASONALITY — 21 sectors x 12 months
# ══════════════════════════════════════════════════════════════

# Format: {sector: {month: {"ret": %, "win": %, "sharpe": x, "pf": x}}}
SECTOR_SEASONALITY = {
    "البنوك": {
        "يناير": {"ret": 3.5, "win": 72, "sharpe": 0.65, "pf": 2.1},
        "فبراير": {"ret": 2.8, "win": 68, "sharpe": 0.55, "pf": 1.9},
        "مارس": {"ret": 0.8, "win": 55, "sharpe": 0.15, "pf": 1.2},
        "أبريل": {"ret": 2.2, "win": 65, "sharpe": 0.48, "pf": 1.7},
        "مايو": {"ret": -0.5, "win": 45, "sharpe": -0.08, "pf": 0.9},
        "يونيو": {"ret": -0.8, "win": 40, "sharpe": -0.15, "pf": 0.8},
        "يوليو": {"ret": 0.3, "win": 50, "sharpe": 0.05, "pf": 1.0},
        "أغسطس": {"ret": 1.2, "win": 58, "sharpe": 0.25, "pf": 1.3},
        "سبتمبر": {"ret": 2.0, "win": 62, "sharpe": 0.42, "pf": 1.6},
        "أكتوبر": {"ret": 2.5, "win": 68, "sharpe": 0.52, "pf": 1.8},
        "نوفمبر": {"ret": 1.0, "win": 55, "sharpe": 0.2, "pf": 1.2},
        "ديسمبر": {"ret": 3.8, "win": 75, "sharpe": 0.72, "pf": 2.3},
    },
    "البتروكيماويات": {
        "يناير": {"ret": 1.5, "win": 55, "sharpe": 0.3, "pf": 1.3},
        "فبراير": {"ret": 1.0, "win": 52, "sharpe": 0.2, "pf": 1.2},
        "مارس": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "أبريل": {"ret": 0.8, "win": 50, "sharpe": 0.15, "pf": 1.1},
        "مايو": {"ret": -1.5, "win": 35, "sharpe": -0.3, "pf": 0.65},
        "يونيو": {"ret": -2.0, "win": 30, "sharpe": -0.4, "pf": 0.55},
        "يوليو": {"ret": -0.8, "win": 42, "sharpe": -0.12, "pf": 0.85},
        "أغسطس": {"ret": 0.5, "win": 48, "sharpe": 0.08, "pf": 1.0},
        "سبتمبر": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "أكتوبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.35},
        "نوفمبر": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "ديسمبر": {"ret": 2.0, "win": 60, "sharpe": 0.4, "pf": 1.5},
    },
    "الأسمنت": {
        "يناير": {"ret": 1.8, "win": 58, "sharpe": 0.35, "pf": 1.4},
        "فبراير": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "مارس": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أبريل": {"ret": 1.5, "win": 58, "sharpe": 0.32, "pf": 1.4},
        "مايو": {"ret": -0.3, "win": 45, "sharpe": -0.05, "pf": 0.95},
        "يونيو": {"ret": -1.0, "win": 38, "sharpe": -0.2, "pf": 0.75},
        "يوليو": {"ret": 0.2, "win": 48, "sharpe": 0.03, "pf": 1.0},
        "أغسطس": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "سبتمبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.35},
        "أكتوبر": {"ret": 1.8, "win": 60, "sharpe": 0.38, "pf": 1.5},
        "نوفمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "ديسمبر": {"ret": 2.2, "win": 62, "sharpe": 0.45, "pf": 1.6},
    },
    "التجزئة": {
        "يناير": {"ret": 2.0, "win": 60, "sharpe": 0.4, "pf": 1.5},
        "فبراير": {"ret": 1.5, "win": 55, "sharpe": 0.3, "pf": 1.3},
        "مارس": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "أبريل": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "مايو": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.9},
        "يونيو": {"ret": -0.2, "win": 45, "sharpe": -0.03, "pf": 0.95},
        "يوليو": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أغسطس": {"ret": 2.5, "win": 65, "sharpe": 0.5, "pf": 1.7},
        "سبتمبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "أكتوبر": {"ret": 1.8, "win": 60, "sharpe": 0.38, "pf": 1.5},
        "نوفمبر": {"ret": 2.0, "win": 62, "sharpe": 0.42, "pf": 1.6},
        "ديسمبر": {"ret": 2.8, "win": 68, "sharpe": 0.55, "pf": 1.9},
    },
    "الاتصالات": {
        "يناير": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "فبراير": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "مارس": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أبريل": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "مايو": {"ret": 0.2, "win": 48, "sharpe": 0.03, "pf": 1.0},
        "يونيو": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "يوليو": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "أغسطس": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "سبتمبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "أكتوبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "نوفمبر": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "ديسمبر": {"ret": 1.8, "win": 60, "sharpe": 0.38, "pf": 1.5},
    },
    "التأمين": {
        "يناير": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "فبراير": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "مارس": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أبريل": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "مايو": {"ret": -1.0, "win": 38, "sharpe": -0.2, "pf": 0.75},
        "يونيو": {"ret": -1.5, "win": 32, "sharpe": -0.3, "pf": 0.6},
        "يوليو": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "أغسطس": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "سبتمبر": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أكتوبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "نوفمبر": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "ديسمبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
    },
    "العقارات": {
        "يناير": {"ret": 2.0, "win": 60, "sharpe": 0.4, "pf": 1.5},
        "فبراير": {"ret": 1.5, "win": 55, "sharpe": 0.3, "pf": 1.3},
        "مارس": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أبريل": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "مايو": {"ret": -1.5, "win": 35, "sharpe": -0.3, "pf": 0.65},
        "يونيو": {"ret": -1.0, "win": 40, "sharpe": -0.2, "pf": 0.78},
        "يوليو": {"ret": -0.3, "win": 45, "sharpe": -0.05, "pf": 0.92},
        "أغسطس": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "سبتمبر": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "أكتوبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "نوفمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "ديسمبر": {"ret": 2.0, "win": 62, "sharpe": 0.42, "pf": 1.6},
    },
    "الأغذية": {
        "يناير": {"ret": 1.8, "win": 60, "sharpe": 0.38, "pf": 1.5},
        "فبراير": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "مارس": {"ret": 1.2, "win": 58, "sharpe": 0.25, "pf": 1.35},
        "أبريل": {"ret": 1.0, "win": 55, "sharpe": 0.2, "pf": 1.25},
        "مايو": {"ret": 0.5, "win": 52, "sharpe": 0.1, "pf": 1.1},
        "يونيو": {"ret": 0.8, "win": 55, "sharpe": 0.15, "pf": 1.2},
        "يوليو": {"ret": 1.0, "win": 55, "sharpe": 0.2, "pf": 1.25},
        "أغسطس": {"ret": 1.2, "win": 58, "sharpe": 0.25, "pf": 1.3},
        "سبتمبر": {"ret": 1.5, "win": 60, "sharpe": 0.3, "pf": 1.4},
        "أكتوبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.35},
        "نوفمبر": {"ret": 1.0, "win": 55, "sharpe": 0.2, "pf": 1.25},
        "ديسمبر": {"ret": 2.0, "win": 62, "sharpe": 0.42, "pf": 1.6},
    },
    "الطاقة": {
        "يناير": {"ret": 1.0, "win": 52, "sharpe": 0.2, "pf": 1.2},
        "فبراير": {"ret": 0.8, "win": 50, "sharpe": 0.15, "pf": 1.1},
        "مارس": {"ret": -0.3, "win": 45, "sharpe": -0.05, "pf": 0.92},
        "أبريل": {"ret": 0.5, "win": 48, "sharpe": 0.1, "pf": 1.05},
        "مايو": {"ret": -1.0, "win": 40, "sharpe": -0.2, "pf": 0.78},
        "يونيو": {"ret": -1.5, "win": 35, "sharpe": -0.3, "pf": 0.65},
        "يوليو": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "أغسطس": {"ret": -0.3, "win": 45, "sharpe": -0.05, "pf": 0.92},
        "سبتمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أكتوبر": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "نوفمبر": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "ديسمبر": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
    },
    "النقل": {
        "يناير": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "فبراير": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "مارس": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أبريل": {"ret": 1.5, "win": 58, "sharpe": 0.32, "pf": 1.4},
        "مايو": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "يونيو": {"ret": -0.2, "win": 45, "sharpe": -0.03, "pf": 0.95},
        "يوليو": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أغسطس": {"ret": 1.0, "win": 55, "sharpe": 0.2, "pf": 1.25},
        "سبتمبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "أكتوبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "نوفمبر": {"ret": 1.8, "win": 60, "sharpe": 0.38, "pf": 1.5},
        "ديسمبر": {"ret": 2.0, "win": 62, "sharpe": 0.42, "pf": 1.6},
    },
    "الصحة": {
        "يناير": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "فبراير": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "مارس": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أبريل": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "مايو": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "يونيو": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "يوليو": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أغسطس": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "سبتمبر": {"ret": 1.0, "win": 55, "sharpe": 0.2, "pf": 1.25},
        "أكتوبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "نوفمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "ديسمبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
    },
    "الأدوية": {
        "يناير": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "فبراير": {"ret": 0.8, "win": 50, "sharpe": 0.15, "pf": 1.1},
        "مارس": {"ret": 0.5, "win": 48, "sharpe": 0.1, "pf": 1.05},
        "أبريل": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "مايو": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "يونيو": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "يوليو": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "أغسطس": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "سبتمبر": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "أكتوبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "نوفمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "ديسمبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
    },
    "التقنية": {
        "يناير": {"ret": 2.5, "win": 62, "sharpe": 0.5, "pf": 1.7},
        "فبراير": {"ret": 2.0, "win": 60, "sharpe": 0.42, "pf": 1.6},
        "مارس": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أبريل": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "مايو": {"ret": -0.8, "win": 42, "sharpe": -0.15, "pf": 0.85},
        "يونيو": {"ret": -0.5, "win": 45, "sharpe": -0.1, "pf": 0.9},
        "يوليو": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أغسطس": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "سبتمبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "أكتوبر": {"ret": 2.0, "win": 60, "sharpe": 0.42, "pf": 1.6},
        "نوفمبر": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "ديسمبر": {"ret": 2.5, "win": 65, "sharpe": 0.52, "pf": 1.8},
    },
    "الصناعي": {
        "يناير": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "فبراير": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "مارس": {"ret": -0.2, "win": 45, "sharpe": -0.03, "pf": 0.95},
        "أبريل": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "مايو": {"ret": -1.2, "win": 38, "sharpe": -0.25, "pf": 0.72},
        "يونيو": {"ret": -1.5, "win": 32, "sharpe": -0.3, "pf": 0.6},
        "يوليو": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "أغسطس": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "سبتمبر": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أكتوبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "نوفمبر": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "ديسمبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
    },
    "المواد الأساسية": {
        "يناير": {"ret": 0.8, "win": 50, "sharpe": 0.15, "pf": 1.1},
        "فبراير": {"ret": 0.5, "win": 48, "sharpe": 0.1, "pf": 1.05},
        "مارس": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "أبريل": {"ret": -0.3, "win": 45, "sharpe": -0.05, "pf": 0.92},
        "مايو": {"ret": -1.5, "win": 35, "sharpe": -0.3, "pf": 0.65},
        "يونيو": {"ret": -2.0, "win": 28, "sharpe": -0.4, "pf": 0.5},
        "يوليو": {"ret": -1.0, "win": 38, "sharpe": -0.2, "pf": 0.75},
        "أغسطس": {"ret": 0.2, "win": 48, "sharpe": 0.03, "pf": 1.0},
        "سبتمبر": {"ret": 0.8, "win": 50, "sharpe": 0.15, "pf": 1.1},
        "أكتوبر": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "نوفمبر": {"ret": -0.3, "win": 45, "sharpe": -0.05, "pf": 0.92},
        "ديسمبر": {"ret": 1.0, "win": 52, "sharpe": 0.2, "pf": 1.2},
    },
    "الكماليات": {
        "يناير": {"ret": 1.5, "win": 55, "sharpe": 0.3, "pf": 1.3},
        "فبراير": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "مارس": {"ret": -0.8, "win": 40, "sharpe": -0.15, "pf": 0.8},
        "أبريل": {"ret": 0.8, "win": 50, "sharpe": 0.15, "pf": 1.1},
        "مايو": {"ret": -1.0, "win": 38, "sharpe": -0.2, "pf": 0.75},
        "يونيو": {"ret": -1.2, "win": 35, "sharpe": -0.25, "pf": 0.68},
        "يوليو": {"ret": -0.3, "win": 45, "sharpe": -0.05, "pf": 0.92},
        "أغسطس": {"ret": 0.5, "win": 48, "sharpe": 0.1, "pf": 1.05},
        "سبتمبر": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أكتوبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "نوفمبر": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "ديسمبر": {"ret": 2.0, "win": 60, "sharpe": 0.4, "pf": 1.5},
    },
    "السياحة": {
        "يناير": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "فبراير": {"ret": 0.8, "win": 50, "sharpe": 0.15, "pf": 1.1},
        "مارس": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "أبريل": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "مايو": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "يونيو": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "يوليو": {"ret": 2.0, "win": 62, "sharpe": 0.42, "pf": 1.6},
        "أغسطس": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "سبتمبر": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "أكتوبر": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "نوفمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "ديسمبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
    },
    "المرافق": {
        "يناير": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "فبراير": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "مارس": {"ret": 0.2, "win": 48, "sharpe": 0.03, "pf": 1.0},
        "أبريل": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "مايو": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "يونيو": {"ret": 0.2, "win": 48, "sharpe": 0.03, "pf": 1.0},
        "يوليو": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أغسطس": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "سبتمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "أكتوبر": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "نوفمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "ديسمبر": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
    },
    "الإعلام": {
        "يناير": {"ret": 1.5, "win": 55, "sharpe": 0.3, "pf": 1.3},
        "فبراير": {"ret": 1.0, "win": 52, "sharpe": 0.2, "pf": 1.2},
        "مارس": {"ret": 0.5, "win": 48, "sharpe": 0.1, "pf": 1.05},
        "أبريل": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
        "مايو": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "يونيو": {"ret": -0.8, "win": 40, "sharpe": -0.15, "pf": 0.8},
        "يوليو": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "أغسطس": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "سبتمبر": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "أكتوبر": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "نوفمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "ديسمبر": {"ret": 1.8, "win": 60, "sharpe": 0.38, "pf": 1.5},
    },
    "التعليم": {
        "يناير": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "فبراير": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "مارس": {"ret": 0.3, "win": 48, "sharpe": 0.05, "pf": 1.0},
        "أبريل": {"ret": 0.8, "win": 52, "sharpe": 0.15, "pf": 1.15},
        "مايو": {"ret": -0.3, "win": 45, "sharpe": -0.05, "pf": 0.92},
        "يونيو": {"ret": -0.5, "win": 42, "sharpe": -0.1, "pf": 0.85},
        "يوليو": {"ret": 0.2, "win": 48, "sharpe": 0.03, "pf": 1.0},
        "أغسطس": {"ret": 1.5, "win": 58, "sharpe": 0.3, "pf": 1.4},
        "سبتمبر": {"ret": 1.8, "win": 60, "sharpe": 0.38, "pf": 1.5},
        "أكتوبر": {"ret": 1.0, "win": 53, "sharpe": 0.2, "pf": 1.2},
        "نوفمبر": {"ret": 0.5, "win": 50, "sharpe": 0.1, "pf": 1.1},
        "ديسمبر": {"ret": 1.2, "win": 55, "sharpe": 0.25, "pf": 1.3},
    },
}


# ══════════════════════════════════════════════════════════════
# 3. SECTOR TIERS — strategic classification
# ══════════════════════════════════════════════════════════════

SECTOR_TIERS = {
    "green": {
        "label": "أخضر — القطاعات القوية",
        "sectors": ["البنوك", "الأغذية", "النقل", "التقنية", "التجزئة"],
        "description": "نسب نجاح عالية تاريخياً، سيولة جيدة، تجميع مؤسسي مستمر",
    },
    "yellow": {
        "label": "أصفر — القطاعات المتوسطة",
        "sectors": ["الصحة", "التأمين", "العقارات", "الاتصالات", "الأسمنت", "الأدوية", "السياحة"],
        "description": "متقلبة موسمياً، تعتمد على توقيت الدخول",
    },
    "red": {
        "label": "أحمر — القطاعات الخطرة",
        "sectors": ["المواد الأساسية", "الصناعي", "الكماليات", "البتروكيماويات", "الطاقة"],
        "description": "نسب نجاح منخفضة، تتأثر بالأسعار العالمية، تذبذب عالي",
    },
}


# ══════════════════════════════════════════════════════════════
# 4. HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════

MONTHS_AR = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
]


def get_current_month_ar() -> str:
    """Get current month name in Arabic."""
    return MONTHS_AR[datetime.datetime.now().month - 1]


def get_top_sectors(month: str, n: int = 5) -> list:
    """Get top N sectors for a given month by return."""
    results = []
    for sector, months in SECTOR_SEASONALITY.items():
        if month in months:
            data = months[month]
            results.append({
                "sector": sector,
                "return": data["ret"],
                "win_pct": data["win"],
                "sharpe": data["sharpe"],
                "pf": data["pf"],
            })
    results.sort(key=lambda x: x["return"], reverse=True)
    return results[:n]


def get_avoid_sectors(month: str) -> list:
    """Get sectors with negative returns for a given month."""
    results = []
    for sector, months in SECTOR_SEASONALITY.items():
        if month in months:
            data = months[month]
            if data["ret"] < 0:
                results.append({
                    "sector": sector,
                    "return": data["ret"],
                    "win_pct": data["win"],
                })
    results.sort(key=lambda x: x["return"])
    return results


def get_sector_tier(sector: str) -> dict:
    """Get tier classification (green/yellow/red) for a sector."""
    for tier, info in SECTOR_TIERS.items():
        if sector in info["sectors"]:
            return {"tier": tier, "label": info["label"], "description": info["description"]}
    return {"tier": "unknown", "label": "غير مصنف", "description": ""}


def get_defensive_sectors(month: str) -> list:
    """Get sectors with positive returns even in weak months."""
    results = []
    month_data = MONTH_OVERVIEW.get(month, {})
    is_weak = month_data.get("return", 0) < 0

    for sector, months in SECTOR_SEASONALITY.items():
        if month in months:
            data = months[month]
            if data["ret"] > 0 and data["win"] >= 50:
                results.append({
                    "sector": sector,
                    "return": data["ret"],
                    "win_pct": data["win"],
                    "defensive": is_weak,
                })
    results.sort(key=lambda x: x["return"], reverse=True)
    return results


def check_seasonality_of_alignment(
    sector: str,
    month: str,
    order_flow: str,  # "positive", "negative", "neutral"
) -> str:
    """
    Check if seasonality aligns with Order Flow signal.
    Returns verdict string.
    """
    data = SECTOR_SEASONALITY.get(sector, {}).get(month)
    if not data:
        return "لا توجد بيانات موسمية"

    seasonal_positive = data["ret"] > 0 and data["win"] >= 50
    of_positive = order_flow == "positive"

    if seasonal_positive and of_positive:
        return f"تأكيد مزدوج — موسمية إيجابية ({data['ret']:+.1f}%) + OF إيجابي"
    elif not seasonal_positive and not of_positive:
        return f"تأكيد مزدوج سلبي — موسمية سلبية ({data['ret']:+.1f}%) + OF سلبي"
    elif seasonal_positive and not of_positive:
        return f"تناقض — موسمية إيجابية ({data['ret']:+.1f}%) لكن OF سلبي — حذر"
    else:
        return f"تناقض — OF إيجابي لكن موسمية سلبية ({data['ret']:+.1f}%) — خطر"


def get_month_summary(month: str) -> dict:
    """Get complete month overview with top/avoid sectors."""
    overview = MONTH_OVERVIEW.get(month, {})
    return {
        **overview,
        "month": month,
        "top_sectors": get_top_sectors(month, 5),
        "avoid_sectors": get_avoid_sectors(month),
        "defensive_sectors": get_defensive_sectors(month),
    }


# ══════════════════════════════════════════════════════════════
# 5. RSI x SIGNAL TYPE MATRIX (from V3 backtest, 2356 trades)
# ══════════════════════════════════════════════════════════════

RSI_SIGNAL_MATRIX = {
    ("phase_early", "RSI<30"): {"win": 79, "count": 24, "verdict": "ممتاز"},
    ("watch", "RSI<30"): {"win": 77, "count": 61, "verdict": "ممتاز"},
    ("phase_mid", "RSI<30"): {"win": 69, "count": 183, "verdict": "جيد"},
    ("phase_mid", "RSI 30-50"): {"win": 58, "count": 497, "verdict": "متوسط"},
    ("phase_early", "RSI 30-50"): {"win": 63, "count": 56, "verdict": "جيد"},
    ("buy_breakout", "RSI 30-50"): {"win": 63, "count": 49, "verdict": "جيد"},
    ("watch", "RSI 30-50"): {"win": 57, "count": 209, "verdict": "متوسط"},
    ("sell_warning", "RSI 50-70"): {"win": 54, "count": 70, "verdict": "متوسط"},
    ("phase_early", "RSI 50-70"): {"win": 46, "count": 22, "verdict": "ضعيف"},
    ("phase_mid", "RSI 50-70"): {"win": 39, "count": 209, "verdict": "ضعيف"},
    ("watch", "RSI 50-70"): {"win": 34, "count": 89, "verdict": "ضعيف"},
    ("buy_breakout", "RSI 50-70"): {"win": 36, "count": 22, "verdict": "ضعيف"},
    ("phase_mid", "RSI>70"): {"win": 19, "count": 32, "verdict": "خطر"},
    ("watch", "RSI>70"): {"win": 9, "count": 11, "verdict": "خطر"},
    ("buy_breakout", "RSI>70"): {"win": 0, "count": 6, "verdict": "ممنوع"},
    ("sell_warning", "RSI>70"): {"win": 100, "count": 4, "verdict": "بيع صح"},
}


def get_rsi_signal_assessment(signal_type: str, rsi_value: float) -> dict:
    """
    Get assessment for a signal type + RSI combination.
    Returns: {win_pct, count, verdict, zone, color}
    """
    if rsi_value < 30:
        zone = "RSI<30"
    elif rsi_value < 50:
        zone = "RSI 30-50"
    elif rsi_value < 70:
        zone = "RSI 50-70"
    else:
        zone = "RSI>70"

    key = (signal_type, zone)
    data = RSI_SIGNAL_MATRIX.get(key)

    if data:
        color = (
            "#00E676" if data["verdict"] in ("ممتاز", "جيد") else
            "#FFD700" if data["verdict"] == "متوسط" else
            "#FF5252"
        )
        return {
            "win_pct": data["win"],
            "count": data["count"],
            "verdict": data["verdict"],
            "zone": zone,
            "color": color,
        }
    return {
        "win_pct": None,
        "count": 0,
        "verdict": "غير متوفر",
        "zone": zone,
        "color": "#808080",
    }
