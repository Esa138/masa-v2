"""
MASA V2 — UI Styles
Professional dark theme with glassmorphism cards.
"""

SECTOR_COLORS = {
    # ── Saudi Market — Tadawul GICS Sectors ──
    "البنوك": "#4FC3F7",                # Light Blue
    "الخدمات المالية": "#29B6F6",       # Blue
    "التأمين": "#FFCA28",              # Yellow
    "الطاقة": "#EF5350",              # Red
    "المواد الأساسية": "#8D6E63",      # Brown
    "القطاع الصناعي": "#78909C",        # Gray-Blue
    "الخدمات التجارية": "#90A4AE",     # Light Gray
    "النقل": "#26A69A",               # Teal
    "السلع الكمالية": "#AB47BC",       # Purple
    "السلع طويلة الأجل": "#9575CD",    # Light Deep Purple
    "الخدمات الاستهلاكية": "#FF7043",  # Orange
    "الإعلام والترفيه": "#EC407A",     # Pink
    "التجزئة": "#E91E63",             # Hot Pink
    "السلع الاستهلاكية": "#66BB6A",     # Green
    "تجزئة السلع الاستهلاكية": "#43A047", # Dark Green
    "الرعاية الصحية": "#CE93D8",       # Light Purple
    "الأدوية": "#BA68C8",             # Medium Purple
    "الاتصالات": "#42A5F5",           # Blue
    "التقنية": "#7E57C2",             # Deep Purple
    "المرافق العامة": "#5C6BC0",      # Indigo
    "العقارات": "#FFA726",            # Orange-Yellow
    # ── US Market ──
    "Technology": "#7E57C2",
    "Consumer": "#EC407A",
    "Fintech": "#4FC3F7",
    "Healthcare": "#AB47BC",
    "Energy": "#EF5350",
    "Industrials": "#78909C",
    "Consumer Staples": "#66BB6A",
    "Communications": "#42A5F5",
    "Utilities": "#5C6BC0",
    "Real Estate": "#FFA726",
    "Materials": "#8D6E63",
    # Default
    "أخرى": "#607D8B",
}

DARK_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');

* { font-family: 'Tajawal', sans-serif !important; }

/* ── App Background ── */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #080b14 0%, #0d1117 50%, #080b14 100%);
    color: #e0e0e0;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0f1a 0%, #0d1321 100%);
    border-right: 1px solid #151d30;
}
[data-testid="stHeader"] { background-color: transparent; }

