import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import requests
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.utils import (
    init_db, sanitize_text, format_price, save_to_tracker,
    DB_FILE, get_now, get_today_str, safe_div,
)
from core.indicators import (
    calculate_zero_reflection, compute_rsi, compute_atr,
    compute_vwap, compute_direction_counter,
)
from core.scanner import scan_market, get_macro_status, get_stock_data
from data.markets import (
    SAUDI_NAMES, US_NAMES, FX_NAMES, CRYPTO_NAMES, get_stock_name,
)
from ui.styles import CUSTOM_CSS, LOGO_HTML, CLOCK_HTML
from ui.formatters import safe_color_table, style_live_tracker

warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="MASA QUANT | V95 PRO",
    layout="wide",
    page_icon="💎",
)

init_db()

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown(LOGO_HTML, unsafe_allow_html=True)
components.html(CLOCK_HTML, height=55)
st.markdown("<br>", unsafe_allow_html=True)

if 'tg_sent' not in st.session_state:
    st.session_state.tg_sent = set()

with st.expander("⚙️ لوحة التحكم والإعدادات (المحفظة وتليجرام)", expanded=False):
    c_set1, c_set2 = st.columns(2)
    with c_set1:
        st.markdown(
            "<h4 style='color:#00d2ff; text-align:right;'>⚙️ إدارة المخاطر</h4>",
            unsafe_allow_html=True
        )
        capital = st.number_input(
            "💵 حجم المحفظة الكلي:", min_value=1000.0,
            value=100000.0, step=1000.0
        )
        risk_pct = st.number_input(
            "⚖️ نسبة المخاطرة للصفقة (%):",
            min_value=0.1, max_value=10.0, value=1.0, step=0.1
        )
    with c_set2:
        st.markdown(
            "<h4 style='color:#00E676; text-align:right;'>🤖 إشعارات التليجرام</h4>",
            unsafe_allow_html=True
        )
        tg_token = st.text_input("Bot Token", type="password")
        tg_chat = st.text_input("Chat ID")


INTERVAL_MAP = {"يومي (1D)": "1d", "ساعة (60m)": "60m", "15 دقيقة (15m)": "15m"}
PERIOD_SCAN = {"1d": "2y", "60m": "3mo", "15m": "1mo"}
PERIOD_UI = {"1d": "2y", "60m": "6mo", "15m": "60d"}

st.markdown("<div class='search-container'>", unsafe_allow_html=True)

col_m1, col_m2 = st.columns([1, 1])
with col_m1:
    market_choice = st.radio(
        "🌐 الأسواق:",
        ["السعودي 🇸🇦", "الأمريكي 🇺🇸", "الفوركس 💱", "الكريبتو ₿"],
        horizontal=True,
    )
with col_m2:
    tf_choice = st.radio(
        "⏳ الفاصل الزمني:",
        ["يومي (1D)", "ساعة (60m)", "15 دقيقة (15m)"],
        horizontal=True,
    )

selected_interval = INTERVAL_MAP[tf_choice]
selected_period_scan = PERIOD_SCAN[selected_interval]
selected_period_ui = PERIOD_UI[selected_interval]
tf_label_name = tf_choice.replace(" (1D)", "").replace(" (60m)", "").replace(" (15m)", "")
lbl = "أيام" if selected_interval == "1d" else "شموع"
col_change_name = 'تغير 1 يوم' if selected_interval == '1d' else 'تغير 1 شمعة'


def _build_selector(names_dict, label, default_key=None, suffix=""):
    display_map = {}
    for tk, name in names_dict.items():
        clean_tk = tk.replace('.SR', '').replace('=X', '').replace('-USD', '')
        display_map[f"{name} ({clean_tk}){suffix}"] = tk
    options = sorted(display_map.keys())
    default_idx = 0
    if default_key:
        for i, opt in enumerate(options):
            if default_key in opt:
                default_idx = i
                break
    selected = st.selectbox(label, options, index=default_idx, label_visibility="collapsed")
    return display_map[selected], selected.split(" (")[0]


col_empty1, col_search1, col_search2, col_empty2 = st.columns([1, 3, 1, 1])

with col_search1:
    if "السعودي" in market_choice:
        ticker, display_name = _build_selector(SAUDI_NAMES, "🎯 اختر السهم:", "الراجحي")
        selected_watchlist = list(SAUDI_NAMES.keys())
        currency = "ريال"
    elif "الأمريكي" in market_choice:
        ticker, display_name = _build_selector(US_NAMES, "🎯 اختر السهم:", "NVIDIA")
        selected_watchlist = list(US_NAMES.keys())
        currency = "$"
    elif "الفوركس" in market_choice:
        ticker, display_name = _build_selector(FX_NAMES, "🎯 اختر الزوج:")
        selected_watchlist = list(FX_NAMES.keys())
        currency = "سعر"
    else:
        ticker, display_name = _build_selector(CRYPTO_NAMES, "🎯 اختر العملة:")
        selected_watchlist = list(CRYPTO_NAMES.keys())
        currency = "$"

with col_search2:
    analyze_btn = st.button("استخراج الفرص 💎", use_container_width=True, type="primary")

macro_status, macro_name, macro_pct, macro_price = get_macro_status(market_choice)

if "الفوركس" in market_choice:
    bg_m, txt_m, bord_m = "rgba(33, 150, 243, 0.1)", "#00d2ff", "#00d2ff"
    msg_m = "سوق العملات لامركزي (درع الماكرو مخصص لمراقبة قوة الدولار فقط 💱)"
elif macro_status == "إيجابي ☀️":
    bg_m, txt_m, bord_m = "rgba(0, 230, 118, 0.1)", "#00E676", "#00E676"
    msg_m = "الرادار الهجومي مفتوح 🚀 (الاختراقات مدعومة من سيولة السوق الكلي)"
elif macro_status == "سلبي ⛈️":
    bg_m, txt_m, bord_m = "rgba(255, 82, 82, 0.1)", "#FF5252", "#FF5252"
    msg_m = "الإغلاق المطلق مُفعل 🔒 (حظر التوصيات باستثناء [قيعان زيرو] أو [السماء الزرقاء 🌌])"
else:
    bg_m, txt_m, bord_m = "rgba(255, 215, 0, 0.1)", "#FFD700", "#FFD700"
    msg_m = "تذبذب وحيرة ⚖️ (التركيز على المضاربة السريعة)"

