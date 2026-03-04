CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Tajawal', sans-serif !important; -webkit-text-size-adjust: 100%; }
#MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}

div[data-testid="metric-container"] {
    background-color: #1a1c24; border: 1px solid #2d303e;
    padding: 15px 20px; border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); transition: all 0.3s ease;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-5px); border-color: #00d2ff;
    box-shadow: 0 6px 12px rgba(0, 210, 255, 0.2);
}

.stTabs [data-baseweb="tab-list"] { gap: 15px; }
.stTabs [data-baseweb="tab"] {
    height: 50px; white-space: pre-wrap; background-color: transparent;
    border-radius: 4px 4px 0px 0px; padding-top: 10px; padding-bottom: 10px;
    font-size: 16px; font-weight: 600; color: #888;
}
.stTabs [aria-selected="true"] { color: #00d2ff !important; border-bottom: 2px solid #00d2ff; }

.scanner-header-gray {
    background-color: #2d303e; color: #fff; padding: 8px; text-align: center;
    border-radius: 5px; font-weight: bold; margin-bottom: 10px; border-bottom: 2px solid #00d2ff;
}
.bo-badge {
    font-weight: bold; padding: 4px 10px; border-radius: 6px;
    font-size: 12px; display: inline-block; white-space: nowrap; margin: 2px;
}
.whale-table {
    width: 100%; border-collapse: collapse; font-size: 14px; text-align: center;
    border-radius: 10px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
}
.whale-table th { color: white; padding: 12px; font-weight: 900; }
.whale-table td {
    padding: 12px; border-bottom: 1px solid #2d303e; color: white; font-weight: bold;
}
.whale-acc th { background-color: rgba(0, 230, 118, 0.2); border-bottom: 2px solid #00E676; color: #00E676; }
.whale-dist th { background-color: rgba(255, 82, 82, 0.2); border-bottom: 2px solid #FF5252; color: #FF5252; }

.vip-container {
    display: flex; gap: 20px; justify-content: center; flex-wrap: wrap;
    margin-top: 20px; margin-bottom: 30px;
}
.vip-card {
    background: linear-gradient(135deg, #2b2302 0%, #1a1c24 100%);
    border: 1px solid #ffd700; border-top: 4px solid #ffd700;
    padding: 25px 20px; border-radius: 15px; width: 31%; min-width: 280px;
    box-shadow: 0 10px 20px rgba(255, 215, 0, 0.1); transition: transform 0.3s ease;
    text-align: center; position: relative; overflow: hidden;
}
.vip-card:hover { transform: translateY(-8px); box-shadow: 0 15px 30px rgba(255, 215, 0, 0.25); }
.vip-crown { position: absolute; top: -15px; right: -15px; font-size: 60px; transform: rotate(15deg); opacity: 0.1; }
.vip-title { color: #ffd700; font-size: 26px; font-weight: 900; margin-bottom: 5px; }
.vip-time {
    font-size: 13px; color: #aaa; margin-bottom: 15px; background-color: rgba(255,255,255,0.05);
    padding: 4px 10px; border-radius: 4px; display: inline-block; border: 1px solid rgba(255,255,255,0.1);
}
.vip-rr {
    font-size: 13px; color: #00d2ff; background-color: rgba(0, 210, 255, 0.1);
    border: 1px dashed #00d2ff; padding: 4px 10px; border-radius: 4px;
    display: inline-block; margin-bottom: 15px; font-weight: bold;
}
.vip-price { font-size: 32px; color: white; font-weight: bold; margin-bottom: 15px; }
.vip-details {
    display: flex; justify-content: space-between; margin-bottom: 15px; font-size: 15px;
    background: rgba(0,0,0,0.4); padding: 12px; border-radius: 10px;
    border: 1px solid rgba(255, 215, 0, 0.2);
}
.vip-target { color: #00e676; font-weight: 900; font-size: 18px; }
.vip-stop { color: #ff5252; font-weight: 900; font-size: 18px; }
.vip-score {
    background: #ffd700; color: black; padding: 8px 20px; border-radius: 20px;
    font-weight: 900; font-size: 18px; display: inline-block; margin-top: 15px;
    box-shadow: 0 4px 10px rgba(255, 215, 0, 0.4);
}
.search-container {
    background: linear-gradient(145deg, #1e2129, #15171e); padding: 20px;
    border-radius: 15px; border: 1px solid #2d303e; margin-bottom: 25px;
    box-shadow: 0 8px 16px rgba(0,0,0,0.4); text-align: center;
}
.empty-box {
    text-align:center; padding:15px; background-color:#1e2129; border-radius:8px;
    color:#888; margin-bottom:15px; font-size:15px; border: 1px dashed #2d303e;
}
.news-card {
    background: linear-gradient(145deg, #1a1c24, #12141a);
    border: 1px solid #2d303e; border-radius: 12px;
    padding: 20px; margin-bottom: 15px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    transition: all 0.3s ease;
}
.news-card:hover { border-color: #00d2ff; transform: translateY(-3px); }
.news-positive { border-right: 4px solid #00E676; }
.news-negative { border-right: 4px solid #FF5252; }
.news-neutral { border-right: 4px solid #FFD700; }
.news-badge {
    display: inline-block; padding: 4px 12px; border-radius: 20px;
    font-size: 12px; font-weight: bold; margin-top: 8px;
}
.news-badge-pos { background: rgba(0,230,118,0.15); color: #00E676; border: 1px solid #00E676; }
.news-badge-neg { background: rgba(255,82,82,0.15); color: #FF5252; border: 1px solid #FF5252; }
.news-badge-neu { background: rgba(255,215,0,0.15); color: #FFD700; border: 1px solid #FFD700; }
[data-testid="collapsedControl"] { display: none; }

/* Wolf V2 Breakout Styles */
.wolf-badge { display:inline-block; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:bold; margin:2px; }
.wolf-badge-confirmed { background:rgba(255,152,0,0.15); color:#FF9800; border:1px solid #FF9800; }
.wolf-badge-only { background:rgba(156,39,176,0.15); color:#CE93D8; border:1px solid #CE93D8; }
.wolf-card {
    background: linear-gradient(135deg, #2b1a02 0%, #1a1c24 100%);
    border: 1px solid #FF9800; border-top: 4px solid #FF9800;
    padding: 25px 20px; border-radius: 15px; width: 48%; min-width: 340px;
    box-shadow: 0 10px 20px rgba(255, 152, 0, 0.1); transition: transform 0.3s ease;
    margin-bottom: 20px; position: relative; overflow: hidden;
}
.wolf-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(255, 152, 0, 0.25); }
.wolf-card-only { border-color: #CE93D8; border-top-color: #CE93D8; }
.wolf-icon { position: absolute; top: -15px; right: -15px; font-size: 60px; transform: rotate(15deg); opacity: 0.1; }
.wolf-title { color: #FF9800; font-size: 24px; font-weight: 900; margin-bottom: 5px; }
.wolf-filter-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 15px;
    padding: 15px; background: rgba(0,0,0,0.3); border-radius: 10px;
    border: 1px solid rgba(255, 152, 0, 0.2);
}
.wolf-filter-item { font-size: 13px; padding: 6px 10px; border-radius: 6px; text-align: center; font-weight: bold; }
.wolf-filter-pass { background: rgba(0,230,118,0.1); color: #00E676; border: 1px solid rgba(0,230,118,0.3); }
.wolf-filter-fail { background: rgba(255,82,82,0.1); color: #FF5252; border: 1px solid rgba(255,82,82,0.3); }
.wolf-container { display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; margin-top: 20px; margin-bottom: 30px; }

/* TASI Keyword Scanner Styles */
.kw-tag { display:inline-block; padding:4px 10px; border-radius:15px; font-size:12px;
    font-weight:bold; margin:3px; direction:rtl; }
.kw-killer { background:rgba(255,82,82,0.15); color:#FF5252; border:1px solid #FF5252; }
.kw-rocket { background:rgba(0,230,118,0.15); color:#00E676; border:1px solid #00E676; }
.kw-section { padding:12px; margin-top:10px; border-radius:10px;
    background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.1); }
.kw-verdict-danger { background:rgba(255,82,82,0.1); border:2px solid #FF5252;
    padding:10px 20px; border-radius:10px; text-align:center; color:#FF5252; font-weight:bold; font-size:18px; }
.kw-verdict-rocket { background:rgba(0,230,118,0.1); border:2px solid #00E676;
    padding:10px 20px; border-radius:10px; text-align:center; color:#00E676; font-weight:bold; font-size:18px; }
.kw-verdict-neutral { background:rgba(255,215,0,0.1); border:2px solid #FFD700;
    padding:10px 20px; border-radius:10px; text-align:center; color:#FFD700; font-weight:bold; font-size:18px; }

/* Confluence Stars */
.confluence-stars { font-size:20px; letter-spacing:2px; display:inline-block; margin:3px 0; }
.confluence-badge { display:inline-block; padding:4px 12px; border-radius:20px; font-size:12px;
    font-weight:bold; margin:2px; background:rgba(255,215,0,0.12); color:#FFD700; border:1px solid rgba(255,215,0,0.4); }
.confluence-high { background:rgba(255,215,0,0.25); border-color:#FFD700; animation: pulse-star 2s infinite; }
@keyframes pulse-star { 0%, 100% { box-shadow: 0 0 5px rgba(255,215,0,0.3); } 50% { box-shadow: 0 0 15px rgba(255,215,0,0.6); } }

/* Signal Quality Badge (الحَكَم) */
.signal-quality-badge { display:inline-block; padding:6px 16px; border-radius:20px; font-size:13px; font-weight:bold; margin:2px 0 10px 0; letter-spacing:0.5px; }
.signal-quality-gold { background:rgba(255,215,0,0.2); color:#FFD700; border:2px solid #FFD700; animation: pulse-gold 2s infinite; }
.signal-quality-silver { background:rgba(192,192,192,0.15); color:#E0E0E0; border:1px solid #C0C0C0; }
.signal-quality-bronze { background:rgba(205,127,50,0.15); color:#CD7F32; border:1px solid #CD7F32; }
.signal-quality-blocked { background:rgba(255,82,82,0.2); color:#FF5252; border:2px solid #FF5252; animation: pulse-warn 2s infinite; }
@keyframes pulse-gold { 0%, 100% { box-shadow: 0 0 5px rgba(255,215,0,0.3); } 50% { box-shadow: 0 0 20px rgba(255,215,0,0.6); } }
@keyframes pulse-warn { 0%, 100% { box-shadow: 0 0 5px rgba(255,82,82,0.2); } 50% { box-shadow: 0 0 15px rgba(255,82,82,0.5); } }

/* Arbitrator Warning */
.arb-warning { background:rgba(255,152,0,0.1); border:1px solid rgba(255,152,0,0.4); border-radius:10px;
    padding:8px 14px; margin:6px 0 10px 0; font-size:12px; color:#FF9800; line-height:1.6; direction:rtl; }

/* Sector Tags */
.sector-tag { display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px;
    font-weight:bold; margin:2px; background:rgba(0,210,255,0.1); color:#00d2ff; border:1px solid rgba(0,210,255,0.3); }

/* Divergence Badges */
.div-badge { display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px;
    font-weight:bold; margin:2px; }
.div-bearish { background:rgba(255,82,82,0.12); color:#FF5252; border:1px solid rgba(255,82,82,0.3); }
.div-bullish { background:rgba(0,230,118,0.12); color:#00E676; border:1px solid rgba(0,230,118,0.3); }

/* Dynamic VIP Threshold Badge */
.vip-threshold { display:inline-block; padding:6px 16px; border-radius:8px; font-size:13px;
    font-weight:bold; margin:8px 0; text-align:center; }
.vip-threshold-bull { background:rgba(0,230,118,0.1); color:#00E676; border:1px solid rgba(0,230,118,0.3); }
.vip-threshold-bear { background:rgba(255,82,82,0.1); color:#FF5252; border:1px solid rgba(255,82,82,0.3); }
.vip-threshold-normal { background:rgba(255,215,0,0.1); color:#FFD700; border:1px solid rgba(255,215,0,0.3); }

/* 🏗️ Accumulation Scanner Styles */
.accum-container { display:flex; gap:20px; justify-content:center; flex-wrap:wrap; margin-top:20px; margin-bottom:30px; }
.accum-card {
    background: linear-gradient(135deg, #1a1c24 0%, #12141a 100%);
    border: 1px solid #2d303e; border-top: 4px solid #808080;
    padding: 25px 20px; border-radius: 15px; width: 31%; min-width: 280px;
    box-shadow: 0 10px 20px rgba(0,0,0,0.3); transition: transform 0.3s ease;
    text-align: center; position: relative; overflow: hidden;
}
.accum-card:hover { transform: translateY(-5px); }
.accum-card-late { border-color:#00E676; border-top-color:#00E676; background: linear-gradient(135deg, #0a1f0e 0%, #1a1c24 100%); }
.accum-card-late:hover { box-shadow: 0 15px 30px rgba(0,230,118,0.2); }
.accum-card-strong { border-color:#2196F3; border-top-color:#2196F3; background: linear-gradient(135deg, #0a1525 0%, #1a1c24 100%); }
.accum-card-strong:hover { box-shadow: 0 15px 30px rgba(33,150,243,0.2); }
.accum-card-mid { border-color:#CE93D8; border-top-color:#CE93D8; }
.accum-card-early { border-color:#FFD700; border-top-color:#FFD700; }
.accum-card-distribute { border-color:#FF5252; border-top-color:#FF5252; background: linear-gradient(135deg, #250a0a 0%, #1a1c24 100%); }
.accum-card-distribute:hover { box-shadow: 0 15px 30px rgba(255,82,82,0.2); }
.accum-card-breakout { border-color:#FF9800; border-top-color:#FF9800; background: linear-gradient(135deg, #1f1508 0%, #1a1c24 100%); }
.accum-card-breakout:hover { box-shadow: 0 15px 30px rgba(255,152,0,0.2); }
.accum-card-pullback_buy { border-color:#4CAF50; border-top-color:#4CAF50; background: linear-gradient(135deg, #0a1f0e 0%, #1a1c24 100%); }
.accum-card-pullback_buy:hover { box-shadow: 0 15px 30px rgba(76,175,80,0.25); }
.accum-card-pullback_wait { border-color:#FFC107; border-top-color:#FFC107; background: linear-gradient(135deg, #1f1a08 0%, #1a1c24 100%); }
.accum-card-pullback_wait:hover { box-shadow: 0 15px 30px rgba(255,193,7,0.2); }
.accum-card-exhausted { border-color:#E91E63; border-top-color:#E91E63; background: linear-gradient(135deg, #250a15 0%, #1a1c24 100%); }
.accum-card-exhausted:hover { box-shadow: 0 15px 30px rgba(233,30,99,0.2); }
.accum-phase-badge {
    display:inline-block; padding:5px 16px; border-radius:20px; font-size:13px;
    font-weight:bold; margin:5px 0; letter-spacing:1px;
}
.accum-phase-late { background:rgba(0,230,118,0.15); color:#00E676; border:1px solid #00E676; }
.accum-phase-strong { background:rgba(33,150,243,0.15); color:#2196F3; border:1px solid #2196F3; }
.accum-phase-mid { background:rgba(206,147,216,0.15); color:#CE93D8; border:1px solid #CE93D8; }
.accum-phase-early { background:rgba(255,215,0,0.15); color:#FFD700; border:1px solid #FFD700; }
.accum-phase-distribute { background:rgba(255,82,82,0.15); color:#FF5252; border:1px solid #FF5252; }
.accum-phase-breakout { background:rgba(255,152,0,0.2); color:#FF9800; border:1px solid #FF9800; animation: pulse-gold 2s infinite; }
.accum-phase-pullback_buy { background:rgba(76,175,80,0.2); color:#4CAF50; border:2px solid #4CAF50; animation: pulse-gold 2s infinite; }
.accum-phase-pullback_wait { background:rgba(255,193,7,0.15); color:#FFC107; border:1px solid #FFC107; }
.accum-phase-exhausted { background:rgba(233,30,99,0.15); color:#E91E63; border:1px solid #E91E63; }
.lifecycle-meta {
    background:rgba(0,0,0,0.3); border-radius:10px; padding:8px 12px; margin:8px 0;
    border:1px solid rgba(255,255,255,0.05); font-size:12px; color:#aaa; direction:rtl;
}
.lifecycle-meta b { color:#fff; }
.accum-bar-bg {
    background:#2d303e; border-radius:10px; height:14px; width:100%; margin:10px 0;
    overflow:hidden; position:relative;
}
.accum-bar-fill {
    height:100%; border-radius:10px; transition: width 0.5s ease;
    background: linear-gradient(90deg, #2196F3, #00E676);
}
.accum-bar-fill-dist { background: linear-gradient(90deg, #FF5252, #FF9800); }
.accum-metrics {
    display:flex; justify-content:space-around; margin-top:12px; padding:10px;
    background:rgba(0,0,0,0.3); border-radius:10px; border:1px solid rgba(255,255,255,0.05);
}
.accum-metric { text-align:center; }
.accum-metric-label { font-size:11px; color:#888; margin-bottom:3px; }
.accum-metric-value { font-size:16px; font-weight:bold; color:#fff; }
.accum-zr-badge {
    display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px;
    font-weight:bold; margin:3px; background:rgba(255,215,0,0.15); color:#FFD700;
    border:1px solid rgba(255,215,0,0.4); animation: pulse-star 2s infinite;
}
.accum-loc-badge {
    display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px;
    font-weight:bold; margin:3px; letter-spacing:0.5px;
}
.accum-loc-bottom { background:rgba(0,230,118,0.12); color:#00E676; border:1px solid rgba(0,230,118,0.4); }
.accum-loc-blue_sky { background:rgba(0,176,255,0.12); color:#00B0FF; border:1px solid rgba(0,176,255,0.4); }
.accum-loc-middle { background:rgba(206,147,216,0.12); color:#CE93D8; border:1px solid rgba(206,147,216,0.4); }
.accum-loc-resistance { background:rgba(255,152,0,0.12); color:#FF9800; border:1px solid rgba(255,152,0,0.4); }
.accum-icon { position:absolute; top:-15px; right:-15px; font-size:60px; transform:rotate(15deg); opacity:0.08; }

/* ── Two-Tier Card: Details (expandable) ──────────── */
.accum-details { margin-top:10px; border-top:1px solid rgba(255,255,255,0.08); }
.accum-details-btn {
    cursor:pointer; text-align:center; font-size:13px; color:#00d2ff;
    padding:10px 0 2px; list-style:none; user-select:none;
}
.accum-details-btn::-webkit-details-marker { display:none; }
.accum-details[open] .accum-details-btn { color:#FFD700; }
.accum-tier2 {
    background:rgba(0,0,0,0.2); border-radius:10px; padding:12px;
    margin-top:8px; border:1px solid rgba(255,255,255,0.05);
}
/* ── Win Rate Badge ──────────────────────────────── */
.accum-winrate {
    display:inline-block; padding:4px 14px; border-radius:8px;
    font-size:12px; font-weight:700;
    background:rgba(0,230,118,0.1); color:#00E676;
    border:1px solid rgba(0,230,118,0.3);
}
.accum-winrate-none {
    display:inline-block; padding:4px 14px; border-radius:8px;
    font-size:11px; font-weight:600;
    background:rgba(255,255,255,0.04); color:#555;
    border:1px solid rgba(255,255,255,0.08);
}
/* ── Target / Stop Row ───────────────────────────── */
.accum-targets-row {
    display:flex; justify-content:center; gap:20px;
    margin:8px 0; font-size:13px; color:#aaa;
}
/* ── Wolf Hero Badge (only for ≥7) ───────────────── */
.accum-wolf-hero {
    background:rgba(255,215,0,0.12); border:1px solid rgba(255,215,0,0.4);
    border-radius:10px; padding:6px 16px; font-size:14px;
    font-weight:700; color:#FFD700; animation:pulse-gold 2s infinite;
    display:inline-block;
}

/* ── Pressure Gauge Bar ─────────────────────────────── */
.pressure-bar-bg {
    background:#2d303e; border-radius:10px; height:14px; width:100%; margin:10px 0;
    overflow:hidden; position:relative;
}
.pressure-bar-fill {
    height:100%; border-radius:10px; transition: width 0.5s ease;
    background: linear-gradient(90deg, #4CAF50, #FF9800, #f44336);
}
.pressure-bar-fill-high {
    animation: pressure-pulse 1.5s infinite;
}
@keyframes pressure-pulse { 0%,100%{opacity:1; filter:brightness(1);} 50%{opacity:0.8; filter:brightness(1.3);} }

/* ── Wolf Readiness Grid ────────────────────────────── */
.wolf-ready-grid {
    display:grid; grid-template-columns:1fr 1fr; gap:4px; margin:6px 0;
}
.wolf-ready-item {
    font-size:11px; padding:3px 6px; border-radius:4px; text-align:center;
}
.wolf-ready-pass { background:rgba(0,230,118,0.1); color:#00E676; }
.wolf-ready-fail { background:rgba(255,82,82,0.1); color:#FF5252; }

/* ── Expected Move ──────────────────────────────────── */
.expected-move {
    font-size:14px; color:#FFD700; font-weight:bold; margin:10px 0; text-align:center;
    padding:8px; background:rgba(255,215,0,0.08); border-radius:8px;
    border:1px solid rgba(255,215,0,0.2);
}

/* ── Market Pulse Gauge ─────────────────────────────── */
.market-pulse-box {
    background: linear-gradient(145deg, #12141a, #1a1c24);
    border: 1px solid #2d303e; border-radius: 15px;
    padding: 20px; margin: 15px 0 20px 0;
    box-shadow: 0 8px 20px rgba(0,0,0,0.4);
}
.market-pulse-title {
    text-align:center; font-size:20px; font-weight:900; color:#00d2ff;
    margin-bottom:15px; letter-spacing:1px;
}
.market-bar-container {
    display:flex; align-items:center; gap:10px; margin:10px 0 18px 0;
}
.market-bar-label { font-size:12px; font-weight:bold; white-space:nowrap; min-width:80px; }
.market-bar-track {
    flex:1; height:24px; border-radius:12px; overflow:hidden;
    display:flex; background:#1e2129; border:1px solid #2d303e;
}
.market-bar-dist { background: linear-gradient(90deg, #FF5252, #FF8A80); height:100%; transition:width 0.5s; }
.market-bar-neutral { background: #3a3d4a; height:100%; transition:width 0.5s; }
.market-bar-accum { background: linear-gradient(90deg, #69F0AE, #00E676); height:100%; transition:width 0.5s; }
.market-pulse-metrics {
    display:flex; justify-content:space-around; flex-wrap:wrap; gap:8px;
    margin:15px 0; padding:12px;
    background:rgba(0,0,0,0.3); border-radius:10px; border:1px solid rgba(255,255,255,0.05);
}
.market-pulse-metric { text-align:center; min-width:80px; }
.market-pulse-metric-label { font-size:11px; color:#888; margin-bottom:4px; }
.market-pulse-metric-value { font-size:20px; font-weight:bold; color:#fff; }
.market-verdict-bull {
    text-align:center; padding:10px 20px; border-radius:10px; font-size:17px; font-weight:900;
    background:rgba(0,230,118,0.1); color:#00E676; border:2px solid rgba(0,230,118,0.3);
    margin-top:12px;
}
.market-verdict-mid {
    text-align:center; padding:10px 20px; border-radius:10px; font-size:17px; font-weight:900;
    background:rgba(255,215,0,0.1); color:#FFD700; border:2px solid rgba(255,215,0,0.3);
    margin-top:12px;
}
.market-verdict-warn {
    text-align:center; padding:10px 20px; border-radius:10px; font-size:17px; font-weight:900;
    background:rgba(255,152,0,0.1); color:#FF9800; border:2px solid rgba(255,152,0,0.3);
    margin-top:12px;
}
.market-verdict-bear {
    text-align:center; padding:10px 20px; border-radius:10px; font-size:17px; font-weight:900;
    background:rgba(255,82,82,0.1); color:#FF5252; border:2px solid rgba(255,82,82,0.3);
    margin-top:12px; animation: pressure-pulse 2s infinite;
}

/* ── Breadth Chart (QAFAH-Style) ──────────────────── */
.breadth-chart-box {
    background: linear-gradient(145deg, #12141a, #1a1c24);
    border: 1px solid #2d303e; border-radius: 15px;
    padding: 16px; margin: 5px 0 20px 0;
    box-shadow: 0 6px 16px rgba(0,0,0,0.3);
}
.breadth-stats-row {
    display: flex; justify-content: space-around; flex-wrap: wrap;
    gap: 8px; margin-bottom: 12px;
    padding: 12px; background: rgba(0,0,0,0.3);
    border-radius: 10px; border: 1px solid rgba(255,255,255,0.05);
}
.breadth-stat-item { text-align: center; min-width: 80px; }
.breadth-stat-label { font-size: 11px; color: #888; margin-bottom: 4px; }
.breadth-stat-value { font-size: 22px; font-weight: bold; color: #fff; }
.breadth-stat-sub { font-size: 12px; color: #555; font-weight: normal; }
.breadth-verdict-bull {
    text-align:center; padding:8px 16px; border-radius:10px; font-size:15px; font-weight:900;
    background:rgba(0,230,118,0.1); color:#00E676; border:1px solid rgba(0,230,118,0.3);
}
.breadth-verdict-mid {
    text-align:center; padding:8px 16px; border-radius:10px; font-size:15px; font-weight:900;
    background:rgba(255,215,0,0.1); color:#FFD700; border:1px solid rgba(255,215,0,0.3);
}
.breadth-verdict-warn {
    text-align:center; padding:8px 16px; border-radius:10px; font-size:15px; font-weight:900;
    background:rgba(255,152,0,0.1); color:#FF9800; border:1px solid rgba(255,152,0,0.3);
}
.breadth-verdict-bear {
    text-align:center; padding:8px 16px; border-radius:10px; font-size:15px; font-weight:900;
    background:rgba(255,82,82,0.1); color:#FF5252; border:1px solid rgba(255,82,82,0.3);
    animation: pressure-pulse 2s infinite;
}

/* ── Backtest Cards ──────────────────────────────── */
.backtest-cards-row {
    display:flex; gap:15px; justify-content:center; flex-wrap:wrap;
    margin:20px 0;
}
.backtest-summary-card {
    background:linear-gradient(135deg, #1a1c24 0%, #15171e 100%);
    border:1px solid #2d303e; border-radius:14px;
    padding:20px 24px; text-align:center; min-width:150px; flex:1;
    box-shadow:0 4px 10px rgba(0,0,0,0.3); transition:all 0.3s ease;
}
.backtest-summary-card:hover {
    transform:translateY(-4px); box-shadow:0 6px 15px rgba(0,210,255,0.15);
}
.backtest-win { color:#00E676; font-weight:700; }
.backtest-lose { color:#FF5252; font-weight:700; }

/* ══════════════════════════════════════════════════════
   📱 MOBILE RESPONSIVE — iPhone / Small Screens
   ══════════════════════════════════════════════════════ */

/* ── Tablet (≤ 768px) ─────────────────────────────── */
@media (max-width: 768px) {
    /* CRITICAL: Override Streamlit's inline column styles */
    [data-testid="column"] { width:100% !important; flex:1 1 100% !important; min-width:0 !important; }
    .stHorizontalBlock { flex-wrap:wrap !important; gap:8px !important; }

    /* Cards: 2 columns on tablet */
    .vip-card, .accum-card { width:48%; min-width:0; padding:18px 14px; }
    .wolf-card { width:100%; min-width:0; padding:18px 14px; }
    .wolf-filter-grid { grid-template-columns: repeat(3, 1fr); gap:6px; }
    .vip-container, .wolf-container, .accum-container { gap:12px; }
    .vip-title, .wolf-title { font-size:20px; }
    .vip-price { font-size:26px; }

    /* Tables scroll horizontally */
    .whale-table { display:block; overflow-x:auto; white-space:nowrap; -webkit-overflow-scrolling:touch; }

    /* Backtest cards: 2 columns on tablet */
    .backtest-cards-row { gap:10px; }
    .backtest-summary-card { min-width:140px; padding:16px 18px; }

    /* Plotly & iframes responsive */
    iframe { max-width:100% !important; }
    .stPlotlyChart { overflow-x:auto !important; -webkit-overflow-scrolling:touch; }
}

/* ── Phone (≤ 480px) ──────────────────────────────── */
@media (max-width: 480px) {
    /* CRITICAL: Force Streamlit columns to stack vertically */
    [data-testid="column"] {
        width:100% !important; flex:1 1 100% !important;
        min-width:0 !important; max-width:100% !important;
    }
    .stHorizontalBlock {
        flex-direction:column !important; gap:6px !important;
    }
    /* Main content: no overflow */
    .main .block-container {
        padding-left:8px !important; padding-right:8px !important;
        max-width:100% !important;
    }
    section[data-testid="stSidebar"] { display:none !important; }

    /* ALL cards: single column, full width */
    .vip-card, .wolf-card, .accum-card {
        width:100% !important; min-width:0 !important;
        padding:16px 12px; margin-bottom:12px;
    }
    .vip-container, .wolf-container, .accum-container {
        flex-direction:column; gap:10px; padding:0 4px;
    }

    /* Typography shrink */
    .vip-title, .wolf-title { font-size:18px; }
    .vip-price { font-size:24px; }
    .vip-score { font-size:15px; padding:6px 14px; }
    .vip-details { flex-direction:column; gap:8px; font-size:13px; padding:10px; }
    .vip-target, .vip-stop { font-size:15px; }
    .accum-metric-value { font-size:14px; }
    .accum-metric-label { font-size:10px; }
    .accum-metrics { padding:8px; gap:4px; }

    /* Wolf filter grid: 2 columns on phone */
    .wolf-filter-grid { grid-template-columns: 1fr 1fr; gap:4px; padding:10px; }
    .wolf-filter-item { font-size:11px; padding:4px 6px; }

    /* Wolf readiness grid */
    .wolf-ready-grid { grid-template-columns: 1fr 1fr; gap:3px; }
    .wolf-ready-item { font-size:10px; padding:2px 4px; }

    /* Phase badge smaller */
    .accum-phase-badge { font-size:11px; padding:3px 10px; }

    /* Bars thinner */
    .accum-bar-bg, .pressure-bar-bg { height:10px; margin:6px 0; }

    /* Expected move */
    .expected-move { font-size:12px; padding:6px; }

    /* Two-tier card mobile */
    .accum-targets-row { gap:10px; font-size:12px; }
    .accum-wolf-hero { font-size:12px; padding:4px 10px; }
    .accum-winrate, .accum-winrate-none { font-size:11px; padding:3px 10px; }
    .accum-tier2 { padding:8px; }
    .accum-details-btn { font-size:12px; }

    /* Tables: horizontal scroll + smaller font */
    .whale-table { display:block; overflow-x:auto; white-space:nowrap; font-size:12px; -webkit-overflow-scrolling:touch; }
    .whale-table th, .whale-table td { padding:8px 6px; }

    /* Metric containers */
    div[data-testid="metric-container"] { padding:8px 10px; font-size:13px; }
    div[data-testid="metric-container"] [data-testid="stMetricLabel"] { font-size:12px !important; }

    /* Tabs: scrollable horizontally */
    .stTabs [data-baseweb="tab-list"] {
        gap:4px; overflow-x:auto; -webkit-overflow-scrolling:touch;
        flex-wrap:nowrap !important; scrollbar-width:none;
    }
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display:none; }
    .stTabs [data-baseweb="tab"] {
        font-size:12px; height:36px; padding:4px 8px;
        white-space:nowrap; flex-shrink:0;
    }

    /* News cards */
    .news-card { padding:14px 10px; }

    /* Search container */
    .search-container { padding:12px; }

    /* Badges */
    .bo-badge { font-size:10px; padding:3px 6px; }
    .sector-tag { font-size:10px; padding:2px 6px; }
    .kw-tag { font-size:10px; padding:3px 6px; }

    /* Hidden icons on mobile (save space) */
    .vip-crown, .wolf-icon, .accum-icon { display:none; }

    /* Confluence */
    .confluence-stars { font-size:16px; }
    .confluence-badge { font-size:10px; padding:3px 8px; }

    /* Plotly & iframes responsive */
    iframe { max-width:100% !important; height:auto !important; min-height:300px; }
    .stPlotlyChart > div { overflow-x:auto !important; -webkit-overflow-scrolling:touch; }

    /* Market Pulse responsive */
    .market-pulse-box { padding:12px; margin:10px 0; }
    .market-pulse-title { font-size:16px; }
    .market-bar-container { flex-direction:column; gap:6px; }
    .market-bar-label { text-align:center; min-width:0; font-size:11px; }
    .market-bar-track { height:20px; }
    .market-pulse-metrics { gap:4px; padding:8px; }
    .market-pulse-metric { min-width:60px; }
    .market-pulse-metric-value { font-size:16px; }
    .market-pulse-metric-label { font-size:10px; }
    .market-verdict-bull, .market-verdict-mid, .market-verdict-warn, .market-verdict-bear {
        font-size:14px; padding:8px 12px;
    }

    /* Breadth Chart responsive */
    .breadth-chart-box { padding:10px; margin:8px 0 12px 0; }
    .breadth-stats-row { gap:4px; padding:8px; }
    .breadth-stat-item { min-width:60px; }
    .breadth-stat-value { font-size:18px; }
    .breadth-stat-label { font-size:10px; }
    .breadth-stat-sub { font-size:10px; }
    .breadth-verdict-bull, .breadth-verdict-mid, .breadth-verdict-warn, .breadth-verdict-bear {
        font-size:13px; padding:6px 10px;
    }

    /* Backtest cards: stack on phone */
    .backtest-cards-row { flex-direction:column; gap:10px; padding:0 4px; }
    .backtest-summary-card { min-width:0; width:100% !important; padding:14px 12px; }

    /* Selectbox / inputs */
    .stSelectbox, .stTextInput, .stNumberInput { font-size:14px !important; }
}
</style>
"""

LOGO_HTML = """
<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 5px; margin-top: -10px; padding: 0 10px;">
    <svg width="90" height="90" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" style="max-width:70px; height:auto;">
        <defs>
            <linearGradient id="neonBlue" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#00d2ff" /><stop offset="100%" stop-color="#3a7bd5" />
            </linearGradient>
            <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#ffd700" /><stop offset="100%" stop-color="#ffaa00" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
        </defs>
        <path d="M 50,5 L 90,35 L 50,95 L 10,35 Z" fill="rgba(0, 210, 255, 0.05)" stroke="url(#neonBlue)" stroke-width="2.5" filter="url(#glow)" stroke-linejoin="round"/>
        <path d="M 20,35 L 50,60 L 80,35" fill="none" stroke="url(#neonBlue)" stroke-width="2" opacity="0.6" stroke-linejoin="round"/>
        <path d="M 50,5 L 50,60" fill="none" stroke="url(#neonBlue)" stroke-width="2" opacity="0.6"/>
        <path d="M 30,75 L 75,25 M 55,25 L 75,25 L 75,45" fill="none" stroke="url(#goldGrad)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
    </svg>
    <div style="font-family: 'Arial', sans-serif; text-align: center; margin-top: 15px; line-height: 1;">
        <span style="font-size: clamp(24px, 6vw, 42px); font-weight: 900; letter-spacing: 3px; color: #ffffff; text-shadow: 0 0 10px rgba(255,255,255,0.1);">MASA</span>
        <span style="font-size: clamp(24px, 6vw, 42px); font-weight: 300; letter-spacing: 3px; color: #00d2ff; text-shadow: 0 0 15px rgba(0,210,255,0.4);"> QUANT</span>
    </div>
    <div style="color: #888; font-size: clamp(9px, 2.5vw, 13px); letter-spacing: 2px; font-weight: bold; margin-top: 8px; text-align:center;">
        INSTITUTIONAL ALGORITHMIC TRADING <span style="color:#ffd700">V95 PRO</span>
    </div>
</div>
"""

CLOCK_HTML = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@700&display=swap');
body { margin: 0; padding: 0; background-color: transparent; display: flex;
       justify-content: center; align-items: center; height: 100%; font-family: 'Tajawal', sans-serif;}
.clock-wrapper { background: linear-gradient(145deg, #15171e, #1a1c24); border: 1px solid #2d303e;
    padding: 6px 15px; border-radius: 50px; box-shadow: 0 4px 15px rgba(0, 210, 255, 0.1);
    color: #aaa; font-size: clamp(11px, 2.5vw, 15px); font-weight: bold; display: flex; align-items: center; gap: 6px;
    border-bottom: 2px solid #00d2ff; flex-wrap:wrap; justify-content:center;}
.time-pulse { color: #00d2ff; font-size: clamp(13px, 3vw, 18px); letter-spacing: 1px;
              font-family: 'Courier New', monospace; text-shadow: 0 0 10px rgba(0, 210, 255, 0.5);}
.date-text { color: #e0e0e0;}
</style>
<div class="clock-wrapper" dir="rtl">
    <span>&#x1f54b; &#x062a;&#x0648;&#x0642;&#x064a;&#x062a; &#x0645;&#x0643;&#x0629; (24H):</span>
    <span class="time-pulse" id="live-time">--:--:--</span>
    <span class="date-text" id="live-date"></span>
</div>
<script>
    function updateClock() {
        var now = new Date();
        var timeOpts = { timeZone: 'Asia/Riyadh', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' };
        var dateOpts = { timeZone: 'Asia/Riyadh', year: 'numeric', month: 'short', day: 'numeric' };
        document.getElementById('live-time').innerText = now.toLocaleTimeString('en-GB', timeOpts);
        document.getElementById('live-date').innerText = ' | ' + now.toLocaleDateString('ar-SA', dateOpts);
    }
    setInterval(updateClock, 1000);
    updateClock();
</script>
"""
