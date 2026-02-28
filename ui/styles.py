CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Tajawal', sans-serif !important; }
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
[data-testid="collapsedControl"] { display: none; }
</style>
"""

LOGO_HTML = """
<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 5px; margin-top: -10px;">
    <svg width="90" height="90" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
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
        <span style="font-size: 42px; font-weight: 900; letter-spacing: 5px; color: #ffffff; text-shadow: 0 0 10px rgba(255,255,255,0.1);">MASA</span>
        <span style="font-size: 42px; font-weight: 300; letter-spacing: 5px; color: #00d2ff; text-shadow: 0 0 15px rgba(0,210,255,0.4);"> QUANT</span>
    </div>
    <div style="color: #888; font-size: 13px; letter-spacing: 3px; font-weight: bold; margin-top: 8px;">
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
    padding: 8px 25px; border-radius: 50px; box-shadow: 0 4px 15px rgba(0, 210, 255, 0.1);
    color: #aaa; font-size: 15px; font-weight: bold; display: flex; align-items: center; gap: 10px;
    border-bottom: 2px solid #00d2ff;}
.time-pulse { color: #00d2ff; font-size: 18px; letter-spacing: 2px;
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
