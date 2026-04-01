"""
MASA V2 — Order Flow Scanner
Built on one principle: Who is initiating — the buyer or the seller?
"""

import streamlit as st
import streamlit.components.v1 as components
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.scanner import scan_market
from core.database import init_database, log_signal, get_win_rates, get_total_performance
from core.tracker import update_signal_outcomes, get_tracking_status
from core.institutional import get_ownership_summary, import_from_csv
from data.markets import get_all_tickers, SAUDI_STOCKS, US_STOCKS, MARKETS
from core.events import classify_events
from ui.styles import DARK_THEME_CSS, SECTOR_COLORS

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="MASA V2 — Order Flow",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

# ── Initialize ───────────────────────────────────────────────
init_database()

# ── Session State ─────────────────────────────────────────────
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "market_health" not in st.session_state:
    st.session_state.market_health = None
if "last_market" not in st.session_state:
    st.session_state.last_market = None
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = None
if "composite_dates" not in st.session_state:
    st.session_state.composite_dates = None
if "composite_vals" not in st.session_state:
    st.session_state.composite_vals = None


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def make_sparkline(values, color="#4FC3F7", uid="x"):
    """Generate SVG sparkline from price values (last 60 days)."""
    vals = values[-60:] if len(values) > 60 else list(values)
    if len(vals) < 3:
        return ""

    W, H = 300, 55
    mn = min(vals) * 0.998
    mx = max(vals) * 1.002
    rng = mx - mn or 1

    step = W / (len(vals) - 1)
    pts = []
    for i, v in enumerate(vals):
        x = round(i * step, 1)
        y = round(H - ((v - mn) / rng * (H - 4)) - 2, 1)
        pts.append(f"{x},{y}")

    line = "M" + " L".join(pts)
    fill = f"M0,{H} L" + " L".join(pts) + f" L{W},{H} Z"

    return f'''<svg width="100%" height="{H}" viewBox="0 0 {W} {H}" preserveAspectRatio="none"
        style="display:block;margin:8px 0 4px 0;border-radius:8px;overflow:hidden">
        <defs>
            <linearGradient id="sg{uid}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="{color}" stop-opacity="0.35"/>
                <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
            </linearGradient>
        </defs>
        <path d="{fill}" fill="url(#sg{uid})"/>
        <path d="{line}" fill="none" stroke="{color}" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round"/>
    </svg>'''


def _maturity_mini(r):
    """Build mini maturity badge for card: stage + days + start date."""
    parts = []
    _is_intra = r.get("timeframe", "1d") != "1d"
    _unit = "شمعة" if _is_intra else "يوم"
    # Accumulation maturity
    m_stage = r.get("maturity_stage", "none")
    if m_stage != "none":
        m_label = r.get("maturity_label", "")
        m_color = r.get("maturity_color", "#808080")
        m_days = r.get("maturity_days", 0)
        m_timeline = r.get("maturity_timeline", [])
        start = m_timeline[0]["date"] if m_timeline else ""
        _cf_ev = r.get("maturity_cf_events", 0)
        _conv = r.get("maturity_conviction", 100.0)
        _conv_txt = ""
        if m_days >= 5:
            _cc = "#00E676" if _conv >= 85 else "#FFD700" if _conv >= 65 else "#FF5252"
            _conv_txt = f' • <span style="color:{_cc};font-weight:700">نقاء {_conv:.0f}%</span>'
            if _cf_ev > 0:
                _conv_txt += f' <span style="color:#FF5252;font-size:0.9em">({_cf_ev}🔴)</span>'
        parts.append(
            f'<span style="background:{m_color}12;color:{m_color};font-size:0.68em;'
            f'font-weight:600;padding:2px 8px;border-radius:8px;border:1px solid {m_color}25">'
            f'📦 {m_label} • {m_days} {_unit}'
            f'{f" • من {start}" if start else ""}{_conv_txt}</span>'
        )
    # Distribution maturity
    dm_stage = r.get("dist_maturity_stage", "none")
    if dm_stage != "none":
        dm_label = r.get("dist_maturity_label", "")
        dm_color = r.get("dist_maturity_color", "#FF5252")
        dm_days = r.get("dist_maturity_days", 0)
        dm_timeline = r.get("dist_maturity_timeline", [])
        start = dm_timeline[0]["date"] if dm_timeline else ""
        _dcf_ev = r.get("dist_cf_events", 0)
        _dconv = r.get("dist_conviction", 100.0)
        _dconv_txt = ""
        if dm_days >= 5:
            _dcc = "#FF5252" if _dconv >= 85 else "#FFD700" if _dconv >= 65 else "#00E676"
            _dconv_txt = f' • <span style="color:{_dcc};font-weight:700">نقاء {_dconv:.0f}%</span>'
            if _dcf_ev > 0:
                _dconv_txt += f' <span style="color:#00E676;font-size:0.9em">({_dcf_ev}🟢)</span>'
        parts.append(
            f'<span style="background:{dm_color}12;color:{dm_color};font-size:0.68em;'
            f'font-weight:600;padding:2px 8px;border-radius:8px;border:1px solid {dm_color}25">'
            f'🔻 {dm_label} • {dm_days} {_unit}'
            f'{f" • من {start}" if start else ""}{_dconv_txt}</span>'
        )
    return "".join(parts)


def _flow_bar_svg(flow_bias, width=240, height=16):
    """Generate an SVG bar showing flow bias (-100 to +100)."""
    mid = width / 2
    val = max(-100, min(100, flow_bias))
    bar_len = abs(val) / 100 * mid

    if val > 0:
        color = "#00E676"
        x = mid
    else:
        color = "#FF5252"
        x = mid - bar_len

    return (
        f'<svg width="{width}" height="{height}" style="display:block;margin:4px 0">'
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="3" fill="#0a0f1a"/>'
        f'<rect x="{x}" y="1" width="{bar_len}" height="{height-2}" rx="2" fill="{color}" opacity="0.7"/>'
        f'<line x1="{mid}" y1="0" x2="{mid}" y2="{height}" stroke="#333" stroke-width="1"/>'
        f'</svg>'
    )


def compute_relative_flow(results):
    """
    Post-process scan results: compare each stock's flow_bias
    against its sector average. Mutates results in-place.
    """
    from collections import defaultdict

    # Step 1: Sector averages
    sector_flows = defaultdict(list)
    for r in results:
        sector = r.get("sector", "أخرى")
        fb = r.get("flow_bias", 0)
        if fb is not None and fb == fb:  # NaN guard
            sector_flows[sector].append(fb)

    sector_avg = {}
    for sector, flows in sector_flows.items():
        sector_avg[sector] = sum(flows) / len(flows) if flows else 0

    # Step 2: Relative flow per stock
    for r in results:
        sector = r.get("sector", "أخرى")
        avg = sector_avg.get(sector, 0)
        stock_fb = r.get("flow_bias", 0) or 0
        rel = stock_fb - avg

        # Classify
        if rel > 20:
            label, color = "ضد التيار", "#00E676"
        elif rel > 10:
            label, color = "يتفوق", "#4FC3F7"
        elif rel >= -10:
            label, color = "مع القطاع", "#9ca3af"
        else:
            label, color = "أضعف من القطاع", "#FF5252"

        r["relative_flow"] = round(rel, 1)
        r["relative_flow_label"] = label
        r["relative_flow_color"] = color
        r["sector_avg_flow"] = round(avg, 1)

    return results


def build_card_html(r):
    """Build Order Flow card HTML."""
    decision = r["decision"]
    name = r["name"]
    ticker_display = r["ticker"].replace(".SR", "")
    sector = r["sector"]
    price = r["price"]
    change = r["change_pct"]
    phase_label = r["phase_label"]
    phase_color = r["phase_color"]
    flow_type_label = r.get("flow_type_label", "")
    flow_type_color = r.get("flow_type_color", "#808080")
    flow_bias = r["flow_bias"]
    aggressor = r["aggressor"]
    aggressive_ratio = r["aggressive_ratio"]
    absorption_score = r["absorption_score"]
    divergence = r["divergence"]
    location_label = r["location_label"]
    days = r["days"]
    rsi = r["rsi"]
    volume_ratio = r["volume_ratio"]
    decision_label = r["decision_label"]
    decision_color = r["decision_color"]

    sector_color = SECTOR_COLORS.get(sector, "#607D8B")
    change_color = "#00E676" if change >= 0 else "#FF5252"
    change_icon = "▲" if change >= 0 else "▼"

    # Aggressor display
    if aggressor == "buyers":
        agg_text = "🟢 مشتري"
        agg_color = "#00E676"
    elif aggressor == "sellers":
        agg_text = "🔴 بائع"
        agg_color = "#FF5252"
    else:
        agg_text = "⚪ متوازن"
        agg_color = "#9ca3af"

    # Flow bias color
    flow_color = "#00E676" if flow_bias > 10 else "#FF5252" if flow_bias < -10 else "#9ca3af"

    # Divergence color
    div_color = "#00E676" if divergence > 15 else "#FF5252" if divergence < -15 else "#9ca3af"

    # Absorption color
    abs_color = "#FFD700" if absorption_score > 70 else "#9ca3af"

    # RSI color
    rsi_color = "#FF5252" if rsi > 70 else "#00E676" if rsi < 30 else "#9ca3af"

    # SVG sparkline
    close_vals = r.get("chart_close", [])
    uid = r["ticker"].replace(".", "").replace("-", "")
    sparkline = make_sparkline(close_vals, color=phase_color, uid=uid)

    # Flow bar
    flow_bar = _flow_bar_svg(flow_bias)

    # ZR status badge
    zr_badge = ""
    zr_status = r.get("zr_status", "normal")
    zr_status_label = r.get("zr_status_label", "")
    zr_status_color = r.get("zr_status_color", "#808080")
    if zr_status != "normal" and zr_status_label:
        zr_badge = (
            f'<span style="background:{zr_status_color}12;color:{zr_status_color};'
            f'padding:2px 8px;border-radius:8px;font-size:0.72em;font-weight:700;'
            f'border:1px solid {zr_status_color}25">{zr_status_label}</span>'
        )

    # Institutional badge
    inst_badge = ""
    fc = r.get("foreign_change")
    if fc is not None and fc > 0.1:
        inst_badge = (
            '<span style="background:rgba(0,230,118,0.10);color:#00E676;'
            'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            'margin-right:4px">🏛 مؤسساتي ↑</span>'
        )
    elif fc is not None and fc < -0.1:
        inst_badge = (
            '<span style="background:rgba(255,82,82,0.10);color:#FF5252;'
            'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            'margin-right:4px">🏛 تصريف ↓</span>'
        )

    # Relative flow badge — always show (with value)
    rel_badge = ""
    rel_label = r.get("relative_flow_label", "")
    rel_color = r.get("relative_flow_color", "#9ca3af")
    rel_val = r.get("relative_flow", 0)
    if rel_label:
        rel_badge = (
            f'<span style="background:{rel_color}12;color:{rel_color};'
            f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            f'border:1px solid {rel_color}25">📊 {rel_label} ({rel_val:+.0f})</span>'
        )

    # Volatility badge — always show ATR%
    vol_badge = ""
    atr_pct = r.get("atr_pct", 0)
    vol_key = r.get("volatility", "medium")
    vol_label_str = r.get("volatility_label", "")
    vol_color_str = r.get("volatility_color", "#9ca3af")
    if atr_pct > 0:
        if vol_label_str:
            vol_badge = (
                f'<span style="background:{vol_color_str}12;color:{vol_color_str};'
                f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
                f'border:1px solid {vol_color_str}25">{vol_label_str} ({atr_pct:.1f}%)</span>'
            )
        else:
            vol_badge = (
                f'<span style="background:#9ca3af12;color:#9ca3af;'
                f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
                f'border:1px solid #9ca3af25">ATR {atr_pct:.1f}%</span>'
            )

    # Volume Profile location badge
    vp_badge = ""
    vp_label = r.get("vp_location_label", "")
    vp_color = r.get("vp_location_color", "#808080")
    vp_poc = r.get("vp_poc", 0)
    if vp_label:
        vp_badge = (
            f'<span style="background:{vp_color}12;color:{vp_color};'
            f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            f'border:1px solid {vp_color}25">{vp_label}</span>'
        )
    elif vp_poc > 0:
        vp_badge = (
            f'<span style="background:#AB47BC12;color:#AB47BC;'
            f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            f'border:1px solid #AB47BC25">POC {vp_poc}</span>'
        )

    # Timeframe badge (only for intraday)
    tf_badge = ""
    timeframe = r.get("timeframe", "1d")
    timeframe_label = r.get("timeframe_label", "يومي")
    if timeframe != "1d":
        tf_badge = (
            f'<span style="background:#FF980012;color:#FF9800;'
            f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            f'border:1px solid #FF980025">⏱️ {timeframe_label}</span>'
        )

    # Trade info (enter only)
    trade_html = ""
    if decision == "enter":
        trade_html = (
            f'<div style="display:flex;justify-content:space-between;padding:8px 12px;'
            f'background:rgba(0,230,118,0.04);border-radius:10px;margin-top:10px;'
            f'font-size:0.82em;border:1px solid rgba(0,230,118,0.10)">'
            f'<span>🛡️ <span style="color:#FF5252;font-weight:700">{r["stop_loss"]}</span></span>'
            f'<span>🎯 <span style="color:#00E676;font-weight:700">{r["target"]}</span></span>'
            f'<span style="font-weight:600;color:#9ca3af">R:R <b style="color:#fff">{r["rr_ratio"]:.1f}</b></span>'
            f'</div>'
        )

    # Early bounce badge
    bounce_badge = ""
    if r.get("early_bounce"):
        _bl = r.get("early_bounce_label", "")
        bounce_badge = (
            f'<div style="color:#FF9800;font-weight:700;font-size:0.78em;margin-top:8px;'
            f'padding:6px 10px;background:rgba(255,152,0,0.08);border-radius:8px;'
            f'border:1px solid rgba(255,152,0,0.15);text-align:center">{_bl}</div>'
        )

    # Veto
    veto_html = ""
    if r.get("veto"):
        veto_html = (
            f'<div style="color:#FF5252;font-weight:600;font-size:0.78em;margin-top:8px;'
            f'padding:6px 10px;background:rgba(255,82,82,0.06);border-radius:8px;'
            f'border:1px solid rgba(255,82,82,0.10)">{r["veto"]}</div>'
        )

    return f'''<div class="masa-card masa-card-{decision}">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
<span style="background:{decision_color}18;color:{decision_color};padding:4px 14px;border-radius:20px;font-weight:700;font-size:0.82em;letter-spacing:0.3px">{decision_label}</span>
<span style="background:{sector_color}12;color:{sector_color};padding:3px 10px;border-radius:12px;font-size:0.72em;font-weight:500;border:1px solid {sector_color}18">{sector}</span>
</div>
<div style="margin-bottom:4px">
<div style="font-size:1.12em;font-weight:700;color:#fff;line-height:1.3">{name}</div>
<div style="display:flex;align-items:baseline;gap:8px;margin-top:5px;flex-wrap:wrap">
<span style="color:#4b5563;font-size:0.82em">{ticker_display}</span>
<span style="color:#fff;font-size:1.35em;font-weight:800">{price}</span>
<span style="color:{change_color};font-weight:700;font-size:0.88em">{change_icon} {abs(change):.1f}%</span>
</div>
</div>
{sparkline}
<div style="display:flex;justify-content:space-between;align-items:center;margin:4px 0 8px 0;padding-top:8px;border-top:1px solid #151d30">
<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
<span style="color:{phase_color};font-weight:600;font-size:0.84em">{phase_label}</span>
{f'<span style="background:{flow_type_color}15;color:{flow_type_color};font-size:0.72em;font-weight:600;padding:2px 8px;border-radius:8px;border:1px solid {flow_type_color}30">{flow_type_label}</span>' if flow_type_label else ''}
{zr_badge}
{inst_badge}
{rel_badge}
{vol_badge}
{vp_badge}
{tf_badge}
</div>
<span style="color:#4b5563;font-size:0.72em">📍 {location_label} • {abs(days)} {"شمعة" if timeframe != "1d" else "يوم"}</span>
</div>
<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:4px">
{_maturity_mini(r)}
</div>
<div style="margin:6px 0 8px 0">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
<span style="color:#374151;font-size:0.68em;font-weight:600">أوردر فلو</span>
<span style="color:{flow_color};font-weight:700;font-size:0.80em">{flow_bias:+.0f}</span>
</div>
{flow_bar}
</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;background:rgba(8,11,20,0.6);border-radius:10px;padding:10px 4px">
<div style="text-align:center">
<div style="color:#374151;font-size:0.60em;margin-bottom:2px;font-weight:600">المهاجم</div>
<div style="color:{agg_color};font-weight:700;font-size:0.78em">{agg_text}</div>
</div>
<div style="text-align:center;border-left:1px solid #151d30;border-right:1px solid #151d30">
<div style="color:#374151;font-size:0.60em;margin-bottom:2px;font-weight:600">امتصاص</div>
<div style="color:{abs_color};font-weight:700;font-size:0.82em">{absorption_score:.0f}</div>
</div>
<div style="text-align:center;border-left:0;border-right:1px solid #151d30">
<div style="color:#374151;font-size:0.60em;margin-bottom:2px;font-weight:600">دايفرجنس</div>
<div style="color:{div_color};font-weight:700;font-size:0.82em">{divergence:+.0f}</div>
</div>
<div style="text-align:center">
<div style="color:#374151;font-size:0.60em;margin-bottom:2px;font-weight:600">RSI</div>
<div style="color:{rsi_color};font-weight:700;font-size:0.82em">{rsi:.0f}</div>
</div>
</div>
{bounce_badge}
{trade_html}
{veto_html}
</div>'''