st.markdown(f"""
<div style='background-color: {bg_m}; border: 1px solid {bord_m}; padding: 15px;
     border-radius: 10px; margin-top: 15px; text-align: center;
     box-shadow: 0 4px 10px rgba(0,0,0,0.3);'>
    <h4 style='color: {txt_m}; margin: 0; font-weight:900;'>
        🛡️ درع السوق الكلي (The Macro Shield)
    </h4>
    <div style='font-size: 18px; color: white; margin-top: 5px;'>
        المؤشر القيادي: <b style='color:#00d2ff;'>{sanitize_text(macro_name)}</b> |
        الإغلاق: <b>{format_price(macro_price, "^GSPC")} ({macro_pct:+.2f}%)</b> |
        الطقس: <b>{macro_status}</b>
    </div>
    <div style='font-size: 15px; color: {txt_m}; margin-top: 5px; font-weight:bold;'>{msg_m}</div>
</div>
""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)


if analyze_btn:
    with st.spinner(f"⚡ جاري مسح السوق وجلب بيانات ({display_name})..."):
        df_loads, df_alerts, df_ai_picks = scan_market(
            watchlist_tuple=tuple(selected_watchlist),
            period=selected_period_scan,
            interval=selected_interval,
            lbl=lbl,
            tf_label=tf_label_name,
            macro_status=macro_status,
        )
        st.session_state['scan_results'] = {
            'df_loads': df_loads,
            'df_alerts': df_alerts,
            'df_ai_picks': df_ai_picks,
        }

    df = get_stock_data(ticker, selected_period_ui, selected_interval)

    if df is None or df.empty:
        st.warning(
            f"⚠️ تعذر جلب بيانات ({display_name}). يرجى الانتظار والمحاولة مرة أخرى."
        )
    else:
        st.session_state['chart_data'] = df
        st.session_state['chart_ticker'] = ticker
        st.session_state['chart_display'] = display_name

scan_results = st.session_state.get('scan_results')
df = st.session_state.get('chart_data')
chart_ticker = st.session_state.get('chart_ticker', ticker)
chart_display = st.session_state.get('chart_display', display_name)

if scan_results and df is not None and not df.empty:
    df_loads = scan_results['df_loads']
    df_alerts = scan_results['df_alerts']
    df_ai_picks = scan_results['df_ai_picks']

    is_fx_main = "=X" in chart_ticker
    is_crypto_main = "-USD" in chart_ticker

    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df.get('Volume', pd.Series(np.zeros(len(close)), index=close.index))

    df['SMA_50'] = close.rolling(50).mean()
    df['SMA_200'] = close.rolling(200).mean() if len(close) >= 200 else close.rolling(50).mean()

    if vol.sum() == 0 or is_fx_main:
        df['VWAP'] = close.rolling(20).mean()
    else:
        df['VWAP'] = compute_vwap(high, low, close, vol)

    df['High_3D'] = high.rolling(3).max().shift(1)
    df['Low_3D'] = low.rolling(3).min().shift(1)
    df['High_4D'] = high.rolling(4).max().shift(1)
    df['Low_4D'] = low.rolling(4).min().shift(1)
    df['High_10D'] = high.rolling(10).max().shift(1)
    df['Low_10D'] = low.rolling(10).min().shift(1)
    df['High_15D'] = high.rolling(15).max().shift(1)
    df['Low_15D'] = low.rolling(15).min().shift(1)

    df['1d_%'] = close.pct_change(1) * 100
    df['3d_%'] = close.pct_change(3) * 100
    df['5d_%'] = close.pct_change(5) * 100
    df['10d_%'] = close.pct_change(10) * 100

    df['Counter'] = compute_direction_counter(close)
    df['RSI'] = compute_rsi(close)

    zr1_h, zr1_l = calculate_zero_reflection(high, low, 400, 25)
    zr2_h, zr2_l = calculate_zero_reflection(high, low, 300, 30)
    df['ZR_High'] = zr1_h
    df['ZR_Low'] = zr1_l
    df['ZR2_High'] = zr2_h
    df['ZR2_Low'] = zr2_l

    last_close = close.iloc[-1]
    prev_close = close.iloc[-2] if len(close) > 1 else last_close
    pct_change = safe_div((last_close - prev_close) * 100, prev_close, 0)

    last_sma200 = df['SMA_200'].iloc[-1]
    last_sma50 = df['SMA_50'].iloc[-1]
    last_zr_high = df['ZR_High'].iloc[-1]
    last_zr_low = df['ZR_Low'].iloc[-1]

    if is_fx_main or is_crypto_main:
        vol_status, vol_color = "سوق سيولة عالمية", "💱"
    else:
        last_vol = vol.iloc[-1] if pd.notna(vol.iloc[-1]) and vol.iloc[-1] > 0 else 1e6
        avg_vol10 = vol.rolling(10).mean().iloc[-1]
        if pd.isna(avg_vol10) or avg_vol10 <= 0:
            avg_vol10 = 1e6
        accel = safe_div(last_vol, avg_vol10, 1.0)
        if accel >= 1.2:
            vol_status, vol_color = "تسارع سيولة", "🔥"
        elif last_vol > avg_vol10:
            vol_status, vol_color = "سيولة جيدة", "📈"
        else:
            vol_status, vol_color = "سيولة ضعيفة", "❄️"

    if pd.notna(last_sma200) and pd.notna(last_sma50):
        if last_close > last_sma200 and last_close > last_sma50:
            trend, trend_color = "مسار صاعد 🚀", "🟢"
        elif last_close < last_sma200 and last_close < last_sma50:
            trend, trend_color = "مسار هابط 🔴", "🔴"
        else:
            trend, trend_color = "تذبذب (حيرة) ⚖️", "🟡"
    else:
        trend, trend_color = "جاري الحساب...", "⚪"

    if pd.notna(last_zr_high) and last_close > last_zr_high:
        zr_status, zr_color = "سماء زرقاء", "🌌"
    elif pd.notna(last_zr_high) and last_close >= last_zr_high * 0.98:
        zr_status, zr_color = "يختبر سقف زيرو", "⚠️"
    elif pd.notna(last_zr_low) and last_close <= last_zr_low * 1.05:
        zr_status, zr_color = "يختبر قاع زيرو", "💎"
    else:
        zr_status, zr_color = "في منتصف القناة", "⚖️"

    st.markdown(
        f"### 🤖 قراءة استراتيجية ماسة لـ ({chart_display}) - فاصل [{tf_label_name}]:"
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"الإغلاق ({currency})", format_price(last_close, chart_ticker), f"{pct_change:.2f}%")
    m2.metric(f"الترند {trend_color}", trend)
    m3.metric(f"السيولة {vol_color}", vol_status)
    m4.metric(f"القناة {zr_color}", zr_status)
    st.markdown("<br>", unsafe_allow_html=True)

    tab_vip, tab_whales, tab_ai, tab1, tab5, tab6, tab_backtest, tab_track, tab2, tab3, tab4 = st.tabs([
        "👑 VIP ماسة", "🐋 رادار الحيتان", "🧠 التوصيات",
        "🎯 الاختراقات", "🗂️ ماسح السوق", "🚨 التنبيهات",
        "⏳ الباك تيست", "📂 المراقبة", "🌐 TradingView",
        "📊 الشارت", "📋 البيانات"
    ])

    # ═══════════════════════════════════════════════════════════
    # TAB: VIP
    # ═══════════════════════════════════════════════════════════
    with tab_vip:
        if not df_ai_picks.empty:
            df_vip_full = pd.DataFrame(df_ai_picks)
            mask = (
                (df_vip_full['raw_score'] >= 80)
                & (df_vip_full['raw_mom'] >= 75)
                & (~df_vip_full['raw_events'].str.contains('كسر|هابط|تصحيح|🔻'))
            )
            df_vip = df_vip_full[mask].sort_values(
                by=['raw_score', 'raw_mom'], ascending=[False, False]
            ).head(3)

            if not df_vip.empty:
                st.markdown(
                    "<h3 style='text-align: center; color: #ffd700; font-weight: 900;'>"
                    "👑 الصندوق الأسود: أقوى الفرص الاستثمارية الآن</h3>",
                    unsafe_allow_html=True
                )
                col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
                with col_b2:
                    market_clean = sanitize_text(market_choice.split()[0])
                    if st.button("💾 حفظ هذه الفرص في محفظة المراقبة", use_container_width=True):
                        save_to_tracker(df_vip, market_clean, tf_label_name)
                        st.success("✅ تم الحفظ! راجع تبويب (المراقبة 📂)")

                today_str = get_today_str()
                cards_html = "<div class='vip-container'>"
                for _, row in df_vip.iterrows():
                    risk_amount = capital * (risk_pct / 100)
                    risk_per_share = float(row['raw_price']) - float(row['raw_sl'])

                    if risk_per_share > 0:
                        if "=X" in row['الرمز']:
                            shares_str = "رافعة (Lot)"
                            pos_value_str = "تداول هامشي 💱"
                        elif "-USD" in row['الرمز']:
                            shares = risk_amount / risk_per_share
                            pos_value = shares * float(row['raw_price'])
                            pos_value_str = f"{pos_value:,.2f} $"
                            shares_str = f"{shares:.4f} حبة"
                        else:
                            shares = int(risk_amount / risk_per_share)
                            pos_value = shares * float(row['raw_price'])
                            pos_value_str = f"{pos_value:,.2f} {currency}"
                            shares_str = f"{shares:,} سهم"
                    else:
                        shares_str, pos_value_str = "0", "0"

                    alert_id = f"{today_str}_{row['الرمز']}_{selected_interval}"
                    if tg_token and tg_chat and alert_id not in st.session_state.tg_sent:
                        msg = (
                            f"🚨 *Masa VIP Alert!* 💎\n\n"
                            f"📌 *Asset:* {row['الشركة']} ({row['الرمز']})\n"
                            f"⏱️ *Timeframe:* {tf_choice}\n"
                            f"💰 *Price:* {row['السعر']}\n"
                            f"🎯 *Target:* {row['الهدف 🎯']}\n"
                            f"🛡️ *SL (ATR):* {row['الوقف 🛡️']}\n"
                            f"⚖️ *R:R:* 1:{row['raw_rr']:.1f}\n\n"
                            f"🤖 _Masa Quant System V95_"
                        )
                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                                data={"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"},
                                timeout=10,
                            )
                            st.session_state.tg_sent.add(alert_id)
                        except requests.RequestException:
                            pass

                    rr_disp = f"⚖️ العائد للمخاطرة R:R = 1 : {row['raw_rr']:.1f}"
                    clean_name = sanitize_text(str(row['الشركة']))
                    cards_html += (
                        f"<div class='vip-card'>"
                        f"<div class='vip-crown'>👑</div>"
                        f"<div class='vip-title'>{clean_name}</div>"
                        f"<div class='vip-time'>{str(row['raw_time'])}</div><br>"
                        f"<div class='vip-rr'>{rr_disp}</div>"
                        f"<div class='vip-price'>{row['السعر']} "
                        f"<span style='font-size:16px; color:#aaa;'>{currency}</span></div>"
                        f"<div class='vip-details'>"
                        f"<div>الهدف 🎯<br><span class='vip-target'>{row['الهدف 🎯']}</span></div>"
                        f"<div>الوقف (ATR) 🛡️<br><span class='vip-stop'>{row['الوقف 🛡️']}</span></div>"
                        f"</div>"
                        f"<div style='margin-bottom: 15px;'>{row['الحالة اللحظية ⚡']}</div>"
                        f"<div style='background:rgba(33,150,243,0.1); padding:10px; border-radius:8px; "
                        f"border:1px solid rgba(33,150,243,0.3); font-size:14px; margin-bottom:15px; color:#00d2ff;'>"
                        f"📦 الكمية/العقد: <b>{shares_str}</b><br>💵 التكلفة: <b>{pos_value_str}</b></div>"
                        f"<div class='vip-score'>التقييم: {row['raw_score']}/100</div>"
                        f"</div>"
                    )
                cards_html += "</div>"
                st.markdown(cards_html, unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div class='empty-box'>👑 الصندوق مغلق حالياً!<br><br>"
                    "محرك الصناديق يمنع الصفقات المعاكسة للفريم الأكبر أو التي لا تحقق عائداً مناسباً. 🔒</div>",
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                "<div class='empty-box'>السوق لا يحتوي على فرص حالياً.</div>",
                unsafe_allow_html=True
            )

    # ═══════════════════════════════════════════════════════════
    # TAB: Whales
    # ═══════════════════════════════════════════════════════════
    with tab_whales:
        st.markdown(
            "<h3 style='text-align: center; color: #00d2ff; font-weight: bold;'>"
            "🧲 رادار تدفق السيولة (أثر الحيتان)</h3>",
            unsafe_allow_html=True
        )
        if not df_loads.empty:
            df_w = pd.DataFrame(df_loads).copy()
            df_w['acc_score'] = df_w['raw_3d'] + df_w['raw_5d'] + df_w['raw_10d']
            df_acc = df_w[(df_w['raw_3d'] > 0) & (df_w['raw_5d'] > 0) & (df_w['raw_10d'] > 0)]
            df_acc = df_acc.sort_values('acc_score', ascending=False).head(10)
            df_dist = df_w[(df_w['raw_3d'] < 0) & (df_w['raw_5d'] < 0) & (df_w['raw_10d'] < 0)]
            df_dist = df_dist.sort_values('acc_score', ascending=True).head(10)

            col_w1, col_w2 = st.columns(2)
            with col_w1:
                st.markdown(
                    "<div style='background:rgba(0,230,118,0.15); border:1px solid #00E676; "
                    "padding:10px; text-align:center; border-radius:8px; margin-bottom:10px;'>"
                    "<h4 style='color:#00E676; margin:0;'>🟩 أقوى 10 أصول (تجميع مؤسساتي)</h4></div>",
                    unsafe_allow_html=True
                )
                if not df_acc.empty:
                    acc_html = (
                        "<table class='whale-table whale-acc' dir='rtl'>"
                        "<tr><th>الأصل</th><th>3 فترات</th><th>5 فترات</th>"
                        "<th>10 فترات</th><th>الحالة</th></tr>"
                    )
                    for _, r in df_acc.iterrows():
                        n = sanitize_text(str(r['الشركة']))
                        acc_html += (
                            f"<tr><td style='color:#00d2ff;'>{n}</td>"
                            f"<td><span style='color:#00E676;'>+{r['raw_3d']:.2f}%</span></td>"
                            f"<td><span style='color:#00E676;'>+{r['raw_5d']:.2f}%</span></td>"
                            f"<td><span style='color:#00E676;'>+{r['raw_10d']:.2f}%</span></td>"
                            f"<td>🔥 تجميع</td></tr>"
                        )
                    acc_html += "</table>"
                    st.markdown(acc_html, unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<div class='empty-box' style='border-color:#00E676;'>"
                        "لا توجد عمليات تجميع واضحة حالياً.</div>",
                        unsafe_allow_html=True
                    )

            with col_w2:
                st.markdown(
                    "<div style='background:rgba(255,82,82,0.15); border:1px solid #FF5252; "
                    "padding:10px; text-align:center; border-radius:8px; margin-bottom:10px;'>"
                    "<h4 style='color:#FF5252; margin:0;'>🟥 أضعف 10 أصول (تصريف دموي)</h4></div>",
                    unsafe_allow_html=True
                )
                if not df_dist.empty:
                    dist_html = (
                        "<table class='whale-table whale-dist' dir='rtl'>"
                        "<tr><th>الأصل</th><th>3 فترات</th><th>5 فترات</th>"
                        "<th>10 فترات</th><th>الحالة</th></tr>"
                    )
                    for _, r in df_dist.iterrows():
                        n = sanitize_text(str(r['الشركة']))
                        dist_html += (
                            f"<tr><td style='color:#00d2ff;'>{n}</td>"
                            f"<td><span style='color:#FF5252;'>{r['raw_3d']:.2f}%</span></td>"
                            f"<td><span style='color:#FF5252;'>{r['raw_5d']:.2f}%</span></td>"
                            f"<td><span style='color:#FF5252;'>{r['raw_10d']:.2f}%</span></td>"
                            f"<td>🩸 تصريف</td></tr>"
                        )
                    dist_html += "</table>"
                    st.markdown(dist_html, unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<div class='empty-box' style='border-color:#FF5252;'>"
                        "لا توجد عمليات تصريف واضحة حالياً.</div>",
                        unsafe_allow_html=True
                    )
        else:
            st.info("لا توجد بيانات كافية.")

    # ═══════════════════════════════════════════════════════════
    # TAB: AI Recommendations
    # ═══════════════════════════════════════════════════════════
    with tab_ai:
        st.markdown(
            "<h3 style='text-align: center; color: #00d2ff; margin-bottom: 20px;'>"
            "🧠 تقرير أشعة إكس (تحليل الخوارزمية المفصل)</h3>",
            unsafe_allow_html=True
        )
        if not df_ai_picks.empty:
            df_ai_disp = pd.DataFrame(df_ai_picks).sort_values("Score 💯", ascending=False)
            for _, row in df_ai_disp.iterrows():
                safe_reasons = [sanitize_text(str(r)) for r in row['raw_reasons']]
                reasons_html = "".join(
                    f"<li style='font-size:14px; color:#ddd; margin-bottom:8px; "
                    f"line-height:1.6;'>{r}</li>" for r in safe_reasons
                )

                c_name = sanitize_text(str(row['الشركة']))
                c_score = str(row['Score 💯'])
                c_dec = sanitize_text(str(row['التوصية 🚦']))
                c_col = str(row['اللون'])

                try:
                    st.markdown(f"""
                    <div style='background: linear-gradient(145deg, #1a1c24, #12141a);
                         border: 1px solid {c_col}50; border-right: 6px solid {c_col};
                         border-radius: 12px; padding: 20px; margin-bottom: 25px;
                         box-shadow: 0 8px 20px rgba(0,0,0,0.4);' dir='rtl'>
                        <div style='display: flex; justify-content: space-between; align-items: center;
                             border-bottom: 1px dashed #2d303e; padding-bottom: 15px; margin-bottom: 15px;'>
                            <div style='font-size: 24px; font-weight: 900; color: #fff;'>
                                {c_name} <span style='font-size:16px; color:#888;'>({row['الرمز']})</span>
                            </div>
                            <div style='font-size: 28px; font-weight: bold; color: {c_col};
                                 text-shadow: 0 0 15px {c_col}40;'>{c_score}/100</div>
                        </div>
                        <div style='display: flex; flex-wrap: wrap; gap: 20px;'>
                            <div style='flex: 1; min-width: 250px;'>
                                <div style='margin-bottom: 15px; font-size: 16px; color: #ccc;'>
                                    <b>💵 السعر:</b>
                                    <span style='color: white; font-weight: bold; font-size: 18px;'>
                                        {row['السعر']}
                                    </span>
                                </div>
                                <div style='margin-bottom: 18px; font-size: 16px;'>
                                    <b>🚦 القرار:</b>
                                    <span style='color:{c_col}; font-weight:900; background-color:{c_col}20;
                                           padding:6px 12px; border-radius:8px; border: 1px solid {c_col}50;'>
                                        {c_dec}
                                    </span>
                                </div>
                                <div style='font-size: 16px; color: #ccc;'>
                                    <b>⚡ الحدث:</b><br>
                                    <div style='margin-top:10px;'>{row['الحالة اللحظية ⚡']}</div>
                                </div>
                            </div>
                            <div style='flex: 2; min-width: 300px; background: rgba(0,0,0,0.3);
                                 padding: 20px; border-radius: 10px; border: 1px solid #2d303e;'>
                                <b style='color:#00d2ff; font-size: 16px;'>🔬 تقرير الذكاء الاصطناعي:</b>
                                <ul style='margin-top: 12px; padding-right: 25px; list-style-type: disc;'>
                                    {reasons_html}
                                </ul>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                except Exception:
                    st.error(f"⚠️ تعذر عرض بطاقة {row['الرمز']}.")
        else:
            st.markdown(
                "<div class='empty-box'>📉 لا توجد أصول مطابقة للمعايير حالياً.</div>",
                unsafe_allow_html=True
            )

    # ═══════════════════════════════════════════════════════════
    # TAB: Breakouts Chart
    # ═══════════════════════════════════════════════════════════
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        show_3d = c1.checkbox(f"عرض 3 {lbl} 🟠", value=True)
        show_4d = c2.checkbox(f"عرض 4 {lbl} 🟢", value=False)
        show_10d = c3.checkbox(f"عرض 10 {lbl} 🟣", value=True)
        show_15d = c4.checkbox(f"عرض 15 {lbl} 🔴", value=False)

        df_plot2 = df.tail(150).copy()
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df_plot2.index, y=df_plot2['Close'], mode='lines+markers',
            name='السعر', line=dict(color='dodgerblue', width=2), marker=dict(size=5)
        ))

        def add_channel(fig, h_col, l_col, color, dash, name, m_color, m_size, s_up, s_dn):
            if h_col in df_plot2.columns and l_col in df_plot2.columns:
                fig.add_trace(go.Scatter(
                    x=df_plot2.index, y=df_plot2[h_col],
                    line=dict(color=color, width=1.5, dash=dash, shape='hv'),
                    name=f'مقاومة {name}'
                ))
                fig.add_trace(go.Scatter(
                    x=df_plot2.index, y=df_plot2[l_col],
                    line=dict(color=color, width=1.5, dash=dash, shape='hv'),
                    name=f'دعم {name}'
                ))
                bo_up = df_plot2[
                    (df_plot2['Close'] > df_plot2[h_col])
                    & (df_plot2['Close'].shift(1) <= df_plot2[h_col].shift(1))
                ]
                bo_dn = df_plot2[
                    (df_plot2['Close'] < df_plot2[l_col])
                    & (df_plot2['Close'].shift(1) >= df_plot2[l_col].shift(1))
                ]
                fig.add_trace(go.Scatter(
                    x=bo_up.index, y=bo_up['Close'], mode='markers',
                    marker=dict(symbol=s_up, size=m_size, color=m_color,
                                line=dict(width=1, color='black')),
                    name=f'اختراق {name}'
                ))
                fig.add_trace(go.Scatter(
                    x=bo_dn.index, y=bo_dn['Close'], mode='markers',
                    marker=dict(symbol=s_dn, size=m_size, color='red',
                                line=dict(width=1, color='black')),
                    name=f'كسر {name}'
                ))

        if show_3d:
            add_channel(fig2, 'High_3D', 'Low_3D', 'orange', 'dot',
                        f'3 {lbl}', 'orange', 12, 'triangle-up', 'triangle-down')
        if show_4d:
            add_channel(fig2, 'High_4D', 'Low_4D', '#4caf50', 'dash',
                        f'4 {lbl}', '#4caf50', 12, 'triangle-up', 'triangle-down')
        if show_10d:
            add_channel(fig2, 'High_10D', 'Low_10D', '#9c27b0', 'solid',
                        f'10 {lbl}', '#9c27b0', 14, 'diamond', 'diamond-tall')
        if show_15d:
            add_channel(fig2, 'High_15D', 'Low_15D', '#f44336', 'dashdot',
                        f'15 {lbl}', '#f44336', 16, 'star', 'star-triangle-down')

        fig2.update_layout(
            height=650, hovermode='x unified', template='plotly_dark',
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        if selected_interval != "1d":
            if is_crypto_main:
                pass
            elif is_fx_main:
                fig2.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            else:
                fig2.update_xaxes(rangebreaks=[
                    dict(bounds=["sat", "mon"]),
                    dict(bounds=[16, 9], pattern="hour"),
                ])
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})

    # ═══════════════════════════════════════════════════════════
    # TAB: Market Scanner Table
    # ═══════════════════════════════════════════════════════════
    with tab5:
        if not df_loads.empty:
            df_ls = pd.DataFrame(df_loads).copy()
            try:
                for src_col, cat_col in [
                    (col_change_name, '1d_cat'),
                    (f'تراكمي 3 {lbl}', '3d_cat'),
                    (f'تراكمي 5 {lbl}', '5d_cat'),
                    (f'تراكمي 10 {lbl}', '10d_cat'),
                ]:
                    if src_col in df_ls.columns and cat_col in df_ls.columns:
                        df_ls[src_col] = df_ls.apply(
                            lambda x: _format_cat_row(x, src_col, cat_col), axis=1
                        )

                drop_cols = ['1d_cat', '3d_cat', '5d_cat', '10d_cat',
                             'raw_3d', 'raw_5d', 'raw_10d']
                df_ls = df_ls.drop(columns=[c for c in drop_cols if c in df_ls.columns])
                df_ls = df_ls.fillna('')

                style_cols = [
                    c for c in [
                        col_change_name,
                        f'حالة 3 {lbl}', f'تراكمي 3 {lbl}',
                        f'حالة 5 {lbl}', f'تراكمي 5 {lbl}',
                        f'حالة 10 {lbl}', f'تراكمي 10 {lbl}',
                    ]
                    if c in df_ls.columns
                ]
                if style_cols:
                    st.dataframe(
                        df_ls.style.map(safe_color_table, subset=style_cols),
                        use_container_width=True, height=550,
                    )
                else:
                    st.dataframe(df_ls.astype(str), use_container_width=True, height=550)
            except Exception:
                st.dataframe(df_ls.astype(str), use_container_width=True, height=550)
        else:
            st.markdown(
                "<div class='empty-box'>📭 لا توجد بيانات للتحليل.</div>",
                unsafe_allow_html=True
            )

    # ═══════════════════════════════════════════════════════════
    # TAB: Alerts
    # ═══════════════════════════════════════════════════════════
    with tab6:
        if not df_alerts.empty:
            df_al = pd.DataFrame(df_alerts).fillna('')
            try:
                if 'التنبيه' in df_al.columns:
                    st.dataframe(
                        df_al.style.map(safe_color_table, subset=['التنبيه']),
                        use_container_width=True, height=550,
                    )
                else:
                    st.dataframe(df_al.astype(str), use_container_width=True, height=550)
            except Exception:
                st.dataframe(df_al.astype(str), use_container_width=True, height=550)
        else:
            st.markdown(
                "<div class='empty-box'>لم يتم رصد أي اختراقات أو كسور في السوق.</div>",
                unsafe_allow_html=True
            )

    # ═══════════════════════════════════════════════════════════
    # TAB: Backtest
    # ═══════════════════════════════════════════════════════════
    with tab_backtest:
        st.markdown(
            f"<h3 style='text-align: center; color: #FFD700;'>"
            f"⏳ السجل التاريخي لـ ({chart_display})</h3>",
            unsafe_allow_html=True
        )
        try:
            df_bt = df.tail(150).copy()
            bt_logs = []
            zr_state, ma_state = "inside", "neutral"

            for i in range(1, len(df_bt)):
                curr = df_bt.iloc[i]
                try:
                    t_str = (
                        df_bt.index[i].strftime('%Y-%m-%d | %H:%M')
                        if selected_interval != '1d'
                        else df_bt.index[i].strftime('%Y-%m-%d')
                    )
                except Exception:
                    t_str = str(df_bt.index[i])[:16]

                if pd.notna(curr.get('ZR_High')) and pd.notna(curr.get('ZR_Low')):
                    if curr['Close'] > curr['ZR_High']:
                        if zr_state != "above":
                            bt_logs.append({
                                "التاريخ والوقت": t_str,
                                "السعر": format_price(curr['Close'], chart_ticker),
                                "الحدث التاريخي": "🚀 اختراق سقف زيرو 👑"
                            })
                            zr_state = "above"
                    elif curr['Close'] < curr['ZR_Low']:
                        if zr_state != "below":
                            bt_logs.append({
                                "التاريخ والوقت": t_str,
                                "السعر": format_price(curr['Close'], chart_ticker),
                                "الحدث التاريخي": "🔻 كسر قاع زيرو (انهيار) 🕳️"
                            })
                            zr_state = "below"
                    else:
                        if zr_state == "above" and curr['Close'] < curr['ZR_High'] * 0.985:
                            zr_state = "inside"
                        elif zr_state == "below" and curr['Close'] > curr['ZR_Low'] * 1.015:
                            zr_state = "inside"

                if pd.notna(curr.get('SMA_50')):
                    if curr['Close'] > curr['SMA_50']:
                        if ma_state != "above":
                            bt_logs.append({
                                "التاريخ والوقت": t_str,
                                "السعر": format_price(curr['Close'], chart_ticker),
                                "الحدث التاريخي": "🟢 اختراق متوسط 50"
                            })
                            ma_state = "above"
                    elif curr['Close'] < curr['SMA_50']:
                        if ma_state != "below" and ma_state != "neutral":
                            bt_logs.append({
                                "التاريخ والوقت": t_str,
                                "السعر": format_price(curr['Close'], chart_ticker),
                                "الحدث التاريخي": "🔴 كسر متوسط 50"
                            })
                            ma_state = "below"
                        elif ma_state == "neutral":
                            ma_state = "below"

            if bt_logs:
                df_bt_res = pd.DataFrame(bt_logs).iloc[::-1]
                df_bt_res.set_index("التاريخ والوقت", inplace=True)
                st.dataframe(
                    df_bt_res.style.map(safe_color_table, subset=['الحدث التاريخي']),
                    use_container_width=True, height=500,
                )
            else:
                st.info("لم يمر السهم بأي أحداث مفصلية خلال الـ 150 شمعة الماضية.")
        except Exception as e:
            st.error(f"⚠️ حدث خطأ في بناء الباك تيست: {e}")

    # ═══════════════════════════════════════════════════════════
    # TAB: Tracker
    # ═══════════════════════════════════════════════════════════
    with tab_track:
        st.markdown(
            "<h3 style='text-align: center; color: #00d2ff;'>"
            "📂 محفظة المراقبة الحية (Live Tracker)</h3>",
            unsafe_allow_html=True
        )
        try:
            with sqlite3.connect(DB_FILE) as conn:
                df_saved = pd.read_sql_query(
                    "SELECT * FROM tracker ORDER BY date_time DESC", conn
                )

            if not df_saved.empty:
                c_f1, c_f2, c_btn = st.columns([2, 2, 1.5])
                with c_f1:
                    markets_opts = ["الكل"] + sorted(df_saved['market'].dropna().unique().tolist())
                    sel_market = st.selectbox("🌐 تصفية حسب السوق:", markets_opts)
                with c_f2:
                    tf_opts = (
                        ["الكل"] + sorted(df_saved['timeframe'].dropna().unique().tolist())
                        if 'timeframe' in df_saved.columns else ["الكل"]
                    )
                    sel_tf = st.selectbox("⏳ تصفية حسب الفريم:", tf_opts)
                with c_btn:
                    st.write("")
                    st.write("")
                    refresh_btn = st.button("🔄 تحديث الأسعار", type="primary", use_container_width=True)

                df_filtered = df_saved.copy()
                if sel_market != "الكل":
                    df_filtered = df_filtered[df_filtered['market'] == sel_market]
                if sel_tf != "الكل" and 'timeframe' in df_filtered.columns:
                    df_filtered = df_filtered[df_filtered['timeframe'] == sel_tf]

                if df_filtered.empty:
                    st.warning("لا توجد صفقات تطابق الفلترة.")
                else:
                    if refresh_btn:
                        with st.spinner("📡 جاري جلب الأسعار الحية..."):
                            unique_tickers = df_filtered['ticker'].unique()
                            live_prices = {}

                            def fetch_live(tk_arg):
                                try:
                                    return tk_arg, yf.Ticker(tk_arg).history(period="1d")['Close'].iloc[-1]
                                except Exception:
                                    return tk_arg, None

                            with ThreadPoolExecutor(max_workers=5) as ex:
                                for f in as_completed([ex.submit(fetch_live, t) for t in unique_tickers]):
                                    t, px = f.result()
                                    if px is not None:
                                        live_prices[t] = px
                            st.session_state['live_prices'] = live_prices

                    display_records = []
                    for _, r in df_filtered.iterrows():
                        tk_r = r['ticker']
                        entry = float(r['entry'])
                        tgt = float(r['target'])
                        sl_r = float(r['stop_loss'])
                        live_p = st.session_state.get('live_prices', {}).get(tk_r, entry)
                        pnl = safe_div((live_p - entry) * 100, entry, 0)

                        if live_p >= tgt:
                            status = "🎯 تحقق الهدف"
                        elif live_p <= sl_r:
                            status = "🩸 ضرب الوقف"
                        else:
                            status = "⏳ جارية"

                        fmt = ".5f" if entry < 2 else ".2f"
                        display_records.append({
                            "وقت الرصد": r['date_time'],
                            "السوق": r['market'],
                            "الفريم": r.get('timeframe', 'غير محدد'),
                            "الشركة": r['company'],
                            "الرمز": tk_r,
                            "سعر الدخول": f"{entry:{fmt}}",
                            "الهدف": f"{tgt:{fmt}}",
                            "الوقف": f"{sl_r:{fmt}}",
                            "السعر اللحظي 📡": f"{live_p:{fmt}}",
                            "الربح/الخسارة": f"{pnl:+.2f}%",
                            "حالة الصفقة": status,
                        })

                    if display_records:
                        df_live = pd.DataFrame(display_records)
                        st.dataframe(
                            df_live.style.map(
                                style_live_tracker,
                                subset=['الربح/الخسارة', 'حالة الصفقة']
                            ),
                            use_container_width=True, hide_index=True,
                        )

                st.markdown("<br>", unsafe_allow_html=True)
                _, col_del, _ = st.columns([1, 1, 1])
                with col_del:
                    if st.button("🗑️ تنظيف المحفظة بالكامل", type="secondary", use_container_width=True):
                        with sqlite3.connect(DB_FILE) as conn:
                            conn.execute("DELETE FROM tracker")
                            conn.commit()
                        st.rerun()
            else:
                st.info(
                    "📂 المحفظة فارغة. اذهب إلى (👑 VIP) واضغط على [حفظ] لإضافة الفرص."
                )
        except Exception as e:
            st.error(f"حدث خطأ في قراءة قاعدة البيانات: {e}")

    # ═══════════════════════════════════════════════════════════
    # TAB: TradingView
    # ═══════════════════════════════════════════════════════════
    with tab2:
        if is_fx_main:
            tv_ticker = chart_ticker.replace('=X', '')
            if len(tv_ticker) == 3:
                tv_ticker = "USD" + tv_ticker
            tv_symbol = f"FX:{tv_ticker}"
        elif is_crypto_main:
            tv_ticker = chart_ticker.replace('-USD', '')
            tv_symbol = f"BINANCE:{tv_ticker}USDT"
        elif "السعودي" in market_choice:
            tv_ticker = chart_ticker.replace('.SR', '')
            tv_symbol = f"TADAWUL:{tv_ticker}"
        else:
            tv_symbol = chart_ticker

        tv_interval_tv = "D" if selected_interval == "1d" else selected_interval.replace("m", "")
        tv_html = (
            f'<div class="tradingview-widget-container" style="height:700px;width:100%">'
            f'<div id="tradingview_masa" style="height:100%;width:100%"></div>'
            f'<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>'
            f'<script type="text/javascript">'
            f'new TradingView.widget({{'
            f'"autosize": true, "symbol": "{tv_symbol}", "interval": "{tv_interval_tv}", '
            f'"timezone": "Asia/Riyadh", "theme": "dark", "style": "1", "locale": "ar_AE", '
            f'"enable_publishing": false, "backgroundColor": "#1a1c24", "gridColor": "#2d303e", '
            f'"hide_top_toolbar": false, "hide_legend": false, "save_image": false, '
            f'"container_id": "tradingview_masa", "toolbar_bg": "#1e2129", '
            f'"studies": ["Volume@tv-basicstudies","RSI@tv-basicstudies",'
            f'"MASimple@tv-basicstudies","VWAP@tv-basicstudies"]'
            f'}});</script></div>'
        )
        components.html(tv_html, height=700)

    # ═══════════════════════════════════════════════════════════
    # TAB: Chart
    # ═══════════════════════════════════════════════════════════
    with tab3:
        df_plot = df.tail(150) if selected_interval != '1d' else df.tail(300)
        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True,
            vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2]
        )

        fig.add_trace(go.Candlestick(
            x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
            low=df_plot['Low'], close=df_plot['Close'], name='السعر'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['SMA_200'],
            line=dict(color='#9c27b0', width=2), name='MA 200'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['SMA_50'],
            line=dict(color='#00bcd4', width=2), name='MA 50'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['VWAP'],
            line=dict(color='#ffeb3b', width=2, dash='dot'), name='VWAP'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['ZR_High'], mode='lines',
            line=dict(color='white', width=3, dash='dash'),
            name='سقف زيرو (الأساسي)', hoverinfo='skip'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['ZR_Low'], mode='lines',
            line=dict(color='rgb(251, 140, 0)', width=3, dash='dash'),
            name='قاع زيرو (الأساسي)', hoverinfo='skip'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['ZR2_High'], mode='lines',
            line=dict(color='white', width=4, dash='dashdot'),
            name='سقف زيرو (المطور)', hoverinfo='skip'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['ZR2_Low'], mode='lines',
            line=dict(color='orange', width=4, dash='dashdot'),
            name='قاع زيرو (المطور)', hoverinfo='skip'
        ), row=1, col=1)

        czr_h = df['ZR_High'].iloc[-1] if pd.notna(df['ZR_High'].iloc[-1]) else df_plot['High'].max()
        czr_l = df['ZR_Low'].iloc[-1] if pd.notna(df['ZR_Low'].iloc[-1]) else df_plot['Low'].min()
        czr2_h = df['ZR2_High'].iloc[-1] if pd.notna(df['ZR2_High'].iloc[-1]) else df_plot['High'].max()
        czr2_l = df['ZR2_Low'].iloc[-1] if pd.notna(df['ZR2_Low'].iloc[-1]) else df_plot['Low'].min()

        fig.add_annotation(
            x=df_plot.index[-min(10, len(df_plot) - 1)], y=czr_h,
            text=(
                f"<b>ZR Basic (400,25)</b><br>H: {czr_h:.4f} | L: {czr_l:.4f}<br>"
                f"<b>ZR Pro (300,30)</b><br>H: {czr2_h:.4f} | L: {czr2_l:.4f}"
            ),
            showarrow=False, yshift=40,
            font=dict(color="white", size=10, family="Courier New"),
            bgcolor="rgba(26, 28, 36, 0.85)",
            bordercolor="rgba(255, 255, 255, 0.4)", borderwidth=1, borderpad=5,
        )

        colors = ['green' if row['Close'] >= row['Open'] else 'red' for _, row in df_plot.iterrows()]
        fig.add_trace(go.Bar(
            x=df_plot.index, y=df_plot['Volume'],
            marker_color=colors, name='السيولة'
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['RSI'],
            line=dict(color='purple', width=2), name='RSI 14'
        ), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", row=3, col=1, line_color="red")
        fig.add_hline(y=50, line_dash="solid", row=3, col=1, line_color="gray", opacity=0.5)
        fig.add_hline(y=30, line_dash="dot", row=3, col=1, line_color="green")

        fig.update_layout(
            height=800, template='plotly_dark', showlegend=False,
            xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10),
        )
        if selected_interval != "1d":
            if is_crypto_main:
                pass
            elif is_fx_main:
                fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            else:
                fig.update_xaxes(rangebreaks=[
                    dict(bounds=["sat", "mon"]),
                    dict(bounds=[16, 9], pattern="hour"),
                ])
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # ═══════════════════════════════════════════════════════════
    # TAB: Data Table
    # ═══════════════════════════════════════════════════════════
    with tab4:
        st.markdown(
            "<h3 style='text-align: center; color: #00d2ff;'>📋 البيانات التاريخية المفصلة</h3>",
            unsafe_allow_html=True
        )
        df_display = df.tail(20).iloc[::-1].copy()

        time_list = []
        for d in df_display.index:
            try:
                time_list.append(
                    d.strftime('%Y-%m-%d | 00:00') if selected_interval == '1d'
                    else d.strftime('%Y-%m-%d | %H:%M')
                )
            except Exception:
                time_list.append(str(d)[:16])

        table_data = {
            'الوقت': time_list,
            'الإغلاق': [format_price(x, chart_ticker) for x in df_display['Close']],
            'VWAP 🐋': [
                format_price(x, chart_ticker) for x in df_display.get('VWAP', df_display['Close'])
            ],
            'الاتجاه': [
                str(int(x)) if pd.notna(x) else "0"
                for x in df_display.get('Counter', pd.Series([0] * len(df_display)))
            ],
            'MA 50': [format_price(x, chart_ticker) for x in df_display.get('SMA_50', df_display['Close'])],
            'MA 200': [format_price(x, chart_ticker) for x in df_display.get('SMA_200', df_display['Close'])],
        }

        for col_name, src_name in [
            (col_change_name, '1d_%'),
            (f'تراكمي 3 {lbl}', '3d_%'),
            (f'تراكمي 5 {lbl}', '5d_%'),
            (f'تراكمي 10 {lbl}', '10d_%'),
        ]:
            series = df_display.get(src_name, pd.Series([0] * len(df_display)))
            table_data[col_name] = [_format_cat(v, _get_cat(v)) for v in series]

        if not is_fx_main and not is_crypto_main:
            table_data['حجم السيولة'] = [
                f"{int(x):,}" if pd.notna(x) and not np.isinf(x) else "0"
                for x in df_display.get('Volume', pd.Series([0] * len(df_display)))
            ]

        try:
            final_df = pd.DataFrame(table_data)
            final_df.set_index('الوقت', inplace=True)
            style_cols = [
                c for c in [
                    col_change_name, f'تراكمي 3 {lbl}',
                    f'تراكمي 5 {lbl}', f'تراكمي 10 {lbl}',
                ] if c in final_df.columns
            ]
            if style_cols:
                st.dataframe(
                    final_df.style.map(safe_color_table, subset=style_cols),
                    use_container_width=True, height=600,
                )
            else:
                st.dataframe(final_df.astype(str), use_container_width=True, height=600)
        except Exception:
            st.dataframe(df_display, use_container_width=True, height=600)

elif not scan_results:
    st.markdown(
        "<div style='text-align:center; padding:50px; color:#888; font-size:18px;'>"
        "اضغط على زر <b style='color:#00d2ff;'>استخراج الفرص 💎</b> لبدء المسح والتحليل"
        "</div>",
        unsafe_allow_html=True
    )


def _format_cat_row(row, src_col, cat_col):
    from core.scanner import _format_cat
    return _format_cat(row[src_col], row[cat_col])


def _get_cat(val):
    from core.scanner import _get_cat as gc
    return gc(val)


def _format_cat(val, cat):
    from core.scanner import _format_cat as fc
    return fc(val, cat)
