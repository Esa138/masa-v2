"""
MASA V2 — Order Flow Scanner
Built on one principle: Who is initiating — the buyer or the seller?
"""

import streamlit as st
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
{zr_badge}
{inst_badge}
</div>
<span style="color:#4b5563;font-size:0.72em">📍 {location_label} • {abs(days)} يوم</span>
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
        row_heights=[0.45, 0.15, 0.22, 0.18],
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
        decreasing_line_color="#FF5252", decreasing_fillcolor="#FF5252",
        name="السعر",
    ), row=1, col=1)

    # ZR lines
    zr_high = r.get("zr_high")
    zr_low = r.get("zr_low")
    if zr_high and zr_high > 0:
        fig.add_hline(
            y=zr_high, line_dash="dashdot", line_color="#FFFFFF",
            line_width=1.5, row=1, col=1,
            annotation_text=f"ZR سقف {zr_high}",
            annotation_position="top right",
            annotation_font=dict(size=10, color="#FFFFFF"),
        )
    if zr_low and zr_low > 0:
        fig.add_hline(
            y=zr_low, line_dash="dashdot", line_color="#FF9800",
            line_width=1.5, row=1, col=1,
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

    fig.update_layout(
        height=700,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,24,36,0.8)",
        showlegend=False,
        annotations=[
            dict(text="شموع + MA20 · MA50 · MA200 + ZR", x=0.01, y=1.02,
                 xref="paper", yref="paper", showarrow=False,
                 font=dict(size=11, color="#6b7280")),
            dict(text=f"CDV — <span style='color:{arrow_color}'>{phase_label}</span>",
                 x=0.01, y=0.37, xref="paper", yref="paper", showarrow=False,
                 font=dict(size=10, color="#6b7280")),
            dict(text="RSI (14)", x=0.01, y=0.17, xref="paper", yref="paper",
                 showarrow=False, font=dict(size=10, color="#6b7280")),
        ],
        xaxis=dict(showticklabels=False, showgrid=False, rangeslider=dict(visible=False)),
        xaxis2=dict(showticklabels=False, showgrid=False),
        xaxis3=dict(showticklabels=False, showgrid=False),
        xaxis4=dict(showgrid=False, tickfont=dict(size=10, color="#6b7280"),
                    dtick="M1", tickformat="%b %Y"),
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

    n = len(closes)
    if n < 20:
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

        # Breakout markers
        if breakout_dates:
            fig.add_trace(go.Scatter(
                x=breakout_dates, y=breakout_prices,
                mode="markers",
                marker=dict(symbol="triangle-up", size=12, color=tf["color"],
                            line=dict(width=1, color="#fff")),
                name=f"اختراق {tf['label']}",
                hovertemplate=f"اختراق {tf['label']}<br>%{{x}}<br>%{{y:.2f}}<extra></extra>",
            ))
        # Breakdown markers
        if breakdown_dates:
            fig.add_trace(go.Scatter(
                x=breakdown_dates, y=breakdown_prices,
                mode="markers",
                marker=dict(symbol="circle", size=10, color=tf["color"],
                            line=dict(width=1, color="#fff")),
                name=f"كسر {tf['label']}",
                hovertemplate=f"كسر {tf['label']}<br>%{{x}}<br>%{{y:.2f}}<extra></extra>",
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
                   tickformat="%d %b", dtick=14*86400000, tickangle=-45),
        yaxis=dict(showgrid=True, gridcolor="#151d30",
                   tickfont=dict(size=10, color="#4b5563"), title=None),
        yaxis2=dict(showgrid=False,
                    tickfont=dict(size=9, color="#FFD700"),
                    title=None, overlaying="y", side="left"),
        hovermode="x unified",
    )

    return fig


# ══════════════════════════════════════════════════════════════
# MARKET BREAKOUT INDEX (مؤشر الاختراقات)
# ══════════════════════════════════════════════════════════════

def build_composite_index(results):
    """
    Build a composite market index by aggregating daily returns of ALL stocks.
    Returns: (dates, index_values, index_highs, index_lows)
    Starting at 100, each day = average daily return across all stocks.
    """
    if not results:
        return [], [], [], []

    # Collect stocks with valid chart data
    stocks = []
    for r in results:
        dates = r.get("chart_dates", [])
        closes = r.get("chart_close", [])
        opens = r.get("chart_open", [])
        highs = r.get("chart_high", [])
        lows = r.get("chart_low", [])
        if len(dates) < 15:
            continue
        stocks.append({
            "dates": dates,
            "closes": closes,
            "opens": opens,
            "highs": highs,
            "lows": lows,
        })

    if not stocks:
        return [], [], [], []

    # Build date -> return mapping for each stock
    all_dates = sorted(set(d for s in stocks for d in s["dates"]))
    n_dates = len(all_dates)

    # For each date, compute average daily return across all stocks
    avg_returns = []
    avg_high_returns = []
    avg_low_returns = []

    for date_str in all_dates:
        day_returns = []
        day_high_returns = []
        day_low_returns = []
        for s in stocks:
            if date_str not in s["dates"]:
                continue
            idx = s["dates"].index(date_str)
            if idx == 0:
                continue
            prev_c = s["closes"][idx - 1]
            if prev_c == 0:
                continue
            day_returns.append((s["closes"][idx] - prev_c) / prev_c)
            day_high_returns.append((s["highs"][idx] - prev_c) / prev_c)
            day_low_returns.append((s["lows"][idx] - prev_c) / prev_c)

        if day_returns:
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
        index_vals.append(round(index_vals[-1] * (1 + avg_returns[i]), 2))
        index_highs.append(round(index_vals[-2] * (1 + avg_high_returns[i]), 2))
        index_lows.append(round(index_vals[-2] * (1 + avg_low_returns[i]), 2))

    # Handle first entry
    if len(index_vals) > 0:
        index_highs[0] = index_vals[0]
        index_lows[0] = index_vals[0]

    return all_dates, index_vals, index_highs, index_lows


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


def build_composite_breakouts_chart(dates, index_vals, index_highs, index_lows):
    """Build a breakout chart for the composite index — same style as individual stocks."""
    n = len(dates)
    if n < 20:
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
        if breakout_dates:
            fig.add_trace(go.Scatter(
                x=breakout_dates, y=breakout_prices, mode="markers",
                marker=dict(symbol="triangle-up", size=12, color=tf["color"],
                            line=dict(width=1, color="#fff")),
                name=f"اختراق {tf['label']}",
            ))
        if breakdown_dates:
            fig.add_trace(go.Scatter(
                x=breakdown_dates, y=breakdown_prices, mode="markers",
                marker=dict(symbol="circle", size=10, color=tf["color"],
                            line=dict(width=1, color="#fff")),
                name=f"كسر {tf['label']}",
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
                   tickformat="%d %b %Y"),
        yaxis=dict(showgrid=True, gridcolor="#151d30",
                   tickfont=dict(size=10, color="#4b5563")),
        hovermode="x unified",
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
    """
    bench = BENCHMARK_MAP.get(market_key, BENCHMARK_MAP["saudi"])
    try:
        t = yf.Ticker(bench["ticker"])
        df = t.history(period="1y", interval="1d")
        if df is None or df.empty:
            return {}, 0, 0, bench["name"], bench["color"]
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Build date -> close map
        bench_map = {}
        for dt, row in df.iterrows():
            bench_map[dt.strftime("%Y-%m-%d")] = float(row["Close"])

        # Find first date that exists in both
        first_val = None
        for d in dates:
            if d in bench_map:
                first_val = bench_map[d]
                break

        if first_val is None or first_val == 0:
            return {}, 0, 0, bench["name"], bench["color"]

        # Normalize
        normalized = {}
        for d in dates:
            if d in bench_map:
                normalized[d] = round(bench_map[d] / first_val * start_val, 2)

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

    if len(dates) < 20:
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
    day_return = (index_vals[-1] - index_vals[-2]) / index_vals[-2] * 100 if len(index_vals) >= 2 else 0
    week_return = (index_vals[-1] - index_vals[-5]) / index_vals[-5] * 100 if len(index_vals) >= 5 else 0

    # Benchmark return
    bench_first = list(bench_norm.values())[0] if bench_norm else 100
    bench_last_norm = list(bench_norm.values())[-1] if bench_norm else 100
    bench_total_ret = (bench_last_norm - bench_first) / bench_first * 100 if bench_first > 0 else 0

    tc = "#00E676" if total_return >= 0 else "#FF5252"
    dc = "#00E676" if day_return >= 0 else "#FF5252"
    bench_tc = "#00E676" if bench_total_ret >= 0 else "#FF5252"

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
        <div style="background:linear-gradient(135deg,#131a2e,#0e1424);border:1px solid #192035;
                    border-radius:12px;padding:14px;text-align:center">
            <div style="color:#6b7280;font-size:0.78em;margin-bottom:6px">📊 المؤشر المركب</div>
            <div style="color:#4FC3F7;font-size:1.8em;font-weight:800">{last_val:.2f}</div>
            <div style="color:{dc};font-size:0.82em;font-weight:600">{day_return:+.2f}% اليوم</div>
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
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px;direction:rtl">
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

    # Tabs
    idx_tab_compare, idx_tab_chart, idx_tab_data, idx_tab_lag = st.tabs([
        f"📊 مقارنة مع {bench_name}", "🚀 شارت الاختراقات", "📋 البيانات", "⚡ تحليل السبق"
    ])

    with idx_tab_compare:
        # Comparison chart: Composite vs Benchmark
        comp_fig = go.Figure()
        comp_fig.add_trace(go.Scatter(
            x=dates, y=index_vals, mode="lines",
            line=dict(color="#4FC3F7", width=2.5),
            name="المؤشر المركب",
            hovertemplate="المؤشر: %{y:.2f}<extra></extra>",
        ))
        # Benchmark line
        b_dates = [d for d in dates if d in bench_norm]
        b_vals = [bench_norm[d] for d in b_dates]
        if b_dates:
            comp_fig.add_trace(go.Scatter(
                x=b_dates, y=b_vals, mode="lines",
                line=dict(color=bench_color, width=2.5),
                name=bench_name,
                hovertemplate=f"{bench_name}: %{{y:.2f}}<extra></extra>",
            ))

        # Shade the gap
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
            xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#6b7280"),
                       tickformat="%d %b %Y"),
            yaxis=dict(showgrid=True, gridcolor="#151d30",
                       tickfont=dict(size=10, color="#4b5563")),
            hovermode="x unified",
            annotations=[
                dict(text="كلاهما يبدأ من 100 — المقارنة نسبية",
                     x=0.5, y=-0.08, xref="paper", yref="paper",
                     showarrow=False, font=dict(size=10, color="#4b5563")),
            ],
        )
        st.plotly_chart(comp_fig, use_container_width=True, config={"displayModeBar": False})

    with idx_tab_chart:
        bc1, bc2, bc3, bc4 = st.columns(4)
        show_3 = bc1.checkbox("عرض 3 أيام 🟠", value=True, key="idx_brk3")
        show_4 = bc2.checkbox("عرض 4 أيام 🟢", value=False, key="idx_brk4")
        show_10 = bc3.checkbox("عرض 10 أيام 🟣", value=True, key="idx_brk10")
        show_15 = bc4.checkbox("عرض 15 أيام 🔴", value=False, key="idx_brk15")

        brk_chart = build_composite_breakouts_chart(dates, index_vals, index_highs, index_lows)
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
    <div style="text-align:center;padding:12px 0 8px 0">
        <span style="font-size:2.2em">🔬</span>
        <div style="font-size:1.4em;font-weight:800;color:#fff;margin-top:4px;
                    letter-spacing:1px">MASA V2</div>
        <div style="color:#4b5563;font-size:0.78em;margin-top:2px">
            Order Flow Scanner — من المهاجم؟</div>
    </div>
    ''', unsafe_allow_html=True)

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

    page = st.radio(
        "الصفحة",
        ["🔬 Order Flow", "🚀 مؤشر الاختراقات", "📊 أداء النظام"],
        label_visibility="collapsed",
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

    hcol1, hcol2 = st.columns([3, 1])
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
        scan_btn = st.button("▶️ ابدأ المسح", use_container_width=True, type="primary")

    if scan_btn:
        tickers = get_all_tickers(market_key)

        progress = st.progress(0, text="جاري المسح...")

        def _update(current, total):
            progress.progress(current / total, text=f"تحليل {current}/{total}")

        results = scan_market(
            tickers=tickers,
            market_health=50.0,
            progress_callback=_update,
        )
        progress.empty()

        # حساب صحة السوق من نتائج المسح (بدون استعلامات إضافية)
        if results:
            above_ma50 = sum(1 for r in results if r.get("chart_ma50") and r["price"] > r["chart_ma50"][-1])
            total_valid = sum(1 for r in results if r.get("chart_ma50") and r["chart_ma50"][-1] is not None)
            health = round(above_ma50 / total_valid * 100, 1) if total_valid > 0 else 50.0
        else:
            health = 50.0

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
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        show_filter = st.selectbox(
            "🎯 التصنيف",
            ["✅ ادخل + ⚠️ راقب", "✅ ادخل فقط", "الكل"],
        )
    with fcol2:
        sectors = sorted(set(r["sector"] for r in results))
        selected_sector = st.selectbox("📂 القطاع", ["كل القطاعات"] + sectors)
    with fcol3:
        sort_by = st.selectbox(
            "📊 الترتيب",
            ["أقوى أوردر فلو", "أكبر تغير ↑", "أعلى امتصاص", "أقوى دايفرجنس"],
        )

    if show_filter == "✅ ادخل فقط":
        filtered = [r for r in results if r["decision"] == "enter"]
    elif show_filter == "✅ ادخل + ⚠️ راقب":
        filtered = [r for r in results if r["decision"] in ("enter", "watch")]
    else:
        filtered = list(results)

    if selected_sector != "كل القطاعات":
        filtered = [r for r in filtered if r["sector"] == selected_sector]

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


# ══════════════════════════════════════════════════════════════
# PAGE: Market Breakout Index
# ══════════════════════════════════════════════════════════════

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
# PAGE: Performance
# ══════════════════════════════════════════════════════════════

elif page == "📊 أداء النظام":

    st.title("📊 أداء النظام — الحقيقة الكاملة")
    st.caption("كل رقم هنا من بيانات حقيقية — إشارات سابقة ونتائجها الفعلية")

    tracking = get_tracking_status()
    pending = tracking["pending_5d"] + tracking["pending_10d"] + tracking["pending_20d"]

    if pending > 0:
        with st.spinner(f"📡 تحديث نتائج {pending} إشارة..."):
            result = update_signal_outcomes(lookback_days=60)
        if result["updated"] > 0:
            st.success(f"تم تحديث {result['updated']} إشارة")
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("إجمالي الإشارات", perf["total"])
    c2.metric("إشارات 'ادخل'", perf["enter_count"])

    if perf["enter_completed"] > 0:
        wr = perf["win_rate"]
        wr_color = "normal" if wr >= 55 else "inverse" if wr < 45 else "off"
        c3.metric("نسبة النجاح (10 أيام)", f"{wr:.1f}%", delta_color=wr_color)
        c4.metric("متوسط العائد", f"{perf['avg_return']:+.1f}%")
    else:
        c3.metric("نسبة النجاح", "⏳ انتظار")
        c4.metric("متوسط العائد", "⏳ انتظار")

    st.divider()
    st.subheader("📡 حالة التتبع")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("إشارات دخول", tracking["total_enter"])
    t2.metric("مكتملة", tracking["completed"])
    t3.metric("قيد التتبع", pending)
    t4.metric(
        "تغطية",
        f"{tracking['completed'] / tracking['total_enter'] * 100:.0f}%"
        if tracking["total_enter"] > 0 else "—"
    )

    st.divider()

    if win_rates:
        st.subheader("نسب النجاح حسب نوع الإشارة")
        for key, data in win_rates.items():
            wr = data["win_rate"]
            total = data["completed"]
            st.markdown(f"**{key}** — {wr:.1f}% نجاح ({data['wins']}/{total})")
            st.progress(wr / 100)

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