def build_detail_chart(r):
    """Build detailed Plotly chart: Candles+MAs+ZR / Volume / CDV / RSI."""
    dates = r.get("chart_dates", [])
    open_vals = r.get("chart_open", [])
    high_vals = r.get("chart_high", [])
    low_vals = r.get("chart_low", [])
    close_vals = r.get("chart_close", [])
    vol_vals = r.get("chart_volume", [])
    ma20_vals = r.get("chart_ma20", [])
    ma50_vals = r.get("chart_ma50", [])
    ma200_vals = r.get("chart_ma200", [])
    rsi_vals = r.get("chart_rsi", [])
    cdv_vals = r.get("chart_cdv", [])
    is_intraday = r.get("timeframe", "1d") != "1d"

    if not dates or len(dates) < 20:
        return None

    close_s = pd.Series(close_vals)

    # Bollinger Bands
    ma20_s = close_s.rolling(20).mean()
    std20 = close_s.rolling(20).std()
    bb_upper = (ma20_s + 2 * std20).tolist()
    bb_lower = (ma20_s - 2 * std20).tolist()

    # Normalize CDV
    if cdv_vals and cdv_vals[0] != 0:
        cdv_base = cdv_vals[0]
        cdv_norm = [round(v - cdv_base, 2) for v in cdv_vals]
    else:
        cdv_norm = cdv_vals
    pos_cdv = [max(0, v) for v in cdv_norm]
    neg_cdv = [min(0, v) for v in cdv_norm]

    # CDV trend
    phase = r.get("phase", "neutral")
    if phase in ("accumulation", "spring", "markup"):
        trend_up = True
    elif phase in ("distribution", "markdown", "upthrust"):
        trend_up = False
    else:
        recent = cdv_norm[-10:] if len(cdv_norm) >= 10 else cdv_norm
        trend_up = sum(recent) / max(len(recent), 1) > 0

    # Volume colors (green if close >= open, red if not)
    vol_colors = []
    for i in range(len(close_vals)):
        o = open_vals[i] if i < len(open_vals) else close_vals[i]
        vol_colors.append("#00E676" if close_vals[i] >= o else "#FF5252")

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.50, 0.13, 0.20, 0.17],
        vertical_spacing=0.03,
    )

    # ═══ Row 1: Candlestick + MAs + BB + ZR ═══

    # Bollinger Bands fill
    fig.add_trace(go.Scatter(
        x=dates, y=bb_upper, mode="lines",
        line=dict(color="rgba(79,195,247,0.25)", width=1, dash="dot"),
        name="BB Upper", showlegend=False, hoverinfo="skip",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=bb_lower, mode="lines",
        line=dict(color="rgba(79,195,247,0.25)", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(79,195,247,0.04)",
        name="BB Lower", showlegend=False, hoverinfo="skip",
    ), row=1, col=1)

    # MA20 — yellow dotted
    fig.add_trace(go.Scatter(
        x=dates, y=ma20_vals, mode="lines",
        line=dict(color="#FFD700", width=1.2, dash="dot"),
        name="MA20", showlegend=False,
        hovertemplate="MA20: %{y:.2f}<extra></extra>",
    ), row=1, col=1)

    # MA50 — cyan
    fig.add_trace(go.Scatter(
        x=dates, y=ma50_vals, mode="lines",
        line=dict(color="#4FC3F7", width=1.5),
        name="MA50", showlegend=False,
        hovertemplate="MA50: %{y:.2f}<extra></extra>",
    ), row=1, col=1)

    # MA200 — magenta/pink
    fig.add_trace(go.Scatter(
        x=dates, y=ma200_vals, mode="lines",
        line=dict(color="#CE93D8", width=1.5),
        name="MA200", showlegend=False,
        hovertemplate="MA200: %{y:.2f}<extra></extra>",
    ), row=1, col=1)

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=dates,
        open=open_vals, high=high_vals, low=low_vals, close=close_vals,
        increasing_line_color="#00E676", increasing_fillcolor="#00E676",
        increasing_line_width=1.5,
        decreasing_line_color="#FF5252", decreasing_fillcolor="#FF5252",
        decreasing_line_width=1.5,
        name="السعر",
    ), row=1, col=1)

    # ZR lines
    zr_high = r.get("zr_high")
    zr_low = r.get("zr_low")
    if zr_high and zr_high > 0:
        fig.add_hline(
            y=zr_high, line_dash="dashdot", line_color="#FFFFFF",
            line_width=2.5, row=1, col=1,
            annotation_text=f"ZR سقف {zr_high}",
            annotation_position="top right",
            annotation_font=dict(size=10, color="#FFFFFF"),
        )
    if zr_low and zr_low > 0:
        fig.add_hline(
            y=zr_low, line_dash="dashdot", line_color="#FF9800",
            line_width=2.5, row=1, col=1,
            annotation_text=f"ZR قاع {zr_low}",
            annotation_position="bottom right",
            annotation_font=dict(size=10, color="#FF9800"),
        )

    # Stop / Target
    if r["decision"] == "enter" and r["stop_loss"] > 0:
        fig.add_hline(
            y=r["stop_loss"], line_dash="dash", line_color="#FF5252",
            line_width=1, row=1, col=1,
            annotation_text=f"وقف {r['stop_loss']}",
            annotation_position="bottom left",
            annotation_font=dict(size=10, color="#FF5252"),
        )
        fig.add_hline(
            y=r["target"], line_dash="dash", line_color="#00E676",
            line_width=1, row=1, col=1,
            annotation_text=f"هدف {r['target']}",
            annotation_position="top left",
            annotation_font=dict(size=10, color="#00E676"),
        )

    # ═══ Volume Profile + Pivot lines ═══
    poc_val = r.get("vp_poc")
    if poc_val and poc_val > 0:
        fig.add_hline(
            y=poc_val, line_dash="longdash", line_color="#AB47BC",
            line_width=1, row=1, col=1,
            annotation_text=f"POC {poc_val}",
            annotation_position="top right",
            annotation_font=dict(size=9, color="#AB47BC"),
        )
    s1_val = r.get("pivot_s1")
    if s1_val and s1_val > 0:
        fig.add_hline(
            y=s1_val, line_dash="dot", line_color="#4FC3F7",
            line_width=1, row=1, col=1,
            annotation_text=f"S1 {s1_val}",
            annotation_position="bottom left",
            annotation_font=dict(size=9, color="#4FC3F7"),
        )
    r1_val = r.get("pivot_r1")
    if r1_val and r1_val > 0:
        fig.add_hline(
            y=r1_val, line_dash="dot", line_color="#FF8A80",
            line_width=1, row=1, col=1,
            annotation_text=f"R1 {r1_val}",
            annotation_position="top left",
            annotation_font=dict(size=9, color="#FF8A80"),
        )

    # ═══ Row 2: Volume Bars ═══
    fig.add_trace(go.Bar(
        x=dates, y=vol_vals,
        marker_color=vol_colors,
        marker_line_width=0,
        opacity=0.8,
        name="الحجم",
        hovertemplate="%{x}<br>الحجم: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # ═══ Row 3: CDV ═══
    cdv_color = "#00E676" if trend_up else "#FF5252"
    fig.add_trace(go.Scatter(
        x=dates, y=cdv_norm, mode="lines",
        line=dict(color=cdv_color, width=2),
        name="CDV",
        hovertemplate="%{x}<br>CDV: %{y:+,.0f}<extra></extra>",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=pos_cdv, fill="tozeroy",
        fillcolor="rgba(0,230,118,0.15)",
        line=dict(width=0), showlegend=False, hoverinfo="skip",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=neg_cdv, fill="tozeroy",
        fillcolor="rgba(255,82,82,0.15)",
        line=dict(width=0), showlegend=False, hoverinfo="skip",
    ), row=3, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#555", line_width=1, row=3, col=1)

    # ═══ Row 4: RSI ═══
    fig.add_trace(go.Scatter(
        x=dates, y=rsi_vals, mode="lines",
        line=dict(color="#CE93D8", width=1.5),
        name="RSI",
        hovertemplate="%{x}<br>RSI: %{y:.0f}<extra></extra>",
    ), row=4, col=1)
    # Overbought / Oversold lines
    fig.add_hline(y=70, line_dash="dot", line_color="#FF5252", line_width=1, row=4, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#00E676", line_width=1, row=4, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="#333", line_width=0.5, row=4, col=1)

    # ═══ Layout ═══
    phase_label = r["phase_label"]
    arrow_color = "#00E676" if trend_up else "#FF5252"

    # Adjust x-axis for intraday vs daily
    tf_label = r.get("timeframe_label", "")
    if is_intraday:
        # Category axis = no gaps between trading sessions
        x_type = "category"
        x1_cfg = dict(showticklabels=False, showgrid=False,
                       rangeslider=dict(visible=False), type=x_type)
        x2_cfg = dict(showticklabels=False, showgrid=False, type=x_type)
        x3_cfg = dict(showticklabels=False, showgrid=False, type=x_type)
        x4_cfg = dict(showgrid=False, type=x_type, nticks=10,
                       tickfont=dict(size=10, color="#6b7280"))
        title_text = f"شموع + MA20 · MA50 · MA200 + ZR  ⏱️ {tf_label}"
    else:
        x1_cfg = dict(showticklabels=False, showgrid=False,
                       rangeslider=dict(visible=False))
        x2_cfg = dict(showticklabels=False, showgrid=False)
        x3_cfg = dict(showticklabels=False, showgrid=False)
        x4_cfg = dict(showgrid=False, tickfont=dict(size=10, color="#6b7280"),
                       dtick="M1", tickformat="%b %Y")
        title_text = "شموع + MA20 · MA50 · MA200 + ZR"

    fig.update_layout(
        height=850,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,24,36,0.8)",
        showlegend=False,
        annotations=[
            dict(text=title_text, x=0.01, y=1.02,
                 xref="paper", yref="paper", showarrow=False,
                 font=dict(size=11, color="#6b7280")),
            dict(text=f"CDV — <span style='color:{arrow_color}'>{phase_label}</span>",
                 x=0.01, y=0.37, xref="paper", yref="paper", showarrow=False,
                 font=dict(size=10, color="#6b7280")),
            dict(text="RSI (14)", x=0.01, y=0.17, xref="paper", yref="paper",
                 showarrow=False, font=dict(size=10, color="#6b7280")),
        ],
        xaxis=x1_cfg,
        xaxis2=x2_cfg,
        xaxis3=x3_cfg,
        xaxis4=x4_cfg,
        yaxis=dict(showgrid=True, gridcolor="#151d30",
                   tickfont=dict(size=9, color="#4b5563")),
        yaxis2=dict(showgrid=False, tickfont=dict(size=8, color="#374151")),
        yaxis3=dict(showgrid=True, gridcolor="#151d30",
                    tickfont=dict(size=9, color="#4b5563"),
                    zeroline=True, zerolinecolor="#333"),
        yaxis4=dict(showgrid=False, tickfont=dict(size=9, color="#4b5563"),
                    range=[10, 90]),
    )

    return fig


# ══════════════════════════════════════════════════════════════
# DATA TABLE (البيانات التاريخية المفصلة)
# ══════════════════════════════════════════════════════════════

def _change_label(pct):
    """Return a severity label based on absolute change percentage."""
    a = abs(pct)
    if a >= 1.5:
        return "MAJOR"
    if a >= 0.3:
        return "HIGH"
    return "MEDIUM"


def _change_dot(pct):
    """Return a colored dot + formatted change string."""
    if pct > 0.05:
        color = "#00E676"
    elif pct < -0.05:
        color = "#FF5252"
    else:
        color = "#6b7280"
    label = _change_label(pct)
    sign = "+" if pct > 0 else ""
    return (
        f'<span style="color:{color};font-weight:600">'
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;background:{color};margin-left:4px"></span>'
        f' {sign}{pct:.2f}% {label}</span>'
    )


def build_data_table(r):
    """Build a styled HTML table of detailed historical data."""
    dates = r.get("chart_dates", [])
    closes = r.get("chart_close", [])
    opens = r.get("chart_open", [])
    highs = r.get("chart_high", [])
    lows = r.get("chart_low", [])
    volumes = r.get("chart_volume", [])
    ma50s = r.get("chart_ma50", [])
    ma200s = r.get("chart_ma200", [])

    n = len(closes)
    if n < 5:
        return "<p style='color:#6b7280'>لا توجد بيانات كافية</p>"

    # Compute VWAP (cumulative typical_price * volume / cumulative volume)
    vwaps = []
    for i in range(n):
        tp = (highs[i] + lows[i] + closes[i]) / 3
        # Simple daily VWAP approximation
        vwaps.append(round(tp, 2))

    # Direction score: count how many MAs price is above (range roughly -5 to +5)
    directions = []
    for i in range(n):
        score = 0
        c = closes[i]
        if ma50s[i] is not None and c > ma50s[i]:
            score += 1
        elif ma50s[i] is not None and c < ma50s[i]:
            score -= 1
        if ma200s[i] is not None and c > ma200s[i]:
            score += 1
        elif ma200s[i] is not None and c < ma200s[i]:
            score -= 1
        # Trend: compare with previous closes
        if i >= 1 and closes[i] > closes[i - 1]:
            score += 1
        elif i >= 1 and closes[i] < closes[i - 1]:
            score -= 1
        if i >= 3 and closes[i] > closes[i - 3]:
            score += 1
        elif i >= 3 and closes[i] < closes[i - 3]:
            score -= 1
        if i >= 5 and closes[i] > closes[i - 5]:
            score += 1
        elif i >= 5 and closes[i] < closes[i - 5]:
            score -= 1
        directions.append(score)

    # Cumulative changes
    def cum_change(idx, days):
        prev_idx = idx - days
        if prev_idx < 0:
            return 0.0
        if closes[prev_idx] == 0:
            return 0.0
        return (closes[idx] - closes[prev_idx]) / closes[prev_idx] * 100

    # Build table — show last 20 days, most recent first
    show_n = min(20, n)
    rows_html = ""
    for j in range(show_n):
        i = n - 1 - j  # reverse: most recent first
        day_change = cum_change(i, 1)
        cum3 = cum_change(i, 3)
        cum5 = cum_change(i, 5)
        cum10 = cum_change(i, 10)

        vol_str = f"{volumes[i]:,.0f}" if i < len(volumes) else "—"
        ma50_str = f"{ma50s[i]:.2f}" if ma50s[i] is not None else "—"
        ma200_str = f"{ma200s[i]:.2f}" if ma200s[i] is not None else "—"

        rows_html += f'''
        <tr style="border-bottom:1px solid #1a1f30">
            <td style="padding:6px 8px;color:#9ca3af;font-size:0.82em;white-space:nowrap">{dates[i]}</td>
            <td style="padding:6px 8px;color:#fff;font-weight:600">{closes[i]:.2f}</td>
            <td style="padding:6px 8px;color:#4FC3F7">{vwaps[i]}</td>
            <td style="padding:6px 8px;color:#CE93D8">{ma50_str}</td>
            <td style="padding:6px 8px;color:#FFD700">{ma200_str}</td>
            <td style="padding:6px 8px;color:{'#00E676' if directions[i] > 0 else '#FF5252' if directions[i] < 0 else '#6b7280'};font-weight:600">{directions[i]}</td>
            <td style="padding:6px 8px">{_change_dot(day_change)}</td>
            <td style="padding:6px 8px">{_change_dot(cum3)}</td>
            <td style="padding:6px 8px">{_change_dot(cum5)}</td>
            <td style="padding:6px 8px">{_change_dot(cum10)}</td>
            <td style="padding:6px 8px;color:#6b7280;font-size:0.82em;text-align:left">{vol_str}</td>
        </tr>'''

    return f'''
    <div style="text-align:center;margin-bottom:12px">
        <span style="font-size:1.3em;font-weight:800;color:#fff">📋 البيانات التاريخية المفصلة</span>
    </div>
    <div style="overflow-x:auto;direction:rtl">
    <table style="width:100%;border-collapse:collapse;font-size:0.88em;direction:ltr">
        <thead>
            <tr style="border-bottom:2px solid #2a3050;color:#6b7280;font-size:0.82em">
                <th style="padding:8px;text-align:left">الوقت</th>
                <th style="padding:8px;text-align:left">الإغلاق</th>
                <th style="padding:8px;text-align:left">VWAP 🔮</th>
                <th style="padding:8px;text-align:left">MA 50</th>
                <th style="padding:8px;text-align:left">MA 200</th>
                <th style="padding:8px;text-align:left">الاتجاه</th>
                <th style="padding:8px;text-align:left">تغير 1 يوم</th>
                <th style="padding:8px;text-align:left">تراكمي 3 أيام</th>
                <th style="padding:8px;text-align:left">تراكمي 5 أيام</th>
                <th style="padding:8px;text-align:left">تراكمي 10 أيام</th>
                <th style="padding:8px;text-align:left">حجم السيولة</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    </div>'''


# ══════════════════════════════════════════════════════════════
# BREAKOUTS CHART (الاختراقات)
# ══════════════════════════════════════════════════════════════

def build_breakouts_chart(r, composite_dates=None, composite_vals=None):
    """Build a breakout chart with support/resistance for multiple timeframes.
    Optionally overlay the composite market index (normalized to stock price scale).
    """
    dates = r.get("chart_dates", [])
    closes = r.get("chart_close", [])
    highs = r.get("chart_high", [])
    lows = r.get("chart_low", [])
    is_intraday = r.get("timeframe", "1d") != "1d"

    # For intraday: show only today's session
    if is_intraday and dates:
        _today_str = dates[-1][:10]  # "2026-03-19" from last date
        _today_idx = [i for i, d in enumerate(dates) if d[:10] == _today_str]
        if _today_idx:
            _start = _today_idx[0]
            dates = dates[_start:]
            closes = closes[_start:]
            highs = highs[_start:]
            lows = lows[_start:]

    n = len(closes)
    if n < 5:
        return None

    close_arr = np.array(closes, dtype=float)
    high_arr = np.array(highs, dtype=float)
    low_arr = np.array(lows, dtype=float)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Price line
    fig.add_trace(go.Scatter(
        x=dates, y=closes, mode="lines",
        line=dict(color="#4FC3F7", width=2),
        name="السعر",
        hovertemplate="%{x}<br>السعر: %{y:.2f}<extra></extra>",
    ))

    # Define timeframes
    timeframes = [
        {"days": 3, "label": "3 أيام", "color": "#FF9800", "dash": "dot"},
        {"days": 4, "label": "4 أيام", "color": "#66BB6A", "dash": "dot"},
        {"days": 10, "label": "10 أيام", "color": "#AB47BC", "dash": "solid"},
        {"days": 15, "label": "15 أيام", "color": "#EF5350", "dash": "solid"},
    ]

    for tf in timeframes:
        d = tf["days"]
        resistance = []
        support = []
        breakout_dates = []
        breakout_prices = []
        breakdown_dates = []
        breakdown_prices = []

        for i in range(n):
            if i < d:
                resistance.append(None)
                support.append(None)
                continue

            res_val = float(np.max(high_arr[i - d:i]))
            sup_val = float(np.min(low_arr[i - d:i]))
            resistance.append(round(res_val, 2))
            support.append(round(sup_val, 2))

            # Breakout: close crosses above previous resistance
            if i >= d + 1:
                prev_res = float(np.max(high_arr[i - d - 1:i - 1]))
                prev_sup = float(np.min(low_arr[i - d - 1:i - 1]))
                if close_arr[i] > prev_res and close_arr[i - 1] <= prev_res:
                    breakout_dates.append(dates[i])
                    breakout_prices.append(closes[i])
                if close_arr[i] < prev_sup and close_arr[i - 1] >= prev_sup:
                    breakdown_dates.append(dates[i])
                    breakdown_prices.append(closes[i])

        # Resistance line
        fig.add_trace(go.Scatter(
            x=dates, y=resistance, mode="lines",
            line=dict(color=tf["color"], width=1.5, dash=tf["dash"]),
            name=f"مقاومة {tf['label']}",
            hovertemplate=f"مقاومة {tf['label']}: %{{y:.2f}}<extra></extra>",
        ))
        # Support line
        fig.add_trace(go.Scatter(
            x=dates, y=support, mode="lines",
            line=dict(color=tf["color"], width=1, dash="dot"),
            name=f"دعم {tf['label']}",
            opacity=0.7,
            hovertemplate=f"دعم {tf['label']}: %{{y:.2f}}<extra></extra>",
        ))

        # Build sequential numbers that reset on opposite event
        _all_events = []
        for _idx, _dt in enumerate(breakout_dates):
            _all_events.append(("bo", _dt, breakout_prices[_idx], _idx))
        for _idx, _dt in enumerate(breakdown_dates):
            _all_events.append(("bd", _dt, breakdown_prices[_idx], _idx))
        _all_events.sort(key=lambda x: x[1])

        _bo_nums = [0] * len(breakout_dates)
        _bd_nums = [0] * len(breakdown_dates)
        _bo_count = 0
        _bd_count = 0
        for _evt_type, _dt, _pr, _orig_idx in _all_events:
            if _evt_type == "bo":
                _bo_count += 1
                _bd_count = 0  # reset breakdown count
                _bo_nums[_orig_idx] = _bo_count
            else:
                _bd_count += 1
                _bo_count = 0  # reset breakout count
                _bd_nums[_orig_idx] = _bd_count

        # Breakout markers with reset count
        if breakout_dates:
            fig.add_trace(go.Scatter(
                x=breakout_dates, y=breakout_prices,
                mode="markers+text",
                marker=dict(symbol="triangle-up", size=12, color=tf["color"],
                            line=dict(width=1, color="#fff")),
                text=[str(i) for i in _bo_nums],
                textposition="top center",
                textfont=dict(size=13, color=tf["color"], family="Tajawal"),
                name=f"اختراق {tf['label']} ({len(breakout_dates)})",
                hovertemplate=f"اختراق {tf['label']} #%{{text}}<br>%{{x}}<br>%{{y:.2f}}<extra></extra>",
            ))
        # Breakdown markers with reset count
        if breakdown_dates:
            fig.add_trace(go.Scatter(
                x=breakdown_dates, y=breakdown_prices,
                mode="markers+text",
                marker=dict(symbol="circle", size=10, color=tf["color"],
                            line=dict(width=1, color="#fff")),
                text=[str(i) for i in _bd_nums],
                textposition="bottom center",
                textfont=dict(size=13, color=tf["color"], family="Tajawal"),
                name=f"كسر {tf['label']} ({len(breakdown_dates)})",
                hovertemplate=f"كسر {tf['label']} #%{{text}}<br>%{{x}}<br>%{{y:.2f}}<extra></extra>",
            ))

    # ── Composite Market Index overlay ──
    if composite_dates and composite_vals and len(composite_dates) > 10:
        # Build lookup: date -> composite value
        comp_map = dict(zip(composite_dates, composite_vals))
        # Match stock dates to composite dates
        matched_comp = []
        matched_dates_comp = []
        for d in dates:
            if d in comp_map:
                matched_comp.append(comp_map[d])
                matched_dates_comp.append(d)

        if len(matched_comp) > 10:
            fig.add_trace(go.Scatter(
                x=matched_dates_comp, y=matched_comp,
                mode="lines",
                line=dict(color="#FFD700", width=2.5),
                name="المؤشر المركب",
                opacity=0.9,
                hovertemplate="المؤشر المركب: %{y:.1f}<extra></extra>",
            ), secondary_y=True)

    fig.update_layout(
        height=550,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,24,36,0.8)",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
            font=dict(size=10, color="#9ca3af"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(showgrid=False, tickfont=dict(size=9, color="#6b7280"),
                   tickformat="%d %b %H:%M" if is_intraday else "%d %b",
                   dtick=None if is_intraday else 14*86400000, tickangle=-45,
                   rangebreaks=([dict(bounds=[16, 9.5], pattern="hour"),
                                 dict(bounds=["sat", "mon"], pattern="day of week")]
                                if is_intraday else []),
                   showspikes=True, spikemode="across", spikethickness=1,
                   spikecolor="#4b5563", spikedash="dot"),
        yaxis=dict(showgrid=True, gridcolor="#151d30",
                   tickfont=dict(size=10, color="#4b5563"), title=None,
                   showspikes=True, spikemode="across", spikethickness=1,
                   spikecolor="#4b5563", spikedash="dot"),
        yaxis2=dict(showgrid=False,
                    tickfont=dict(size=9, color="#FFD700"),
                    title=None, overlaying="y", side="left"),
        hovermode="x unified",
        spikedistance=-1,
    )

    return fig


# ══════════════════════════════════════════════════════════════
# EVENTS PAGE — الارتدادات والاختراقات
# ══════════════════════════════════════════════════════════════

def build_event_card_html(r):
    """Build HTML card for a bounce/breakout/breakdown event."""
    event_type = r["event_type"]
    name = r["name"]
    ticker_display = r["ticker"].replace(".SR", "")
    sector = r["sector"]
    price = r["price"]
    change = r["change_pct"]
    phase_label = r["phase_label"]
    phase_color = r["phase_color"]
    flow_type_label = r.get("flow_type_label", "")
    flow_type_color = r.get("flow_type_color", "#808080")
    flow_bias = r["flow_bias"]
    absorption_score = r["absorption_score"]
    divergence = r["divergence"]
    rsi = r["rsi"]
    aggressor = r["aggressor"]

    event_type_display = r["event_type_display"]
    event_type_color = r["event_type_color"]
    event_label = r["event_label"]
    event_strength = r["event_strength"]
    event_grade_label = r["event_grade_label"]
    event_grade_color = r["event_grade_color"]
    event_backing_label = r["event_backing_label"]
    event_date = r["event_date"]
    event_scan_time = r.get("event_scan_time", "")
    event_factors = r["event_factors"]
    stock_index = r.get("stock_index")
    _idx_badge = f' <span style="background:#E040FB18;color:#E040FB;padding:1px 6px;border-radius:6px;font-size:0.70em;font-weight:700;margin-right:4px">📍 {stock_index}</span>' if stock_index else ""

    sector_color = SECTOR_COLORS.get(sector, "#607D8B")
    change_color = "#00E676" if change >= 0 else "#FF5252"
    change_icon = "▲" if change >= 0 else "▼"
    flow_color = "#00E676" if flow_bias > 10 else "#FF5252" if flow_bias < -10 else "#9ca3af"
    div_color = "#00E676" if divergence > 15 else "#FF5252" if divergence < -15 else "#9ca3af"
    rsi_color = "#FF5252" if rsi > 70 else "#00E676" if rsi < 30 else "#9ca3af"

    if aggressor == "buyers":
        agg_text, agg_color = "🟢 مشتري", "#00E676"
    elif aggressor == "sellers":
        agg_text, agg_color = "🔴 بائع", "#FF5252"
    else:
        agg_text, agg_color = "⚪ متوازن", "#9ca3af"

    # Sparkline
    close_vals = r.get("chart_close", [])
    uid = r["ticker"].replace(".", "").replace("-", "")
    sparkline = make_sparkline(close_vals, color=phase_color, uid=f"ev_{uid}")

    # Strength bar
    bar_color = event_grade_color
    bar_pct = min(event_strength, 100)
    strength_bar = (
        f'<div style="display:flex;align-items:center;gap:8px;margin:8px 0">'
        f'<span style="color:#4b5563;font-size:0.68em;font-weight:600">القوة</span>'
        f'<div style="flex:1;background:#080b14;border-radius:4px;height:6px;overflow:hidden">'
        f'<div style="width:{bar_pct}%;height:100%;background:{bar_color};border-radius:4px"></div>'
        f'</div>'
        f'<span style="color:{bar_color};font-weight:700;font-size:0.80em">{event_strength}</span>'
        f'</div>'
    )

    # Backing badge
    if r["event_backing"] == "accumulation":
        backing_html = (
            '<span style="background:rgba(0,230,118,0.08);color:#00E676;padding:3px 10px;'
            'border-radius:8px;font-size:0.72em;font-weight:600;border:1px solid rgba(0,230,118,0.15)">'
            f'📦 {event_backing_label}</span>'
        )
    elif r["event_backing"] == "distribution":
        backing_html = (
            '<span style="background:rgba(255,82,82,0.08);color:#FF5252;padding:3px 10px;'
            'border-radius:8px;font-size:0.72em;font-weight:600;border:1px solid rgba(255,82,82,0.15)">'
            f'🔴 {event_backing_label}</span>'
        )
    else:
        backing_html = (
            '<span style="background:rgba(156,163,175,0.08);color:#9ca3af;padding:3px 10px;'
            'border-radius:8px;font-size:0.72em;font-weight:600;border:1px solid rgba(156,163,175,0.15)">'
            f'⚪ {event_backing_label}</span>'
        )

    # Early bounce badge
    bounce_badge = ""
    if r.get("early_bounce") and event_type == "bounce":
        _bl = r.get("early_bounce_label", "")
        if _bl:
            bounce_badge = (
                f'<div style="color:#FF9800;font-weight:700;font-size:0.75em;margin-top:6px;'
                f'padding:5px 8px;background:rgba(255,152,0,0.08);border-radius:8px;'
                f'border:1px solid rgba(255,152,0,0.15);text-align:center">{_bl}</div>'
            )

    # ZR badge
    zr_badge = ""
    zr_status = r.get("zr_status", "normal")
    zr_status_label = r.get("zr_status_label", "")
    zr_status_color = r.get("zr_status_color", "#808080")
    if zr_status != "normal" and zr_status_label:
        zr_badge = (
            f'<span style="background:{zr_status_color}12;color:{zr_status_color};'
            f'padding:2px 8px;border-radius:8px;font-size:0.72em;font-weight:700;'
            f'border:1px solid {zr_status_color}25">{zr_status_label}</span>'
        )

    # Relative flow badge (event card) — always show
    ev_rel_badge = ""
    ev_rel_label = r.get("relative_flow_label", "")
    ev_rel_color = r.get("relative_flow_color", "#9ca3af")
    ev_rel_val = r.get("relative_flow", 0)
    if ev_rel_label:
        ev_rel_badge = (
            f'<span style="background:{ev_rel_color}12;color:{ev_rel_color};'
            f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            f'border:1px solid {ev_rel_color}25">📊 {ev_rel_label} ({ev_rel_val:+.0f})</span>'
        )

    # Volatility badge (event card)
    ev_vol_badge = ""
    ev_atr_pct = r.get("atr_pct", 0)
    ev_vol_label = r.get("volatility_label", "")
    ev_vol_color = r.get("volatility_color", "#9ca3af")
    if ev_atr_pct > 0:
        if ev_vol_label:
            ev_vol_badge = (
                f'<span style="background:{ev_vol_color}12;color:{ev_vol_color};'
                f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
                f'border:1px solid {ev_vol_color}25">{ev_vol_label} ({ev_atr_pct:.1f}%)</span>'
            )
        else:
            ev_vol_badge = (
                f'<span style="background:#9ca3af12;color:#9ca3af;'
                f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
                f'border:1px solid #9ca3af25">ATR {ev_atr_pct:.1f}%</span>'
            )

    # Volume Profile location badge (event card)
    ev_vp_badge = ""
    ev_vp_label = r.get("vp_location_label", "")
    ev_vp_color = r.get("vp_location_color", "#808080")
    ev_vp_poc = r.get("vp_poc", 0)
    if ev_vp_label:
        ev_vp_badge = (
            f'<span style="background:{ev_vp_color}12;color:{ev_vp_color};'
            f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            f'border:1px solid {ev_vp_color}25">{ev_vp_label}</span>'
        )
    elif ev_vp_poc > 0:
        ev_vp_badge = (
            f'<span style="background:#AB47BC12;color:#AB47BC;'
            f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            f'border:1px solid #AB47BC25">POC {ev_vp_poc}</span>'
        )

    # Timeframe badge (event card — only for intraday)
    ev_tf_badge = ""
    ev_timeframe = r.get("timeframe", "1d")
    ev_timeframe_label = r.get("timeframe_label", "يومي")
    if ev_timeframe != "1d":
        ev_tf_badge = (
            f'<span style="background:#FF980012;color:#FF9800;'
            f'padding:2px 8px;border-radius:8px;font-size:0.70em;font-weight:600;'
            f'border:1px solid #FF980025">⏱️ {ev_timeframe_label}</span>'
        )

    # Factors breakdown
    factors_html = ""
    for f in event_factors:
        f_pct = round(f["score"] / f["max"] * 100) if f["max"] > 0 else 0
        f_color = "#00E676" if f_pct >= 60 else "#FFD700" if f_pct >= 30 else "#4b5563"
        factors_html += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:2px 0;font-size:0.68em">'
            f'<span style="color:#6b7280">{f["name"]}</span>'
            f'<span style="color:{f_color};font-weight:600">{f["score"]}/{f["max"]}</span>'
            f'</div>'
        )

    return f'''<div class="masa-card masa-card-{event_type}">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
<span style="background:{event_type_color}18;color:{event_type_color};padding:4px 14px;border-radius:20px;font-weight:700;font-size:0.82em">{event_type_display}</span>
<span style="background:{event_grade_color}18;color:{event_grade_color};padding:3px 10px;border-radius:12px;font-size:0.75em;font-weight:700">{event_grade_label} {event_strength}/100</span>
</div>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
<span style="background:{sector_color}12;color:{sector_color};padding:2px 8px;border-radius:10px;font-size:0.68em;font-weight:500;border:1px solid {sector_color}18">{sector}</span>
<span style="color:{event_type_color};font-size:0.72em;font-weight:600">{event_label}{_idx_badge}</span>
</div>
<div style="margin-bottom:4px">
<div style="font-size:1.10em;font-weight:700;color:#fff;line-height:1.3">{name}</div>
<div style="display:flex;align-items:baseline;gap:8px;margin-top:4px;flex-wrap:wrap">
<span style="color:#4b5563;font-size:0.82em">{ticker_display}</span>
<span style="color:#fff;font-size:1.30em;font-weight:800">{price}</span>
<span style="color:{change_color};font-weight:700;font-size:0.88em">{change_icon} {abs(change):.1f}%</span>
<span style="color:#4b5563;font-size:0.72em">📅 {event_date} • 🕐 {event_scan_time}</span>
</div>
</div>
{sparkline}
<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:4px 0 6px 0;padding-top:6px;border-top:1px solid #151d30">
<span style="color:{phase_color};font-weight:600;font-size:0.80em">{phase_label}</span>
{f'<span style="background:{flow_type_color}15;color:{flow_type_color};font-size:0.68em;font-weight:600;padding:2px 6px;border-radius:6px;border:1px solid {flow_type_color}30">{flow_type_label}</span>' if flow_type_label else ''}
{zr_badge}
{ev_rel_badge}
{ev_vol_badge}
{ev_vp_badge}
{ev_tf_badge}
</div>
{strength_bar}
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;background:rgba(8,11,20,0.6);border-radius:10px;padding:8px 4px">
<div style="text-align:center">
<div style="color:#374151;font-size:0.58em;margin-bottom:2px;font-weight:600">المهاجم</div>
<div style="color:{agg_color};font-weight:700;font-size:0.75em">{agg_text}</div>
</div>
<div style="text-align:center;border-left:1px solid #151d30;border-right:1px solid #151d30">
<div style="color:#374151;font-size:0.58em;margin-bottom:2px;font-weight:600">امتصاص</div>
<div style="color:#9ca3af;font-weight:700;font-size:0.78em">{absorption_score:.0f}</div>
</div>
<div style="text-align:center;border-right:1px solid #151d30">
<div style="color:#374151;font-size:0.58em;margin-bottom:2px;font-weight:600">دايفرجنس</div>
<div style="color:{div_color};font-weight:700;font-size:0.78em">{divergence:+.0f}</div>
</div>
<div style="text-align:center">
<div style="color:#374151;font-size:0.58em;margin-bottom:2px;font-weight:600">RSI</div>
<div style="color:{rsi_color};font-weight:700;font-size:0.78em">{rsi:.0f}</div>
</div>
</div>
<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;align-items:center">
{backing_html}
<span style="color:#374151;font-size:0.68em">فلو: <b style="color:{flow_color}">{flow_bias:+.0f}</b></span>
</div>
{bounce_badge}
<div style="margin-top:8px;padding:6px 8px;background:rgba(8,11,20,0.4);border-radius:8px">
{factors_html}
</div>
</div>'''


def show_events_page(results):
    """Display the Events page — bounces, breakouts, breakdowns."""

    # ── Detail panel (if a stock is selected) ──
    if st.session_state.selected_ticker:
        selected_r = None
        for r in results:
            if r["ticker"] == st.session_state.selected_ticker:
                selected_r = r
                break
        if selected_r:
            if st.button("→ رجوع للأحداث", key="ev_back_btn", type="secondary"):
                st.session_state.selected_ticker = None
                st.rerun()
            show_detail_panel(selected_r)
            return

    # Compute composite index value for index_floor detection
    _comp_dates, _comp_vals, _, _ = build_composite_index(results)
    _comp_last = _comp_vals[-1] if _comp_vals else None
    _comp_prev = _comp_vals[-2] if len(_comp_vals) >= 2 else None

    events = classify_events(results, composite_value=_comp_last, composite_prev=_comp_prev)
    all_events = (events["bounces"] + events["breakouts"]
                  + events["breakdowns"] + events["index_floors"])

    bounce_count = len(events["bounces"])
    breakout_count = len(events["breakouts"])
    breakdown_count = len(events["breakdowns"])
    index_floor_count = len(events["index_floors"])
    total_count = len(all_events)

    # Header
    st.markdown('''
    <div style="text-align:center;padding:20px 0 10px 0">
        <span style="font-size:1.8em;font-weight:800;color:#fff">⚡ الارتدادات والاختراقات</span>
        <div style="color:#6b7280;font-size:0.92em;margin-top:6px">
            كشف تلقائي لكل ارتداد واختراق وكسر — مع تحليل القوة والتصنيف
        </div>
    </div>
    ''', unsafe_allow_html=True)

    if total_count == 0:
        st.info("لا توجد أحداث مكتشفة في المسح الحالي. جرب مسح أوسع.")
        return

    # Stats
    avg_strength = round(sum(e["event_strength"] for e in all_events) / total_count) if total_count else 0
    strong_count = sum(1 for e in all_events if e["event_grade"] == "strong")
    acc_count = sum(1 for e in all_events if e["event_backing"] == "accumulation")
    dist_count = sum(1 for e in all_events if e["event_backing"] == "distribution")
    acc_pct = round(acc_count / total_count * 100) if total_count else 0
    dist_pct = round(dist_count / total_count * 100) if total_count else 0

    avg_color = "#00E676" if avg_strength >= 65 else "#FFD700" if avg_strength >= 40 else "#9ca3af"

    st.markdown(f'''
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:10px 0">
        <div class="masa-stat">
            <div class="masa-stat-label">📊 إجمالي الأحداث</div>
            <div class="masa-stat-value" style="color:#fff;font-size:1.4em">{total_count}</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">⚡ ارتدادات</div>
            <div class="masa-stat-value" style="color:#00E676;font-size:1.4em">{bounce_count}</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">🚀 اختراقات</div>
            <div class="masa-stat-value" style="color:#FFD700;font-size:1.4em">{breakout_count}</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">📉 كسرات</div>
            <div class="masa-stat-value" style="color:#FF5252;font-size:1.4em">{breakdown_count}</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">🔻 قاع المؤشر</div>
            <div class="masa-stat-value" style="color:#E040FB;font-size:1.4em">{index_floor_count}</div>
        </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:0 0 16px 0">
        <div class="masa-stat">
            <div class="masa-stat-label">💪 متوسط القوة</div>
            <div class="masa-stat-value" style="color:{avg_color};font-size:1.4em">{avg_strength}/100</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">🏆 أحداث قوية</div>
            <div class="masa-stat-value" style="color:#00E676;font-size:1.4em">{strong_count}</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">📦 مدعومة بتجميع</div>
            <div class="masa-stat-value" style="color:#00E676;font-size:1.4em">{acc_pct}%</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">🔴 مدعومة بتصريف</div>
            <div class="masa-stat-value" style="color:#FF5252;font-size:1.4em">{dist_pct}%</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # Filters
    fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns(5)
    with fcol1:
        type_filter = st.selectbox(
            "🏷️ النوع",
            ["الكل", "⚡ ارتدادات فقط", "🚀 اختراقات فقط", "📉 كسرات فقط",
             "🔻 قاع المؤشر فقط"],
            key="ev_type_filter",
        )
    with fcol2:
        strength_filter = st.selectbox(
            "💪 القوة",
            ["الكل", "قوية فقط (65+)", "متوسطة+ (40+)", "ضعيفة فقط (<40)"],
            key="ev_strength_filter",
        )
    with fcol3:
        ev_sectors = sorted(set(e["sector"] for e in all_events))
        ev_sector = st.selectbox("📂 القطاع", ["كل القطاعات"] + ev_sectors, key="ev_sector")
    with fcol4:
        _ev_rel_map = {
            "الكل": None,
            "📊 ضد التيار": "ضد التيار",
            "📊 يتفوق": "يتفوق",
            "📊 أضعف من القطاع": "أضعف من القطاع",
        }
        ev_rel_label = st.selectbox("📊 قوة نسبية", list(_ev_rel_map.keys()), key="ev_rel")
        ev_rel_val = _ev_rel_map[ev_rel_label]
    with fcol5:
        ev_sort = st.selectbox(
            "📊 الترتيب",
            ["أقوى حدث", "أقوى أوردر فلو", "أعلى تغير ↑"],
            key="ev_sort",
        )

    # Apply filters
    if type_filter == "⚡ ارتدادات فقط":
        filtered = list(events["bounces"])
    elif type_filter == "🚀 اختراقات فقط":
        filtered = list(events["breakouts"])
    elif type_filter == "📉 كسرات فقط":
        filtered = list(events["breakdowns"])
    elif type_filter == "🔻 قاع المؤشر فقط":
        filtered = list(events["index_floors"])
    else:
        filtered = list(all_events)

    if strength_filter == "قوية فقط (65+)":
        filtered = [e for e in filtered if e["event_strength"] >= 65]
    elif strength_filter == "متوسطة+ (40+)":
        filtered = [e for e in filtered if e["event_strength"] >= 40]
    elif strength_filter == "ضعيفة فقط (<40)":
        filtered = [e for e in filtered if e["event_strength"] < 40]

    if ev_sector != "كل القطاعات":
        filtered = [e for e in filtered if e["sector"] == ev_sector]

    if ev_rel_val:
        filtered = [e for e in filtered if e.get("relative_flow_label") == ev_rel_val]

    if ev_sort == "أقوى أوردر فلو":
        filtered.sort(key=lambda x: abs(x["flow_bias"]), reverse=True)
    elif ev_sort == "أعلى تغير ↑":
        filtered.sort(key=lambda x: x["change_pct"], reverse=True)
    else:
        filtered.sort(key=lambda x: x["event_strength"], reverse=True)

    if not filtered:
        st.info("لا توجد أحداث مع هذا الفلتر.")
        return

    # ── Composite Index Event Card ──
    composite_ev = _detect_composite_event(results)
    if composite_ev:
        st.markdown(
            '<div style="color:#B39DDB;font-size:0.85em;font-weight:700;margin:12px 0 6px 0">'
            '📊 حالة مؤشر المنصة</div>',
            unsafe_allow_html=True,
        )
        st.markdown(build_composite_event_card_html(composite_ev), unsafe_allow_html=True)
        st.markdown('<div style="border-bottom:1px solid #1a2035;margin:12px 0 16px 0"></div>',
                    unsafe_allow_html=True)

    st.markdown(f'<div style="color:#4b5563;font-size:0.82em;margin-bottom:8px">'
                f'عرض {len(filtered)} من {total_count} حدث</div>',
                unsafe_allow_html=True)

    # Cards grid
    cols = st.columns(3)
    for idx, ev in enumerate(filtered):
        with cols[idx % 3]:
            st.markdown(build_event_card_html(ev), unsafe_allow_html=True)
            if st.button(
                f"📊 تفاصيل {ev['name']}",
                key=f"ev_detail_{ev['ticker']}_{idx}",
                use_container_width=True,
            ):
                st.session_state.selected_ticker = ev["ticker"]
                st.session_state.prev_page = "events"
                st.rerun()


# ══════════════════════════════════════════════════════════════
# COMPOSITE INDEX EVENT DETECTION (مؤشر المنصة كحدث)
# ══════════════════════════════════════════════════════════════

def _detect_composite_event(results):
    """
    Detect if the composite market index itself has a bounce/breakout/breakdown.
    Returns: event dict (like a stock result) or None.
    """
    dates, idx_vals, idx_highs, idx_lows = build_composite_index(results)
    if len(idx_vals) < 15:
        return None

    # Also get PFI for flow context
    pfi, acc_breadth, dist_breadth, _, interp = build_platform_flow_index(results)

    # Current values
    last_val = idx_vals[-1]
    prev_val = idx_vals[-2] if len(idx_vals) >= 2 else last_val
    change_pct = ((last_val - prev_val) / prev_val * 100) if prev_val > 0 else 0

    # Recent peak & trough (20 days)
    lookback = min(20, len(idx_vals))
    recent_vals = idx_vals[-lookback:]
    recent_lows_vals = idx_lows[-lookback:]
    recent_highs = idx_highs[-lookback:]

    peak_20 = max(recent_vals)
    trough_20 = min(recent_lows_vals)

    # Drop from peak
    drop_from_peak = ((trough_20 - peak_20) / peak_20 * 100) if peak_20 > 0 else 0
    # Bounce from trough
    bounce_from_low = ((last_val - trough_20) / trough_20 * 100) if trough_20 > 0 else 0

    # 5-day & 10-day momentum
    val_5d = idx_vals[-6] if len(idx_vals) >= 6 else idx_vals[0]
    val_10d = idx_vals[-11] if len(idx_vals) >= 11 else idx_vals[0]
    mom_5d = ((last_val - val_5d) / val_5d * 100) if val_5d > 0 else 0
    mom_10d = ((last_val - val_10d) / val_10d * 100) if val_10d > 0 else 0

    # All-time high in this scan
    all_high = max(idx_vals)
    near_high = (last_val >= all_high * 0.98)

    # ── Event Detection ──
    event_type = None
    event_label = ""

    # 1. BOUNCE: dropped significantly and recovering
    if drop_from_peak <= -3 and bounce_from_low >= 1.5 and mom_5d > 0:
        event_type = "bounce"
        if drop_from_peak <= -8 and bounce_from_low >= 4:
            event_label = "⚡ ارتداد حاد — المؤشر هبط {:.1f}% وارتد {:.1f}%".format(
                abs(drop_from_peak), bounce_from_low
            )
        elif pfi >= 55:
            event_label = "ارتداد مدعوم بتدفق شرائي (PFI {:.0f})".format(pfi)
        else:
            event_label = "ارتداد أولي — المؤشر يتعافى من القاع"

    # 2. BREAKOUT: at/near highs with momentum
    elif near_high and mom_5d > 1 and pfi >= 55:
        event_type = "breakout"
        if pfi >= 65 and acc_breadth >= 50:
            event_label = "🚀 اختراق سوقي مع تجميع واسع ({:.0f}% أسهم)".format(acc_breadth)
        elif mom_5d > 2:
            event_label = "اختراق قمة — زخم قوي {:.1f}%".format(mom_5d)
        else:
            event_label = "اختراق قمة المؤشر"

    # 3. BREAKDOWN: declining with selling pressure
    elif mom_5d < -1.5 and pfi <= 45:
        event_type = "breakdown"
        if pfi <= 35 and dist_breadth >= 50:
            event_label = "📉 كسر سوقي مع تصريف واسع ({:.0f}% أسهم)".format(dist_breadth)
        elif mom_10d < -3:
            event_label = "كسر هابط — المؤشر خسر {:.1f}% في 10 أيام".format(abs(mom_10d))
        else:
            event_label = "كسر — ضغط بيعي على المؤشر"

    if not event_type:
        return None

    # ── Build synthetic result dict ──
    # Phase mapping from PFI
    if pfi >= 60:
        phase, phase_label, phase_color = "accumulation", "تجميع سوقي", "#00E676"
    elif pfi <= 40:
        phase, phase_label, phase_color = "distribution", "تصريف سوقي", "#FF5252"
    elif pfi >= 50:
        phase, phase_label, phase_color = "transition", "تحول إيجابي", "#FFD700"
    else:
        phase, phase_label, phase_color = "neutral", "حياد", "#9ca3af"

    # Flow bias from PFI (convert 0-100 to -100..+100)
    flow_bias = round((pfi - 50) * 2, 1)

    # RSI-like: compute from index values
    gains, losses = [], []
    for i in range(max(1, len(idx_vals) - 14), len(idx_vals)):
        diff = idx_vals[i] - idx_vals[i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = np.mean(gains) if gains else 0
    avg_loss = np.mean(losses) if losses else 0.001
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = round(100 - (100 / (1 + rs)), 1)

    # Volume ratio: average of stock volume ratios
    vol_ratios = [r.get("volume_ratio", 1.0) for r in results if r.get("volume_ratio")]
    volume_ratio = round(np.mean(vol_ratios), 2) if vol_ratios else 1.0

    synthetic = {
        "ticker": "COMPOSITE_INDEX",
        "name": "📊 مؤشر المنصة",
        "sector": "مؤشر السوق",
        "price": round(last_val, 2),
        "change_pct": round(change_pct, 2),
        "phase": phase,
        "phase_label": phase_label,
        "phase_color": phase_color,
        "flow_bias": flow_bias,
        "flow_type": "accumulation" if pfi >= 60 else "distribution" if pfi <= 40 else "neutral",
        "flow_type_label": interp.split("—")[0].strip() if "—" in interp else interp,
        "flow_type_color": "#00E676" if pfi >= 55 else "#FF5252" if pfi <= 45 else "#9ca3af",
        "location": "above" if near_high else "bottom" if last_val <= trough_20 * 1.02 else "middle",
        "zr_status": "normal",
        "zr_status_label": "",
        "zr_status_color": "#808080",
        "volume_ratio": volume_ratio,
        "rsi": rsi,
        "divergence": 0,
        "absorption_score": 0,
        "absorption_bias": "neutral",
        "aggressor": "buyers" if pfi >= 60 else "sellers" if pfi <= 40 else "neutral",
        "cdv_trend": "rising" if pfi >= 55 else "falling" if pfi <= 45 else "flat",
        "maturity_stage": "none",
        "dist_maturity_stage": "none",
        "early_bounce": False,
        "early_bounce_label": "",
        "chart_dates": list(dates),
        "chart_close": list(idx_vals),
        "chart_high": list(idx_highs),
        "chart_low": list(idx_lows),
        "chart_volume": [],
        "chart_cdv": [],
        # Extra PFI data
        "_is_composite": True,
        "_pfi": pfi,
        "_acc_breadth": acc_breadth,
        "_dist_breadth": dist_breadth,
        "_mom_5d": round(mom_5d, 2),
        "_mom_10d": round(mom_10d, 2),
        "_interp": interp,
    }

    # Run through event classification
    from core.events import classify_events as _classify
    events = _classify([synthetic])
    all_ev = events["bounces"] + events["breakouts"] + events["breakdowns"]

    if all_ev:
        ev = all_ev[0]
        # Override the label with our more descriptive one
        ev["event_label"] = event_label
        ev["_is_composite"] = True
        ev["_pfi"] = pfi
        ev["_acc_breadth"] = acc_breadth
        ev["_dist_breadth"] = dist_breadth
        ev["_interp"] = interp
        return ev

    # If classify_events didn't pick it up, build manually
    from core.events import _build_event
    ev = _build_event(synthetic, event_type, event_label)
    ev["_is_composite"] = True
    ev["_pfi"] = pfi
    ev["_acc_breadth"] = acc_breadth
    ev["_dist_breadth"] = dist_breadth
    ev["_interp"] = interp
    return ev


def build_composite_event_card_html(ev):
    """Build a special HTML card for the composite index event."""
    event_type = ev["event_type"]
    event_type_display = ev["event_type_display"]
    event_type_color = ev["event_type_color"]
    event_label = ev["event_label"]
    event_strength = ev["event_strength"]
    event_grade_label = ev["event_grade_label"]
    event_grade_color = ev["event_grade_color"]
    event_date = ev["event_date"]
    event_scan_time = ev.get("event_scan_time", "")
    event_factors = ev["event_factors"]

    price = ev["price"]
    change = ev["change_pct"]
    change_color = "#00E676" if change >= 0 else "#FF5252"
    change_icon = "▲" if change >= 0 else "▼"

    pfi = ev.get("_pfi", 50)
    acc_breadth = ev.get("_acc_breadth", 0)
    dist_breadth = ev.get("_dist_breadth", 0)
    interp = ev.get("_interp", "")
    mom_5d = ev.get("_mom_5d", 0)

    pfi_color = "#00E676" if pfi >= 60 else "#FF5252" if pfi <= 40 else "#FFD700"

    # Sparkline
    close_vals = ev.get("chart_close", [])
    sparkline = make_sparkline(close_vals, color=event_type_color, uid="composite_ev")

    # Strength bar
    bar_pct = min(event_strength, 100)
    strength_bar = (
        f'<div style="display:flex;align-items:center;gap:8px;margin:8px 0">'
        f'<span style="color:#4b5563;font-size:0.68em;font-weight:600">القوة</span>'
        f'<div style="flex:1;background:#080b14;border-radius:4px;height:6px;overflow:hidden">'
        f'<div style="width:{bar_pct}%;height:100%;background:{event_grade_color};border-radius:4px"></div>'
        f'</div>'
        f'<span style="color:{event_grade_color};font-weight:700;font-size:0.80em">{event_strength}</span>'
        f'</div>'
    )

    # Factors
    factors_html = ""
    for f in event_factors:
        f_pct = round(f["score"] / f["max"] * 100) if f["max"] > 0 else 0
        f_color = "#00E676" if f_pct >= 60 else "#FFD700" if f_pct >= 30 else "#4b5563"
        factors_html += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:2px 0;font-size:0.68em">'
            f'<span style="color:#6b7280">{f["name"]}</span>'
            f'<span style="color:{f_color};font-weight:600">{f["score"]}/{f["max"]}</span>'
            f'</div>'
        )

    return f'''<div class="masa-card masa-card-{event_type}" style="border:2px solid {event_type_color}30;position:relative">
<div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,{event_type_color},{event_type_color}40);border-radius:12px 12px 0 0"></div>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
<span style="background:{event_type_color}18;color:{event_type_color};padding:4px 14px;border-radius:20px;font-weight:700;font-size:0.82em">{event_type_display}</span>
<span style="background:{event_grade_color}18;color:{event_grade_color};padding:3px 10px;border-radius:12px;font-size:0.75em;font-weight:700">{event_grade_label} {event_strength}/100</span>
</div>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
<span style="background:#7C4DFF12;color:#7C4DFF;padding:2px 8px;border-radius:10px;font-size:0.68em;font-weight:500;border:1px solid #7C4DFF18">مؤشر السوق</span>
<span style="color:{event_type_color};font-size:0.70em;font-weight:600">{event_label}</span>
</div>
<div style="margin-bottom:4px">
<div style="font-size:1.15em;font-weight:800;color:#fff;line-height:1.3">📊 مؤشر المنصة</div>
<div style="display:flex;align-items:baseline;gap:8px;margin-top:4px;flex-wrap:wrap">
<span style="color:#fff;font-size:1.30em;font-weight:800">{price:.2f}</span>
<span style="color:{change_color};font-weight:700;font-size:0.88em">{change_icon} {abs(change):.2f}%</span>
<span style="color:#4b5563;font-size:0.72em">📅 {event_date} • 🕐 {event_scan_time}</span>
</div>
</div>
{sparkline}
{strength_bar}
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;background:rgba(8,11,20,0.6);border-radius:10px;padding:8px 4px">
<div style="text-align:center">
<div style="color:#374151;font-size:0.58em;margin-bottom:2px;font-weight:600">PFI</div>
<div style="color:{pfi_color};font-weight:700;font-size:0.82em">{pfi:.0f}</div>
</div>
<div style="text-align:center;border-left:1px solid #151d30;border-right:1px solid #151d30">
<div style="color:#374151;font-size:0.58em;margin-bottom:2px;font-weight:600">تجميع</div>
<div style="color:#00E676;font-weight:700;font-size:0.78em">{acc_breadth:.0f}%</div>
</div>
<div style="text-align:center;border-right:1px solid #151d30">
<div style="color:#374151;font-size:0.58em;margin-bottom:2px;font-weight:600">تصريف</div>
<div style="color:#FF5252;font-weight:700;font-size:0.78em">{dist_breadth:.0f}%</div>
</div>
<div style="text-align:center">
<div style="color:#374151;font-size:0.58em;margin-bottom:2px;font-weight:600">زخم 5 أيام</div>
<div style="color:{"#00E676" if mom_5d > 0 else "#FF5252"};font-weight:700;font-size:0.78em">{mom_5d:+.1f}%</div>
</div>
</div>
<div style="margin-top:6px;padding:4px 8px;background:rgba(124,77,255,0.06);border-radius:8px;border:1px solid rgba(124,77,255,0.12)">
<div style="color:#B39DDB;font-size:0.75em;font-weight:600;text-align:center">{interp}</div>
</div>
<div style="margin-top:8px;padding:6px 8px;background:rgba(8,11,20,0.4);border-radius:8px">
{factors_html}
</div>
</div>'''


# ══════════════════════════════════════════════════════════════
# MARKET BREAKOUT INDEX (مؤشر الاختراقات)
# ══════════════════════════════════════════════════════════════

def build_composite_index(results):
    """
    Build a composite market index by aggregating daily returns of ALL stocks.
    Returns: (dates, index_values, index_highs, index_lows)
    Starting at 100, each day = volume-weighted average daily return.
    """
    if not results:
        return [], [], [], []

    # Collect stocks with valid chart data (including volume)
    stocks = []
    for r in results:
        dates = r.get("chart_dates", [])
        closes = r.get("chart_close", [])
        highs = r.get("chart_high", [])
        lows = r.get("chart_low", [])
        volumes = r.get("chart_volume", [])
        if len(dates) < 15:
            continue
        stocks.append({
            "dates": dates,
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
        })

    if not stocks:
        return [], [], [], []

    all_dates = sorted(set(d for s in stocks for d in s["dates"]))

    # For each date, compute volume-weighted average return
    avg_returns = []
    avg_high_returns = []
    avg_low_returns = []

    for date_str in all_dates:
        day_returns = []
        day_high_returns = []
        day_low_returns = []
        day_volumes = []
        for s in stocks:
            if date_str not in s["dates"]:
                continue
            idx = s["dates"].index(date_str)
            if idx == 0:
                continue
            prev_c = s["closes"][idx - 1]
            cur_c = s["closes"][idx]
            cur_h = s["highs"][idx]
            cur_l = s["lows"][idx]
            # Skip NaN or zero values
            if not prev_c or prev_c == 0 or prev_c != prev_c:  # NaN check
                continue
            if not cur_c or cur_c != cur_c:
                continue
            vol = s["volumes"][idx] if s["volumes"] and idx < len(s["volumes"]) else 0
            vol = max(vol, 1)  # fallback: minimum weight of 1
            day_returns.append((cur_c - prev_c) / prev_c)
            day_high_returns.append(((cur_h if cur_h == cur_h else cur_c) - prev_c) / prev_c)
            day_low_returns.append(((cur_l if cur_l == cur_l else cur_c) - prev_c) / prev_c)
            day_volumes.append(vol)

        if day_returns:
            total_vol = sum(day_volumes)
            if total_vol > 0:
                avg_returns.append(sum(r * v for r, v in zip(day_returns, day_volumes)) / total_vol)
                avg_high_returns.append(sum(r * v for r, v in zip(day_high_returns, day_volumes)) / total_vol)
                avg_low_returns.append(sum(r * v for r, v in zip(day_low_returns, day_volumes)) / total_vol)
            else:
                avg_returns.append(np.mean(day_returns))
                avg_high_returns.append(np.mean(day_high_returns))
                avg_low_returns.append(np.mean(day_low_returns))
        else:
            avg_returns.append(0.0)
            avg_high_returns.append(0.0)
            avg_low_returns.append(0.0)

    # Compound into index starting at 100
    index_vals = [100.0]
    index_highs = [100.0]
    index_lows = [100.0]
    for i in range(1, len(avg_returns)):
        r = avg_returns[i]
        r = r if r == r else 0.0  # NaN guard
        index_vals.append(round(index_vals[-1] * (1 + r), 2))
        rh = avg_high_returns[i]
        rh = rh if rh == rh else 0.0
        rl = avg_low_returns[i]
        rl = rl if rl == rl else 0.0
        index_highs.append(round(index_vals[-2] * (1 + rh), 2))
        index_lows.append(round(index_vals[-2] * (1 + rl), 2))

    if len(index_vals) > 0:
        index_highs[0] = index_vals[0]
        index_lows[0] = index_vals[0]

    return all_dates, index_vals, index_highs, index_lows


def build_platform_flow_index(results):
    """
    Build Platform Flow Index (PFI) — volume-weighted aggregate of
    CDV, FlowBias, Absorption, and Phase across all stocks.

    Returns: pfi_value (0-100), acc_breadth (%), dist_breadth (%),
             flow_scores list, interpretation string
    """
    import math

    if not results:
        return 50.0, 0.0, 0.0, [], "لا توجد بيانات"

    flow_scores = []

    for r in results:
        # ── 1. Normalize each component to -1..+1 ──

        # CDV norm: use tanh to cap outliers
        cdv_series = r.get("chart_cdv", [])
        if len(cdv_series) >= 20:
            cdv_recent = cdv_series[-1] if cdv_series[-1] else 0
            cdv_vals = [v for v in cdv_series[-20:] if v is not None]
            cdv_std = np.std(cdv_vals) if cdv_vals else 1
            cdv_norm = math.tanh(cdv_recent / cdv_std) if cdv_std > 0 else 0
        else:
            cdv_norm = 0

        # Flow Bias norm: already -100..+100
        fb = r.get("flow_bias", 0)
        fb_norm = max(-1, min(1, fb / 100))

        # Absorption norm: 0..100 → scale by bias direction
        abs_score = r.get("absorption_score", 0)
        abs_bias = r.get("absorption_bias", "neutral")
        if abs_bias == "buy":
            abs_norm = abs_score / 100
        elif abs_bias == "sell":
            abs_norm = -abs_score / 100
        else:
            abs_norm = 0

        # Phase/State norm: accumulation/spring = +1, distribution/upthrust = -1
        phase = r.get("phase", "neutral")
        if phase in ("accumulation", "spring", "markup"):
            state_norm = 1.0
        elif phase in ("distribution", "upthrust", "markdown"):
            state_norm = -1.0
        else:
            state_norm = 0.0

        # ── 2. FlowScore = weighted sum ──
        score = (0.40 * cdv_norm +
                 0.30 * fb_norm +
                 0.20 * abs_norm +
                 0.10 * state_norm)

        # ── 3. Volume weight ──
        volumes = r.get("chart_volume", [])
        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else 1
        today_vol = volumes[-1] if volumes else 0
        vol_weight = max(0.5, min(2.0, today_vol / avg_vol if avg_vol > 0 else 1))

        flow_scores.append({
            "ticker": r["ticker"],
            "name": r["name"],
            "score": round(score, 3),
            "vol_weight": round(vol_weight, 2),
            "cdv_norm": round(cdv_norm, 2),
            "fb_norm": round(fb_norm, 2),
            "abs_norm": round(abs_norm, 2),
            "state_norm": round(state_norm, 1),
            "volume": today_vol,
        })

    if not flow_scores:
        return 50.0, 0.0, 0.0, [], "لا توجد بيانات"

    # ── 3. Platform Flow Index (volume-weighted) ──
    total_w = sum(fs["vol_weight"] for fs in flow_scores)
    pfi_raw = sum(fs["score"] * fs["vol_weight"] for fs in flow_scores) / total_w if total_w > 0 else 0

    # Convert to 0-100 scale
    pfi = round(50 + 50 * max(-1, min(1, pfi_raw)), 1)

    # ── 4. Breadth ──
    n = len(flow_scores)
    acc_breadth = round(sum(1 for fs in flow_scores if fs["score"] > 0.2) / n * 100, 1)
    dist_breadth = round(sum(1 for fs in flow_scores if fs["score"] < -0.2) / n * 100, 1)

    # ── 5. Interpretation ──
    if pfi >= 65 and acc_breadth >= 50:
        interp = "🟢 تجميع سوقي حقيقي — فلوس تدخل على نطاق واسع"
    elif pfi >= 60 and acc_breadth < 40:
        interp = "🟡 تجميع مركّز — فلوس تدخل أسهم محددة فقط"
    elif pfi <= 35 and dist_breadth >= 50:
        interp = "🔴 تصريف سوقي — فلوس تطلع على نطاق واسع"
    elif pfi <= 40 and dist_breadth < 40:
        interp = "🟠 تصريف مركّز — خروج من أسهم محددة"
    elif pfi >= 55:
        interp = "🟢 ميل شرائي خفيف"
    elif pfi <= 45:
        interp = "🔴 ميل بيعي خفيف"
    else:
        interp = "⚪ حياد — السوق متوازن"

    # Sort by score for display
    flow_scores.sort(key=lambda x: x["score"], reverse=True)

    return pfi, acc_breadth, dist_breadth, flow_scores, interp


def build_composite_data_table(dates, index_vals):
    """Build HTML data table for the composite index (like individual stock table)."""
    n = len(dates)
    if n < 5:
        return "<p style='color:#6b7280'>لا توجد بيانات كافية</p>"

    def cum_change(idx, days):
        prev_idx = idx - days
        if prev_idx < 0 or index_vals[prev_idx] == 0:
            return 0.0
        return (index_vals[idx] - index_vals[prev_idx]) / index_vals[prev_idx] * 100

    show_n = min(20, n)
    rows_html = ""
    for j in range(show_n):
        i = n - 1 - j
        day_chg = cum_change(i, 1)
        cum3 = cum_change(i, 3)
        cum5 = cum_change(i, 5)
        cum10 = cum_change(i, 10)

        # Direction score
        score = 0
        if i >= 1 and index_vals[i] > index_vals[i - 1]: score += 1
        elif i >= 1 and index_vals[i] < index_vals[i - 1]: score -= 1
        if i >= 3 and index_vals[i] > index_vals[i - 3]: score += 1
        elif i >= 3 and index_vals[i] < index_vals[i - 3]: score -= 1
        if i >= 5 and index_vals[i] > index_vals[i - 5]: score += 1
        elif i >= 5 and index_vals[i] < index_vals[i - 5]: score -= 1
        if i >= 10 and index_vals[i] > index_vals[i - 10]: score += 1
        elif i >= 10 and index_vals[i] < index_vals[i - 10]: score -= 1

        sc = "#00E676" if score > 0 else "#FF5252" if score < 0 else "#6b7280"

        rows_html += f'''
        <tr style="border-bottom:1px solid #1a1f30">
            <td style="padding:6px 8px;color:#9ca3af;font-size:0.82em;white-space:nowrap">{dates[i]}</td>
            <td style="padding:6px 8px;color:#fff;font-weight:600">{index_vals[i]:.2f}</td>
            <td style="padding:6px 8px;color:{sc};font-weight:600">{score}</td>
            <td style="padding:6px 8px">{_change_dot(day_chg)}</td>
            <td style="padding:6px 8px">{_change_dot(cum3)}</td>
            <td style="padding:6px 8px">{_change_dot(cum5)}</td>
            <td style="padding:6px 8px">{_change_dot(cum10)}</td>
        </tr>'''

    return f'''
    <div style="text-align:center;margin-bottom:12px">
        <span style="font-size:1.3em;font-weight:800;color:#fff">📋 بيانات المؤشر المركب</span>
    </div>
    <div style="overflow-x:auto;direction:rtl">
    <table style="width:100%;border-collapse:collapse;font-size:0.88em;direction:ltr">
        <thead>
            <tr style="border-bottom:2px solid #2a3050;color:#6b7280;font-size:0.82em">
                <th style="padding:8px;text-align:left">الوقت</th>
                <th style="padding:8px;text-align:left">المؤشر</th>
                <th style="padding:8px;text-align:left">الاتجاه</th>
                <th style="padding:8px;text-align:left">تغير 1 يوم</th>
                <th style="padding:8px;text-align:left">تراكمي 3 أيام</th>
                <th style="padding:8px;text-align:left">تراكمي 5 أيام</th>
                <th style="padding:8px;text-align:left">تراكمي 10 أيام</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>'''


def build_composite_breakouts_chart(dates, index_vals, index_highs, index_lows, is_intraday=False):
    """Build a breakout chart for the composite index — same style as individual stocks."""
    n = len(dates)
    if n < 5:
        return None

    close_arr = np.array(index_vals, dtype=float)
    high_arr = np.array(index_highs, dtype=float)
    low_arr = np.array(index_lows, dtype=float)

    fig = go.Figure()

    # Price line (the composite index)
    fig.add_trace(go.Scatter(
        x=dates, y=index_vals, mode="lines",
        line=dict(color="#4FC3F7", width=2.5),
        name="المؤشر المركب",
        hovertemplate="%{x}<br>المؤشر: %{y:.2f}<extra></extra>",
    ))

    timeframes = [
        {"days": 3, "label": "3 أيام", "color": "#FF9800", "dash": "dot"},
        {"days": 4, "label": "4 أيام", "color": "#66BB6A", "dash": "dot"},
        {"days": 10, "label": "10 أيام", "color": "#AB47BC", "dash": "solid"},
        {"days": 15, "label": "15 أيام", "color": "#EF5350", "dash": "solid"},
    ]

    for tf in timeframes:
        d = tf["days"]
        resistance = []
        support = []
        breakout_dates = []
        breakout_prices = []
        breakdown_dates = []
        breakdown_prices = []

        for i in range(n):
            if i < d:
                resistance.append(None)
                support.append(None)
                continue

            res_val = float(np.max(high_arr[i - d:i]))
            sup_val = float(np.min(low_arr[i - d:i]))
            resistance.append(round(res_val, 2))
            support.append(round(sup_val, 2))

            if i >= d + 1:
                prev_res = float(np.max(high_arr[i - d - 1:i - 1]))
                prev_sup = float(np.min(low_arr[i - d - 1:i - 1]))
                if close_arr[i] > prev_res and close_arr[i - 1] <= prev_res:
                    breakout_dates.append(dates[i])
                    breakout_prices.append(index_vals[i])
                if close_arr[i] < prev_sup and close_arr[i - 1] >= prev_sup:
                    breakdown_dates.append(dates[i])
                    breakdown_prices.append(index_vals[i])

        fig.add_trace(go.Scatter(
            x=dates, y=resistance, mode="lines",
            line=dict(color=tf["color"], width=1.5, dash=tf["dash"]),
            name=f"مقاومة {tf['label']}",
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=support, mode="lines",
            line=dict(color=tf["color"], width=1, dash="dot"),
            name=f"دعم {tf['label']}", opacity=0.7,
        ))
        # Build sequential numbers that reset on opposite event
        _all_ev = []
        for _ix, _dt in enumerate(breakout_dates):
            _all_ev.append(("bo", _dt, _ix))
        for _ix, _dt in enumerate(breakdown_dates):
            _all_ev.append(("bd", _dt, _ix))
        _all_ev.sort(key=lambda x: x[1])
        _bo_n = [0] * len(breakout_dates)
        _bd_n = [0] * len(breakdown_dates)
        _boc, _bdc = 0, 0
        for _et, _dt, _oi in _all_ev:
            if _et == "bo":
                _boc += 1; _bdc = 0; _bo_n[_oi] = _boc
            else:
                _bdc += 1; _boc = 0; _bd_n[_oi] = _bdc

        if breakout_dates:
            fig.add_trace(go.Scatter(
                x=breakout_dates, y=breakout_prices, mode="markers+text",
                marker=dict(symbol="triangle-up", size=12, color=tf["color"],
                            line=dict(width=1, color="#fff")),
                text=[str(i) for i in _bo_n],
                textposition="top center",
                textfont=dict(size=13, color=tf["color"]),
                name=f"اختراق {tf['label']} ({len(breakout_dates)})",
            ))
        if breakdown_dates:
            fig.add_trace(go.Scatter(
                x=breakdown_dates, y=breakdown_prices, mode="markers+text",
                marker=dict(symbol="circle", size=10, color=tf["color"],
                            line=dict(width=1, color="#fff")),
                text=[str(i) for i in _bd_n],
                textposition="bottom center",
                textfont=dict(size=13, color=tf["color"]),
                name=f"كسر {tf['label']} ({len(breakdown_dates)})",
            ))

    fig.update_layout(
        height=550,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,24,36,0.8)",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
            font=dict(size=10, color="#9ca3af"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#6b7280"),
                   tickformat="%d %b %H:%M" if is_intraday else "%d %b %Y",
                   rangebreaks=([dict(bounds=[16, 9.5], pattern="hour"),
                                 dict(bounds=["sat", "mon"], pattern="day of week")]
                                if is_intraday else []),
                   showspikes=True, spikemode="across", spikethickness=1,
                   spikecolor="#4b5563", spikedash="dot"),
        yaxis=dict(showgrid=True, gridcolor="#151d30",
                   tickfont=dict(size=10, color="#4b5563"),
                   showspikes=True, spikemode="across", spikethickness=1,
                   spikecolor="#4b5563", spikedash="dot"),
        hovermode="x unified",
        spikedistance=-1,
    )
    return fig


BENCHMARK_MAP = {
    "saudi": {"ticker": "^TASI.SR", "name": "TASI", "color": "#FFD700"},
    "us": {"ticker": "^GSPC", "name": "S&P 500", "color": "#FF9800"},
}


def _fetch_benchmark_normalized(dates, market_key="saudi", start_val=100.0):
    """
    Fetch benchmark index (TASI / S&P 500) and normalize to start_val,
    aligned to the same dates as the composite index.
    Handles both daily and intraday date formats.
    """
    bench = BENCHMARK_MAP.get(market_key, BENCHMARK_MAP["saudi"])
    try:
        t = yf.Ticker(bench["ticker"])
        df = t.history(period="1y", interval="1d")
        if df is None or df.empty:
            return {}, 0, 0, bench["name"], bench["color"]
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Build date -> close map (daily key: YYYY-MM-DD)
        bench_map = {}
        for dt, row in df.iterrows():
            bench_map[dt.strftime("%Y-%m-%d")] = float(row["Close"])

        # Detect intraday: if dates have time component (longer than 10 chars or contain space/T)
        _is_intraday = False
        if dates and (len(dates[0]) > 10 or " " in dates[0] or "T" in dates[0]):
            _is_intraday = True

        # For intraday dates, extract just the date part for matching
        def _date_key(d):
            return d[:10] if _is_intraday else d

        # Find first date that exists in both
        first_val = None
        for d in dates:
            dk = _date_key(d)
            if dk in bench_map:
                first_val = bench_map[dk]
                break

        if first_val is None or first_val == 0:
            return {}, 0, 0, bench["name"], bench["color"]

        # Normalize — for intraday, spread daily value across all bars of that day
        normalized = {}
        for d in dates:
            dk = _date_key(d)
            if dk in bench_map:
                normalized[d] = round(bench_map[dk] / first_val * start_val, 2)

        # Returns
        closes = [float(v) for v in df["Close"].values]
        day_ret = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
        last_price = closes[-1]

        return normalized, day_ret, last_price, bench["name"], bench["color"]
    except Exception:
        return {}, 0, 0, bench["name"], bench["color"]


def _compute_lead_lag(dates, composite_vals, tasi_normalized):
    """
    Compute correlation at different lags to check if composite leads TASI.
    Positive lag = composite leads (moves first).
    Returns: list of (lag_days, correlation) + best lead.
    """
    # Build aligned daily returns
    comp_rets = []
    tasi_rets = []
    valid_dates = []

    for i in range(1, len(dates)):
        d = dates[i]
        d_prev = dates[i - 1]
        if d in tasi_normalized and d_prev in tasi_normalized:
            t_prev = tasi_normalized[d_prev]
            t_curr = tasi_normalized[d]
            if t_prev > 0 and composite_vals[i - 1] > 0:
                comp_rets.append((composite_vals[i] - composite_vals[i - 1]) / composite_vals[i - 1])
                tasi_rets.append((t_curr - t_prev) / t_prev)
                valid_dates.append(d)

    if len(comp_rets) < 20:
        return [], 0, 0

    comp_arr = np.array(comp_rets)
    tasi_arr = np.array(tasi_rets)

    # Compute correlation at lags -5 to +5
    results = []
    for lag in range(-5, 6):
        if lag > 0:
            # Composite leads: compare comp[:-lag] with tasi[lag:]
            c = comp_arr[:-lag] if lag < len(comp_arr) else comp_arr
            t = tasi_arr[lag:] if lag < len(tasi_arr) else tasi_arr
        elif lag < 0:
            # TASI leads: compare comp[-lag:] with tasi[:lag]
            c = comp_arr[-lag:]
            t = tasi_arr[:lag]
        else:
            c = comp_arr
            t = tasi_arr

        n = min(len(c), len(t))
        if n < 10:
            continue
        c = c[:n]
        t = t[:n]

        corr = float(np.corrcoef(c, t)[0, 1]) if np.std(c) > 0 and np.std(t) > 0 else 0
        results.append({"lag": lag, "corr": round(corr, 3)})

    # Same-day correlation
    same_day_corr = 0
    for r in results:
        if r["lag"] == 0:
            same_day_corr = r["corr"]

    # Find best positive lag (composite leads) — must EXCEED same-day by margin
    best_lead = 0
    best_corr = same_day_corr
    for r in results:
        if r["lag"] > 0 and r["corr"] > best_corr + 0.05:
            best_lead = r["lag"]
            best_corr = r["corr"]

    # Also check if TASI leads (negative lags)
    best_tasi_lead = 0
    best_tasi_corr = same_day_corr
    for r in results:
        if r["lag"] < 0 and r["corr"] > best_tasi_corr + 0.05:
            best_tasi_lead = abs(r["lag"])
            best_tasi_corr = r["corr"]

    # If TASI leads more strongly, return negative lead
    if best_tasi_corr > best_corr:
        best_lead = -best_tasi_lead

    return results, best_lead, same_day_corr


def show_breakout_index(results, market_key="saudi"):
    """Display the composite market breakout index page."""
    bench_info = BENCHMARK_MAP.get(market_key, BENCHMARK_MAP["saudi"])
    bench_name = bench_info["name"]

    st.markdown(f'''
    <div style="text-align:center;margin:10px 0 16px 0">
        <span style="font-size:1.6em;font-weight:800;color:#fff">🚀 مؤشر اختراقات السوق</span>
        <div style="color:#6b7280;font-size:0.85em;margin-top:4px">
            مؤشر مركب من بيانات كل الأسهم — مقارنة مع {bench_name}
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # Build composite index
    dates, index_vals, index_highs, index_lows = build_composite_index(results)

    # For intraday: filter to last session only (match sector map) — keep RAW values
    _idx_intra = len(dates) > 0 and (len(dates[0]) > 10 or " " in dates[0] or "T" in dates[0])
    if _idx_intra and dates:
        _unique_days = sorted(set(d[:10] for d in dates))
        _mask = []
        for _off in range(len(_unique_days)):
            _target = _unique_days[-(1 + _off)]
            _mask = [(i, d, v, h, l) for i, (d, v, h, l) in enumerate(zip(dates, index_vals, index_highs, index_lows)) if d[:10] == _target]
            if len(_mask) >= 2:
                break
        if _mask:
            dates = [m[1] for m in _mask]
            index_vals = [round(m[2], 2) for m in _mask]
            index_highs = [round(m[3], 2) for m in _mask]
            index_lows = [round(m[4], 2) for m in _mask]

    if len(dates) < 2:
        st.warning("لا توجد بيانات كافية لبناء المؤشر")
        return

    # Fetch benchmark (TASI or S&P 500)
    bench_norm, bench_day_ret, bench_last, bench_name, bench_color = _fetch_benchmark_normalized(
        dates, market_key=market_key, start_val=index_vals[0]
    )

    # Lead/lag analysis
    lag_results, best_lead, same_day_corr = _compute_lead_lag(dates, index_vals, bench_norm)

    # Summary
    last_val = index_vals[-1]
    first_val = index_vals[0]
    total_return = (last_val - first_val) / first_val * 100
    # Daily change: compare last bar to previous bar
    prev_val = index_vals[-2] if len(index_vals) >= 2 else last_val
    day_change = last_val - prev_val  # absolute change
    day_return = (day_change / prev_val * 100) if prev_val > 0 else 0
    week_return = (index_vals[-1] - index_vals[-5]) / index_vals[-5] * 100 if len(index_vals) >= 5 else 0

    # Benchmark return
    bench_first = list(bench_norm.values())[0] if bench_norm else 100
    bench_last_norm = list(bench_norm.values())[-1] if bench_norm else 100
    bench_total_ret = (bench_last_norm - bench_first) / bench_first * 100 if bench_first > 0 else 0

    tc = "#00E676" if total_return >= 0 else "#FF5252"
    dc = "#00E676" if day_return >= 0 else "#FF5252"
    bench_tc = "#00E676" if bench_total_ret >= 0 else "#FF5252"

    # ── Support / Resistance on composite index ──
    import numpy as np
    _iv_arr = np.array(index_vals, dtype=float)
    _n_iv = len(_iv_arr)
    _comp_support = round(float(np.min(_iv_arr[-min(20, _n_iv):])), 2) if _n_iv >= 5 else None
    _comp_resistance = round(float(np.max(_iv_arr[-min(20, _n_iv):])), 2) if _n_iv >= 5 else None
    _comp_high_all = round(float(np.max(_iv_arr)), 2)
    _comp_low_all = round(float(np.min(_iv_arr)), 2)

    # Distance from support/resistance
    _dist_support = round((last_val - _comp_support) / _comp_support * 100, 1) if _comp_support and _comp_support > 0 else None
    _dist_resistance = round((_comp_resistance - last_val) / last_val * 100, 1) if _comp_resistance and last_val > 0 else None

    # Alert: crossing key levels
    _comp_alerts = []
    if _comp_support and len(index_vals) >= 3:
        if last_val < _comp_support and index_vals[-2] >= _comp_support:
            _comp_alerts.append(("🔴", f"كسر دعم المؤشر ({_comp_support:.1f})", "#FF5252"))
        if _comp_resistance and last_val > _comp_resistance and index_vals[-2] <= _comp_resistance:
            _comp_alerts.append(("🟢", f"اختراق مقاومة المؤشر ({_comp_resistance:.1f})", "#00E676"))
    # Trend direction
    if _n_iv >= 10:
        _recent_slope = (_iv_arr[-1] - _iv_arr[-10]) / 10
        if _recent_slope > 0.3:
            _comp_trend = ("📈", "صاعد", "#00E676")
        elif _recent_slope < -0.3:
            _comp_trend = ("📉", "هابط", "#FF5252")
        else:
            _comp_trend = ("➡️", "عرضي", "#FFD700")
    else:
        _comp_trend = ("➡️", "—", "#9E9E9E")

    # Lead/lag badge — honest assessment
    if best_lead > 0:
        lead_text = f"يسبق {bench_name} بـ {best_lead} يوم"
        lead_color = "#00E676"
        lead_icon = "⚡"
    elif best_lead < 0:
        lead_text = f"{bench_name} يسبقه بـ {abs(best_lead)} يوم"
        lead_color = "#FF9800"
        lead_icon = "⏪"
    elif same_day_corr > 0.5:
        lead_text = f"متزامن مع {bench_name}"
        lead_color = "#FFD700"
        lead_icon = "🔄"
    else:
        lead_text = f"ارتباط ضعيف مع {bench_name}"
        lead_color = "#FF5252"
        lead_icon = "📊"

    st.markdown(f'''
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px;direction:rtl">
        <div style="background:linear-gradient(135deg,#131a2e,#0e1424);border:1px solid #4FC3F740;
                    border-radius:12px;padding:14px;text-align:center">
            <div style="color:#6b7280;font-size:0.78em;margin-bottom:6px">📊 المؤشر المركب</div>
            <div style="color:#4FC3F7;font-size:2em;font-weight:800">{last_val:.2f}</div>
            <div style="color:{dc};font-size:0.85em;font-weight:600">{day_return:+.2f}% اليوم ({day_change:+.1f})</div>
        </div>
        <div style="background:linear-gradient(135deg,#131a2e,#0e1424);border:1px solid #192035;
                    border-radius:12px;padding:14px;text-align:center">
            <div style="color:#6b7280;font-size:0.78em;margin-bottom:6px">📈 {bench_name}</div>
            <div style="color:{bench_color};font-size:1.8em;font-weight:800">{bench_last:,.0f}</div>
            <div style="color:{'#00E676' if bench_day_ret >= 0 else '#FF5252'};font-size:0.82em;font-weight:600">{bench_day_ret:+.2f}% اليوم</div>
        </div>
        <div style="background:linear-gradient(135deg,#131a2e,#0e1424);border:1px solid #192035;
                    border-radius:12px;padding:14px;text-align:center">
            <div style="color:#6b7280;font-size:0.78em;margin-bottom:6px">📊 الارتباط</div>
            <div style="color:#AB47BC;font-size:1.6em;font-weight:800">{same_day_corr:.1%}</div>
            <div style="color:#4b5563;font-size:0.75em">مع {bench_name}</div>
        </div>
        <div style="background:linear-gradient(135deg,#131a2e,#0e1424);border:1px solid {lead_color}40;
                    border-radius:12px;padding:14px;text-align:center">
            <div style="color:#6b7280;font-size:0.78em;margin-bottom:6px">{lead_icon} العلاقة</div>
            <div style="color:{lead_color};font-size:1.1em;font-weight:800">{lead_text}</div>
        </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:10px;direction:rtl">
        <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:8px 12px;text-align:center">
            <div style="color:#6b7280;font-size:0.7em">🟢 الدعم (20d)</div>
            <div style="color:#00E676;font-weight:700;font-size:1.1em">{_comp_support:.1f}</div>
            <div style="color:#4b5563;font-size:0.7em">بُعد {_dist_support:+.1f}%</div>
        </div>
        <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:8px 12px;text-align:center">
            <div style="color:#6b7280;font-size:0.7em">🔴 المقاومة (20d)</div>
            <div style="color:#FF5252;font-weight:700;font-size:1.1em">{_comp_resistance:.1f}</div>
            <div style="color:#4b5563;font-size:0.7em">بُعد {_dist_resistance:.1f}%</div>
        </div>
        <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:8px 12px;text-align:center">
            <div style="color:#6b7280;font-size:0.7em">{_comp_trend[0]} الاتجاه</div>
            <div style="color:{_comp_trend[2]};font-weight:700;font-size:1.1em">{_comp_trend[1]}</div>
        </div>
        <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:8px 12px;text-align:center">
            <div style="color:#6b7280;font-size:0.7em">🔝 أعلى قمة</div>
            <div style="color:#FFD700;font-weight:700;font-size:1.1em">{_comp_high_all:.1f}</div>
        </div>
        <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:8px 12px;text-align:center">
            <div style="color:#6b7280;font-size:0.7em">📉 أدنى قاع</div>
            <div style="color:#9E9E9E;font-weight:700;font-size:1.1em">{_comp_low_all:.1f}</div>
        </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:8px;direction:rtl">
        <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:10px 16px;
                    display:flex;justify-content:space-between;align-items:center">
            <span style="color:#4FC3F7;font-weight:700;font-size:0.88em">عائد المؤشر المركب</span>
            <span style="color:{tc};font-weight:800;font-size:1.2em">{total_return:+.2f}%</span>
        </div>
        <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:10px 16px;
                    display:flex;justify-content:space-between;align-items:center">
            <span style="color:{bench_color};font-weight:700;font-size:0.88em">عائد {bench_name}</span>
            <span style="color:{bench_tc};font-weight:800;font-size:1.2em">{bench_total_ret:+.2f}%</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Composite Index Alerts ──
    for _ca_icon, _ca_text, _ca_color in _comp_alerts:
        if _ca_color == "#FF5252":
            st.error(f"**{_ca_icon} تنبيه المؤشر المركب:** {_ca_text}")
        else:
            st.success(f"**{_ca_icon} تنبيه المؤشر المركب:** {_ca_text}")

    # ── Platform Flow Index (PFI) ──────────────────────────
    pfi, acc_breadth, dist_breadth, flow_scores, pfi_interp = build_platform_flow_index(results)
    pfi_color = "#00E676" if pfi >= 55 else "#FF5252" if pfi <= 45 else "#FFD700"
    acc_color = "#00E676" if acc_breadth >= 40 else "#FFD700" if acc_breadth >= 25 else "#FF5252"
    dist_color = "#FF5252" if dist_breadth >= 40 else "#FFD700" if dist_breadth >= 25 else "#9ca3af"
    neutral_breadth = round(100 - acc_breadth - dist_breadth, 1)

    st.markdown(f'''
    <div style="background:linear-gradient(135deg,rgba({int(pfi_color[1:3],16)},{int(pfi_color[3:5],16)},{int(pfi_color[5:7],16)},0.06),#0e1424);
                border:1px solid {pfi_color}30;border-radius:14px;padding:18px 22px;margin:6px 0 16px 0;direction:rtl">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
            <span style="font-size:1.2em;font-weight:800;color:#fff">⚡ مؤشر تدفق الأموال (PFI)</span>
            <span style="color:{pfi_color};font-size:2em;font-weight:900">{pfi:.0f}</span>
        </div>
        <div style="background:#0a0f1a;border-radius:8px;height:14px;margin-bottom:12px;overflow:hidden;position:relative">
            <div style="position:absolute;right:0;height:100%;width:{pfi}%;background:linear-gradient(90deg,{pfi_color}88,{pfi_color});border-radius:8px;transition:width 0.5s"></div>
            <div style="position:absolute;right:50%;top:0;height:100%;width:2px;background:#333"></div>
        </div>
        <div style="color:{pfi_color};font-weight:700;font-size:0.95em;margin-bottom:10px">{pfi_interp}</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
            <div style="text-align:center;background:rgba(0,230,118,0.06);border-radius:10px;padding:8px">
                <div style="color:#6b7280;font-size:0.68em;margin-bottom:2px">📦 تجميع</div>
                <div style="color:{acc_color};font-weight:800;font-size:1.2em">{acc_breadth:.0f}%</div>
            </div>
            <div style="text-align:center;background:rgba(156,163,175,0.06);border-radius:10px;padding:8px">
                <div style="color:#6b7280;font-size:0.68em;margin-bottom:2px">⚪ حياد</div>
                <div style="color:#9ca3af;font-weight:800;font-size:1.2em">{neutral_breadth:.0f}%</div>
            </div>
            <div style="text-align:center;background:rgba(255,82,82,0.06);border-radius:10px;padding:8px">
                <div style="color:#6b7280;font-size:0.68em;margin-bottom:2px">🔻 تصريف</div>
                <div style="color:{dist_color};font-weight:800;font-size:1.2em">{dist_breadth:.0f}%</div>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # Tabs
    idx_tab_compare, idx_tab_chart, idx_tab_data, idx_tab_lag = st.tabs([
        f"📊 مقارنة مع {bench_name}", "🚀 شارت الاختراقات", "📋 البيانات", "⚡ تحليل السبق"
    ])

    with idx_tab_compare:
        # Time range filter (daily only)
        _comp_dates = dates
        _comp_vals = index_vals
        if not _idx_intra and len(dates) > 20:
            _total_bars_idx = len(dates)
            _all_idx_ranges = [("الكل", 0), ("3 أشهر", 63), ("6 أشهر", 126), ("سنة", 252), ("سنتين", 504), ("3 سنوات", 756), ("5 سنوات", 1260)]
            _range_options = {k: v for k, v in _all_idx_ranges if v == 0 or v < _total_bars_idx}
            _range_cols = st.columns(len(_range_options))
            _selected_range = st.session_state.get("_comp_range", "الكل")
            if _selected_range not in _range_options:
                _selected_range = "الكل"
            for _ci, (_rlabel, _rdays) in enumerate(_range_options.items()):
                _btn_style = "primary" if _selected_range == _rlabel else "secondary"
                if _range_cols[_ci].button(_rlabel, key=f"_comp_r_{_rlabel}", type=_btn_style, use_container_width=True):
                    st.session_state["_comp_range"] = _rlabel
                    _selected_range = _rlabel
            _rdays = _range_options.get(_selected_range, 0)
            if _rdays > 0 and _rdays < _total_bars_idx:
                _comp_dates = dates[-_rdays:]
                _comp_vals = index_vals[-_rdays:]
            # NO rebase — raw values. Just zoom.

        # Re-fetch benchmark normalized to composite's start value for this range
        _start_v = _comp_vals[0] if _comp_vals else 100
        if _comp_dates is not dates:
            _comp_bench, _, _, _, _ = _fetch_benchmark_normalized(
                _comp_dates, market_key=market_key, start_val=_start_v
            )
        else:
            _comp_bench = bench_norm

        # Comparison chart: Composite vs Benchmark
        comp_fig = go.Figure()

        comp_fig.add_trace(go.Scatter(
            x=_comp_dates, y=_comp_vals, mode="lines",
            line=dict(color="#4FC3F7", width=2.5),
            name="المؤشر المركب",
            hovertemplate="المؤشر: %{y:.2f}<extra></extra>",
        ))
        # Benchmark line
        b_dates = [d for d in _comp_dates if d in _comp_bench]
        b_vals = [_comp_bench[d] for d in b_dates]
        if b_dates:
            comp_fig.add_trace(go.Scatter(
                x=b_dates, y=b_vals, mode="lines",
                line=dict(color=bench_color, width=2.5),
                name=bench_name,
                hovertemplate=f"{bench_name}: %{{y:.2f}}<extra></extra>",
            ))

        # Detect intraday data → add rangebreaks to hide overnight gaps
        _is_intra = len(dates) > 0 and (len(dates[0]) > 10 or " " in dates[0] or "T" in dates[0])
        _xaxis_cfg = dict(showgrid=False, tickfont=dict(size=10, color="#6b7280"),
                          tickformat="%d %b %Y")
        if _is_intra:
            _xaxis_cfg["rangebreaks"] = [
                dict(bounds=[16, 9.5], pattern="hour"),  # Hide after-hours (4pm - 9:30am)
                dict(bounds=["sat", "mon"], pattern="day of week"),  # Hide weekends
            ]
            _xaxis_cfg["tickformat"] = "%d %b %H:%M"
            _xaxis_cfg["hoverformat"] = "%d %b %H:%M"

        comp_fig.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(20,24,36,0.8)",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="center", x=0.5,
                font=dict(size=12, color="#9ca3af"),
                bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=_xaxis_cfg,
            yaxis=dict(showgrid=True, gridcolor="#151d30",
                       tickfont=dict(size=10, color="#4b5563")),
            hovermode="x unified",
        spikedistance=-1,
            annotations=[
            ],
        )

        # Add support/resistance lines on chart
        if _comp_support:
            comp_fig.add_hline(y=_comp_support, line_dash="dot", line_color="#00E676", line_width=1,
                               annotation_text=f"دعم {_comp_support:.1f}", annotation_position="bottom left",
                               annotation_font_size=10, annotation_font_color="#00E676")
        if _comp_resistance:
            comp_fig.add_hline(y=_comp_resistance, line_dash="dot", line_color="#FF5252", line_width=1,
                               annotation_text=f"مقاومة {_comp_resistance:.1f}", annotation_position="top left",
                               annotation_font_size=10, annotation_font_color="#FF5252")

        st.plotly_chart(comp_fig, use_container_width=True, config={"displayModeBar": False})

    with idx_tab_chart:
        bc1, bc2, bc3, bc4 = st.columns(4)
        show_3 = bc1.checkbox("عرض 3 أيام 🟠", value=True, key="idx_brk3")
        show_4 = bc2.checkbox("عرض 4 أيام 🟢", value=False, key="idx_brk4")
        show_10 = bc3.checkbox("عرض 10 أيام 🟣", value=True, key="idx_brk10")
        show_15 = bc4.checkbox("عرض 15 أيام 🔴", value=False, key="idx_brk15")

        brk_chart = build_composite_breakouts_chart(dates, index_vals, index_highs, index_lows, is_intraday=_idx_intra)
        if brk_chart:
            tf_filter = {3: show_3, 4: show_4, 10: show_10, 15: show_15}
            for trace in brk_chart.data:
                name = trace.name or ""
                if name == "المؤشر المركب":
                    trace.visible = True
                    continue
                for days, show in tf_filter.items():
                    label = f"{days} أيام"
                    if label in name:
                        trace.visible = True if show else "legendonly"
                        break
            st.plotly_chart(brk_chart, use_container_width=True, config={"displayModeBar": False})

    with idx_tab_data:
        data_html = build_composite_data_table(dates, index_vals)
        st.html(f'''
        <div style="font-family:Tajawal,sans-serif;background:#0e1424;padding:16px;border-radius:12px">
            {data_html}
        </div>
        ''')

    with idx_tab_lag:
        if not lag_results:
            st.info("لا توجد بيانات كافية لتحليل السبق")
        else:
            st.markdown(f'''
            <div style="text-align:center;margin-bottom:12px">
                <span style="font-size:1.2em;font-weight:700;color:#fff">⚡ تحليل السبق والتأخر</span>
                <div style="color:#6b7280;font-size:0.82em;margin-top:4px">
                    هل المؤشر المركب يتحرك قبل {bench_name} أو بعده؟
                </div>
            </div>
            ''', unsafe_allow_html=True)

            # Lag correlation chart
            lag_fig = go.Figure()
            lags = [r["lag"] for r in lag_results]
            corrs = [r["corr"] for r in lag_results]
            colors = ["#00E676" if l > 0 else "#FF5252" if l < 0 else "#FFD700" for l in lags]

            lag_fig.add_trace(go.Bar(
                x=lags, y=corrs,
                marker_color=colors,
                hovertemplate="تأخر: %{x} يوم<br>ارتباط: %{y:.3f}<extra></extra>",
            ))
            lag_fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(20,24,36,0.8)",
                xaxis=dict(
                    title=dict(text=f"← {bench_name} يسبق  |  المؤشر يسبق →", font=dict(size=11, color="#6b7280")),
                    tickfont=dict(size=10, color="#6b7280"),
                    showgrid=False, dtick=1,
                ),
                yaxis=dict(
                    title=dict(text="الارتباط", font=dict(size=10, color="#6b7280")),
                    showgrid=True, gridcolor="#151d30",
                    tickfont=dict(size=10, color="#4b5563"),
                ),
            )
            st.plotly_chart(lag_fig, use_container_width=True, config={"displayModeBar": False})

            # Interpretation
            st.markdown(f'''
            <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:12px;
                        padding:16px;direction:rtl;margin-top:8px">
                <div style="font-weight:700;color:#fff;margin-bottom:8px;font-size:1em">📖 القراءة:</div>
                <div style="color:#9ca3af;font-size:0.88em;line-height:1.8">
                    • <b style="color:#FFD700">الارتباط المتزامن:</b> {same_day_corr:.1%}
                    {'— قوي ✅' if same_day_corr > 0.5 else '— متوسط 🟡' if same_day_corr > 0.3 else '— ضعيف ❌'}<br>
                    • <b style="color:#00E676">الأعمدة الخضراء (يمين):</b> المؤشر المركب يتحرك أولاً → {bench_name} يتبع بعده<br>
                    • <b style="color:#FF5252">الأعمدة الحمراء (يسار):</b> {bench_name} يتحرك أولاً → المؤشر يتبع<br>
                    • <b>أعلى عمود أخضر = المؤشر يسبق {bench_name} بكم يوم</b><br>
                    • إذا أعلى ارتباط عند lag +1 أو +2 → <span style="color:#00E676;font-weight:700">المؤشر مؤشر قيادي (Leading)</span>
                </div>
            </div>
            ''', unsafe_allow_html=True)


def show_detail_panel(r):
    """Show detailed Order Flow analysis panel for a selected stock."""
    decision_color = r["decision_color"]
    change_color = "#00E676" if r["change_pct"] >= 0 else "#FF5252"
    change_icon = "▲" if r["change_pct"] >= 0 else "▼"
    sector_color = SECTOR_COLORS.get(r["sector"], "#607D8B")
    ticker_display = r["ticker"].replace(".SR", "")
    phase_color = r["phase_color"]

    # ZR status
    zr_status = r.get("zr_status", "normal")
    zr_status_label = r.get("zr_status_label", "")
    zr_status_color = r.get("zr_status_color", "#808080")
    zr_detail_html = ""
    if zr_status != "normal" and zr_status_label:
        zr_detail_html = (
            f'<span style="background:{zr_status_color}15;color:{zr_status_color};'
            f'padding:3px 12px;border-radius:12px;font-size:0.85em;font-weight:700;'
            f'border:1px solid {zr_status_color}25">{zr_status_label}</span>'
        )

    # Aggressor text
    agg = r["aggressor"]
    agg_html = (
        '<span style="color:#00E676;font-weight:600">🟢 المشتري هو المهاجم</span>' if agg == "buyers"
        else '<span style="color:#FF5252;font-weight:600">🔴 البائع هو المهاجم</span>' if agg == "sellers"
        else '<span style="color:#9ca3af;font-weight:500">⚪ متوازن</span>'
    )

    # Header
    flow_color_val = '#00E676' if r['flow_bias'] > 0 else '#FF5252'
    div_color_val = '#00E676' if r['divergence'] > 0 else '#FF5252'
    zr_h = r.get("zr_high", "—")
    zr_l = r.get("zr_low", "—")
    st.html(f'''
    <div style="font-family:Tajawal,sans-serif;background:linear-gradient(135deg,#131a2e,#0e1424);border:1px solid #192035;
                border-radius:16px;padding:20px 24px;margin:10px 0;direction:rtl">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
            <div>
                <span style="font-size:1.5em;font-weight:800;color:#fff">{r["name"]}</span>
                <span style="color:#4b5563;font-size:0.9em;margin-right:10px">{ticker_display}</span>
                <span style="background:{sector_color}15;color:{sector_color};padding:3px 12px;border-radius:12px;font-size:0.78em;font-weight:500">{r["sector"]}</span>
            </div>
            <div style="display:flex;align-items:baseline;gap:12px">
                <span style="font-size:1.8em;font-weight:800;color:#fff">{r["price"]}</span>
                <span style="color:{change_color};font-weight:700;font-size:1.1em">{change_icon} {abs(r["change_pct"]):.1f}%</span>
                <span style="background:{decision_color}18;color:{decision_color};padding:5px 16px;border-radius:20px;font-weight:700;font-size:0.9em">{r["decision_label"]}</span>
            </div>
        </div>
        <div style="display:flex;gap:16px;margin-top:12px;flex-wrap:wrap;color:#6b7280;font-size:0.85em">
            <span style="color:{phase_color};font-weight:600">{r["phase_label"]}</span>
            {f'<span style="background:{r.get("flow_type_color","#808080")}15;color:{r.get("flow_type_color","#808080")};padding:3px 12px;border-radius:12px;font-size:0.88em;font-weight:700;border:1px solid {r.get("flow_type_color","#808080")}30">{r.get("flow_type_label","")}</span>' if r.get("flow_type_label") else ''}
            <span>📍 {r["location_label"]}</span>
            <span>أوردر فلو: <b style="color:{flow_color_val}">{r["flow_bias"]:+.0f}</b></span>
            {agg_html}
            <span>امتصاص: <b>{r["absorption_score"]:.0f}</b></span>
            <span>دايفرجنس: <b style="color:{div_color_val}">{r["divergence"]:+.0f}</b></span>
            <span>RSI: <b>{r["rsi"]:.0f}</b></span>
            {zr_detail_html}
        </div>
        <div style="display:flex;gap:16px;margin-top:6px;flex-wrap:wrap;color:#4b5563;font-size:0.80em">
            <span>ZR سقف: <b style="color:#FFFFFF">{zr_h}</b></span>
            <span>ZR قاع: <b style="color:#FF9800">{zr_l}</b></span>
            <span>قوة نسبية: <b style="color:{r.get('relative_flow_color','#9ca3af')}">{r.get('relative_flow',0):+.0f}</b> ({r.get('relative_flow_label','—')})</span>
            <span>متوسط القطاع: <b>{r.get('sector_avg_flow',0):+.0f}</b></span>
            <span>ATR%: <b style="color:{r.get('volatility_color','#9ca3af')}">{r.get('atr_pct',0):.1f}%</b></span>
            <span>POC: <b style="color:#AB47BC">{r.get('vp_poc','—')}</b></span>
            <span>S1: <b style="color:#4FC3F7">{r.get('pivot_s1','—')}</b> R1: <b style="color:#FF8A80">{r.get('pivot_r1','—')}</b></span>
        </div>
        {f'<div style="margin-top:10px;padding:8px 14px;background:rgba(255,152,0,0.08);border-radius:10px;border:1px solid rgba(255,152,0,0.15);color:#FF9800;font-weight:700;font-size:0.88em;text-align:center">{r.get("early_bounce_label","")}</div>' if r.get("early_bounce") else ''}
    </div>
    ''')

    # ── Accumulation Maturity Timeline ──
    _detail_intra = r.get("timeframe", "1d") != "1d"
    _detail_unit = "شمعة" if _detail_intra else "يوم"
    m_stage = r.get("maturity_stage", "none")
    m_timeline = r.get("maturity_timeline", [])
    if m_stage != "none" and m_timeline:
        m_label = r.get("maturity_label", "")
        m_color = r.get("maturity_color", "#808080")
        m_days = r.get("maturity_days", 0)

        steps_html = ""
        for i, step in enumerate(m_timeline):
            is_current = (i == len(m_timeline) - 1)
            dot_size = "14px" if is_current else "10px"
            border = f"3px solid {m_color}" if is_current else "2px solid #374151"
            bg = m_color if is_current else "transparent"
            font_w = "700" if is_current else "500"
            opacity = "1" if is_current else "0.6"
            steps_html += f'''
            <div style="display:flex;align-items:center;gap:10px;opacity:{opacity}">
                <div style="width:{dot_size};height:{dot_size};border-radius:50%;border:{border};background:{bg};flex-shrink:0"></div>
                <div>
                    <span style="font-weight:{font_w};font-size:0.88em">{step["label"]}</span>
                    <span style="color:#4b5563;font-size:0.78em;margin-right:8px">{step["date"]}</span>
                    <span style="color:{m_color if is_current else '#6b7280'};font-size:0.78em;font-weight:600">{step["action"]}</span>
                </div>
            </div>
            '''
            # Connector line between steps
            if i < len(m_timeline) - 1:
                steps_html += '<div style="width:2px;height:16px;background:#374151;margin-right:5px"></div>'

        _m_cf_ev = r.get("maturity_cf_events", 0)
        _m_cf_d = r.get("maturity_cf_days", 0)
        _m_conv = r.get("maturity_conviction", 100.0)
        _m_clean_d = m_days - _m_cf_d
        _m_conv_html = ""
        if m_days >= 5:
            if _m_conv >= 85:
                _mc = "#00E676"
            elif _m_conv >= 65:
                _mc = "#FFD700"
            else:
                _mc = "#FF5252"
            _g_pct = round(_m_clean_d / m_days * 100) if m_days > 0 else 100
            _r_pct = 100 - _g_pct
            _m_conv_html = (
                f'<div style="margin:10px 0 8px;padding:10px 14px;background:#0a0f1c;border-radius:10px;'
                f'border:1px solid #192035">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                f'<span style="color:#fff;font-weight:700;font-size:0.9em">نقاء المرحلة</span>'
                f'<span style="color:{_mc};font-weight:800;font-size:1.3em">{_m_conv:.0f}%</span>'
                f'</div>'
                f'<div style="display:flex;height:12px;border-radius:6px;overflow:hidden;background:#1a1f30">'
                f'<div style="width:{_g_pct}%;background:#00E676;border-radius:6px 0 0 6px"></div>'
                f'<div style="width:{_r_pct}%;background:#FF5252;border-radius:0 6px 6px 0"></div>'
                f'</div>'
                f'<div style="display:flex;justify-content:space-between;margin-top:8px;font-size:0.78em">'
                f'<span style="color:#00E676">🟢 {_m_clean_d} يوم تجميع</span>'
                f'<span style="color:#FF5252">🔴 {_m_cf_d} يوم تصريف ({_m_cf_ev} نبضة)</span>'
                f'</div>'
                f'</div>'
            )

        st.html(f'''
        <div style="font-family:Tajawal,sans-serif;background:linear-gradient(135deg,rgba({int(m_color[1:3],16)},{int(m_color[3:5],16)},{int(m_color[5:7],16)},0.05),#0e1424);
                    border:1px solid {m_color}25;border-radius:12px;padding:14px 18px;margin:8px 0;direction:rtl">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <span style="color:{m_color};font-weight:700;font-size:0.92em">{m_label}</span>
                <span style="color:#4b5563;font-size:0.78em">تجميع مستمر: <b style="color:#fff">{m_days} {_detail_unit}</b></span>
            </div>
            {_m_conv_html}
            <div style="display:flex;flex-direction:column;gap:4px">
                {steps_html}
            </div>
        </div>
        ''')

    # ── Distribution Maturity Timeline ──
    dm_stage = r.get("dist_maturity_stage", "none")
    dm_timeline = r.get("dist_maturity_timeline", [])
    if dm_stage != "none" and dm_timeline:
        dm_label = r.get("dist_maturity_label", "")
        dm_color = r.get("dist_maturity_color", "#FF5252")
        dm_days = r.get("dist_maturity_days", 0)

        dm_steps_html = ""
        for i, step in enumerate(dm_timeline):
            is_current = (i == len(dm_timeline) - 1)
            dot_size = "14px" if is_current else "10px"
            border = f"3px solid {dm_color}" if is_current else "2px solid #374151"
            bg = dm_color if is_current else "transparent"
            font_w = "700" if is_current else "500"
            opacity = "1" if is_current else "0.6"
            dm_steps_html += f'''
            <div style="display:flex;align-items:center;gap:10px;opacity:{opacity}">
                <div style="width:{dot_size};height:{dot_size};border-radius:50%;border:{border};background:{bg};flex-shrink:0"></div>
                <div>
                    <span style="font-weight:{font_w};font-size:0.88em">{step["label"]}</span>
                    <span style="color:#4b5563;font-size:0.78em;margin-right:8px">{step["date"]}</span>
                    <span style="color:{dm_color if is_current else '#6b7280'};font-size:0.78em;font-weight:600">{step["action"]}</span>
                </div>
            </div>
            '''
            if i < len(dm_timeline) - 1:
                dm_steps_html += '<div style="width:2px;height:16px;background:#374151;margin-right:5px"></div>'

        _d_cf_ev = r.get("dist_cf_events", 0)
        _d_cf_d = r.get("dist_cf_days", 0)
        _d_conv = r.get("dist_conviction", 100.0)
        _d_clean_d = dm_days - _d_cf_d
        _d_conv_html = ""
        if dm_days >= 5:
            # For distribution: high conviction = strong selling (red/bad), low = weak (green/good)
            if _d_conv >= 85:
                _dc = "#FF5252"
            elif _d_conv >= 65:
                _dc = "#FFD700"
            else:
                _dc = "#00E676"
            _dg_pct = round(_d_clean_d / dm_days * 100) if dm_days > 0 else 100
            _dr_pct = 100 - _dg_pct
            _d_conv_html = (
                f'<div style="margin:10px 0 8px;padding:10px 14px;background:#0a0f1c;border-radius:10px;'
                f'border:1px solid #192035">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                f'<span style="color:#fff;font-weight:700;font-size:0.9em">نقاء المرحلة</span>'
                f'<span style="color:{_dc};font-weight:800;font-size:1.3em">{_d_conv:.0f}%</span>'
                f'</div>'
                f'<div style="display:flex;height:12px;border-radius:6px;overflow:hidden;background:#1a1f30">'
                f'<div style="width:{_dg_pct}%;background:#FF5252;border-radius:6px 0 0 6px"></div>'
                f'<div style="width:{_dr_pct}%;background:#00E676;border-radius:0 6px 6px 0"></div>'
                f'</div>'
                f'<div style="display:flex;justify-content:space-between;margin-top:8px;font-size:0.78em">'
                f'<span style="color:#FF5252">🔴 {_d_clean_d} يوم تصريف</span>'
                f'<span style="color:#00E676">🟢 {_d_cf_d} يوم تجميع ({_d_cf_ev} نبضة)</span>'
                f'</div>'
                f'</div>'
            )

        r_hex = int(dm_color[1:3], 16)
        g_hex = int(dm_color[3:5], 16)
        b_hex = int(dm_color[5:7], 16)
        st.html(f'''
        <div style="font-family:Tajawal,sans-serif;background:linear-gradient(135deg,rgba({r_hex},{g_hex},{b_hex},0.05),#0e1424);
                    border:1px solid {dm_color}25;border-radius:12px;padding:14px 18px;margin:8px 0;direction:rtl">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <span style="color:{dm_color};font-weight:700;font-size:0.92em">{dm_label}</span>
                <span style="color:#4b5563;font-size:0.78em">تصريف مستمر: <b style="color:#fff">{dm_days} {_detail_unit}</b></span>
            </div>
            {_d_conv_html}
            <div style="display:flex;flex-direction:column;gap:4px">
                {dm_steps_html}
            </div>
        </div>
        ''')

    # ── Tabs: Chart / Data / Breakouts ──
    tab_chart, tab_data, tab_breakouts = st.tabs(["📊 الشارت", "📋 البيانات", "🚀 الاختراقات"])

    with tab_chart:
        chart = build_detail_chart(r)
        if chart:
            st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})

    with tab_data:
        table_html = build_data_table(r)
        st.html(f'''
        <div style="font-family:Tajawal,sans-serif;background:#0e1424;padding:16px;border-radius:12px">
            {table_html}
        </div>
        ''')

    with tab_breakouts:
        # Timeframe checkboxes
        bc1, bc2, bc3, bc4 = st.columns(4)
        show_3 = bc1.checkbox("عرض 3 أيام 🟠", value=True, key=f"brk3_{r['ticker']}")
        show_4 = bc2.checkbox("عرض 4 أيام 🟢", value=False, key=f"brk4_{r['ticker']}")
        show_10 = bc3.checkbox("عرض 10 أيام 🟣", value=True, key=f"brk10_{r['ticker']}")
        show_15 = bc4.checkbox("عرض 15 أيام 🔴", value=False, key=f"brk15_{r['ticker']}")

        brk_chart = build_breakouts_chart(
            r,
            composite_dates=st.session_state.get("composite_dates"),
            composite_vals=st.session_state.get("composite_vals"),
        )
        if brk_chart:
            # Filter traces based on checkboxes
            tf_filter = {3: show_3, 4: show_4, 10: show_10, 15: show_15}
            for trace in brk_chart.data:
                name = trace.name or ""
                if name in ("السعر", "المؤشر المركب"):
                    trace.visible = True
                    continue
                for days, show in tf_filter.items():
                    label = f"{days} أيام"
                    if label in name:
                        trace.visible = True if show else "legendonly"
                        break

            st.plotly_chart(brk_chart, use_container_width=True, config={"displayModeBar": False})

    # Evidence from Order Flow
    ecol1, ecol2 = st.columns(2)
    with ecol1:
        pos_evidence = [e for e in r.get("evidence", []) if e["type"] == "positive"]
        ev_html = ""
        for e in pos_evidence:
            ev_html += f'<div style="padding:4px 0;font-size:0.86em"><span style="color:#00E676;font-weight:600">{e["factor"]}</span><div style="color:#4b5563;font-size:0.82em;margin-top:1px">{e["meaning"]}</div></div>'
        if not ev_html:
            ev_html = '<div style="color:#4b5563;font-size:0.85em">لا توجد إشارات إيجابية</div>'
        st.markdown(f'''
        <div style="background:rgba(0,230,118,0.03);border:1px solid #1a3a2a;border-radius:12px;padding:14px;direction:rtl">
            <div style="color:#6b7280;font-size:0.78em;margin-bottom:8px;font-weight:700">✅ أدلة الشراء (Order Flow)</div>
            {ev_html}
        </div>
        ''', unsafe_allow_html=True)
    with ecol2:
        neg_evidence = [e for e in r.get("evidence", []) if e["type"] == "negative"]
        ev_html = ""
        for e in neg_evidence:
            ev_html += f'<div style="padding:4px 0;font-size:0.86em"><span style="color:#FF5252;font-weight:600">{e["factor"]}</span><div style="color:#4b5563;font-size:0.82em;margin-top:1px">{e["meaning"]}</div></div>'
        if not ev_html:
            ev_html = '<div style="color:#4b5563;font-size:0.85em">لا توجد إشارات سلبية</div>'
        st.markdown(f'''
        <div style="background:rgba(255,82,82,0.03);border:1px solid #3a2020;border-radius:12px;padding:14px;direction:rtl">
            <div style="color:#6b7280;font-size:0.78em;margin-bottom:8px;font-weight:700">⚠️ أدلة الحذر (Order Flow)</div>
            {ev_html}
        </div>
        ''', unsafe_allow_html=True)

    # Reasons For / Against
    rcol1, rcol2 = st.columns(2)
    with rcol1:
        reasons_html = ""
        for reason in r["reasons_for"]:
            reasons_html += f'<div style="color:#00E676;padding:3px 0;font-size:0.88em">✅ {reason}</div>'
        if reasons_html:
            st.markdown(f'''
            <div style="background:rgba(0,230,118,0.02);border:1px solid #152a1e;border-radius:12px;padding:14px;direction:rtl;margin-top:8px">
                <div style="color:#6b7280;font-size:0.78em;margin-bottom:8px;font-weight:700">✅ أسباب الدخول</div>
                {reasons_html}
            </div>
            ''', unsafe_allow_html=True)
    with rcol2:
        against_html = ""
        for reason in r["reasons_against"]:
            against_html += f'<div style="color:#FF5252;padding:3px 0;font-size:0.88em">⚠️ {reason}</div>'
        if against_html:
            st.markdown(f'''
            <div style="background:rgba(255,82,82,0.02);border:1px solid #2a1515;border-radius:12px;padding:14px;direction:rtl;margin-top:8px">
                <div style="color:#6b7280;font-size:0.78em;margin-bottom:8px;font-weight:700">⚠️ أسباب الحذر</div>
                {against_html}
            </div>
            ''', unsafe_allow_html=True)

    # Trade info for enter
    if r["decision"] == "enter":
        tc1, tc2, tc3 = st.columns(3)
        tc1.metric("🛡️ وقف الخسارة", r["stop_loss"])
        tc2.metric("🎯 الهدف", r["target"])
        tc3.metric("⚖️ R:R", f"{r['rr_ratio']:.1f}")

    # Institutional data
    if r.get("foreign_pct") is not None:
        fc = r.get("foreign_change", 0)
        fc_color = "#00E676" if fc > 0 else "#FF5252" if fc < 0 else "#6b7280"
        st.markdown(f'''
        <div style="background:rgba(14,20,36,0.5);border:1px solid #192035;border-radius:10px;
                    padding:10px 16px;direction:rtl;font-size:0.85em;margin-top:8px">
            🏛 <b>ملكية الأجانب:</b> {r["foreign_pct"]:.1f}%
            <span style="color:{fc_color};font-weight:600;margin-right:12px">
                التغير: {fc:+.1f}%</span>
            <span style="color:#6b7280;margin-right:12px">— {r["inst_label"]}</span>
        </div>
        ''', unsafe_allow_html=True)

    # Veto
    if r.get("veto"):
        st.markdown(f'''
        <div style="background:rgba(255,82,82,0.06);border:1px solid rgba(255,82,82,0.15);
                    border-radius:10px;padding:10px 16px;direction:rtl;margin-top:8px">
            <span style="color:#FF5252;font-weight:700">{r["veto"]}</span>
        </div>
        ''', unsafe_allow_html=True)

    st.divider()


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown('''
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;margin-bottom:4px;margin-top:-10px;">
        <svg width="70" height="70" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="neonBlue" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#00d2ff"/>
                    <stop offset="100%" stop-color="#3a7bd5"/>
                </linearGradient>
                <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#ffd700"/>
                    <stop offset="100%" stop-color="#ffaa00"/>
                </linearGradient>
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur"/>
                    <feComposite in="SourceGraphic" in2="blur" operator="over"/>
                </filter>
            </defs>
            <path d="M 50,5 L 90,35 L 50,95 L 10,35 Z" fill="rgba(0,210,255,0.05)" stroke="url(#neonBlue)" stroke-width="2.5" filter="url(#glow)" stroke-linejoin="round"/>
            <path d="M 20,35 L 50,60 L 80,35" fill="none" stroke="url(#neonBlue)" stroke-width="2" opacity="0.6" stroke-linejoin="round"/>
            <path d="M 50,5 L 50,60" fill="none" stroke="url(#neonBlue)" stroke-width="2" opacity="0.6"/>
            <path d="M 30,75 L 75,25 M 55,25 L 75,25 L 75,45" fill="none" stroke="url(#goldGrad)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
        </svg>
        <div style="text-align:center;margin-top:8px;line-height:1;">
            <span style="font-size:24px;font-weight:900;letter-spacing:3px;color:#fff;text-shadow:0 0 10px rgba(255,255,255,0.1);">MASA</span>
            <span style="font-size:24px;font-weight:300;letter-spacing:3px;color:#00d2ff;text-shadow:0 0 15px rgba(0,210,255,0.4);"> QUANT</span>
        </div>
        <div style="color:#888;font-size:9px;letter-spacing:2px;font-weight:bold;margin-top:4px">
            Order Flow Scanner — من المهاجم؟
        </div>
        <div style="background:#FF6D00;color:#000;font-size:10px;font-weight:bold;padding:2px 8px;border-radius:4px;margin-top:4px;display:inline-block">
            ⚡ V3-TEST — نسخة تجريبية
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Live Clock: 24h + Gregorian + Hijri ──
    components.html('''
    <div style="text-align:center;padding:10px 8px;background:rgba(0,210,255,0.03);border:1px solid rgba(0,210,255,0.08);border-radius:10px;font-family:Tajawal,sans-serif">
        <div id="mk-time" style="font-size:1.8em;font-weight:800;color:#00d2ff;letter-spacing:3px;font-family:'Courier New',monospace;text-shadow:0 0 12px rgba(0,210,255,0.3)">--:--:--</div>
        <div id="mk-greg" style="font-size:0.80em;color:#9ca3af;margin-top:4px">...</div>
        <div id="mk-hijr" style="font-size:0.80em;color:#FFD700;margin-top:2px">...</div>
    </div>
    <script>
    function _mkClock(){
        const n=new Date();
        const tz={timeZone:'Asia/Riyadh'};
        document.getElementById('mk-time').textContent=
            n.toLocaleTimeString('en-GB',{...tz,hour12:false});
        document.getElementById('mk-greg').textContent=
            n.toLocaleDateString('ar-SA',{...tz,weekday:'long',year:'numeric',month:'long',day:'numeric',calendar:'gregory'});
        document.getElementById('mk-hijr').textContent=
            String.fromCodePoint(0x262A)+' '+n.toLocaleDateString('ar-SA',{...tz,day:'numeric',month:'long',year:'numeric',calendar:'islamic-umalqura'});
    }
    _mkClock();setInterval(_mkClock,1000);
    </script>
    ''', height=95)

    st.divider()

    market_options = list(MARKETS.keys())
    selected_market = st.selectbox("السوق", market_options, index=0)
    market_key = MARKETS[selected_market]["key"]
    market_label = MARKETS[selected_market]["label"]

    if st.session_state.last_market != market_key:
        st.session_state.scan_results = None
        st.session_state.market_health = None
        st.session_state.last_market = market_key

    st.divider()

    # Handle navigation from sector map → company analysis
    _pages = ["🔬 Order Flow", "🗺️ خريطة القطاعات", "⚡ الارتدادات والاختراقات", "🚀 مؤشر الاختراقات", "🏆 القطاع القائد", "🔍 تحليل شركة", "📅 تقويم النتائج", "🤖 تقارير AI", "📊 أداء النظام"]
    if st.session_state.get("_goto_page"):
        st.session_state["page_nav"] = st.session_state.pop("_goto_page")

    page = st.radio(
        "الصفحة",
        _pages,
        label_visibility="collapsed",
        key="page_nav",
    )

    st.divider()
    st.markdown('''
    <div style="color:#374151;font-size:0.76em;line-height:1.7;padding:0 6px">
        <div style="font-weight:700;color:#4b5563;margin-bottom:4px">المبدأ</div>
        سؤال واحد: من المهاجم — المشتري أو البائع؟<br>
        <span style="color:#2a3040">CDV + Absorption + Wyckoff</span>
    </div>
    ''', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# PAGE: Order Flow Scanner
# ══════════════════════════════════════════════════════════════

if page == "🔬 Order Flow":

    hcol1, hcol2, hcol3, hcol4 = st.columns([3, 1, 1, 1])
    with hcol1:
        n_stocks = len(get_all_tickers(market_key))
        st.markdown(f'''
        <div style="margin-bottom:4px">
            <span style="font-size:1.8em;font-weight:800;color:#fff">🔬 Order Flow — {market_label}</span>
            <span style="color:#4b5563;font-size:0.88em;margin-right:12px">
                {n_stocks} سهم</span>
        </div>
        ''', unsafe_allow_html=True)
    with hcol2:
        timeframe_options = {
            "📊 يومي": "1d",
            "⏱️ 1 ساعة": "1h",
            "⏱️ 15 دقيقة": "15m",
            "⏱️ 5 دقائق": "5m",
        }
        selected_tf_label = st.selectbox(
            "⏱️ الإطار", list(timeframe_options.keys()), index=0,
            key="scan_timeframe", label_visibility="collapsed"
        )
        selected_interval = timeframe_options[selected_tf_label]
    with hcol3:
        period_options = {"سنة": "1y", "سنتين": "2y", "٣ سنوات": "3y", "٥ سنوات": "5y", "١٠ سنوات": "10y", "الكل": "max"}
        selected_period_label = st.selectbox(
            "📅 الفترة", list(period_options.keys()), index=2,
            key="scan_period", label_visibility="collapsed",
            disabled=(selected_interval != "1d"),  # فترة تلقائية للإطار اللحظي
        )
        selected_period = period_options[selected_period_label]
    with hcol4:
        scan_btn = st.button("▶️ ابدأ المسح", use_container_width=True, type="primary")

    if scan_btn:
        tickers = get_all_tickers(market_key)

        tf_display = selected_tf_label.replace("📊 ", "").replace("⏱️ ", "")
        progress = st.progress(0, text=f"جاري المسح ({tf_display})...")

        def _update(current, total):
            progress.progress(current / total, text=f"تحليل {current}/{total} ({tf_display})")

        results = scan_market(
            tickers=tickers,
            period=selected_period,
            market_health=50.0,
            progress_callback=_update,
            interval=selected_interval,
        )
        progress.empty()

        # حساب صحة السوق من نتائج المسح (بدون استعلامات إضافية)
        if results:
            above_ma50 = sum(1 for r in results if r.get("chart_ma50") and r["price"] > r["chart_ma50"][-1])
            total_valid = sum(1 for r in results if r.get("chart_ma50") and r["chart_ma50"][-1] is not None)
            health = round(above_ma50 / total_valid * 100, 1) if total_valid > 0 else 50.0
        else:
            health = 50.0

        results = compute_relative_flow(results)
        st.session_state.scan_results = results
        st.session_state.market_health = health
        # Pre-compute composite index for breakout overlay
        comp_d, comp_v, _, _ = build_composite_index(results)
        st.session_state.composite_dates = comp_d
        st.session_state.composite_vals = comp_v

    results = st.session_state.scan_results
    health = st.session_state.market_health

    if results is None:
        st.markdown(f'''
        <div style="text-align:center;padding:100px 20px;color:#4b5563">
            <div style="font-size:4em;margin-bottom:20px;opacity:0.4">🔬</div>
            <div style="font-size:1.3em;color:#6b7280;margin-bottom:10px">
                اضغط <b style="color:#00E676">ابدأ المسح</b>
            </div>
            <div style="font-size:0.88em">لتحليل Order Flow و كشف من يسيطر — المشتري أو البائع</div>
        </div>
        ''', unsafe_allow_html=True)
        st.stop()

    if not results:
        st.warning("لم يتم العثور على نتائج.")
        st.stop()

    # ── Market Health Bar ─────────────────────────────────
    if health >= 60:
        health_color, health_icon, health_text = "#00E676", "🟢", "صاعد"
    elif health >= 45:
        health_color, health_icon, health_text = "#FFD700", "🟡", "متذبذب"
    else:
        health_color, health_icon, health_text = "#FF5252", "🔴", "ضعيف"

    st.markdown(f'''
    <div style="background:linear-gradient(135deg,#131a2e,#0e1424);border:1px solid #192035;
                border-radius:14px;padding:14px 20px;margin:8px 0 16px 0;
                display:flex;align-items:center;justify-content:space-between;
                flex-wrap:wrap;gap:10px;direction:rtl">
        <div style="display:flex;align-items:center;gap:10px">
            <span style="font-size:1.3em">{health_icon}</span>
            <span style="color:#6b7280;font-size:0.85em">صحة السوق</span>
            <span style="color:{health_color};font-weight:800;font-size:1.3em">{health:.0f}%</span>
            <span style="color:{health_color};font-size:0.85em;font-weight:500">({health_text})</span>
        </div>
        <div style="flex:1;min-width:120px;max-width:300px">
            <div style="background:#080b14;border-radius:4px;height:5px;overflow:hidden">
                <div style="background:{health_color};height:100%;width:{health}%;
                            border-radius:4px;transition:width 0.5s ease"></div>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Summary Stats ─────────────────────────────────────
    enter_count = sum(1 for r in results if r["decision"] == "enter")
    watch_count = sum(1 for r in results if r["decision"] == "watch")
    avoid_count = sum(1 for r in results if r["decision"] == "avoid")

    # Phase stats
    accum_count = sum(1 for r in results if r["phase"] in ("accumulation", "spring"))
    dist_count = sum(1 for r in results if r["phase"] in ("distribution", "markdown", "upthrust"))
    buyer_count = sum(1 for r in results if r["aggressor"] == "buyers")
    seller_count = sum(1 for r in results if r["aggressor"] == "sellers")

    st.markdown(f'''
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;
                margin-bottom:8px;direction:rtl">
        <div class="masa-stat">
            <div class="masa-stat-label">إجمالي</div>
            <div class="masa-stat-value" style="color:#fff">{len(results)}</div>
        </div>
        <div class="masa-stat masa-stat-enter">
            <div class="masa-stat-label">✅ ادخل</div>
            <div class="masa-stat-value" style="color:#00E676">{enter_count}</div>
        </div>
        <div class="masa-stat masa-stat-watch">
            <div class="masa-stat-label">⚠️ راقب</div>
            <div class="masa-stat-value" style="color:#FFD700">{watch_count}</div>
        </div>
        <div class="masa-stat masa-stat-avoid">
            <div class="masa-stat-label">❌ تجنب</div>
            <div class="masa-stat-value" style="color:#FF5252">{avoid_count}</div>
        </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;
                margin-bottom:20px;direction:rtl">
        <div class="masa-stat">
            <div class="masa-stat-label">🟢 تدفق شرائي</div>
            <div class="masa-stat-value" style="color:#00E676;font-size:1.4em">{accum_count}</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">🔴 تدفق بيعي</div>
            <div class="masa-stat-value" style="color:#FF5252;font-size:1.4em">{dist_count}</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">🔥 مشتري مهاجم</div>
            <div class="masa-stat-value" style="color:#00E676;font-size:1.4em">{buyer_count}</div>
        </div>
        <div class="masa-stat">
            <div class="masa-stat-label">🔥 بائع مهاجم</div>
            <div class="masa-stat-value" style="color:#FF5252;font-size:1.4em">{seller_count}</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Filters ───────────────────────────────────────────
    fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns(5)
    with fcol1:
        show_filter = st.selectbox(
            "🎯 التصنيف",
            ["✅ ادخل + ⚠️ راقب", "✅ ادخل فقط", "🔴 تصريف فقط", "الكل"],
        )
    with fcol2:
        # Flow type filter
        _type_map = {
            "الكل": None,
            "📦 تجميع قاعي": "bottom",
            "🕵️ تجميع خفي": "hidden",
            "🟢 تجميع ظاهر": "visible",
            "🎯 سبرنق": "spring",
            "🔺 تصريف قمّي": "top",
            "🕵️ تصريف خفي": "hidden_dist",
            "🔴 تصريف ظاهر": "visible_dist",
            "⚠️ أبثرست": "upthrust",
        }
        selected_type_label = st.selectbox("🏷️ النوع", list(_type_map.keys()))
        selected_type = _type_map[selected_type_label]
    with fcol3:
        sectors = sorted(set(r["sector"] for r in results))
        selected_sector = st.selectbox("📂 القطاع", ["كل القطاعات"] + sectors)
    with fcol4:
        _rel_map = {
            "الكل": None,
            "📊 ضد التيار": "ضد التيار",
            "📊 يتفوق": "يتفوق",
            "📊 أضعف من القطاع": "أضعف من القطاع",
        }
        selected_rel_label = st.selectbox("📊 قوة نسبية", list(_rel_map.keys()))
        selected_rel = _rel_map[selected_rel_label]
    with fcol5:
        sort_by = st.selectbox(
            "📊 الترتيب",
            ["أقوى أوردر فلو", "أكبر تغير ↑", "أعلى امتصاص", "أقوى دايفرجنس"],
        )

    if show_filter == "✅ ادخل فقط":
        filtered = [r for r in results if r["decision"] == "enter"]
    elif show_filter == "✅ ادخل + ⚠️ راقب":
        filtered = [r for r in results if r["decision"] in ("enter", "watch")]
    elif show_filter == "🔴 تصريف فقط":
        filtered = [r for r in results if r["phase"] in ("distribution", "upthrust", "markdown")]
    else:
        filtered = list(results)

    if selected_type:
        filtered = [r for r in filtered if r.get("flow_type") == selected_type]

    if selected_sector != "كل القطاعات":
        filtered = [r for r in filtered if r["sector"] == selected_sector]

    if selected_rel:
        filtered = [r for r in filtered if r.get("relative_flow_label") == selected_rel]

    if sort_by == "أكبر تغير ↑":
        filtered.sort(key=lambda x: x["change_pct"], reverse=True)
    elif sort_by == "أعلى امتصاص":
        filtered.sort(key=lambda x: x["absorption_score"], reverse=True)
    elif sort_by == "أقوى دايفرجنس":
        filtered.sort(key=lambda x: abs(x["divergence"]), reverse=True)
    else:
        # Default: strongest flow bias
        filtered.sort(key=lambda x: x["flow_bias"], reverse=True)

    if not filtered:
        st.info("لا توجد نتائج للعرض مع هذا الفلتر.")
        st.stop()

    # ── Check if detail page is active ────────────────────
    if st.session_state.selected_ticker:
        # Find the selected stock
        selected_r = None
        for r in results:
            if r["ticker"] == st.session_state.selected_ticker:
                selected_r = r
                break

        if selected_r:
            # Back button
            if st.button("→ رجوع للقائمة", key="back_btn", type="secondary"):
                st.session_state.selected_ticker = None
                st.rerun()

            # Full detail page
            show_detail_panel(selected_r)
            st.stop()
        else:
            st.session_state.selected_ticker = None

    # ── Search Box ────────────────────────────────────────
    search_query = st.text_input(
        "🔎 ابحث عن سهم",
        placeholder="اكتب اسم الشركة أو الرمز...",
        key="search_box",
    )

    if search_query:
        q = search_query.strip().lower()
        filtered = [r for r in filtered
                     if q in r["name"].lower()
                     or q in r["ticker"].lower()
                     or q in r["ticker"].replace(".SR", "").lower()]

    st.markdown(f'''
    <div style="color:#4b5563;font-size:0.85em;margin:4px 0 14px 0;direction:rtl">
        عرض <b style="color:#9ca3af">{len(filtered)}</b> سهم
    </div>
    ''', unsafe_allow_html=True)

    if not filtered:
        st.info("لا توجد نتائج — جرب بحث مختلف.")
        st.stop()

    # ── Cards Grid with buttons ───────────────────────────
    # Render cards in columns of 3
    cols_per_row = 3
    for row_start in range(0, len(filtered), cols_per_row):
        row_items = filtered[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for i, r in enumerate(row_items):
            with cols[i]:
                st.markdown(build_card_html(r), unsafe_allow_html=True)
                if st.button(
                    f"📊 تفاصيل {r['name']}",
                    key=f"detail_{r['ticker']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_ticker = r["ticker"]
                    st.rerun()

    # ── Log Enter Signals ─────────────────────────────────
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    for r in results:
        if r["decision"] == "enter":
            log_signal({
                "date_logged": today,
                "ticker": r["ticker"],
                "company": r["name"],
                "sector": r["sector"],
                "decision": r["decision"],
                "accum_level": r["phase"],
                "accum_days": r["days"],
                "location": r["location"],
                "cmf": r["flow_bias"],
                "entry_price": r["price"],
                "stop_loss": r["stop_loss"],
                "target": r["target"],
                "rr_ratio": r["rr_ratio"],
                "reasons_for": r["reasons_for"],
                "reasons_against": r["reasons_against"],
            })

    # ── Auto-update signal outcomes after every scan ────────
    try:
        result = update_signal_outcomes()
        if result["updated"] > 0:
            st.toast(f"📊 تم تحديث نتائج {result['updated']} إشارة سابقة", icon="✅")
    except Exception:
        pass  # لا نوقف المنصة لو فشل التحديث


# ══════════════════════════════════════════════════════════════
# PAGE: Sector Map — Accumulation & Distribution Heatmap
# ══════════════════════════════════════════════════════════════

elif page == "🗺️ خريطة القطاعات":
    results = st.session_state.scan_results
    if results is None:
        st.markdown('''
        <div style="text-align:center;padding:80px 20px;color:#4b5563">
            <div style="font-size:4em;margin-bottom:20px;opacity:0.4">🗺️</div>
            <div style="font-size:1.3em;color:#6b7280;margin-bottom:10px">
                اضغط <b style="color:#00E676">ابدأ المسح</b> أولاً في صفحة Order Flow
            </div>
            <div style="font-size:0.88em">لعرض خريطة التجميع والتصريف حسب القطاعات</div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('<h2 style="text-align:center;margin-bottom:4px">🗺️ خريطة القطاعات</h2>', unsafe_allow_html=True)
        st.caption("القطاعات مرتبة من أقوى تجميع لأقوى تصريف — الأسهم داخل كل قطاع مرتبة بنفس المنطق")

        # ── Compute Market Breadth (MA50 / MA200) ──────────────
        def _compute_breadth(scan_results):
            """
            For each stock, compare current price with last MA50 and MA200 values.
            Returns overall + per-sector breadth stats.
            """
            total = 0
            above_ma50 = 0
            above_ma200 = 0
            sector_breadth = {}  # sector_name -> {total, above_ma50, above_ma200}

            for r in scan_results:
                price = r.get("price", 0)
                ma50_arr = r.get("chart_ma50", [])
                ma200_arr = r.get("chart_ma200", [])
                sector = r.get("sector", "أخرى")

                # Get last valid MA value
                ma50_val = None
                for v in reversed(ma50_arr):
                    if v is not None and v > 0:
                        ma50_val = v
                        break

                ma200_val = None
                for v in reversed(ma200_arr):
                    if v is not None and v > 0:
                        ma200_val = v
                        break

                if not price or price <= 0:
                    continue

                total += 1
                _a50 = 1 if (ma50_val and price > ma50_val) else 0
                _a200 = 1 if (ma200_val and price > ma200_val) else 0
                above_ma50 += _a50
                above_ma200 += _a200

                if sector not in sector_breadth:
                    sector_breadth[sector] = {"total": 0, "above_ma50": 0, "above_ma200": 0}
                sector_breadth[sector]["total"] += 1
                sector_breadth[sector]["above_ma50"] += _a50
                sector_breadth[sector]["above_ma200"] += _a200

            pct_ma50 = round(above_ma50 / total * 100, 1) if total else 0
            pct_ma200 = round(above_ma200 / total * 100, 1) if total else 0

            return {
                "total": total,
                "above_ma50": above_ma50,
                "above_ma200": above_ma200,
                "pct_ma50": pct_ma50,
                "pct_ma200": pct_ma200,
                "sector_breadth": sector_breadth,
            }

        _breadth = _compute_breadth(results)

        # ── Phase classification (needed early for sector grouping) ──
        _accum_phases = {"accumulation", "markup", "spring"}
        _dist_phases = {"distribution", "markdown", "upthrust"}
        _phase_rank = {
            "accumulation": 1, "markup": 2, "spring": 2.5,
            "transition": 5, "neutral": 5,
            "upthrust": 7, "markdown": 7.5, "distribution": 8,
        }

        # ── Group by sector ──
        from collections import defaultdict
        sector_stocks = defaultdict(list)
        for r in results:
            sector_stocks[r["sector"]].append(r)

        # ── Compute sector health ──
        sector_data = []
        for sector_name, stocks in sector_stocks.items():
            n = len(stocks)
            if n == 0:
                continue

            # 1. Phase balance (40%)
            phase_scores = []
            for s in stocks:
                p = s["phase"]
                if p in _accum_phases:
                    phase_scores.append(1.0)
                elif p in _dist_phases:
                    phase_scores.append(-1.0)
                else:
                    phase_scores.append(0.0)
            phase_balance = (sum(phase_scores) / n) * 100

            # 2. Average flow_bias (30%)
            avg_flow = sum(s["flow_bias"] for s in stocks) / n

            # 3. Decision ratio (30%)
            enters = sum(1 for s in stocks if s["decision"] == "enter")
            avoids = sum(1 for s in stocks if s["decision"] == "avoid")
            decision_ratio = ((enters - avoids) / n) * 100

            health = round(phase_balance * 0.4 + avg_flow * 0.3 + decision_ratio * 0.3, 1)

            # Count categories
            n_accum = sum(1 for s in stocks if s["phase"] in _accum_phases)
            n_dist = sum(1 for s in stocks if s["phase"] in _dist_phases)
            n_neutral = n - n_accum - n_dist

            # Sort stocks within sector
            stocks_sorted = sorted(stocks, key=lambda s: (
                _phase_rank.get(s["phase"], 5),
                -s["flow_bias"],
                -s.get("maturity_days", 0),
            ))

            sector_data.append({
                "name": sector_name,
                "health": health,
                "stocks": stocks_sorted,
                "n": n,
                "n_accum": n_accum,
                "n_dist": n_dist,
                "n_neutral": n_neutral,
                "avg_flow": round(avg_flow, 1),
            })

        # Sort sectors by health (most accumulation first)
        sector_data.sort(key=lambda x: -x["health"])

        # ── Summary metrics ──
        green_sectors = sum(1 for s in sector_data if s["health"] > 20)
        red_sectors = sum(1 for s in sector_data if s["health"] < -20)
        neutral_sectors = len(sector_data) - green_sectors - red_sectors
        best_sector = sector_data[0]["name"] if sector_data else "—"

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("قطاعات تجميع 🟢", green_sectors)
        sc2.metric("قطاعات تصريف 🔴", red_sectors)
        sc3.metric("قطاعات محايدة ⚪", neutral_sectors)
        sc4.metric("أقوى قطاع", best_sector)

        # ── Market Breadth Panel ───────────────────────────────
        if _breadth["total"] > 0:
            _b50 = _breadth["pct_ma50"]
            _b200 = _breadth["pct_ma200"]
            _b50_c = "#00E676" if _b50 >= 70 else "#FFD700" if _b50 >= 40 else "#FF5252"
            _b200_c = "#00E676" if _b200 >= 70 else "#FFD700" if _b200 >= 40 else "#FF5252"
            _b50_bg = f"{_b50_c}15"
            _b200_bg = f"{_b200_c}15"

            # Divergence detection
            _divergence_html = ""
            _comp_dates_pre, _comp_vals_pre, _, _ = build_composite_index(results)
            if len(_comp_vals_pre) >= 5:
                _comp_ret_pre = (_comp_vals_pre[-1] - _comp_vals_pre[0]) / _comp_vals_pre[0] * 100
                if _comp_ret_pre > 0 and _b50 < 50:
                    _divergence_html = '<div style="margin-top:10px;padding:8px 14px;background:rgba(255,215,0,0.08);border:1px solid rgba(255,215,0,0.20);border-radius:10px;text-align:center;direction:rtl"><span style="font-size:1.1em">⚠️</span> <span style="color:#FFD700;font-size:0.85em;font-weight:600">انحراف: المؤشر صاعد لكن أقل من نصف الأسهم فوق متوسط 50 يوم — صعود هش</span></div>'
                elif _comp_ret_pre < 0 and _b50 > 70:
                    _divergence_html = '<div style="margin-top:10px;padding:8px 14px;background:rgba(0,230,118,0.08);border:1px solid rgba(0,230,118,0.20);border-radius:10px;text-align:center;direction:rtl"><span style="font-size:1.1em">💡</span> <span style="color:#00E676;font-size:0.85em;font-weight:600">انحراف إيجابي: المؤشر هابط لكن أغلب الأسهم فوق متوسط 50 يوم — قوة كامنة</span></div>'

            st.markdown(f'''
            <div style="background:linear-gradient(145deg, #131a2e 0%, #0e1424 100%);
                        border:1px solid #192035;border-radius:16px;padding:20px;
                        margin:12px 0;direction:rtl">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
                    <span style="font-size:1.2em">📊</span>
                    <span style="color:#fff;font-size:1.05em;font-weight:700">اتساع السوق</span>
                    <span style="color:#4b5563;font-size:0.78em;margin-right:auto">
                        {_breadth["total"]} سهم
                    </span>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                    <!-- MA50 -->
                    <div style="background:rgba(8,11,20,0.5);border-radius:12px;padding:14px">
                        <div style="color:#6b7280;font-size:0.82em;margin-bottom:6px">
                            فوق متوسط 50 يوم
                        </div>
                        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px">
                            <span style="color:{_b50_c};font-size:1.8em;font-weight:800">{_b50:.0f}%</span>
                            <span style="color:#4b5563;font-size:0.78em">
                                {_breadth["above_ma50"]} من {_breadth["total"]}
                            </span>
                        </div>
                        <div style="height:8px;background:#1a1f2e;border-radius:4px;overflow:hidden">
                            <div style="width:{_b50}%;height:100%;background:{_b50_c};
                                        border-radius:4px;transition:width 0.5s ease"></div>
                        </div>
                    </div>
                    <!-- MA200 -->
                    <div style="background:rgba(8,11,20,0.5);border-radius:12px;padding:14px">
                        <div style="color:#6b7280;font-size:0.82em;margin-bottom:6px">
                            فوق متوسط 200 يوم
                        </div>
                        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px">
                            <span style="color:{_b200_c};font-size:1.8em;font-weight:800">{_b200:.0f}%</span>
                            <span style="color:#4b5563;font-size:0.78em">
                                {_breadth["above_ma200"]} من {_breadth["total"]}
                            </span>
                        </div>
                        <div style="height:8px;background:#1a1f2e;border-radius:4px;overflow:hidden">
                            <div style="width:{_b200}%;height:100%;background:{_b200_c};
                                        border-radius:4px;transition:width 0.5s ease"></div>
                        </div>
                    </div>
                </div>
                {_divergence_html}
            </div>
            ''', unsafe_allow_html=True)

        st.divider()

        # ── Detect intraday mode ──
        _smap_tf = results[0].get("timeframe", "1d") if results else "1d"
        _smap_intra = _smap_tf != "1d"

        def _filter_session(dates, vals):
            """For intraday: keep only the last trading session."""
            if not _smap_intra or not dates or not vals:
                return dates, vals
            # Extract unique trading days
            unique_days = sorted(set(d[:10] for d in dates))
            # Try last day first; if too few bars, use previous day
            for offset in range(len(unique_days)):
                target_day = unique_days[-(1 + offset)]
                filtered = [(d, v) for d, v in zip(dates, vals) if d[:10] == target_day]
                if len(filtered) >= 2:
                    break
            else:
                return dates, vals  # absolute fallback
            fd, fv = zip(*filtered)
            # Re-normalize to start at 100
            start = fv[0]
            if start and start > 0:
                fv = [round(v / start * 100, 2) for v in fv]
            return list(fd), list(fv)

        # ── Pre-compute sector composites ──
        _sector_composites = {}
        for sd in sector_data:
            _sec_dates, _sec_vals, _, _ = build_composite_index(sd["stocks"])
            _sec_dates, _sec_vals = _filter_session(_sec_dates, _sec_vals)
            if len(_sec_dates) >= 3 and len(_sec_vals) >= 3:
                _sec_ret = round((_sec_vals[-1] - _sec_vals[0]) / _sec_vals[0] * 100, 2) if _sec_vals[0] > 0 else 0
                _sector_composites[sd["name"]] = {
                    "dates": _sec_dates, "vals": _sec_vals, "ret": _sec_ret,
                }

        # ══ Master Chart: Platform + Benchmark + All Sectors ══
        _comp_dates, _comp_vals, _, _ = build_composite_index(results)
        _comp_dates, _comp_vals = _filter_session(_comp_dates, _comp_vals)

        # Time range filter (daily only)
        if not _smap_intra and len(_comp_dates) > 20:
            _total_bars = len(_comp_dates)
            _all_ranges = [("الكل", 0), ("3 أشهر", 63), ("6 أشهر", 126), ("سنة", 252), ("سنتين", 504), ("3 سنوات", 756), ("5 سنوات", 1260), ("10 سنوات", 2520)]
            _sm_range_opts = {k: v for k, v in _all_ranges if v == 0 or v < _total_bars}
            _sm_rcols = st.columns(len(_sm_range_opts))
            _sm_sel = st.session_state.get("_smap_range", "الكل")
            if _sm_sel not in _sm_range_opts:
                _sm_sel = "الكل"
            for _ri, (_rl, _rd) in enumerate(_sm_range_opts.items()):
                _btn_t = "primary" if _sm_sel == _rl else "secondary"
                if _sm_rcols[_ri].button(_rl, key=f"_smap_r_{_rl}", type=_btn_t, use_container_width=True):
                    st.session_state["_smap_range"] = _rl
                    _sm_sel = _rl
            _sm_rd = _sm_range_opts.get(_sm_sel, 0)
            if _sm_rd > 0 and _sm_rd < _total_bars:
                _comp_dates = _comp_dates[-_sm_rd:]
                _comp_vals = _comp_vals[-_sm_rd:]
                # NO rebase — keep raw values. Just zoom.
                # Also slice sector composites (raw values too)
                _start_d = _comp_dates[0]
                for _sk in list(_sector_composites.keys()):
                    _sd_data = _sector_composites[_sk]
                    _sd_idx = [i for i, d in enumerate(_sd_data["dates"]) if d >= _start_d]
                    if len(_sd_idx) >= 3:
                        _sd_dates = [_sd_data["dates"][i] for i in _sd_idx]
                        _sd_vals = [_sd_data["vals"][i] for i in _sd_idx]
                        _sd_ret = round((_sd_vals[-1] - _sd_vals[0]) / _sd_vals[0] * 100, 2) if _sd_vals[0] > 0 else 0
                        _sector_composites[_sk] = {"dates": _sd_dates, "vals": _sd_vals, "ret": _sd_ret}
                    else:
                        del _sector_composites[_sk]

        _min_bars = 3 if _smap_intra else 15
        if len(_comp_dates) >= _min_bars:
            # Benchmark only for daily (intraday has no matching benchmark data)
            if not _smap_intra:
                _bench_norm, _, _, _bench_name, _bench_color = _fetch_benchmark_normalized(
                    _comp_dates, market_key=market_key, start_val=_comp_vals[0]
                )
            else:
                _bench_norm, _bench_name, _bench_color = {}, "", ""
            import plotly.graph_objects as go

            # Sector selection checkboxes
            _sec_names = [sd["name"] for sd in sector_data if sd["name"] in _sector_composites]
            _show_sectors = set()
            if _sec_names:
                st.markdown(
                    '<div style="color:#6b7280;font-size:0.82em;margin-bottom:4px">اختر القطاعات للعرض:</div>',
                    unsafe_allow_html=True
                )
                _n_cols = min(len(_sec_names), 7)
                _ck_cols = st.columns(_n_cols)
                for _ci, _sn in enumerate(_sec_names):
                    _sc = SECTOR_COLORS.get(_sn, "#607D8B")
                    with _ck_cols[_ci % _n_cols]:
                        if st.checkbox(_sn, value=(_ci < 3), key=f"sec_ck_{_sn}"):
                            _show_sectors.add(_sn)

            _top_fig = go.Figure()

            # 1. Platform composite (thick green)
            _top_fig.add_trace(go.Scatter(
                x=_comp_dates, y=_comp_vals,
                mode="lines", name="المؤشر المركب",
                line=dict(color="#00E676", width=3),
            ))

            # 2. Benchmark (gold dotted)
            if _bench_norm:
                _b_dates = [d for d in _comp_dates if d in _bench_norm]
                _b_vals = [_bench_norm[d] for d in _b_dates]
                _top_fig.add_trace(go.Scatter(
                    x=_b_dates, y=_b_vals,
                    mode="lines", name=_bench_name,
                    line=dict(color="#FFD700", width=2, dash="dot"),
                ))

            # 3. Selected sector lines
            for _sn in _show_sectors:
                _sc_data = _sector_composites[_sn]
                _sc_color = SECTOR_COLORS.get(_sn, "#607D8B")
                _top_fig.add_trace(go.Scatter(
                    x=_sc_data["dates"], y=_sc_data["vals"],
                    mode="lines", name=f"{_sn} ({_sc_data['ret']:+.1f}%)",
                    line=dict(color=_sc_color, width=1.5),
                    opacity=0.8,
                ))

            _top_fig.add_hline(y=_comp_vals[0], line_dash="dash", line_color="#374151", line_width=1)
            _top_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=400, margin=dict(l=40, r=20, t=10, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                            font=dict(family="Tajawal", size=11)),
                yaxis=dict(title=None, gridcolor="#192035", tickfont=dict(size=10, color="#4b5563")),
                xaxis=dict(gridcolor="#192035", tickfont=dict(size=10, color="#4b5563")),
                font=dict(family="Tajawal"),
                hovermode="x unified",
        spikedistance=-1,
            )
            st.plotly_chart(_top_fig, use_container_width=True, config={"displayModeBar": False})

            _comp_ret = round((_comp_vals[-1] - _comp_vals[0]) / _comp_vals[0] * 100, 2)
            _comp_ret_c = "#00E676" if _comp_ret >= 0 else "#FF5252"
            _tf_labels = {"1d": "يومي", "1h": "ساعة", "15m": "15 دقيقة", "5m": "5 دقائق"}
            _tf_txt = _tf_labels.get(_smap_tf, "")
            _session_txt = " — آخر جلسة" if _smap_intra else ""
            st.markdown(
                f'<div style="text-align:center;color:#6b7280;font-size:0.82em;margin:-10px 0 10px">'
                f'⏱️ فريم {_tf_txt}{_session_txt} • '
                f'عائد المؤشر المركب: <b style="color:{_comp_ret_c}">{_comp_ret:+.2f}%</b></div>',
                unsafe_allow_html=True
            )

        # ── Seasonality Tab ──
        with st.expander("📊 التحليل الموسمي للقطاعات", expanded=False):
            from core.seasonality import build_seasonality_for_sectors, MONTH_NAMES_AR
            # Use full (unsliced) sector composites for seasonality
            _full_sector_comps = {}
            for sd in sector_data:
                _fsd, _fsv, _, _ = build_composite_index(sd["stocks"])
                if len(_fsd) >= 20:
                    _full_sector_comps[sd["name"]] = {"dates": _fsd, "vals": _fsv, "ret": 0}
            # Also add market composite
            _fcd, _fcv, _, _ = build_composite_index(results)
            if len(_fcd) >= 20:
                _full_sector_comps["السوق الكلي"] = {"dates": _fcd, "vals": _fcv, "ret": 0}

            # Detect market type for catalysts
            _market_sel_key = st.session_state.get("market_select", "🇸🇦 السوق السعودي (TASI)")
            _seas_mkt = "us" if "أمريكي" in _market_sel_key or "S&P" in _market_sel_key else "saudi"
            _seasonality = build_seasonality_for_sectors(_full_sector_comps, market_key=_seas_mkt)

            if _seasonality:
                _seas_sectors = ["السوق الكلي"] + [s for s in _seasonality if s != "السوق الكلي"]
                _seas_sel = st.selectbox("اختر القطاع:", _seas_sectors, key="_seas_sel")

                if _seas_sel in _seasonality:
                    _ss = _seasonality[_seas_sel]
                    _ss_stats = _ss["stats"]
                    _ss_years = _ss.get("years_covered", [])
                    _ss_catalysts = _ss.get("catalysts", {})

                    _n_years = len(_ss_years)
                    _yr_range = f"{min(_ss_years)} — {max(_ss_years)}" if _ss_years else ""
                    _sample_note = " ⚠️ عيّنة صغيرة" if _n_years < 5 else ""
                    st.caption(f"البيانات تغطي: {_yr_range} ({_n_years} سنوات){_sample_note}")

                    # ── Current month insight with catalysts ──
                    _ins = _ss.get("insight")
                    if _ins:
                        _ins_txt = (
                            f"{_ins['phase_icon']} **{_ins['month_ar']}** تاريخياً: "
                            f"متوسط العائد **{_ins['avg_return']:+.1f}%** | "
                            f"نسبة النجاح **{_ins['win_rate']:.0f}%** | "
                            f"Sharpe **{_ins.get('sharpe', 0):.1f}** | "
                            f"Profit Factor **{_ins.get('profit_factor', 0):.1f}**"
                        )
                        # Misleading warning
                        if _ins.get("misleading"):
                            _ins_txt += "\n\n⚠️ **تحذير:** نسبة النجاح عالية لكن **التوقع الرياضي سلبي** — الخسائر أكبر من الأرباح!"
                        # Catalyst events
                        if _ins.get("catalyst_events"):
                            _cat_events = " • ".join(_ins["catalyst_events"])
                            _ins_txt += f"\n\n📅 **المحفزات:** {_cat_events}"
                            if _ins.get("catalyst_note"):
                                _ins_txt += f"\n💡 {_ins['catalyst_note']}"
                        # Next month
                        if _ins.get("next_month_ar"):
                            _ins_txt += (
                                f"\n\n{_ins['next_icon']} الشهر القادم (**{_ins['next_month_ar']}**): "
                                f"متوسط **{_ins['next_avg']:+.1f}%** — {_ins['next_phase']}"
                            )
                            if _ins.get("next_catalyst"):
                                _ins_txt += f" | 💡 {_ins['next_catalyst']}"

                        if _ins["avg_return"] > 0:
                            st.success(_ins_txt)
                        elif _ins["avg_return"] < -0.5:
                            st.error(_ins_txt)
                        else:
                            st.info(_ins_txt)

                    # ── Heatmap table with Sharpe + Win/Loss ──
                    st.markdown("##### 🗓️ خريطة الأداء الشهري")
                    _heat_rows = []
                    for mo in range(1, 13):
                        if mo not in _ss_stats:
                            continue
                        s = _ss_stats[mo]
                        _row = {
                            "الشهر": f"{s['phase_icon']} {s['month_ar']}",
                            "متوسط %": s["avg_return"],
                            "نجاح %": s["win_rate"],
                            "Sharpe": s.get("sharpe", 0),
                            "ربح %": s.get("avg_win", 0),
                            "خسارة %": s.get("avg_loss", 0),
                            "P.Factor": s.get("profit_factor", 0),
                            "أفضل %": s["best"],
                            "أسوأ %": s["worst"],
                        }
                        # Add catalyst
                        if mo in _ss_catalysts:
                            _row["المحفز"] = _ss_catalysts[mo]["impact"]
                        else:
                            _row["المحفز"] = ""
                        _heat_rows.append(_row)

                    if _heat_rows:
                        _heat_df = pd.DataFrame(_heat_rows)
                        st.dataframe(
                            _heat_df.style.applymap(
                                lambda v: "color: #00E676" if isinstance(v, (int, float)) and v > 0
                                else "color: #FF5252" if isinstance(v, (int, float)) and v < 0
                                else "",
                                subset=["متوسط %", "ربح %", "خسارة %", "أفضل %", "أسوأ %"]
                            ).applymap(
                                lambda v: "color: #00E676" if isinstance(v, (int, float)) and v >= 60
                                else "color: #FF5252" if isinstance(v, (int, float)) and v < 40
                                else "color: #FFD700",
                                subset=["نجاح %"]
                            ).applymap(
                                lambda v: "color: #00E676" if isinstance(v, (int, float)) and v > 1
                                else "color: #FF5252" if isinstance(v, (int, float)) and v < 0
                                else "color: #FFD700",
                                subset=["Sharpe", "P.Factor"]
                            ),
                            use_container_width=True, hide_index=True,
                        )

                        # Legend
                        st.caption(
                            "**Sharpe** = العائد ÷ التذبذب (أعلى = أفضل جودة) | "
                            "**P.Factor** = إجمالي الأرباح ÷ إجمالي الخسائر (أعلى من 1 = رابح) | "
                            "**ربح %** = متوسط الربح لما يكسب | **خسارة %** = متوسط الخسارة لما يخسر"
                        )

                    # ── Misleading months warning ──
                    _misleading = [s for s in _ss_stats.values() if s.get("misleading")]
                    if _misleading:
                        for _ml in _misleading:
                            st.warning(
                                f"⚠️ **{_ml['month_ar']}**: نسبة نجاح {_ml['win_rate']:.0f}% "
                                f"لكن متوسط الربح **{_ml['avg_win']:+.1f}%** ومتوسط الخسارة **{_ml['avg_loss']:+.1f}%** "
                                f"— التوقع الرياضي **{_ml['expectancy']:+.1f}%** (سلبي رغم النسبة العالية!)"
                            )

                    # ── Heatmap chart ──
                    st.markdown("##### 📈 العوائد الشهرية حسب السنة")
                    _yr_mo_data = []
                    for m in _ss.get("monthly", []):
                        _yr_mo_data.append({
                            "السنة": str(m["year"]),
                            "الشهر": m["month"],
                            "الشهر_عربي": m["month_ar"],
                            "العائد": m["return_pct"],
                        })

                    if _yr_mo_data:
                        _ym_df = pd.DataFrame(_yr_mo_data)
                        _pivot = _ym_df.pivot_table(
                            index="السنة", columns="الشهر",
                            values="العائد", aggfunc="first"
                        )
                        _pivot.columns = [MONTH_NAMES_AR.get(c, str(c)) for c in _pivot.columns]

                        import plotly.figure_factory as ff
                        _z = _pivot.values.tolist()
                        _x = list(_pivot.columns)
                        _y = list(_pivot.index)
                        _z_text = [[f"{v:+.1f}%" if not pd.isna(v) else "" for v in row] for row in _z]

                        _hm_fig = ff.create_annotated_heatmap(
                            z=_z, x=_x, y=_y,
                            annotation_text=_z_text,
                            colorscale=[
                                [0, "#B71C1C"], [0.3, "#FF5252"],
                                [0.45, "#37474F"], [0.55, "#37474F"],
                                [0.7, "#4CAF50"], [1.0, "#00E676"],
                            ],
                            showscale=True, zmin=-10, zmax=10,
                        )
                        _hm_fig.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            height=max(200, len(_y) * 45 + 80),
                            margin=dict(l=60, r=20, t=10, b=40),
                            font=dict(family="Tajawal", size=12),
                            xaxis=dict(side="bottom"),
                        )
                        st.plotly_chart(_hm_fig, use_container_width=True, config={"displayModeBar": False})

                    # ── Catalyst timeline ──
                    if _ss_catalysts:
                        st.markdown("##### 📅 تقويم المحفزات الأساسية")
                        _cat_cols = st.columns(4)
                        for _ci, mo in enumerate(range(1, 13)):
                            if mo not in _ss_catalysts:
                                continue
                            _cat = _ss_catalysts[mo]
                            _cat_icon = "🟢" if _cat["impact"] in ("إيجابي", "إيجابي قوي") else "🔴" if "سلبي" in _cat["impact"] else "⚪"
                            _mo_stat = _ss_stats.get(mo)
                            _mo_avg = f" ({_mo_stat['avg_return']:+.1f}%)" if _mo_stat else ""
                            _cat_cols[_ci % 4].markdown(
                                f"**{_cat_icon} {MONTH_NAMES_AR[mo]}{_mo_avg}**\n\n"
                                f"{'  •  '.join(_cat['events'])}\n\n"
                                f"*{_cat['note']}*\n\n---"
                            )

                    # ── Transitions ──
                    _trans = _ss.get("transitions", [])
                    if _trans:
                        st.markdown("##### 🔄 نقاط التحول الموسمية")
                        for t in _trans:
                            if t["type"] == "تحسن":
                                st.success(f"{t['icon']} {t['description']}")
                            else:
                                st.error(f"{t['icon']} {t['description']}")

                    # ── Best/worst by Sharpe ──
                    if _ss_stats:
                        _by_sharpe = sorted(_ss_stats.values(), key=lambda x: x.get("sharpe", 0), reverse=True)
                        _best3 = _by_sharpe[:3]
                        _worst3 = _by_sharpe[-3:]
                        _b3_txt = " • ".join([f"**{m['month_ar']}** (Sharpe {m.get('sharpe', 0):.1f}, {m['avg_return']:+.1f}%)" for m in _best3])
                        _w3_txt = " • ".join([f"**{m['month_ar']}** (Sharpe {m.get('sharpe', 0):.1f}, {m['avg_return']:+.1f}%)" for m in _worst3])
                        st.markdown(f"🟢 **أفضل 3 أشهر (معدّل بالمخاطرة):** {_b3_txt}")
                        st.markdown(f"🔴 **أسوأ 3 أشهر (معدّل بالمخاطرة):** {_w3_txt}")
            else:
                st.info("لا توجد بيانات كافية للتحليل الموسمي — أعد المسح بفترة أطول (سنة+)")

        # ── Render sector cards ──
        for sd in sector_data:
            sector_color = SECTOR_COLORS.get(sd["name"], "#607D8B")
            health = sd["health"]
            h_color = "#00E676" if health > 20 else "#FF5252" if health < -20 else "#9ca3af"
            h_sign = "+" if health > 0 else ""

            # Proportions for bar
            total = sd["n"]
            g_pct = round(sd["n_accum"] / total * 100) if total else 0
            r_pct = round(sd["n_dist"] / total * 100) if total else 0
            n_pct = 100 - g_pct - r_pct

            # Build stock rows HTML
            rows_html = ""
            for s in sd["stocks"]:
                p = s["phase"]
                p_label = s.get("phase_label", "—")
                p_color = s.get("phase_color", "#808080")
                fb = s["flow_bias"]

                # Maturity info + conviction
                if p in _accum_phases:
                    m_days = s.get("maturity_days", 0)
                    _conv = s.get("maturity_conviction", 100.0)
                    _cf_ev = s.get("maturity_cf_events", 0)
                    m_label = f"{m_days} يوم" if m_days > 0 else ""
                elif p in _dist_phases:
                    m_days = s.get("dist_maturity_days", 0)
                    _conv = s.get("dist_conviction", 100.0)
                    _cf_ev = s.get("dist_cf_events", 0)
                    m_label = f"{m_days} يوم" if m_days > 0 else ""
                else:
                    m_label = ""
                    _conv = 100.0
                    _cf_ev = 0

                # Conviction badge
                _conv_badge = ""
                if p in _accum_phases and s.get("maturity_days", 0) >= 5:
                    _cc = "#00E676" if _conv >= 85 else "#FFD700" if _conv >= 65 else "#FF5252"
                    _conv_badge = f'<span style="color:{_cc};font-size:0.75em;font-weight:700">⟨{_conv:.0f}%⟩</span>'
                elif p in _dist_phases and s.get("dist_maturity_days", 0) >= 5:
                    _cc = "#FF5252" if _conv >= 85 else "#FFD700" if _conv >= 65 else "#00E676"
                    _conv_badge = f'<span style="color:{_cc};font-size:0.75em;font-weight:700">⟨{_conv:.0f}%⟩</span>'

                # Flow bias bar
                fb_abs = min(abs(fb), 100)
                fb_pct = fb_abs / 2  # scale to 50% max width
                fb_color = "#00E676" if fb > 0 else "#FF5252"
                if fb >= 0:
                    fb_bar = f'<div class="smap-fb-fill" style="right:50%;width:{fb_pct}%;background:{fb_color}"></div>'
                else:
                    fb_bar = f'<div class="smap-fb-fill" style="left:50%;width:{fb_pct}%;background:{fb_color}"></div>'

                chg = s.get("change_pct", 0)
                chg_color = "#00E676" if chg > 0 else "#FF5252" if chg < 0 else "#9ca3af"
                chg_str = f"{chg:+.1f}%"
                tk_short = s["ticker"].replace(".SR", "")

                rows_html += f'''
                <div class="smap-row">
                    <div class="smap-row-name">{s["name"]}</div>
                    <div class="smap-row-tk">{tk_short}</div>
                    <div class="smap-row-price">{s["price"]:.2f} <span style="color:{chg_color};font-size:0.82em">{chg_str}</span></div>
                    <div class="smap-phase" style="background:{p_color}18;color:{p_color};border:1px solid {p_color}30">{p_label}</div>
                    <div class="smap-days">{m_label} {_conv_badge}</div>
                    <div class="smap-fb">{fb_bar}<div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:#374151"></div></div>
                </div>'''

            # Sector composite return badge
            _sec_comp = _sector_composites.get(sd["name"])
            _sec_ret_badge = ""
            if _sec_comp:
                _sr = _sec_comp["ret"]
                _src = "#00E676" if _sr >= 0 else "#FF5252"
                _sec_ret_badge = (
                    f'<span style="color:{_src};font-weight:800;font-size:0.88em;'
                    f'background:{_src}12;padding:2px 8px;border-radius:8px">'
                    f'{"+" if _sr >= 0 else ""}{_sr:.1f}%</span>'
                )

            # Per-sector breadth badge
            _sb = _breadth["sector_breadth"].get(sd["name"], {})
            _sb_total = _sb.get("total", 0)
            _sb_ma50 = _sb.get("above_ma50", 0)
            _sb_ma50_pct = round(_sb_ma50 / _sb_total * 100) if _sb_total else 0
            _sb_c = "#00E676" if _sb_ma50_pct >= 70 else "#FFD700" if _sb_ma50_pct >= 40 else "#FF5252"
            _sb_badge = (
                f'<span style="color:{_sb_c};font-size:0.75em;font-weight:600;'
                f'background:{_sb_c}10;padding:2px 8px;border-radius:6px;'
                f'border:1px solid {_sb_c}25">'
                f'MA50: {_sb_ma50}/{_sb_total}</span>'
            ) if _sb_total else ""

            card_html = f'''
            <div class="smap-card" style="border-top:3px solid {sector_color}">
                <div class="smap-header">
                    <div class="smap-header-name" style="color:{sector_color}">{sd["name"]}</div>
                    <div style="display:flex;align-items:center;gap:10px">
                        {_sb_badge}
                        {_sec_ret_badge}
                        <div class="smap-health" style="color:{h_color}">{h_sign}{health}</div>
                    </div>
                </div>
                <div class="smap-counts">
                    <span>🟢 {sd["n_accum"]} تجميع</span>
                    <span>🔴 {sd["n_dist"]} تصريف</span>
                    <span>⚪ {sd["n_neutral"]} محايد</span>
                    <span style="margin-right:auto;color:#4b5563">({sd["n"]} سهم)</span>
                </div>
                <div class="smap-bar-wrap">
                    <div class="smap-bar-g" style="width:{g_pct}%"></div>
                    <div class="smap-bar-n" style="width:{n_pct}%"></div>
                    <div class="smap-bar-r" style="width:{r_pct}%"></div>
                </div>
            </div>'''

            st.markdown(card_html, unsafe_allow_html=True)

            # Stock rows (HTML + clickable buttons)
            if rows_html:
                st.markdown(f'<div class="smap-rows">{rows_html}</div>',
                            unsafe_allow_html=True)
                # Clickable stock buttons → navigate to Order Flow detail
                _btn_cols = st.columns(min(len(sd["stocks"]), 6))
                for _si, s in enumerate(sd["stocks"]):
                    with _btn_cols[_si % min(len(sd["stocks"]), 6)]:
                        if st.button(f"🔍 {s['name']}", key=f"goto_{sd['name']}_{s['ticker']}",
                                     use_container_width=True):
                            st.session_state["_goto_page"] = "🔬 Order Flow"
                            st.session_state.selected_ticker = s["ticker"]
                            st.rerun()