h1, h2, h3 { color: #ffffff !important; }

/* ── Streamlit Component Overrides ── */
[data-testid="stMetric"] {
    background: linear-gradient(145deg, #141b2d 0%, #0f1523 100%);
    border: 1px solid #1a2035;
    border-radius: 14px;
    padding: 14px 16px;
}
[data-testid="stMetricValue"] { font-size: 1.5em !important; font-weight: 800 !important; }
[data-testid="stMetricLabel"] { color: #6b7280 !important; font-size: 0.82em !important; }

.stSelectbox > div > div {
    background: #111827 !important;
    border-color: #1e2540 !important;
    border-radius: 10px !important;
}
.stSelectbox label { color: #6b7280 !important; font-size: 0.82em !important; }

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00E676 0%, #00C853 100%) !important;
    color: #000 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 8px 24px !important;
    font-size: 0.95em !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(0,230,118,0.25) !important;
}

.stProgress > div > div > div {
    background: linear-gradient(90deg, #00E676, #69F0AE) !important;
    border-radius: 4px !important;
}

.stDivider { border-color: #1a2035 !important; }

/* ── MASA Grid ── */
.masa-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    direction: rtl;
}
@media (max-width: 768px) {
    .masa-grid { grid-template-columns: 1fr !important; }
}
@media (min-width: 769px) and (max-width: 1200px) {
    .masa-grid { grid-template-columns: repeat(2, 1fr) !important; }
}

/* ── MASA Card ── */
.masa-card {
    background: linear-gradient(145deg, #131a2e 0%, #0e1424 100%);
    border: 1px solid #192035;
    border-radius: 16px;
    padding: 18px;
    position: relative;
    overflow: hidden;
    direction: rtl;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.masa-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.masa-card-enter::before { background: linear-gradient(90deg, #00E676, #69F0AE); }
.masa-card-watch::before { background: linear-gradient(90deg, #FFD700, #FFF176); }
.masa-card-avoid::before { background: linear-gradient(90deg, #FF5252, #FF8A80); }

.masa-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.4);
    border-color: #283350;
}
.masa-card-avoid { opacity: 0.78; }
.masa-card-avoid:hover { opacity: 1; }

/* ── Event Cards ── */
.masa-card-bounce::before { background: linear-gradient(90deg, #00E676, #69F0AE); }
.masa-card-breakout::before { background: linear-gradient(90deg, #FFD700, #FFF176); }
.masa-card-breakdown::before { background: linear-gradient(90deg, #FF5252, #FF8A80); }
.masa-card-breakdown { opacity: 0.78; }
.masa-card-breakdown:hover { opacity: 1; }

/* ── MASA Stat Cards ── */
.masa-stat {
    background: linear-gradient(145deg, #131a2e 0%, #0e1424 100%);
    border: 1px solid #192035;
    border-radius: 14px;
    padding: 16px;
    text-align: center;
    direction: rtl;
}
.masa-stat-enter {
    border-bottom: 2px solid rgba(0,230,118,0.25);
    background: linear-gradient(145deg, rgba(0,230,118,0.04), #0e1424);
}
.masa-stat-watch {
    border-bottom: 2px solid rgba(255,215,0,0.20);
    background: linear-gradient(145deg, rgba(255,215,0,0.03), #0e1424);
}
.masa-stat-avoid {
    border-bottom: 2px solid rgba(255,82,82,0.20);
    background: linear-gradient(145deg, rgba(255,82,82,0.03), #0e1424);
}
.masa-stat-label {
    color: #6b7280;
    font-size: 0.82em;
    margin-bottom: 6px;
}
.masa-stat-value {
    font-size: 1.8em;
    font-weight: 800;
    line-height: 1.2;
}

/* ── Detail Button ── */
.stButton > button[kind="secondary"] {
    background: rgba(79,195,247,0.06) !important;
    color: #4FC3F7 !important;
    border: 1px solid rgba(79,195,247,0.15) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.82em !important;
    padding: 6px 12px !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="secondary"]:hover {
    background: rgba(79,195,247,0.12) !important;
    border-color: rgba(79,195,247,0.30) !important;
    transform: translateY(-1px) !important;
}

/* ── Search Box ── */
.stTextInput > div > div > input {
    background: #111827 !important;
    border-color: #1e2540 !important;
    border-radius: 12px !important;
    color: #fff !important;
    font-size: 1em !important;
    padding: 10px 16px !important;
}
.stTextInput > div > div > input:focus {
    border-color: #4FC3F7 !important;
    box-shadow: 0 0 0 2px rgba(79,195,247,0.15) !important;
}
.stTextInput label { color: #6b7280 !important; font-size: 0.85em !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #080b14; }
::-webkit-scrollbar-thumb { background: #1e2540; border-radius: 3px; }

/* ── Sector Map ── */
.smap-card {
    background: linear-gradient(135deg, rgba(13,19,33,0.95), rgba(10,15,26,0.98));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    margin-bottom: 16px;
    overflow: hidden;
}
.smap-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 16px 20px 10px;
}
.smap-header-name {
    font-size: 1.15em; font-weight: 700; color: #e0e0e0;
}
.smap-counts {
    display: flex; gap: 12px; padding: 0 20px 12px;
    font-size: 0.78em; color: #9ca3af;
}
.smap-counts span { display: flex; align-items: center; gap: 3px; }
.smap-bar-wrap {
    display: flex; height: 6px; margin: 0 20px 14px;
    border-radius: 3px; overflow: hidden; background: #1a1f2e;
}
.smap-bar-g { background: #00E676; }
.smap-bar-n { background: #4b5563; }
.smap-bar-r { background: #FF5252; }
.smap-rows { padding: 0 12px 12px; }
.smap-row {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 10px; border-radius: 10px;
    background: rgba(255,255,255,0.02);
    margin-bottom: 4px; font-size: 0.82em;
}
.smap-row:hover { background: rgba(255,255,255,0.05); }
.smap-row-name { flex: 1; font-weight: 600; color: #e0e0e0; min-width: 0;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.smap-row-tk { color: #6b7280; font-size: 0.88em; width: 58px; text-align: center; }
.smap-row-price { color: #9ca3af; width: 70px; text-align: left; direction: ltr; }
.smap-phase {
    padding: 2px 8px; border-radius: 8px; font-size: 0.78em;
    font-weight: 500; white-space: nowrap;
}
.smap-days { color: #6b7280; font-size: 0.76em; width: 55px; text-align: center; }
.smap-fb { width: 60px; height: 6px; border-radius: 3px; background: #1a1f2e;
    position: relative; overflow: hidden; }
.smap-fb-fill { height: 100%; border-radius: 3px; position: absolute; }
.smap-health {
    font-size: 1.3em; font-weight: 800; direction: ltr;
}

/* ── Hide Streamlit Branding ── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