# ══════════════════════════════════════════════════════════════
# PAGE: Market Breakout Index
# ══════════════════════════════════════════════════════════════

elif page == "⚡ الارتدادات والاختراقات":
    results = st.session_state.scan_results
    if results is None:
        st.markdown('''
        <div style="text-align:center;padding:80px 20px;color:#4b5563">
            <div style="font-size:4em;margin-bottom:20px;opacity:0.4">⚡</div>
            <div style="font-size:1.3em;color:#6b7280;margin-bottom:10px">
                اضغط <b style="color:#00E676">ابدأ المسح</b> أولاً في صفحة Order Flow
            </div>
            <div style="font-size:0.88em">لاكتشاف الارتدادات والاختراقات والكسرات</div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        show_events_page(results)

elif page == "🚀 مؤشر الاختراقات":
    results = st.session_state.scan_results
    if results is None:
        st.markdown('''
        <div style="text-align:center;padding:80px 20px;color:#4b5563">
            <div style="font-size:4em;margin-bottom:20px;opacity:0.4">🚀</div>
            <div style="font-size:1.3em;color:#6b7280;margin-bottom:10px">
                اضغط <b style="color:#00E676">ابدأ المسح</b> أولاً في صفحة Order Flow
            </div>
            <div style="font-size:0.88em">لتحليل بيانات الأسهم وبناء مؤشر الاختراقات</div>
        </div>
        ''', unsafe_allow_html=True)
    else:
        show_breakout_index(results, market_key=market_key)


# ══════════════════════════════════════════════════════════════
# PAGE: Sector Leader — القطاع القائد
# ══════════════════════════════════════════════════════════════

elif page == "🏆 القطاع القائد":

    from core.sector_leader import (
        SECTORS_CONFIG, classify_sector, classify_pattern,
        compute_sector_returns, merge_order_flow,
        save_session, load_history, compute_historical_stats,
    )
    from core.sector_alerts import render_alerts

    st.markdown("## 🏆 القطاع القائد")
    st.markdown("أي قطاع يسبق المؤشر وأيهم يتبعه — تلقائياً كل جلسة")

    results = st.session_state.scan_results

    if results is None or len(results) == 0:
        st.warning("⚠️ لا توجد بيانات — شغّل المسح أولاً من صفحة Order Flow")
    else:
        # ── Group scan results by sector → compute sector returns ──
        from collections import defaultdict
        _sector_returns_raw = defaultdict(list)
        for r in results:
            sec = r.get("sector", "أخرى")
            chg = r.get("change_pct", 0)
            if chg is not None:
                _sector_returns_raw[sec].append(float(chg))

        # Average change per sector
        _sector_returns = {}
        for sec, changes in _sector_returns_raw.items():
            if changes:
                _sector_returns[sec] = round(sum(changes) / len(changes), 2)

        # Index return = average of all stocks
        _all_changes = [r.get("change_pct", 0) for r in results if r.get("change_pct") is not None]
        _index_return = round(sum(_all_changes) / max(len(_all_changes), 1), 2) if _all_changes else 0.0

        # Compute sector DataFrame
        _sl_df = compute_sector_returns(_sector_returns, _index_return)

        # ── Order Flow data per sector ──
        _of_data = defaultdict(lambda: {"accumulation": 0, "distribution": 0, "masa_score": 0, "count": 0})
        for r in results:
            sec = r.get("sector", "أخرى")
            phase = r.get("phase", "")
            if phase in ("accumulation", "spring"):
                _of_data[sec]["accumulation"] += 1
            elif phase in ("distribution", "upthrust", "markdown"):
                _of_data[sec]["distribution"] += 1
            bias = r.get("flow_bias", 0) or 0
            _of_data[sec]["masa_score"] += float(bias)
            _of_data[sec]["count"] += 1
        # Average MASA Score
        _of_dict = {}
        for sec, vals in _of_data.items():
            cnt = max(vals["count"], 1)
            _of_dict[sec] = {
                "accumulation": vals["accumulation"],
                "distribution": vals["distribution"],
                "masa_score": round(vals["masa_score"] / cnt, 1),
            }
        _sl_df = merge_order_flow(_sl_df, _of_dict)

        # ── Summary metrics ──
        _n_leaders = len(_sl_df[_sl_df['الحالة'] == 'قائد'])
        _n_synced = len(_sl_df[_sl_df['الحالة'] == 'متزامن'])
        _n_followers = len(_sl_df[_sl_df['الحالة'] == 'تابع'])
        _n_negatives = len(_sl_df[_sl_df['الحالة'] == 'سلبي'])

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🏆 قائد", _n_leaders)
        c2.metric("🔄 متزامن", _n_synced)
        c3.metric("📉 تابع", _n_followers)
        c4.metric("⛔ سلبي", _n_negatives)
        c5.metric("📊 المؤشر", f"{_index_return:+.2f}%")

        # ── Leader alert ──
        if _n_leaders > 0:
            _top = _sl_df.iloc[0]
            st.success(f"🏆 القائد: **{_top['القطاع']}** (+{_top['العائد']}% | Alpha: +{_top['Alpha']}%)")

        # ── Contradiction alerts ──
        for _, _row in _sl_df.iterrows():
            if _row.get('MASA_Score', 0) != '' and _row.get('MASA_Score', 0) != 0:
                _masa = float(_row.get('MASA_Score', 0))
                if _row['الحالة'] == 'تابع' and _masa > 20:
                    st.info(f"⚡ تناقض: **{_row['القطاع']}** تابع بالعائد لكن MASA Score +{_masa:.1f} (تجميع نشط!) — راقب")

        # ── Main table ──
        st.markdown("### ترتيب القطاعات")
        _display = _sl_df.copy()
        _display['#'] = range(1, len(_display) + 1)
        _cols = ['#', 'القطاع', 'العائد', 'Alpha', 'الحالة']
        if 'تجميع' in _display.columns:
            _cols.extend(['تجميع', 'تصريف', 'نسبة_تجميع', 'MASA_Score'])
        st.dataframe(
            _display[_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                'العائد': st.column_config.NumberColumn(format="%.2f%%"),
                'Alpha': st.column_config.NumberColumn(format="%.2f%%"),
            }
        )

        # ── Comparison chart ──
        st.markdown("### شارت المقارنة")
        import plotly.graph_objects as go
        _sl_fig = go.Figure()
        for _, _row in _sl_df.iterrows():
            _sl_fig.add_trace(go.Bar(
                y=[_row['القطاع']],
                x=[_row['العائد']],
                orientation='h',
                marker_color=_row['اللون'],
                name=_row['القطاع'],
                showlegend=False,
                text=f"{_row['العائد']:+.2f}%",
                textposition='outside',
            ))
        _sl_fig.add_vline(x=_index_return, line_dash="dash", line_color="#1D9E75",
                          annotation_text=f"المؤشر {_index_return:+.2f}%")
        _sl_fig.add_vline(x=0, line_dash="dot", line_color="gray", line_width=0.5)
        _sl_fig.update_layout(
            height=max(400, len(_sl_df) * 30),
            margin=dict(l=0, r=0, t=30, b=0),
            yaxis=dict(autorange="reversed"),
            xaxis_title="العائد %",
            template="plotly_dark",
        )
        st.plotly_chart(_sl_fig, use_container_width=True)

        # ── Contradiction alerts ──
        render_alerts(_sl_df)

        # ── Save session ──
        _scan_tf_label = st.session_state.get("scan_timeframe", "📊 يومي")
        _tf_map = {"📊 يومي": "daily", "⏱️ 1 ساعة": "1h", "⏱️ 15 دقيقة": "15m", "⏱️ 5 دقائق": "15m"}
        save_session(_sl_df, _tf_map.get(_scan_tf_label, "daily"), _index_return)

        # ── History ──
        st.divider()
        st.markdown("### 📜 تاريخ الجلسات")
        _hist_days = st.slider("عدد الأيام", 7, 90, 30, key="sl_hist_days")
        _hist = load_history(days=_hist_days)
        if len(_hist) == 0:
            st.info("لا يوجد تاريخ بعد — سيتراكم مع كل جلسة")
        else:
            _hist_tf = st.radio("الفريم", ['daily', '1h', '15m'], horizontal=True, key="sl_hist_tf")
            _stats = compute_historical_stats(_hist, timeframe=_hist_tf)
            if len(_stats) == 0:
                st.info(f"لا توجد بيانات على فريم {_hist_tf}")
            else:
                st.dataframe(_stats, use_container_width=True, hide_index=True)
                import plotly.express as px
                _hist_fig = px.bar(
                    _stats.head(10), y='القطاع', x='نسبة_القيادة', orientation='h',
                    color='نسبة_القيادة', color_continuous_scale=['#E24B4A', '#EF9F27', '#1D9E75'],
                    title='نسبة القيادة لأفضل 10 قطاعات',
                )
                _hist_fig.update_layout(
                    height=400, yaxis=dict(autorange="reversed"),
                    xaxis_title="نسبة القيادة %", template="plotly_dark",
                )
                st.plotly_chart(_hist_fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# PAGE: Company Analysis — تحليل شركة
# ══════════════════════════════════════════════════════════════

elif page == "🔍 تحليل شركة":

    # ── Helper: Fetch company data (cached 5 min) ──
    @st.cache_data(ttl=300, show_spinner=False)
    def _fetch_company(ticker, period="10y"):
        import time
        for _attempt in range(3):
            try:
                t = yf.Ticker(ticker)
                df = t.history(period=period, interval="1d")
                if df is not None and not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                info = {}
                try:
                    info = t.info or {}
                except Exception:
                    pass
                return df, info
            except Exception as e:
                if "RateLimit" in str(type(e).__name__) or "429" in str(e):
                    time.sleep(2 * (_attempt + 1))
                    continue
                raise
        return pd.DataFrame(), {}

    # ── Helper: Compute seasonality ──
    def _compute_seasonality(df):
        if df is None or df.empty:
            return None
        monthly = {}  # {(year, month): return_pct}
        df_copy = df.copy()
        df_copy.index = pd.to_datetime(df_copy.index)
        for (year, month), grp in df_copy.groupby([df_copy.index.year, df_copy.index.month]):
            if len(grp) < 2:
                continue
            first_close = grp["Close"].iloc[0]
            last_close = grp["Close"].iloc[-1]
            if first_close and first_close > 0:
                ret = round((last_close - first_close) / first_close * 100, 2)
                monthly[(year, month)] = ret

        if not monthly:
            return None

        years = sorted(set(y for y, m in monthly.keys()), reverse=True)
        months = list(range(1, 13))
        month_names = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                       "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

        # Probability and average per month
        prob = {}
        avg = {}
        for m in months:
            vals = [monthly[(y, m)] for y in years if (y, m) in monthly]
            if vals:
                prob[m] = round(sum(1 for v in vals if v > 0) / len(vals) * 100)
                avg[m] = round(sum(vals) / len(vals), 2)
            else:
                prob[m] = 0
                avg[m] = 0

        return {
            "monthly": monthly,
            "years": years,
            "months": months,
            "month_names": month_names,
            "prob": prob,
            "avg": avg,
        }

    st.markdown('<h2 style="text-align:center;margin-bottom:4px">🔍 تحليل شركة</h2>', unsafe_allow_html=True)
    st.caption("بحث وتحليل مفصل لأي شركة — نظرة عامة + موسمية الأداء")

    # ── Stock selector ──
    from data.markets import SAUDI_STOCKS, US_STOCKS, FOREX_STOCKS, CRYPTO_STOCKS, COMMODITIES_STOCKS, get_sector
    if market_key == "us":
        _stocks_dict = US_STOCKS
    elif market_key == "forex":
        _stocks_dict = FOREX_STOCKS
    elif market_key == "commodities":
        _stocks_dict = COMMODITIES_STOCKS
    elif market_key == "crypto":
        _stocks_dict = CRYPTO_STOCKS
    else:
        _stocks_dict = SAUDI_STOCKS

    def _fmt_label(tk, name):
        clean = tk.replace(".SR", "").replace("=X", "").replace("-USD", "")
        return f"{name} ({clean})"

    _stock_options = {tk: _fmt_label(tk, name) for tk, name in _stocks_dict.items()}
    _stock_list = list(_stock_options.keys())
    _stock_labels = list(_stock_options.values())

    # Check if redirected from sector map
    _default_idx = 0
    if "_goto_ticker" in st.session_state:
        _goto_tk = st.session_state.pop("_goto_ticker")
        if _goto_tk in _stock_list:
            _default_idx = _stock_list.index(_goto_tk)

    _selected_label = st.selectbox(
        "اختر الشركة",
        _stock_labels,
        index=_default_idx,
        key="company_select",
    )
    _selected_tk = _stock_list[_stock_labels.index(_selected_label)]
    _selected_name = _stocks_dict[_selected_tk]
    _selected_sector = get_sector(_selected_tk)

    # ── Fetch data ──
    try:
        with st.spinner(f"📡 جاري تحميل بيانات {_selected_name}..."):
            _c_df, _c_info = _fetch_company(_selected_tk)
    except Exception as _fetch_err:
        st.error(f"⚠️ خطأ في تحميل البيانات: {type(_fetch_err).__name__}")
        st.info("💡 حاول مرة ثانية بعد دقيقة — قد يكون السبب تجاوز حد الطلبات من Yahoo Finance")
        _c_df, _c_info = pd.DataFrame(), {}

    if _c_df is None or _c_df.empty:
        st.error(f"❌ لا توجد بيانات لـ {_selected_name}")
    else:
        # ── Company Header ──
        _cur_price = round(float(_c_df["Close"].iloc[-1]), 2)
        _prev_price = float(_c_df["Close"].iloc[-2]) if len(_c_df) >= 2 else _cur_price
        _change_pct = round((_cur_price - _prev_price) / _prev_price * 100, 2) if _prev_price else 0
        _chg_color = "#00E676" if _change_pct >= 0 else "#FF5252"
        _chg_icon = "▲" if _change_pct >= 0 else "▼"

        _mcap = _c_info.get("marketCap", 0)
        _mcap_str = ""
        if _mcap:
            if _mcap >= 1e12:
                _mcap_str = f"{_mcap/1e12:.1f}T"
            elif _mcap >= 1e9:
                _mcap_str = f"{_mcap/1e9:.1f}B"
            elif _mcap >= 1e6:
                _mcap_str = f"{_mcap/1e6:.0f}M"

        _pe = _c_info.get("trailingPE", 0)
        _pe_str = f"{_pe:.1f}" if _pe else "—"
        _high52 = _c_info.get("fiftyTwoWeekHigh", 0)
        _low52 = _c_info.get("fiftyTwoWeekLow", 0)
        _sector_color = SECTOR_COLORS.get(_selected_sector, "#607D8B")

        st.markdown(f'''
        <div style="background:linear-gradient(145deg, #131a2e 0%, #0e1424 100%);
                    border:1px solid #192035;border-radius:16px;padding:20px;margin:10px 0;direction:rtl">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                <div style="flex:1">
                    <div style="color:#fff;font-size:1.5em;font-weight:800">{_selected_name}</div>
                    <div style="display:flex;align-items:center;gap:10px;margin-top:4px;flex-wrap:wrap">
                        <span style="color:#6b7280;font-size:0.9em">{_selected_tk.replace(".SR", "").replace("=X", "").replace("-USD", "")}</span>
                        <span style="background:{_sector_color}18;color:{_sector_color};padding:2px 10px;
                                     border-radius:8px;font-size:0.78em;border:1px solid {_sector_color}30">
                            {_selected_sector}</span>
                    </div>
                </div>
                <div style="text-align:left">
                    <div style="color:#fff;font-size:2em;font-weight:800">{_cur_price}</div>
                    <div style="color:{_chg_color};font-weight:700;font-size:0.95em">{_chg_icon} {abs(_change_pct):.2f}%</div>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px;
                        background:rgba(8,11,20,0.5);border-radius:10px;padding:10px">
                <div style="text-align:center">
                    <div style="color:#4b5563;font-size:0.72em">القيمة السوقية</div>
                    <div style="color:#fff;font-weight:700;font-size:0.95em">{_mcap_str or "—"}</div>
                </div>
                <div style="text-align:center;border-right:1px solid #192035;border-left:1px solid #192035">
                    <div style="color:#4b5563;font-size:0.72em">مكرر الأرباح</div>
                    <div style="color:#fff;font-weight:700;font-size:0.95em">{_pe_str}</div>
                </div>
                <div style="text-align:center;border-left:1px solid #192035">
                    <div style="color:#4b5563;font-size:0.72em">أعلى 52 أسبوع</div>
                    <div style="color:#00E676;font-weight:700;font-size:0.95em">{_high52:.2f}</div>
                </div>
                <div style="text-align:center">
                    <div style="color:#4b5563;font-size:0.72em">أدنى 52 أسبوع</div>
                    <div style="color:#FF5252;font-weight:700;font-size:0.95em">{_low52:.2f}</div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        # ── Price Chart with period selector ──
        _period_opts = {"3 أشهر": 63, "6 أشهر": 126, "سنة": 252, "سنتين": 504, "5 سنوات": None}
        _p_cols = st.columns(len(_period_opts))
        if "chart_period" not in st.session_state:
            st.session_state.chart_period = "سنة"
        for _pi, _pk in enumerate(_period_opts.keys()):
            with _p_cols[_pi]:
                if st.button(_pk, key=f"cp_{_pk}", use_container_width=True,
                             type="primary" if st.session_state.chart_period == _pk else "secondary"):
                    st.session_state.chart_period = _pk

        _period_bars = _period_opts[st.session_state.chart_period]
        _chart_df = _c_df.iloc[-_period_bars:] if _period_bars else _c_df

        # Build candlestick chart
        _c_fig = go.Figure()

        _c_fig.add_trace(go.Candlestick(
            x=_chart_df.index,
            open=_chart_df["Open"], high=_chart_df["High"],
            low=_chart_df["Low"], close=_chart_df["Close"],
            increasing_line_color="#00E676", decreasing_line_color="#FF5252",
            increasing_fillcolor="#00E676", decreasing_fillcolor="#FF5252",
            name="السعر",
        ))

        # MA50
        if len(_chart_df) >= 50:
            _ma50 = _chart_df["Close"].rolling(50).mean()
            _c_fig.add_trace(go.Scatter(
                x=_chart_df.index, y=_ma50, mode="lines",
                name="MA50", line=dict(color="#00BCD4", width=1.5),
            ))

        # MA200
        if len(_chart_df) >= 200:
            _ma200 = _chart_df["Close"].rolling(200).mean()
            _c_fig.add_trace(go.Scatter(
                x=_chart_df.index, y=_ma200, mode="lines",
                name="MA200", line=dict(color="#E040FB", width=1.5),
            ))

        _c_fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(20,24,36,0.8)",
            height=500, margin=dict(l=40, r=20, t=10, b=30),
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                        font=dict(family="Tajawal", size=11)),
            yaxis=dict(title=None, gridcolor="#192035", tickfont=dict(size=10, color="#4b5563")),
            xaxis=dict(gridcolor="#192035", tickfont=dict(size=10, color="#4b5563")),
            font=dict(family="Tajawal"),
        )
        st.plotly_chart(_c_fig, use_container_width=True, config={"displayModeBar": False})

        # ── Seasonality Table ──
        st.markdown('<h3 style="text-align:center;margin:20px 0 8px">📅 الموسمية — أداء شهري تاريخي</h3>',
                    unsafe_allow_html=True)

        _seas = _compute_seasonality(_c_df)
        if _seas:
            # Build HTML table
            _mnames = _seas["month_names"]
            _th_cells = "".join(f'<th style="padding:8px 6px;color:#9ca3af;font-size:0.78em;font-weight:600">{m}</th>' for m in _mnames)

            # Probability row
            _prob_cells = ""
            for m in _seas["months"]:
                p = _seas["prob"][m]
                pc = "#00E676" if p >= 60 else "#FF5252" if p <= 40 else "#FFD700"
                arrow = "▲" if p >= 50 else "▼"
                _prob_cells += f'<td style="text-align:center;padding:6px;color:{pc};font-weight:700;font-size:0.85em">{arrow} {p}%</td>'

            # Average row
            _avg_cells = ""
            for m in _seas["months"]:
                a = _seas["avg"][m]
                ac = "#00E676" if a > 0 else "#FF5252" if a < 0 else "#9ca3af"
                _avg_cells += f'<td style="text-align:center;padding:6px;color:{ac};font-weight:600;font-size:0.82em">{a:+.2f}%</td>'

            # Year rows
            _year_rows = ""
            for y in _seas["years"]:
                cells = ""
                for m in _seas["months"]:
                    val = _seas["monthly"].get((y, m))
                    if val is not None:
                        vc = "#00E676" if val > 0 else "#FF5252" if val < 0 else "#9ca3af"
                        bg = f"{vc}08"
                        cells += f'<td style="text-align:center;padding:6px;color:{vc};background:{bg};font-size:0.82em">{val:+.2f}%</td>'
                    else:
                        cells += '<td style="text-align:center;padding:6px;color:#374151;font-size:0.82em">—</td>'
                _year_rows += f'<tr><td style="padding:8px;color:#fff;font-weight:700;font-size:0.88em;white-space:nowrap">{y}</td>{cells}</tr>'

            _table_html = f'''
            <div style="overflow-x:auto;border-radius:12px;border:1px solid #192035;margin:8px 0">
                <table style="width:100%;border-collapse:collapse;background:#0e1424;direction:ltr">
                    <thead>
                        <tr style="border-bottom:2px solid #192035">
                            <th style="padding:8px;color:#6b7280;font-size:0.78em">السنة</th>
                            {_th_cells}
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="border-bottom:2px solid #192035;background:rgba(124,77,255,0.05)">
                            <td style="padding:8px;color:#B39DDB;font-weight:700;font-size:0.82em;white-space:nowrap">الاحتمال %</td>
                            {_prob_cells}
                        </tr>
                        <tr style="border-bottom:2px solid #192035;background:rgba(0,230,118,0.03)">
                            <td style="padding:8px;color:#6b7280;font-weight:600;font-size:0.82em;white-space:nowrap">المتوسط %</td>
                            {_avg_cells}
                        </tr>
                        {_year_rows}
                    </tbody>
                </table>
            </div>'''
            st.markdown(_table_html, unsafe_allow_html=True)
        else:
            st.info("لا توجد بيانات كافية لحساب الموسمية")

        # ── Seasonality Overlay Chart ──────────────────────────
        st.markdown('<h3 style="text-align:center;margin:30px 0 8px">📈 شارت الموسمية — مقارنة السنوات</h3>',
                    unsafe_allow_html=True)
        st.caption("أداء السنة الحالية مقارنة بمتوسط السنوات السابقة وأقرب سنة تشابهاً")

        # Date range + years selector
        _dr_c1, _dr_c2, _dr_c3 = st.columns([1, 1, 1])
        _this_year = datetime.date.today().year
        with _dr_c1:
            _date_from = st.date_input("من تاريخ", value=datetime.date(_this_year, 1, 1),
                                       min_value=datetime.date(_this_year, 1, 1),
                                       max_value=datetime.date(_this_year, 12, 31),
                                       key="season_from")
        with _dr_c2:
            _date_to = st.date_input("إلى تاريخ", value=datetime.date.today(),
                                     min_value=datetime.date(_this_year, 1, 1),
                                     max_value=datetime.date(_this_year, 12, 31),
                                     key="season_to")
        with _dr_c3:
            _n_years = st.selectbox("عدد السنوات", [1, 2, 3, 5, 7, 10],
                                    index=2, key="season_nyears")
        _doy_from = _date_from.timetuple().tm_yday
        _doy_to = _date_to.timetuple().tm_yday
        if _doy_from >= _doy_to:
            _doy_from, _doy_to = 1, datetime.date.today().timetuple().tm_yday

        def _filter_curve(curve, doy_from, doy_to):
            """Filter curve to day-of-year range and re-normalize to 0% at start."""
            filtered = [(d, v) for d, v in curve if doy_from <= d <= doy_to]
            if not filtered:
                return []
            base = filtered[0][1]
            return [(d, round(v - base, 2)) for d, v in filtered]

        def _smooth_curve(curve, window=5):
            """Smooth a curve using simple moving average."""
            if len(curve) < window:
                return curve
            days = [d for d, _ in curve]
            vals = [v for _, v in curve]
            smoothed = []
            half = window // 2
            for i in range(len(vals)):
                start = max(0, i - half)
                end = min(len(vals), i + half + 1)
                avg = sum(vals[start:end]) / (end - start)
                smoothed.append((days[i], round(avg, 2)))
            return smoothed

        def _build_yearly_curves(df):
            """Build normalized daily curves for each year (Jan 1 = 0%)."""
            if df is None or df.empty:
                return None
            df_c = df.copy()
            df_c.index = pd.to_datetime(df_c.index)
            yearly = {}
            for year, grp in df_c.groupby(df_c.index.year):
                if len(grp) < 20:
                    continue
                first_price = grp["Close"].iloc[0]
                if not first_price or first_price <= 0:
                    continue
                # Day of year (trading days from start)
                pcts = [(d.timetuple().tm_yday, round((c - first_price) / first_price * 100, 2))
                        for d, c in zip(grp.index, grp["Close"])]
                yearly[year] = pcts
            return yearly

        def _compute_correlation(curve_a, curve_b):
            """Pearson correlation between two yearly curves."""
            # Align by day-of-year
            dict_a = dict(curve_a)
            dict_b = dict(curve_b)
            common = sorted(set(dict_a.keys()) & set(dict_b.keys()))
            if len(common) < 10:
                return 0
            vals_a = [dict_a[d] for d in common]
            vals_b = [dict_b[d] for d in common]
            mean_a = sum(vals_a) / len(vals_a)
            mean_b = sum(vals_b) / len(vals_b)
            num = sum((a - mean_a) * (b - mean_b) for a, b in zip(vals_a, vals_b))
            den_a = sum((a - mean_a) ** 2 for a in vals_a) ** 0.5
            den_b = sum((b - mean_b) ** 2 for b in vals_b) ** 0.5
            if den_a == 0 or den_b == 0:
                return 0
            return round(num / (den_a * den_b) * 100, 1)

        _yearly = _build_yearly_curves(_c_df)
        if _yearly and len(_yearly) >= 2:
            _current_year = datetime.date.today().year
            _all_past = sorted([y for y in _yearly if y != _current_year], reverse=True)
            _past_years = _all_past[:_n_years]  # Limit to selected number of years

            if _current_year in _yearly and _past_years:
                # Apply date range filter to all curves
                _cur_curve = _filter_curve(_yearly[_current_year], _doy_from, _doy_to)
                _filtered_yearly = {y: _filter_curve(_yearly[y], _doy_from, _doy_to) for y in _past_years}
                _filtered_yearly = {y: c for y, c in _filtered_yearly.items() if len(c) >= 5}

                if _cur_curve and _filtered_yearly:
                    # Average curve from past years (filtered)
                    _all_days = sorted(set(d for y in _filtered_yearly for d, _ in _filtered_yearly[y]))
                    _avg_curve = []
                    for day in _all_days:
                        vals = [dict(_filtered_yearly[y]).get(day) for y in _filtered_yearly
                                if dict(_filtered_yearly[y]).get(day) is not None]
                        if vals:
                            _avg_curve.append((day, round(sum(vals) / len(vals), 2)))

                    # Find most correlated year (within filtered range)
                    _filt_past = list(_filtered_yearly.keys())
                    _best_year = _filt_past[0]
                    _best_corr = 0
                    _correlations = {}
                    for y in _filt_past:
                        corr = _compute_correlation(_cur_curve, _filtered_yearly[y])
                        _correlations[y] = corr
                        if corr > _best_corr:
                            _best_corr = corr
                            _best_year = y

                    # Month labels for x-axis
                    _month_ticks = {1: "يناير", 32: "فبراير", 60: "مارس", 91: "أبريل",
                                    121: "مايو", 152: "يونيو", 182: "يوليو", 213: "أغسطس",
                                    244: "سبتمبر", 274: "أكتوبر", 305: "نوفمبر", 335: "ديسمبر"}
                    # Filter month ticks to visible range
                    _vis_ticks = {k: v for k, v in _month_ticks.items() if _doy_from <= k <= _doy_to}
                    if not _vis_ticks:
                        _vis_ticks = _month_ticks

                    _s_fig = go.Figure()

                    # Smooth curves for cleaner display
                    _avg_smooth = _smooth_curve(_avg_curve, window=7)
                    _best_curve_raw = _filtered_yearly[_best_year]
                    _best_smooth = _smooth_curve(_best_curve_raw, window=5)

                    # Average (green)
                    if _avg_smooth:
                        _s_fig.add_trace(go.Scatter(
                            x=[d for d, _ in _avg_smooth], y=[v for _, v in _avg_smooth],
                            mode="lines", name=f"المتوسط ({len(_filt_past)} سنوات)",
                            line=dict(color="#00E676", width=2),
                        ))

                    # Best match year (dark green dotted)
                    _s_fig.add_trace(go.Scatter(
                        x=[d for d, _ in _best_smooth], y=[v for _, v in _best_smooth],
                        mode="lines", name=f"{_best_year} ({_best_corr:.0f}% تطابق)",
                        line=dict(color="#1DE9B6", width=1.5, dash="dot"),
                    ))

                    # Current year (red/pink)
                    _s_fig.add_trace(go.Scatter(
                        x=[d for d, _ in _cur_curve], y=[v for _, v in _cur_curve],
                        mode="lines", name=f"{_current_year} (الحالي)",
                        line=dict(color="#FF5252", width=2.5),
                    ))

                    # Zero line
                    _s_fig.add_hline(y=0, line_dash="dash", line_color="#374151", line_width=1)

                    # Today marker (only if within selected range)
                    _today_doy = datetime.date.today().timetuple().tm_yday
                    if _doy_from <= _today_doy <= _doy_to:
                        _s_fig.add_vline(x=_today_doy, line_dash="dot", line_color="#FFD700", line_width=1,
                                         annotation_text="اليوم", annotation_font_color="#FFD700",
                                         annotation_font_size=11)

                    _s_fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(20,24,36,0.8)",
                        height=400, margin=dict(l=40, r=20, t=10, b=40),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                                    font=dict(family="Tajawal", size=11)),
                        yaxis=dict(title="% العائد", gridcolor="#192035",
                                   tickfont=dict(size=10, color="#4b5563"), ticksuffix="%"),
                        xaxis=dict(gridcolor="#192035", tickfont=dict(size=10, color="#4b5563"),
                                   tickvals=list(_vis_ticks.keys()),
                                   ticktext=list(_vis_ticks.values()),
                                   range=[_doy_from - 2, _doy_to + 2]),
                        font=dict(family="Tajawal"),
                        hovermode="x unified",
        spikedistance=-1,
                    )
                    st.plotly_chart(_s_fig, use_container_width=True, config={"displayModeBar": False})

                    # Correlation cards
                    _sorted_corr = sorted(_correlations.items(), key=lambda x: -x[1])[:3]
                    _corr_cols = st.columns(len(_sorted_corr))
                    for _ci, (_cy, _cv) in enumerate(_sorted_corr):
                        _cc = "#00E676" if _cv >= 70 else "#FFD700" if _cv >= 40 else "#FF5252"
                        with _corr_cols[_ci]:
                            st.markdown(f'<div style="background:#131a2e;border:1px solid #192035;border-radius:12px;padding:16px;text-align:center"><div style="color:#6b7280;font-size:0.78em;margin-bottom:4px">تطابق مع {_cy}</div><div style="color:{_cc};font-size:1.8em;font-weight:800">{_cv:.0f}%</div></div>', unsafe_allow_html=True)
                else:
                    st.info("لا توجد بيانات كافية للنطاق المحدد")
        else:
            st.info("لا توجد بيانات كافية لشارت الموسمية")

        # ── Trades Statistics ────────────────────────────────────
        st.markdown('<h3 style="text-align:center;margin:30px 0 8px">📊 إحصائيات الصفقات</h3>',
                    unsafe_allow_html=True)
        _from_mmdd = f"{_date_from.month:02d}/{_date_from.day:02d}"
        _to_mmdd = f"{_date_to.month:02d}/{_date_to.day:02d}"
        st.caption(f"لو اشتريت {_from_mmdd} وبعت {_to_mmdd} كل سنة — كم كان العائد؟")

        if _c_df is not None and not _c_df.empty:
            _tdf = _c_df.copy()
            _tdf.index = pd.to_datetime(_tdf.index)
            _trades = []
            _available_years = sorted([y for y in _tdf.index.year.unique() if y != datetime.date.today().year], reverse=True)
            _trade_years = _available_years[:_n_years]  # Respect selected year count
            for _yr in _trade_years:
                # Find open: first trading day on or after from_date (extend up to 5 days forward)
                # Find close: if close_target falls on non-trading day, extend up to 5 days forward
                _open_target = datetime.date(_yr, _date_from.month, _date_from.day)
                _open_extended = _open_target + datetime.timedelta(days=5)
                _close_target = datetime.date(_yr, _date_to.month, _date_to.day)
                _close_extended = _close_target + datetime.timedelta(days=5)
                # Get full range including extensions
                _yr_data = _tdf[(_tdf.index.date >= _open_target) & (_tdf.index.date <= _close_extended)]
                if _yr_data.empty:
                    continue
                # Find actual open: first trading day on or after open_target
                _actual_open_idx = _yr_data.index[0]
                # Find actual close: first trading day on or after close_target
                _post_target = _yr_data[_yr_data.index.date >= _close_target]
                if not _post_target.empty:
                    _actual_close_idx = _post_target.index[0]
                else:
                    _actual_close_idx = _yr_data.index[-1]
                _yr_data = _tdf[(_tdf.index >= _actual_open_idx) & (_tdf.index <= _actual_close_idx)]
                if _yr_data.empty or len(_yr_data) < 1:
                    continue
                _open_price = _yr_data["Close"].iloc[0]
                _close_price = _yr_data["Close"].iloc[-1]
                _open_dt = _yr_data.index[0].strftime("%Y/%m/%d")
                _close_dt = _yr_data.index[-1].strftime("%Y/%m/%d")
                _ret = (_close_price - _open_price) / _open_price * 100
                # Max drop and max rise during period
                _min_price = _yr_data["Low"].min() if "Low" in _yr_data.columns else _yr_data["Close"].min()
                _max_price = _yr_data["High"].max() if "High" in _yr_data.columns else _yr_data["Close"].max()
                _max_drop = (_min_price - _open_price) / _open_price * 100
                _max_rise = (_max_price - _open_price) / _open_price * 100
                _trades.append({
                    "open_dt": _open_dt, "close_dt": _close_dt,
                    "open_p": _open_price, "close_p": _close_price,
                    "ret": _ret, "drop": _max_drop, "rise": _max_rise
                })

            if _trades:
                _wins = sum(1 for t in _trades if t["ret"] > 0)
                _total = len(_trades)
                _win_rate = _wins / _total * 100
                _avg_ret = sum(t["ret"] for t in _trades) / _total

                # Summary cards
                _wr_color = "#00E676" if _win_rate >= 60 else "#FFD700" if _win_rate >= 40 else "#FF5252"
                _ar_color = "#00E676" if _avg_ret > 0 else "#FF5252"
                _sc1, _sc2, _sc3 = st.columns(3)
                with _sc1:
                    st.markdown(f'<div style="background:#131a2e;border:1px solid #192035;border-radius:12px;padding:16px;text-align:center"><div style="color:#6b7280;font-size:0.78em;margin-bottom:4px">نسبة النجاح</div><div style="color:{_wr_color};font-size:1.8em;font-weight:800">{_win_rate:.0f}%</div><div style="color:#374151;font-size:0.75em">{_wins}/{_total} سنوات</div></div>', unsafe_allow_html=True)
                with _sc2:
                    st.markdown(f'<div style="background:#131a2e;border:1px solid #192035;border-radius:12px;padding:16px;text-align:center"><div style="color:#6b7280;font-size:0.78em;margin-bottom:4px">متوسط العائد</div><div style="color:{_ar_color};font-size:1.8em;font-weight:800">{_avg_ret:+.2f}%</div></div>', unsafe_allow_html=True)
                with _sc3:
                    _avg_drop = sum(t["drop"] for t in _trades) / _total
                    st.markdown(f'<div style="background:#131a2e;border:1px solid #192035;border-radius:12px;padding:16px;text-align:center"><div style="color:#6b7280;font-size:0.78em;margin-bottom:4px">متوسط أقصى انخفاض</div><div style="color:#FF5252;font-size:1.8em;font-weight:800">{_avg_drop:.2f}%</div></div>', unsafe_allow_html=True)

                # Trades table
                _t_header = '<tr><th style="padding:10px 12px;color:#6b7280;font-size:0.8em;border-bottom:1px solid #192035">تاريخ الشراء</th><th style="padding:10px 12px;color:#6b7280;font-size:0.8em;border-bottom:1px solid #192035">تاريخ البيع</th><th style="padding:10px 12px;color:#6b7280;font-size:0.8em;border-bottom:1px solid #192035">سعر الشراء</th><th style="padding:10px 12px;color:#6b7280;font-size:0.8em;border-bottom:1px solid #192035">سعر البيع</th><th style="padding:10px 12px;color:#6b7280;font-size:0.8em;border-bottom:1px solid #192035">العائد %</th><th style="padding:10px 12px;color:#6b7280;font-size:0.8em;border-bottom:1px solid #192035">أقصى انخفاض %</th><th style="padding:10px 12px;color:#6b7280;font-size:0.8em;border-bottom:1px solid #192035">أقصى ارتفاع %</th></tr>'
                _t_rows = ""
                for _t in _trades:
                    _rc = "#00E676" if _t["ret"] > 0 else "#FF5252"
                    _t_rows += f'<tr><td style="padding:8px 12px;border-bottom:1px solid #0d1117;color:#9ca3af;font-size:0.85em">{_t["open_dt"]}</td><td style="padding:8px 12px;border-bottom:1px solid #0d1117;color:#9ca3af;font-size:0.85em">{_t["close_dt"]}</td><td style="padding:8px 12px;border-bottom:1px solid #0d1117;color:#e5e7eb;font-size:0.85em">{_t["open_p"]:.2f}</td><td style="padding:8px 12px;border-bottom:1px solid #0d1117;color:#e5e7eb;font-size:0.85em">{_t["close_p"]:.2f}</td><td style="padding:8px 12px;border-bottom:1px solid #0d1117;color:{_rc};font-weight:700;font-size:0.85em">{_t["ret"]:+.2f}%</td><td style="padding:8px 12px;border-bottom:1px solid #0d1117;color:#FF5252;font-size:0.85em">{_t["drop"]:.2f}%</td><td style="padding:8px 12px;border-bottom:1px solid #0d1117;color:#00E676;font-size:0.85em">+{_t["rise"]:.2f}%</td></tr>'
                st.markdown(f'<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;background:#131a2e;border-radius:12px;overflow:hidden;margin-top:12px"><thead>{_t_header}</thead><tbody>{_t_rows}</tbody></table></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# PAGE: Earnings Calendar — تقويم النتائج
# ══════════════════════════════════════════════════════════════

elif page == "📅 تقويم النتائج":
    from core.earnings import _fetch_earnings_info, check_earnings_proximity, check_ex_dividend
    from core.earnings_tracker import get_earnings_history, compute_earnings_stats
    from data.markets import SAUDI_STOCKS, US_STOCKS, get_stock_name

    results = st.session_state.get("scan_results")
    _market_key = st.session_state.get("market_key", "saudi")

    st.markdown('''
    <div style="text-align:center;padding:20px 0 10px 0">
        <span style="font-size:1.8em;font-weight:800;color:#fff">📅 تقويم النتائج</span>
        <div style="color:#6b7280;font-size:0.92em;margin-top:6px">
            إعلانات النتائج والتوزيعات القادمة — مع إحصائيات تاريخية
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # Get tickers based on market
    _cal_stocks = SAUDI_STOCKS if _market_key == "saudi" else US_STOCKS
    _cal_tickers = list(_cal_stocks.keys())

    # Limit to scanned stocks if available
    if results:
        _cal_tickers = [r["ticker"] for r in results]

    with st.spinner("📅 جاري جلب تواريخ النتائج..."):
        _upcoming = []
        for _tk in _cal_tickers:
            _info = _fetch_earnings_info(_tk)
            if _info and "earnings_date" in _info:
                try:
                    from datetime import datetime
                    _ed = datetime.strptime(_info["earnings_date"], "%Y-%m-%d")
                    _days = (_ed - datetime.now()).days
                    if -7 <= _days <= 90:  # Past week to 3 months ahead
                        _name = get_stock_name(_tk)
                        # Check if accumulating
                        _flow = 0
                        _phase = ""
                        _cdv = ""
                        if results:
                            _r = next((r for r in results if r["ticker"] == _tk), None)
                            if _r:
                                _flow = _r.get("flow_bias", 0)
                                _phase = _r.get("phase", "")
                                _cdv = _r.get("cdv_trend", "")

                        _upcoming.append({
                            "ticker": _tk,
                            "name": _name,
                            "earnings_date": _info["earnings_date"],
                            "days": _days,
                            "eps_est": _info.get("earnings_eps_est"),
                            "ex_div": _info.get("ex_dividend_date"),
                            "flow": _flow,
                            "phase": _phase,
                            "cdv": _cdv,
                        })
                except Exception:
                    pass

    _upcoming.sort(key=lambda x: x["days"])

    if not _upcoming:
        st.info("لا توجد إعلانات نتائج قادمة في الأسهم المسحوبة")
    else:
        # Summary cards
        _imminent = [u for u in _upcoming if 0 <= u["days"] <= 7]
        _near = [u for u in _upcoming if 7 < u["days"] <= 30]
        _later = [u for u in _upcoming if u["days"] > 30]
        _past = [u for u in _upcoming if u["days"] < 0]

        _sc1, _sc2, _sc3, _sc4 = st.columns(4)
        _sc1.metric("🔴 خلال أسبوع", len(_imminent))
        _sc2.metric("🟡 خلال شهر", len(_near))
        _sc3.metric("📅 بعد شهر+", len(_later))
        _sc4.metric("✅ أعلنت مؤخراً", len(_past))

        # Alert for imminent
        for _u in _imminent:
            _accum_badge = ""
            if _u["flow"] > 15 and _u["cdv"] == "rising":
                _accum_badge = " | 📈 **تجميع مؤسسي قبل النتائج!**"
            st.error(
                f"🔴 **{_u['name']}** ({_u['ticker']}) — النتائج خلال **{_u['days']} يوم** "
                f"({_u['earnings_date']}){_accum_badge}"
            )

        # Table
        st.markdown("### 📋 جميع الإعلانات القادمة")
        _cal_rows = []
        for _u in _upcoming:
            if _u["days"] < 0:
                _urgency = "✅ أعلنت"
            elif _u["days"] <= 3:
                _urgency = "🔴 وشيك!"
            elif _u["days"] <= 7:
                _urgency = "🟡 قريب"
            elif _u["days"] <= 30:
                _urgency = "📅 خلال شهر"
            else:
                _urgency = "⏳ بعيد"

            _accum_status = ""
            if _u["flow"] > 20 and _u["cdv"] == "rising" and _u["phase"] in ("accumulation", "spring"):
                _accum_status = "📈 تجميع قوي"
            elif _u["flow"] > 10 and _u["cdv"] == "rising":
                _accum_status = "📊 تجميع خفيف"
            elif _u["flow"] < -10:
                _accum_status = "📉 تصريف"
            else:
                _accum_status = "➡️ محايد"

            _cal_rows.append({
                "السهم": _u["name"],
                "الرمز": _u["ticker"],
                "تاريخ النتائج": _u["earnings_date"],
                "باقي": f"{_u['days']} يوم" if _u["days"] >= 0 else f"قبل {abs(_u['days'])} يوم",
                "الحالة": _urgency,
                "EPS المتوقع": f"{_u['eps_est']:.2f}" if _u["eps_est"] else "—",
                "التدفق": _accum_status,
                "توزيعات": _u.get("ex_div", "—") or "—",
            })

        if _cal_rows:
            st.dataframe(pd.DataFrame(_cal_rows), use_container_width=True, hide_index=True)

        # Historical earnings performance
        st.markdown("---")
        st.markdown("### 📊 إحصائية ما بعد النتائج")
        st.caption("كيف يتحرك السهم تاريخياً بعد إعلان النتائج")

        _sel_stock = st.selectbox(
            "اختر سهم:",
            [f"{u['name']} ({u['ticker']})" for u in _upcoming],
            key="_earn_sel"
        )

        if _sel_stock:
            _sel_tk = _sel_stock.split("(")[-1].replace(")", "").strip()

            with st.spinner(f"📊 جاري تحليل {_sel_stock}..."):
                _hist = get_earnings_history(_sel_tk, max_events=12)

            if _hist:
                _stats = compute_earnings_stats(_hist)

                # Stats cards
                _e1, _e2, _e3, _e4 = st.columns(4)
                _wr_c = "#00E676" if _stats["win_rate_5d"] >= 50 else "#FF5252"
                _e1.markdown(f'''
                <div style="background:#131a2e;border:1px solid #192035;border-radius:10px;padding:12px;text-align:center">
                    <div style="color:#6b7280;font-size:0.75em">نسبة الارتفاع بعد 5d</div>
                    <div style="color:{_wr_c};font-size:1.6em;font-weight:800">{_stats["win_rate_5d"]:.0f}%</div>
                    <div style="color:#4b5563;font-size:0.7em">{_stats["rose_5d"]}/{_stats["total"]}</div>
                </div>''', unsafe_allow_html=True)
                _avg_c = "#00E676" if _stats["avg_post_5d"] > 0 else "#FF5252"
                _e2.markdown(f'''
                <div style="background:#131a2e;border:1px solid #192035;border-radius:10px;padding:12px;text-align:center">
                    <div style="color:#6b7280;font-size:0.75em">متوسط العائد بعد 5d</div>
                    <div style="color:{_avg_c};font-size:1.6em;font-weight:800">{_stats["avg_post_5d"]:+.2f}%</div>
                </div>''', unsafe_allow_html=True)
                _e3.markdown(f'''
                <div style="background:#131a2e;border:1px solid #192035;border-radius:10px;padding:12px;text-align:center">
                    <div style="color:#6b7280;font-size:0.75em">أفضل / أسوأ</div>
                    <div style="font-size:1em"><span style="color:#00E676">{_stats["best_post_5d"]:+.1f}%</span> / <span style="color:#FF5252">{_stats["worst_post_5d"]:+.1f}%</span></div>
                </div>''', unsafe_allow_html=True)
                _e4.markdown(f'''
                <div style="background:#131a2e;border:1px solid #192035;border-radius:10px;padding:12px;text-align:center">
                    <div style="color:#6b7280;font-size:0.75em">متوسط الحجم</div>
                    <div style="color:#AB47BC;font-size:1.6em;font-weight:800">{_stats["avg_volume_ratio"]:.1f}x</div>
                </div>''', unsafe_allow_html=True)

                # Pre-accumulation insight
                if _stats["pre_accum_count"] > 0 and _stats["no_accum_count"] > 0:
                    _diff = _stats["pre_accum_win_rate"] - _stats["no_accum_win_rate"]
                    if _diff > 10:
                        st.success(
                            f"📈 **التجميع قبل النتائج يرفع النجاح!** "
                            f"مع تجميع: **{_stats['pre_accum_win_rate']:.0f}%** ({_stats['pre_accum_count']} مرة) | "
                            f"بدون: **{_stats['no_accum_win_rate']:.0f}%** ({_stats['no_accum_count']} مرة)"
                        )
                    elif _diff < -10:
                        st.warning(
                            f"⚠️ **التجميع قبل النتائج ما يساعد هالسهم!** "
                            f"مع تجميع: **{_stats['pre_accum_win_rate']:.0f}%** | "
                            f"بدون: **{_stats['no_accum_win_rate']:.0f}%**"
                        )

                # History table
                st.markdown("#### 📅 سجل النتائج السابقة")
                _h_rows = []
                for _h in _hist:
                    _icon = "🟢" if _h["return_post_5d"] > 0 else "🔴"
                    _h_rows.append({
                        "التاريخ": _h["date"],
                        "قبل 5d": f"{_h['return_pre_5d']:+.1f}%",
                        "الفجوة": f"{_h['gap_pct']:+.1f}%",
                        "بعد 1d": f"{_h['return_post_1d']:+.1f}%",
                        "بعد 5d": f"{_icon} {_h['return_post_5d']:+.1f}%",
                        "بعد 10d": f"{_h['return_post_10d']:+.1f}%",
                        "الحجم": f"{_h['volume_ratio']}x",
                        "تجميع قبل": "📈" if _h["pre_accum"] else "📉",
                    })
                st.dataframe(pd.DataFrame(_h_rows), use_container_width=True, hide_index=True)

                # Chart
                _h_dates = [h["date"] for h in _hist]
                _h_post5 = [h["return_post_5d"] for h in _hist]
                _h_pre5 = [h["return_pre_5d"] for h in _hist]

                import plotly.graph_objects as go
                _earn_fig = go.Figure()
                _earn_fig.add_trace(go.Bar(
                    x=_h_dates, y=_h_post5, name="بعد النتائج (5d)",
                    marker_color=["#00E676" if v > 0 else "#FF5252" for v in _h_post5],
                ))
                _earn_fig.add_trace(go.Scatter(
                    x=_h_dates, y=_h_pre5, name="قبل النتائج (5d)",
                    mode="lines+markers", line=dict(color="#FFD700", width=2),
                ))
                _earn_fig.add_hline(y=0, line_dash="dash", line_color="#374151")
                _earn_fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    height=350, margin=dict(l=40, r=20, t=30, b=30),
                    legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
                    yaxis=dict(title="العائد %", ticksuffix="%"),
                    barmode="group",
                )
                st.plotly_chart(_earn_fig, use_container_width=True, config={"displayModeBar": False})

            else:
                st.info("لا توجد بيانات نتائج سابقة كافية لهذا السهم")


# PAGE: AI Reports — تقارير AI
# ══════════════════════════════════════════════════════════════

elif page == "🤖 تقارير AI":
    from core.ai_reports import (
        is_ai_available, generate_market_report, generate_sector_report,
        generate_stock_report, generate_composite_report, generate_opportunities_report,
    )

    st.markdown('''
    <div style="text-align:center;padding:20px 0 10px 0">
        <span style="font-size:1.8em;font-weight:800;color:#fff">🤖 تقارير AI</span>
        <div style="color:#6b7280;font-size:0.92em;margin-top:6px">
            تحليل ذكي شامل بالذكاء الاصطناعي — مدعوم بـ Claude Sonnet
        </div>
    </div>
    ''', unsafe_allow_html=True)

    if not is_ai_available():
        st.error("❌ مفتاح API غير موجود. أضف `ANTHROPIC_API_KEY` في Settings → Secrets")
    else:
        results = st.session_state.get("scan_results")
        if results is None:
            st.info("🔍 أمسح السوق أولاً من Order Flow ثم ارجع هنا")
        else:
            # Get market key
            _market_sel = st.session_state.get("market_select", "🇸🇦 السوق السعودي (TASI)")
            _mkt_info = MARKETS.get(_market_sel, list(MARKETS.values())[0])
            market_key = _mkt_info["key"]

            # Prepare composite data
            _ai_comp_dates, _ai_comp_vals, _, _ = build_composite_index(results)
            _ai_comp_data = None
            if _ai_comp_vals:
                _ai_comp_data = {
                    "value": round(_ai_comp_vals[-1], 2),
                    "prev": round(_ai_comp_vals[-2], 2) if len(_ai_comp_vals) >= 2 else None,
                    "change_pct": round((_ai_comp_vals[-1] - _ai_comp_vals[-2]) / _ai_comp_vals[-2] * 100, 2) if len(_ai_comp_vals) >= 2 else 0,
                    "high_20d": round(max(_ai_comp_vals[-20:]), 2) if len(_ai_comp_vals) >= 20 else round(max(_ai_comp_vals), 2),
                    "low_20d": round(min(_ai_comp_vals[-20:]), 2) if len(_ai_comp_vals) >= 20 else round(min(_ai_comp_vals), 2),
                    "total_bars": len(_ai_comp_vals),
                }

            # PFI data
            try:
                _ai_pfi, _ai_acc, _ai_dist, _, _ai_interp = build_platform_flow_index(results)
                _ai_pfi_data = {
                    "pfi": _ai_pfi,
                    "accumulation_pct": _ai_acc,
                    "distribution_pct": _ai_dist,
                    "interpretation": _ai_interp,
                }
            except Exception:
                _ai_pfi_data = None

            # Report type tabs
            _ai_tabs = st.tabs([
                "📋 تقرير السوق اليومي",
                "🏢 تقرير قطاع",
                "📈 تحليل سهم",
                "📊 تقرير المؤشر المركب",
                "💎 اكتشاف الفرص والمخاطر",
            ])

            # ── Tab 1: Daily Market Report ──
            with _ai_tabs[0]:
                st.markdown("### 📋 تقرير السوق اليومي الشامل")
                st.caption(f"يحلل {len(results)} سهم — القرارات، القطاعات، التدفقات، الفرص والمخاطر")
                if st.button("🚀 أنشئ التقرير", key="ai_market_btn", type="primary", use_container_width=True):
                    with st.spinner("🤖 Claude يحلل السوق..."):
                        report = generate_market_report(results, _ai_comp_data, _ai_pfi_data)
                    st.markdown("---")
                    st.markdown(report)

            # ── Tab 2: Sector Report ──
            with _ai_tabs[1]:
                st.markdown("### 🏢 تقرير قطاع مفصّل")
                # Get unique sectors
                _ai_sectors = sorted(set(r.get("sector", "") for r in results if r.get("sector")))
                _ai_sector_sel = st.selectbox("اختر القطاع:", _ai_sectors, key="ai_sector_sel")
                if _ai_sector_sel:
                    _sect_stocks = [r for r in results if r.get("sector") == _ai_sector_sel]
                    st.caption(f"القطاع فيه {len(_sect_stocks)} سهم")
                    if st.button("🚀 حلل القطاع", key="ai_sector_btn", type="primary", use_container_width=True):
                        with st.spinner(f"🤖 Claude يحلل {_ai_sector_sel}..."):
                            report = generate_sector_report(results, _ai_sector_sel)
                        st.markdown("---")
                        st.markdown(report)

            # ── Tab 3: Stock Report ──
            with _ai_tabs[2]:
                st.markdown("### 📈 تحليل سهم بالذكاء الاصطناعي")
                # Stock selector
                _ai_stock_options = {f"{r.get('name', r['ticker'])} ({r['ticker']})": r for r in results}
                _ai_stock_sel = st.selectbox("اختر السهم:", list(_ai_stock_options.keys()), key="ai_stock_sel")
                if _ai_stock_sel:
                    _sel_r = _ai_stock_options[_ai_stock_sel]
                    _dec_color = "#00E676" if _sel_r.get("decision") == "enter" else "#FF5252" if _sel_r.get("decision") == "avoid" else "#FFD700"
                    st.markdown(f"""
                    <div style="display:flex;gap:20px;align-items:center;margin:10px 0">
                        <span style="font-size:1.3em;font-weight:700">{_sel_r.get('last_close', 0):.2f}</span>
                        <span style="color:{'#00E676' if _sel_r.get('change_pct', 0) >= 0 else '#FF5252'};font-weight:600">
                            {_sel_r.get('change_pct', 0):+.1f}%
                        </span>
                        <span style="background:{_dec_color};color:#000;padding:4px 12px;border-radius:20px;font-weight:700;font-size:0.85em">
                            {_sel_r.get('decision_info', {}).get('label', _sel_r.get('decision', ''))}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("🚀 حلل السهم", key="ai_stock_btn", type="primary", use_container_width=True):
                        # Gather sector + seasonality context
                        _stock_sector = _sel_r.get("sector", "")
                        _stock_sector_info = None
                        _stock_season_info = None
                        # Find sector health from results
                        if _stock_sector and results:
                            _sec_stocks = [r for r in results if r.get("sector") == _stock_sector]
                            if _sec_stocks:
                                _n_acc = sum(1 for r in _sec_stocks if r.get("phase") in ("accumulation", "spring", "markup"))
                                _n_dist = sum(1 for r in _sec_stocks if r.get("phase") in ("distribution", "markdown", "upthrust"))
                                _avg_flow = sum(r.get("flow_bias", 0) for r in _sec_stocks) / len(_sec_stocks)
                                _stock_sector_info = {
                                    "name": _stock_sector, "n": len(_sec_stocks),
                                    "n_accum": _n_acc, "n_dist": _n_dist,
                                    "health": round(_avg_flow, 1),
                                }
                        # Seasonality for sector
                        try:
                            from core.seasonality import build_seasonality_for_sectors, compute_monthly_returns, compute_seasonality_stats
                            _sec_results = [r for r in results if r.get("sector") == _stock_sector]
                            if _sec_results and len(_sec_results) >= 3:
                                _sec_dates_all = []
                                _sec_vals_all = []
                                for r in _sec_results:
                                    cd = r.get("chart_dates", [])
                                    cc = r.get("chart_close", [])
                                    if len(cd) >= 20:
                                        _sec_dates_all = cd  # use first stock's dates as proxy
                                        break
                                if _sec_dates_all:
                                    _sec_comps = {_stock_sector: {"dates": _sec_dates_all, "vals": [100] * len(_sec_dates_all)}}
                                    _seas = build_seasonality_for_sectors(_sec_comps)
                                    if _stock_sector in _seas:
                                        _stock_season_info = _seas[_stock_sector]
                        except Exception:
                            pass

                        with st.spinner(f"🤖 Claude يحلل {_sel_r.get('name', '')}..."):
                            report = generate_stock_report(_sel_r, _stock_sector_info, _stock_season_info)
                        st.markdown("---")
                        st.markdown(report)

            # ── Tab 4: Composite Index Report ──
            with _ai_tabs[3]:
                st.markdown("### 📊 تقرير المؤشر المركب")
                if _ai_comp_data:
                    _cv = _ai_comp_data["value"]
                    _cc = _ai_comp_data.get("change_pct", 0)
                    st.markdown(f"""
                    <div style="text-align:center;margin:15px 0">
                        <span style="font-size:2.5em;font-weight:800;color:#4FC3F7">{_cv:.2f}</span>
                        <span style="color:{'#00E676' if _cc >= 0 else '#FF5252'};font-size:1.2em;margin-right:10px">{_cc:+.2f}%</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("🚀 حلل المؤشر", key="ai_comp_btn", type="primary", use_container_width=True):
                        with st.spinner("🤖 Claude يحلل المؤشر المركب..."):
                            report = generate_composite_report(_ai_comp_data, _ai_pfi_data)
                        st.markdown("---")
                        st.markdown(report)
                else:
                    st.warning("لا توجد بيانات كافية للمؤشر المركب")

            # ── Tab 5: Opportunities & Risks ──
            with _ai_tabs[4]:
                st.markdown("### 💎 اكتشاف الفرص المخفية والمخاطر الخفية")
                st.caption("يبحث عن تجميع خفي، صعود كاذب، سبرنق، تناقضات — أشياء ما تشوفها بعينك")
                if st.button("🚀 ابحث عن الفرص", key="ai_opp_btn", type="primary", use_container_width=True):
                    with st.spinner("🤖 Claude يبحث عن الفرص المخفية..."):
                        report = generate_opportunities_report(results)
                    st.markdown("---")
                    st.markdown(report)


# ══════════════════════════════════════════════════════════════
# PAGE: Performance
# ══════════════════════════════════════════════════════════════

elif page == "📊 أداء النظام":

    st.title("📊 أداء النظام — الحقيقة الكاملة")
    st.caption("كل رقم هنا من بيانات حقيقية — إشارات سابقة ونتائجها الفعلية")

    tracking = get_tracking_status()
    pending = tracking["pending_5d"] + tracking["pending_10d"] + tracking["pending_20d"]

    if pending > 0:
        with st.spinner(f"📡 تحديث نتائج {pending} إشارة..."):
            result = update_signal_outcomes()
        if result["updated"] > 0:
            st.success(f"تم تحديث {result['updated']} إشارة")
            # ── Mature signal alerts ──
            try:
                import sqlite3 as _sq3
                with _sq3.connect("masa_v2.db") as _alert_conn:
                    _alert_conn.row_factory = _sq3.Row
                    _today_str = datetime.now().strftime("%Y-%m-%d")
                    _recent_matured = _alert_conn.execute("""
                        SELECT company, ticker, sector, entry_price, outcome_5d, return_5d, price_5d,
                               outcome_10d, return_10d, price_10d, last_updated
                        FROM signals
                        WHERE decision='enter' AND last_updated LIKE ?
                        ORDER BY return_5d DESC
                    """, (f"{_today_str}%",)).fetchall()

                    if _recent_matured:
                        _matured_wins = [dict(r) for r in _recent_matured if r["outcome_5d"] == "win" and r["return_5d"] is not None]
                        _matured_losses = [dict(r) for r in _recent_matured if r["outcome_5d"] == "loss" and r["return_5d"] is not None]

                        if _matured_wins or _matured_losses:
                            st.markdown("### 🔔 إشارات نضجت اليوم")
                            _alert_cols = st.columns(2)
                            with _alert_cols[0]:
                                if _matured_wins:
                                    for _mw in _matured_wins[:5]:
                                        st.success(
                                            f"🟢 **{_mw['company']}** ({_mw['ticker']}) "
                                            f"**{_mw['return_5d']:+.1f}%** — "
                                            f"{_mw['entry_price']:.2f} → {_mw['price_5d']:.2f}"
                                        )
                                else:
                                    st.info("لا توجد إشارات ناجحة اليوم")
                            with _alert_cols[1]:
                                if _matured_losses:
                                    for _ml in _matured_losses[:5]:
                                        st.error(
                                            f"🔴 **{_ml['company']}** ({_ml['ticker']}) "
                                            f"**{_ml['return_5d']:+.1f}%** — "
                                            f"{_ml['entry_price']:.2f} → {_ml['price_5d']:.2f}"
                                        )
                                else:
                                    st.info("لا توجد إشارات فاشلة اليوم")
                            st.divider()
            except Exception:
                pass

            with st.expander("تفاصيل التحديث"):
                for detail in result["details"]:
                    st.markdown(detail)

    perf = get_total_performance()
    win_rates = get_win_rates()

    if perf["total"] == 0:
        st.markdown('''
        <div style="text-align:center;padding:60px 20px;color:#4b5563">
            <div style="font-size:3em;margin-bottom:16px;opacity:0.4">📊</div>
            <div style="font-size:1.1em;color:#6b7280;margin-bottom:12px">
                لا توجد بيانات أداء بعد</div>
            <div style="font-size:0.85em;color:#374151;max-width:500px;margin:0 auto;
                        line-height:1.8;direction:rtl">
                <b>كيف يشتغل:</b><br>
                ١. كل ما تسوي مسح → النظام يسجل إشارات "ادخل"<br>
                ٢. بعد 5/10/20 يوم → يتحقق من السعر الحالي<br>
                ٣. يحسب: هل الإشارة نجحت ولا فشلت<br>
                ٤. يعرض لك النسب الحقيقية هنا
            </div>
        </div>
        ''', unsafe_allow_html=True)
        st.stop()

    # ── Direct DB query for richest data ──
    import sqlite3
    _db_path = "masa_v2.db"
    _db_data = {"rows": [], "has_5d": False, "has_10d": False, "has_20d": False}
    try:
        with sqlite3.connect(_db_path) as _conn:
            _conn.row_factory = sqlite3.Row
            _db_rows = _conn.execute("""
                SELECT * FROM signals WHERE decision='enter' ORDER BY date_logged DESC
            """).fetchall()
            _db_data["rows"] = [dict(r) for r in _db_rows]
            _db_data["has_5d"] = any(r["outcome_5d"] is not None for r in _db_data["rows"])
            _db_data["has_10d"] = any(r["outcome_10d"] is not None for r in _db_data["rows"])
            _db_data["has_20d"] = any(r["outcome_20d"] is not None for r in _db_data["rows"])
    except Exception:
        pass

    _all_signals = _db_data["rows"]
    _n_signals = len(_all_signals)

    # Determine best available period
    if _db_data["has_20d"]:
        _period = "20d"
        _period_label = "20 يوم"
    elif _db_data["has_10d"]:
        _period = "10d"
        _period_label = "10 أيام"
    elif _db_data["has_5d"]:
        _period = "5d"
        _period_label = "5 أيام"
    else:
        _period = None
        _period_label = ""

    if _period:
        _outcome_col = f"outcome_{_period}"
        _return_col = f"return_{_period}"
        _price_col = f"price_{_period}"
        _completed = [s for s in _all_signals if s.get(_outcome_col) is not None]
        _wins = [s for s in _completed if s[_outcome_col] == "win"]
        _losses = [s for s in _completed if s[_outcome_col] == "loss"]
        _n_completed = len(_completed)
        _n_wins = len(_wins)
        _win_rate = (_n_wins / _n_completed * 100) if _n_completed > 0 else 0
        _avg_return = sum(s.get(_return_col, 0) or 0 for s in _completed) / _n_completed if _n_completed > 0 else 0
        _total_gains = sum(s.get(_return_col, 0) or 0 for s in _wins)
        _total_losses = abs(sum(s.get(_return_col, 0) or 0 for s in _losses))
        _profit_factor = round(_total_gains / _total_losses, 2) if _total_losses > 0.01 else 0
    else:
        _completed = []
        _n_completed = 0
        _win_rate = 0
        _avg_return = 0
        _profit_factor = 0

    # ── Top metrics ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("إجمالي الإشارات", _n_signals)

    if _period and _n_completed > 0:
        _wr_color = "normal" if _win_rate >= 55 else "inverse" if _win_rate < 45 else "off"
        _avg_c = "normal" if _avg_return > 0 else "inverse"
        c2.metric(f"نسبة النجاح ({_period_label})", f"{_win_rate:.1f}%", delta_color=_wr_color)
        c3.metric(f"متوسط العائد ({_period_label})", f"{_avg_return:+.2f}%", delta_color=_avg_c)
        _pf_color = "normal" if _profit_factor >= 1.5 else "inverse" if _profit_factor < 1.0 else "off"
        c4.metric("Profit Factor", f"{_profit_factor:.2f}", delta_color=_pf_color)

        # ── Profit Factor breakdown ──
        _avg_win_ret = sum(s.get(_return_col, 0) or 0 for s in _wins) / len(_wins) if _wins else 0
        _avg_loss_ret = sum(s.get(_return_col, 0) or 0 for s in _losses) / len(_losses) if _losses else 0
        _best_trade = max(_completed, key=lambda x: x.get(_return_col, 0) or 0)
        _worst_trade = min(_completed, key=lambda x: x.get(_return_col, 0) or 0)

        _pf_verdict = "🟢 مربحة" if _profit_factor >= 1.5 else "🟡 على الحد" if _profit_factor >= 1.0 else "🔴 خاسرة"

        st.markdown(f'''
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:10px 0;direction:rtl">
            <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:10px;text-align:center">
                <div style="color:#6b7280;font-size:0.72em">🟢 متوسط الربح</div>
                <div style="color:#00E676;font-weight:700;font-size:1.2em">{_avg_win_ret:+.2f}%</div>
                <div style="color:#4b5563;font-size:0.7em">{len(_wins)} صفقة</div>
            </div>
            <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:10px;text-align:center">
                <div style="color:#6b7280;font-size:0.72em">🔴 متوسط الخسارة</div>
                <div style="color:#FF5252;font-weight:700;font-size:1.2em">{_avg_loss_ret:+.2f}%</div>
                <div style="color:#4b5563;font-size:0.7em">{len(_losses)} صفقة</div>
            </div>
            <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:10px;text-align:center">
                <div style="color:#6b7280;font-size:0.72em">📊 Profit Factor</div>
                <div style="color:{"#00E676" if _profit_factor >= 1.5 else "#FF5252" if _profit_factor < 1.0 else "#FFD700"};font-weight:700;font-size:1.2em">{_profit_factor:.2f}</div>
                <div style="color:#4b5563;font-size:0.7em">{_pf_verdict}</div>
            </div>
            <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:10px;text-align:center">
                <div style="color:#6b7280;font-size:0.72em">🏆 أفضل صفقة</div>
                <div style="color:#00E676;font-weight:700;font-size:1em">{(_best_trade.get(_return_col, 0) or 0):+.1f}%</div>
                <div style="color:#4b5563;font-size:0.7em">{_best_trade.get("company", "")[:12]}</div>
            </div>
            <div style="background:rgba(14,20,36,0.6);border:1px solid #192035;border-radius:10px;padding:10px;text-align:center">
                <div style="color:#6b7280;font-size:0.72em">💀 أسوأ صفقة</div>
                <div style="color:#FF5252;font-weight:700;font-size:1em">{(_worst_trade.get(_return_col, 0) or 0):+.1f}%</div>
                <div style="color:#4b5563;font-size:0.7em">{_worst_trade.get("company", "")[:12]}</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    else:
        c2.metric("نسبة النجاح", "⏳ انتظار")
        c3.metric("متوسط العائد", "⏳ انتظار")
        c4.metric("Profit Factor", "⏳")

    # ── Progress bars for 5d/10d/20d ──
    st.divider()
    st.subheader("📡 شريط التقدم")
    for _p, _pl in [("5d", "5 أيام"), ("10d", "10 أيام"), ("20d", "20 يوم")]:
        _oc = f"outcome_{_p}"
        _done = sum(1 for s in _all_signals if s.get(_oc) is not None)
        _pct = _done / _n_signals if _n_signals > 0 else 0
        _wins_p = sum(1 for s in _all_signals if s.get(_oc) == "win")
        _wr_p = (_wins_p / _done * 100) if _done > 0 else 0
        _avg_p = sum(s.get(f"return_{_p}", 0) or 0 for s in _all_signals if s.get(_oc) is not None) / _done if _done > 0 else 0

        _status = f"✅ {_done}/{_n_signals}" if _done > 0 else f"⏳ 0/{_n_signals}"
        _wr_txt = f" | نجاح {_wr_p:.1f}% | عائد {_avg_p:+.2f}%" if _done > 0 else ""
        st.markdown(f"**{_pl}:** {_status}{_wr_txt}")
        st.progress(min(_pct, 1.0))

    # ── Best/Worst 5 trades ──
    if _period and _n_completed > 0:
        st.divider()
        _bc1, _bc2 = st.columns(2)

        with _bc1:
            st.subheader("🟢 أفضل 5 صفقات")
            _sorted_best = sorted(_completed, key=lambda x: x.get(_return_col, 0) or 0, reverse=True)[:5]
            for _s in _sorted_best:
                _ret = _s.get(_return_col, 0) or 0
                _name = _s.get("company", _s.get("ticker", ""))
                _entry = _s.get("entry_price", 0)
                _exit = _s.get(_price_col, 0) or 0
                _sector = _s.get("sector", "")
                st.markdown(
                    f'<div style="background:#0a1a0a;border:1px solid #1b5e20;border-radius:8px;padding:8px 12px;margin:4px 0;direction:rtl">'
                    f'<b style="color:#00E676">{_name}</b> '
                    f'<span style="color:#4b5563;font-size:0.8em">({_sector})</span><br>'
                    f'<span style="color:#9ca3af">{_entry:.2f} → {_exit:.2f}</span> '
                    f'<b style="color:#00E676;font-size:1.1em">{_ret:+.2f}%</b></div>',
                    unsafe_allow_html=True
                )

        with _bc2:
            st.subheader("🔴 أسوأ 5 صفقات")
            _sorted_worst = sorted(_completed, key=lambda x: x.get(_return_col, 0) or 0)[:5]
            for _s in _sorted_worst:
                _ret = _s.get(_return_col, 0) or 0
                _name = _s.get("company", _s.get("ticker", ""))
                _entry = _s.get("entry_price", 0)
                _exit = _s.get(_price_col, 0) or 0
                _sector = _s.get("sector", "")
                st.markdown(
                    f'<div style="background:#1a0a0a;border:1px solid #b71c1c;border-radius:8px;padding:8px 12px;margin:4px 0;direction:rtl">'
                    f'<b style="color:#FF5252">{_name}</b> '
                    f'<span style="color:#4b5563;font-size:0.8em">({_sector})</span><br>'
                    f'<span style="color:#9ca3af">{_entry:.2f} → {_exit:.2f}</span> '
                    f'<b style="color:#FF5252;font-size:1.1em">{_ret:+.2f}%</b></div>',
                    unsafe_allow_html=True
                )

    # ── Sector breakdown — split by market ──
    if _period and _n_completed > 0:
        st.divider()
        st.subheader("🏭 الأداء حسب القطاع")

        # Split signals by market
        _sa_signals = [s for s in _completed if ".SR" in s.get("ticker", "")]
        _us_signals = [s for s in _completed if ".SR" not in s.get("ticker", "")]

        def _build_sector_table(signals, market_label):
            if not signals:
                return
            _sector_perf = {}
            for _s in signals:
                _sec = _s.get("sector", "غير مصنف")
                if _sec not in _sector_perf:
                    _sector_perf[_sec] = {"total": 0, "wins": 0, "returns": []}
                _sector_perf[_sec]["total"] += 1
                if _s.get(_outcome_col) == "win":
                    _sector_perf[_sec]["wins"] += 1
                _sector_perf[_sec]["returns"].append(_s.get(_return_col, 0) or 0)

            _sec_rows = []
            for _sec, _sd in sorted(_sector_perf.items(), key=lambda x: sum(x[1]["returns"]) / len(x[1]["returns"]) if x[1]["returns"] else 0, reverse=True):
                _wr = _sd["wins"] / _sd["total"] * 100 if _sd["total"] > 0 else 0
                _avg = sum(_sd["returns"]) / len(_sd["returns"]) if _sd["returns"] else 0
                _sec_rows.append({
                    "القطاع": _sec,
                    "إشارات": _sd["total"],
                    "نجاح": f"{_wr:.0f}%",
                    "عائد": f"{_avg:+.2f}%",
                    "حكم": "🟢" if _wr >= 55 else "🔴" if _wr < 40 else "🟡",
                })
            if _sec_rows:
                # Market summary
                _total = len(signals)
                _wins = sum(1 for s in signals if s.get(_outcome_col) == "win")
                _wr_all = _wins / _total * 100 if _total > 0 else 0
                _avg_all = sum(s.get(_return_col, 0) or 0 for s in signals) / _total if _total > 0 else 0
                st.markdown(
                    f"**{market_label}** — {_total} إشارة | "
                    f"نجاح **{_wr_all:.0f}%** | "
                    f"عائد **{_avg_all:+.2f}%**"
                )
                st.dataframe(pd.DataFrame(_sec_rows), use_container_width=True, hide_index=True)

        if _sa_signals and _us_signals:
            _mkt_tab1, _mkt_tab2 = st.tabs(["🇸🇦 السوق السعودي", "🇺🇸 السوق الأمريكي"])
            with _mkt_tab1:
                _build_sector_table(_sa_signals, "🇸🇦 السوق السعودي")
            with _mkt_tab2:
                _build_sector_table(_us_signals, "🇺🇸 السوق الأمريكي")
        elif _sa_signals:
            _build_sector_table(_sa_signals, "🇸🇦 السوق السعودي")
        elif _us_signals:
            _build_sector_table(_us_signals, "🇺🇸 السوق الأمريكي")

    # ── Equity Curve ──
    if _period and _n_completed > 5:
        st.divider()
        st.subheader("📈 منحنى رأس المال (Equity Curve)")
        _sorted_by_date = sorted(_completed, key=lambda x: x.get("date_logged", ""))
        _equity = [100000]  # Start with 100K
        _dates_eq = ["البداية"]
        _position_size = 0.1  # 10% per trade
        for _s in _sorted_by_date:
            _ret = (_s.get(_return_col, 0) or 0) / 100
            _pnl = _equity[-1] * _position_size * _ret
            _equity.append(round(_equity[-1] + _pnl, 2))
            _name = _s.get("company", _s.get("ticker", ""))[:15]
            _dates_eq.append(_s.get("date_logged", "")[:10])

        _eq_fig = go.Figure()
        _eq_fig.add_trace(go.Scatter(
            x=list(range(len(_equity))), y=_equity,
            mode="lines", line=dict(color="#4FC3F7" if _equity[-1] >= 100000 else "#FF5252", width=2.5),
            fill="tozeroy", fillcolor="rgba(79,195,247,0.1)" if _equity[-1] >= 100000 else "rgba(255,82,82,0.1)",
            hovertemplate="الصفقة %{x}: %{y:,.0f} ريال<extra></extra>",
        ))
        _eq_fig.add_hline(y=100000, line_dash="dash", line_color="#374151", line_width=1,
                          annotation_text="رأس المال الأولي 100,000", annotation_position="bottom left",
                          annotation_font_size=10, annotation_font_color="#4b5563")
        _eq_fig.update_layout(
            height=350, margin=dict(l=0, r=0, t=10, b=30),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(20,24,36,0.8)",
            yaxis=dict(title="ريال", gridcolor="#151d30", tickformat=","),
            xaxis=dict(title=f"عدد الصفقات ({_n_completed})", gridcolor="#151d30"),
            font=dict(family="Tajawal"),
        )
        st.plotly_chart(_eq_fig, use_container_width=True, config={"displayModeBar": False})

        _final_eq = _equity[-1]
        _total_pnl = _final_eq - 100000
        _pnl_pct = _total_pnl / 100000 * 100
        _pnl_color = "#00E676" if _total_pnl >= 0 else "#FF5252"
        st.markdown(
            f'<div style="text-align:center;color:{_pnl_color};font-size:1.2em;font-weight:700">'
            f'{"📈" if _total_pnl >= 0 else "📉"} '
            f'لو دخلت كل إشارة بـ 10% من رأس المال: '
            f'{_total_pnl:+,.0f} ريال ({_pnl_pct:+.2f}%)</div>',
            unsafe_allow_html=True
        )

    # ── Signal Quality Breakdown ──
    if _period and _n_completed > 5:
        st.divider()
        st.subheader("🎯 جودة الإشارات vs نسبة النجاح")
        st.caption("هل الإشارات القوية فعلاً تنجح أكثر؟")

        _quality_tiers = {"🟢 قوية (70+)": [], "🟡 متوسطة (40-69)": [], "🔴 ضعيفة (0-39)": []}
        for _s in _completed:
            _qs = _s.get("quality_score", 0) or 0
            _ret = _s.get(_return_col, 0) or 0
            _outcome = _s.get(_outcome_col, "")
            _entry = {"name": _s.get("company", ""), "return": _ret, "outcome": _outcome, "score": _qs}
            if _qs >= 70:
                _quality_tiers["🟢 قوية (70+)"].append(_entry)
            elif _qs >= 40:
                _quality_tiers["🟡 متوسطة (40-69)"].append(_entry)
            else:
                _quality_tiers["🔴 ضعيفة (0-39)"].append(_entry)

        _qt_rows = []
        for _tier_name, _tier_data in _quality_tiers.items():
            if not _tier_data:
                _qt_rows.append({"الفئة": _tier_name, "عدد": 0, "نجاح": "—", "عائد": "—", "التوصية": "—"})
                continue
            _t_total = len(_tier_data)
            _t_wins = sum(1 for t in _tier_data if t["outcome"] == "win")
            _t_wr = _t_wins / _t_total * 100
            _t_avg = sum(t["return"] for t in _tier_data) / _t_total
            _rec = "✅ ابقِها" if _t_wr >= 50 else "⚠️ شدد" if _t_wr >= 35 else "❌ أوقفها"
            _qt_rows.append({
                "الفئة": _tier_name,
                "عدد": _t_total,
                "نجاح": f"{_t_wr:.0f}%",
                "عائد": f"{_t_avg:+.2f}%",
                "التوصية": _rec,
            })

        st.dataframe(pd.DataFrame(_qt_rows), use_container_width=True, hide_index=True)

        # Insight
        _strong = _quality_tiers["🟢 قوية (70+)"]
        _weak = _quality_tiers["🔴 ضعيفة (0-39)"]
        if _strong and _weak:
            _s_wr = sum(1 for t in _strong if t["outcome"] == "win") / len(_strong) * 100
            _w_wr = sum(1 for t in _weak if t["outcome"] == "win") / len(_weak) * 100
            _diff = _s_wr - _w_wr
            if _diff > 15:
                st.success(f"💡 الإشارات القوية تنجح **{_diff:.0f}%** أكثر من الضعيفة — الفلتر يشتغل!")
            elif _diff > 0:
                st.info(f"💡 فرق بسيط ({_diff:.0f}%) — يحتاج بيانات أكثر للتأكد")
            else:
                st.warning(f"⚠️ الإشارات الضعيفة تنجح أكثر ({abs(_diff):.0f}%) — الـ scoring يحتاج مراجعة")

    # ── Signal Type + Location Breakdown ──
    if _period and _n_completed > 5:
        st.divider()
        st.subheader("🏆 أفضل نوع إشارة")

        _type_tab1, _type_tab2 = st.tabs(["📊 حسب نوع التجميع", "📍 حسب الموقع"])

        with _type_tab1:
            _type_perf = {}
            for _s in _completed:
                _al = _s.get("accum_level", "") or "غير محدد"
                if _al not in _type_perf:
                    _type_perf[_al] = {"total": 0, "wins": 0, "returns": [], "best": -999, "worst": 999}
                _type_perf[_al]["total"] += 1
                _ret = _s.get(_return_col, 0) or 0
                if _s.get(_outcome_col) == "win":
                    _type_perf[_al]["wins"] += 1
                _type_perf[_al]["returns"].append(_ret)
                if _ret > _type_perf[_al]["best"]:
                    _type_perf[_al]["best"] = _ret
                if _ret < _type_perf[_al]["worst"]:
                    _type_perf[_al]["worst"] = _ret

            _type_names = {
                "accumulation": "🟢 تجميع (Accumulation)",
                "spring": "💎 سبرنق (Spring)",
                "markup": "🚀 صعود (Markup)",
                "distribution": "🔴 تصريف (Distribution)",
                "markdown": "📉 هبوط (Markdown)",
            }

            _type_rows = []
            for _al, _td in sorted(_type_perf.items(), key=lambda x: sum(x[1]["returns"]) / len(x[1]["returns"]) if x[1]["returns"] else 0, reverse=True):
                _wr = _td["wins"] / _td["total"] * 100 if _td["total"] > 0 else 0
                _avg = sum(_td["returns"]) / len(_td["returns"]) if _td["returns"] else 0
                _pf_gains = sum(r for r in _td["returns"] if r > 0)
                _pf_losses = abs(sum(r for r in _td["returns"] if r < 0)) or 0.01
                _pf = round(_pf_gains / _pf_losses, 2)
                _rec = "✅ ابقِ" if _wr >= 50 else "⚠️ شدد" if _wr >= 30 else "❌ أوقف"
                _type_rows.append({
                    "النوع": _type_names.get(_al, _al),
                    "إشارات": _td["total"],
                    "نجاح": f"{_wr:.0f}%",
                    "عائد": f"{_avg:+.2f}%",
                    "PF": _pf,
                    "أفضل": f"{_td['best']:+.1f}%",
                    "أسوأ": f"{_td['worst']:+.1f}%",
                    "التوصية": _rec,
                })
            if _type_rows:
                st.dataframe(pd.DataFrame(_type_rows), use_container_width=True, hide_index=True)

        with _type_tab2:
            _loc_perf = {}
            for _s in _completed:
                _loc = _s.get("location", "") or "غير محدد"
                if _loc not in _loc_perf:
                    _loc_perf[_loc] = {"total": 0, "wins": 0, "returns": []}
                _loc_perf[_loc]["total"] += 1
                _ret = _s.get(_return_col, 0) or 0
                if _s.get(_outcome_col) == "win":
                    _loc_perf[_loc]["wins"] += 1
                _loc_perf[_loc]["returns"].append(_ret)

            _loc_names = {
                "bottom": "📉 قاع القناة",
                "support": "🟢 منطقة دعم",
                "middle": "➡️ وسط المدى",
                "above": "🚀 فوق المقاومة",
                "resistance": "🔴 عند المقاومة",
            }

            _loc_rows = []
            for _loc, _ld in sorted(_loc_perf.items(), key=lambda x: sum(x[1]["returns"]) / len(x[1]["returns"]) if x[1]["returns"] else 0, reverse=True):
                _wr = _ld["wins"] / _ld["total"] * 100 if _ld["total"] > 0 else 0
                _avg = sum(_ld["returns"]) / len(_ld["returns"]) if _ld["returns"] else 0
                _rec = "✅ ابقِ" if _wr >= 50 else "⚠️ شدد" if _wr >= 30 else "❌ أوقف"
                _loc_rows.append({
                    "الموقع": _loc_names.get(_loc, _loc),
                    "إشارات": _ld["total"],
                    "نجاح": f"{_wr:.0f}%",
                    "عائد": f"{_avg:+.2f}%",
                    "التوصية": _rec,
                })
            if _loc_rows:
                st.dataframe(pd.DataFrame(_loc_rows), use_container_width=True, hide_index=True)

                # Insight
                _best_loc = max(_loc_perf.items(), key=lambda x: sum(x[1]["returns"]) / len(x[1]["returns"]) if x[1]["returns"] else 0)
                _worst_loc = min(_loc_perf.items(), key=lambda x: sum(x[1]["returns"]) / len(x[1]["returns"]) if x[1]["returns"] else 0)
                st.info(
                    f"💡 أفضل موقع: **{_loc_names.get(_best_loc[0], _best_loc[0])}** "
                    f"({sum(_best_loc[1]['returns'])/len(_best_loc[1]['returns']):+.2f}%) | "
                    f"أسوأ موقع: **{_loc_names.get(_worst_loc[0], _worst_loc[0])}** "
                    f"({sum(_worst_loc[1]['returns'])/len(_worst_loc[1]['returns']):+.2f}%)"
                )

    # ── Weekly AI Report ──
    if _n_completed > 10:
        st.divider()
        st.subheader("📱 تقرير أسبوعي بالذكاء الاصطناعي")
        st.caption("تحليل شامل لأداء المنصة — مدعوم بـ Claude Sonnet")

        if st.button("🚀 أنشئ التقرير الأسبوعي", key="weekly_ai_btn", type="primary", use_container_width=True):
            # Build performance summary for AI
            _weekly_data = {
                "period": _period,
                "total_signals": len(_all_signals),
                "completed": _n_completed,
                "win_rate": round(sum(1 for s in _completed if s.get(_outcome_col) == "win") / _n_completed * 100, 1) if _n_completed > 0 else 0,
                "avg_return": round(sum(s.get(_return_col, 0) or 0 for s in _completed) / _n_completed, 2) if _n_completed > 0 else 0,
                "best_trades": [],
                "worst_trades": [],
                "sector_performance": {},
                "signal_type_performance": {},
                "platform_version": "V3-TEST" if "v3" in st.session_state.get("_app_url", "") else "V2",
            }

            # Best/worst
            _sorted_trades = sorted(_completed, key=lambda x: x.get(_return_col, 0) or 0, reverse=True)
            for _t in _sorted_trades[:5]:
                _weekly_data["best_trades"].append({
                    "name": _t.get("company", _t.get("ticker", "")),
                    "sector": _t.get("sector", ""),
                    "return": _t.get(_return_col, 0),
                    "accum_level": _t.get("accum_level", ""),
                    "location": _t.get("location", ""),
                })
            for _t in _sorted_trades[-5:]:
                _weekly_data["worst_trades"].append({
                    "name": _t.get("company", _t.get("ticker", "")),
                    "sector": _t.get("sector", ""),
                    "return": _t.get(_return_col, 0),
                    "accum_level": _t.get("accum_level", ""),
                    "location": _t.get("location", ""),
                })

            # Sector performance
            for _s in _completed:
                _sec = _s.get("sector", "غير مصنف")
                _is_sr = ".SR" in (_s.get("ticker", ""))
                _mkt = "🇸🇦" if _is_sr else "🇺🇸"
                _key = f"{_mkt} {_sec}"
                if _key not in _weekly_data["sector_performance"]:
                    _weekly_data["sector_performance"][_key] = {"total": 0, "wins": 0, "returns": []}
                _weekly_data["sector_performance"][_key]["total"] += 1
                if _s.get(_outcome_col) == "win":
                    _weekly_data["sector_performance"][_key]["wins"] += 1
                _weekly_data["sector_performance"][_key]["returns"].append(_s.get(_return_col, 0) or 0)

            # Summarize sectors
            for _k, _v in _weekly_data["sector_performance"].items():
                _v["win_rate"] = round(_v["wins"] / _v["total"] * 100, 1) if _v["total"] > 0 else 0
                _v["avg_return"] = round(sum(_v["returns"]) / len(_v["returns"]), 2) if _v["returns"] else 0
                del _v["returns"]

            # Signal type performance
            for _s in _completed:
                _al = _s.get("accum_level", "") or "غير محدد"
                if _al not in _weekly_data["signal_type_performance"]:
                    _weekly_data["signal_type_performance"][_al] = {"total": 0, "wins": 0, "avg_return": 0, "returns": []}
                _weekly_data["signal_type_performance"][_al]["total"] += 1
                if _s.get(_outcome_col) == "win":
                    _weekly_data["signal_type_performance"][_al]["wins"] += 1
                _weekly_data["signal_type_performance"][_al]["returns"].append(_s.get(_return_col, 0) or 0)
            for _k, _v in _weekly_data["signal_type_performance"].items():
                _v["win_rate"] = round(_v["wins"] / _v["total"] * 100, 1) if _v["total"] > 0 else 0
                _v["avg_return"] = round(sum(_v["returns"]) / len(_v["returns"]), 2) if _v["returns"] else 0
                del _v["returns"]

            import json
            _weekly_prompt = f"""حلل أداء منصة MASA QUANT وأعطني تقرير أسبوعي شامل:

{json.dumps(_weekly_data, ensure_ascii=False, indent=2)}

## الهيكل المطلوب:

### 📊 ملخص الأسبوع (3 أسطر)
إجمالي، نسبة نجاح، ربح/خسارة، هل المنصة مربحة؟

### 🏆 أفضل 3 صفقات ولماذا نجحت
اربط النجاح بنوع الإشارة والقطاع والموقع

### 💀 أسوأ 3 صفقات ولماذا فشلت
اكتشف النمط — هل فيه قطاع أو نوع إشارة يتكرر في الفشل؟

### 📈 القطاعات: أين نركز وأين نبتعد
رتب القطاعات من الأفضل للأسوأ. حدد: أي قطاعات لازم نشدد عليها أو نمنعها.

### 🎯 نوع الإشارة: أي نوع ينجح وأي نوع يفشل
Spring vs Accumulation vs Markup — مين الأفضل؟

### 🔧 توصيات التحسين
3 توصيات محددة قابلة للتنفيذ بناءً على البيانات.
مثال: "أوقف إشارات Healthcare" أو "شدد Spring يحتاج flow>30"

### 🇸🇦 vs 🇺🇸 المقارنة
أي سوق أفضل؟ بكم؟ ولماذا؟

درجة ثقة المنصة الحالية: X/100
لا تتجاوز 800 كلمة."""

            _weekly_system = """أنت محلل أداء أنظمة تداول — مستوى risk manager في hedge fund.
تكتب بالعربية (سعودي مهني). تحلل الأرقام بصرامة وبدون تجميل.
لو المنصة خاسرة قلها خاسرة. لو فيها مشكلة وضحها. الصراحة أهم من التفاؤل.
كل توصية لازم تكون مبنية على رقم حقيقي من البيانات."""

            try:
                from core.ai_reports import _call_sonnet
                with st.spinner("🤖 Claude يحلل الأداء..."):
                    _weekly_report = _call_sonnet(_weekly_system, _weekly_prompt, 4000)
                st.markdown("---")
                st.markdown(_weekly_report)
            except Exception as _e:
                st.error(f"خطأ: {_e}")

    st.divider()
    st.subheader("🏛 بيانات الملكية المؤسساتية")
    inst_summary = get_ownership_summary(get_all_tickers())

    i1, i2, i3 = st.columns(3)
    i1.metric("إجمالي الأسهم", inst_summary["total_stocks"])
    i2.metric("أسهم مع بيانات ملكية", inst_summary["with_data"])
    i3.metric("تغطية", f"{inst_summary['coverage_pct']:.0f}%")

    if inst_summary["last_update"]:
        st.caption(f"آخر تحديث: {inst_summary['last_update'][:16]}")

    with st.expander("📥 استيراد بيانات ملكية من CSV"):
        st.markdown(
            "صيغة الملف: `ticker,foreign_pct,foreign_limit,foreign_change_pct`\n\n"
            "مثال:\n```\nticker,foreign_pct,foreign_limit,foreign_change_pct\n"
            "2222.SR,5.2,49,0.3\n1120.SR,12.3,49,-0.1\n```"
        )
        csv_file = st.file_uploader("اختر ملف CSV", type=["csv"])
        if csv_file:
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
                tmp.write(csv_file.getvalue().decode("utf-8"))
                tmp_path = tmp.name
            count = import_from_csv(tmp_path)
            if count > 0:
                st.success(f"تم استيراد {count} سجل ملكية")
            else:
                st.warning("لم يتم استيراد أي بيانات — تحقق من صيغة الملف")

    st.divider()
    st.markdown('''
    <div style="color:#374151;font-size:0.82em;line-height:1.6;direction:rtl;
                padding:8px 12px;background:rgba(14,20,36,0.5);border-radius:10px;
                border:1px solid #151d30">
        <b style="color:#4b5563">الشفافية:</b> هذه الأرقام من إشارات فعلية أعطاها النظام
        وتم تتبع نتائجها. لا يوجد فلترة أو إخفاء للنتائج السيئة.
    </div>
    ''', unsafe_allow_html=True)
