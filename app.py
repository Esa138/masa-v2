import os
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import requests
import warnings
import re
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.utils import (
    init_db, sanitize_text, format_price, save_to_tracker,
    DB_FILE, get_now, get_today_str, safe_div,
)
from core.indicators import (
    calculate_zero_reflection, compute_rsi, compute_atr,
    compute_vwap, compute_direction_counter, ACCUM_PHASES,
)
from core.scanner import scan_market, get_macro_status, get_stock_data, _format_cat, _get_cat
from data.markets import (
    SAUDI_NAMES, US_NAMES, FX_NAMES, CRYPTO_NAMES, get_stock_name, get_stock_sector,
)
from ui.styles import CUSTOM_CSS, LOGO_HTML, CLOCK_HTML
from ui.formatters import safe_color_table, style_live_tracker
from core.breadth import fetch_breadth_closes, compute_market_breadth, get_breadth_stats, get_tasi_regime
from core.backtest_engine import backtest_accumulation_signals, compute_backtest_summary
from core.signal_tracker import (
    init_signal_log, log_signals_from_scan, update_signal_outcomes,
    compute_signal_stats, get_signal_log_df, clear_signal_log, get_signal_count,
    get_ticker_signal_history, get_distribution_summary,
)

warnings.filterwarnings('ignore')


def _get_vip_thresholds(macro_status):
    """Dynamic VIP thresholds based on market conditions."""
    if "إيجابي" in macro_status:
        return 75, 70, "متساهل - سوق صاعد", "vip-threshold-bull"
    elif "سلبي" in macro_status:
        return 85, 80, "صارم - سوق هابط", "vip-threshold-bear"
    else:
        return 80, 75, "معياري", "vip-threshold-normal"


def _diversify_vip(df_vip, max_picks=3, max_per_sector=2):
    """Ensure sector diversification in VIP picks (max 2 from same sector)."""
    if df_vip.empty or 'stock_sector' not in df_vip.columns:
        return df_vip.head(max_picks)

    selected = []
    sector_counts = {}
    for _, row in df_vip.iterrows():
        sector = row.get('stock_sector', '')
        if sector and sector_counts.get(sector, 0) >= max_per_sector:
            continue
        selected.append(row)
        if sector:
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= max_picks:
            break

    return pd.DataFrame(selected)


def _calc_confidence(row):
    """Calculate confidence score (0-5 stars) combining all key signals.

    The 4+1 keys discovered through live analysis:
    ① CMF positive   = money flowing IN
    ② Wolf ≥ 6       = technical filters aligned
    ③ All green       = 3d, 5d, 10d momentum positive
    ④ Score ≥ 60     = accumulation threshold
    ⑤ V2 buy signal  = engine confirmation (bonus)
    """
    stars = 0
    details = []

    # ① CMF — money flow direction
    cmf = row.get('accum_cmf', 0)
    if cmf > 0:
        stars += 1
        details.append(("CMF إيجابي", True, f"{cmf:+.3f}"))
    else:
        details.append(("CMF سلبي", False, f"{cmf:+.3f}"))

    # ② Wolf readiness — technical alignment
    wolf = row.get('wolf_readiness', 0)
    if wolf >= 6:
        stars += 1
        details.append(("وولف جاهز", True, f"{wolf}/9"))
    else:
        details.append(("وولف ضعيف", False, f"{wolf}/9"))

    # ③ Momentum — all timeframes green
    r3 = row.get('raw_3d', 0) or 0
    r5 = row.get('raw_5d', 0) or 0
    r10 = row.get('raw_10d', 0) or 0
    all_green = r3 > 0 and r5 > 0 and r10 > 0
    green_count = sum(1 for x in [r3, r5, r10] if x > 0)
    if all_green:
        stars += 1
        details.append(("زخم ✅✅✅", True, f"{green_count}/3"))
    else:
        details.append(("زخم ناقص", False, f"{green_count}/3"))

    # ④ Accumulation score threshold
    score = row.get('accum_score', 0)
    if score >= 60:
        stars += 1
        details.append(("سكور كافي", True, f"{score:.0f}/100"))
    else:
        details.append(("سكور ضعيف", False, f"{score:.0f}/100"))

    # ⑤ V2 signal — bonus star
    v2 = row.get('accum_v2_signal', 'none')
    if v2 in ('buy_confirmed', 'buy_breakout'):
        stars += 1
        details.append(("V2 شراء", True, "✓"))
    elif v2 == 'sell_confirmed':
        stars = max(0, stars - 1)  # penalty
        details.append(("V2 بيع", False, "✗"))
    elif v2 == 'sell_warning':
        details.append(("V2 تحذير", False, "⚠"))
    else:
        details.append(("V2 محايد", False, "—"))

    # Determine verdict
    phase = row.get('accum_phase', 'neutral')
    if phase in ('distribute', 'exhausted'):
        verdict = "تصريف — لا تدخل"
        verdict_color = "#FF5252"
        verdict_icon = "🔴"
    elif stars >= 4:
        verdict = "فرصة قوية — مراقبة للدخول"
        verdict_color = "#00E676"
        verdict_icon = "🟢"
    elif stars == 3:
        verdict = "واعد — انتظر تأكيد"
        verdict_color = "#69F0AE"
        verdict_icon = "🟡"
    elif stars == 2:
        verdict = "ضعيف — حذر"
        verdict_color = "#FFD700"
        verdict_icon = "🟠"
    else:
        verdict = "ارتداد مؤقت — لا تدخل"
        verdict_color = "#FF5252"
        verdict_icon = "🔴"

    return stars, details, verdict, verdict_color, verdict_icon


def _build_accum_card(row, currency, bt_win_rates=None):
    """Build two-tier HTML card: clean decision view + expandable details."""
    phase = row.get('accum_phase', 'neutral')
    score = row.get('accum_score', 0)
    cmf = row.get('accum_cmf', 0)
    obv_slope = row.get('accum_obv_slope', 0)
    days = row.get('accum_days', 0)
    zr_bonus = row.get('accum_zr_bonus', 0)
    phase_label = row.get('accum_phase_label', 'محايد ⚪')
    phase_color = row.get('accum_phase_color', '#808080')
    pressure = row.get('accum_pressure', 0)
    expected_move = row.get('accum_expected_move', 0)
    expected_target = row.get('accum_expected_target', 0)
    wolf_ready = row.get('wolf_readiness', 0)
    wolf_filters = row.get('wolf_readiness_filters', [])
    # Lifecycle metadata
    is_post_bo = row.get('accum_is_post_breakout', False)
    late_entry = row.get('accum_late_entry_price', 0)
    bo_price = row.get('accum_breakout_price', 0)
    peak_price = row.get('accum_peak_price', 0)
    peak_gain = row.get('accum_peak_gain_pct', 0)
    retracement = row.get('accum_retracement', 0)
    accum_start_dt = row.get('accum_start_date', '')
    breakout_dt = row.get('accum_breakout_date', '')
    peak_dt = row.get('accum_peak_date', '')
    # Location data
    accum_loc = row.get('accum_location', 'middle')
    accum_loc_label = row.get('accum_location_label', '🟣 تجميع في الوسط')
    # Target / Stop from ai_pick
    target_val = row.get('raw_target', 0)
    sl_val = row.get('raw_sl', 0)
    tk = str(row['الرمز'])
    masa_score = row.get('raw_score', 0)

    # V2 Signal data
    v2_signal = row.get('accum_v2_signal', 'none')
    v2_label = row.get('accum_v2_label', '')
    v2_color = row.get('accum_v2_color', '#808080')
    v2_confidence = row.get('accum_v2_confidence', 0)
    has_cross_ma20 = row.get('accum_cross_ma20', False)
    has_break_20d = row.get('accum_break_20d', False)
    has_above_ma50 = row.get('accum_above_ma50', False)

    # ══════════════════════════════════════
    # Confidence Score (THE KEY ADDITION)
    # ══════════════════════════════════════
    conf_stars, conf_details, conf_verdict, conf_verdict_color, conf_verdict_icon = _calc_confidence(row)
    _stars_display = "⭐" * conf_stars + "☆" * (5 - conf_stars)
    _conf_details_html = ""
    for _cd_label, _cd_pass, _cd_val in conf_details:
        _cd_icon = "✅" if _cd_pass else "❌"
        _cd_color = "#00E676" if _cd_pass else "#FF5252"
        _conf_details_html += (
            f"<div style='display:flex; justify-content:space-between; align-items:center; "
            f"padding:3px 0; font-size:12px; direction:rtl;'>"
            f"<span style='color:{_cd_color};'>{_cd_icon} {_cd_label}</span>"
            f"<span style='color:#888;'>{_cd_val}</span>"
            f"</div>"
        )

    confidence_badge = (
        f"<div style='background:rgba(255,255,255,0.04); border:1px solid {conf_verdict_color}44; "
        f"border-radius:10px; padding:10px 14px; margin:8px 0; direction:rtl;'>"
        f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
        f"<div>"
        f"<div style='font-size:16px; font-weight:900; color:{conf_verdict_color};'>"
        f"{conf_verdict_icon} {conf_verdict}</div>"
        f"<div style='font-size:20px; margin-top:2px;'>{_stars_display}</div>"
        f"</div>"
        f"<div style='font-size:36px; font-weight:900; color:{conf_verdict_color};'>"
        f"{conf_stars}<span style='font-size:16px; color:#666;'>/5</span></div>"
        f"</div>"
        f"<details style='margin-top:8px;'>"
        f"<summary style='cursor:pointer; font-size:11px; color:#666;'>تفاصيل التقييم</summary>"
        f"<div style='margin-top:6px; padding:8px; background:rgba(0,0,0,0.2); border-radius:8px;'>"
        f"{_conf_details_html}"
        f"</div></details>"
        f"</div>"
    )

    clean_name = sanitize_text(str(row['الشركة']))
    sector = row.get('stock_sector', '')
    sector_html = f"<span class='sector-tag'>{sanitize_text(sector)}</span>" if sector else ""

    bar_cls = "accum-bar-fill-dist" if phase in ("distribute", "exhausted") else "accum-bar-fill"
    zr_html = "<span class='accum-zr-badge'>💎 قرب قاع زيرو</span>" if zr_bonus > 0 else ""
    loc_html = f"<span class='accum-loc-badge accum-loc-{accum_loc}'>{sanitize_text(accum_loc_label)}</span>"

    # ══════════════════════════════════════
    # TIER 1: Lifecycle summary (compact)
    # ══════════════════════════════════════
    lifecycle_html = ""
    if is_post_bo and late_entry > 0:
        retr_pct = int(retracement * 100)
        retr_color = "#4CAF50" if retr_pct < 40 else "#FFC107" if retr_pct < 65 else "#FF5252"
        bo_html = f" → انطلق <b style='color:#FF9800;'>{bo_price:.2f}</b>" if bo_price > 0 else ""
        lifecycle_html = (
            f"<div class='lifecycle-meta'>"
            f"📦 بدء: <b>{accum_start_dt}</b> | دخول: <b>{late_entry:.2f}</b>{bo_html} | "
            f"📉 تراجع: <b style='color:{retr_color};'>{retr_pct}%</b>"
            f"</div>"
        )
    elif late_entry > 0 and accum_start_dt:
        cur_gain = ((float(row.get('raw_price', 0)) - late_entry) / late_entry * 100) if late_entry > 0 else 0
        gain_color = "#00E676" if cur_gain > 0 else "#FF5252"
        lifecycle_html = (
            f"<div class='lifecycle-meta'>"
            f"📦 بدء: <b>{accum_start_dt}</b> | دخول: <b>{late_entry:.2f}</b> | "
            f"التغير: <b style='color:{gain_color};'>{cur_gain:+.1f}%</b>"
            f"</div>"
        )

    # ══════════════════════════════════════
    # TIER 1: Target + Stop + Win Rate
    # ══════════════════════════════════════
    targets_html = ""
    if target_val > 0 and sl_val > 0 and phase not in ("distribute", "exhausted"):
        targets_html = (
            f"<div class='accum-targets-row'>"
            f"<span>🎯 هدف: <b style='color:#00E676;'>{format_price(target_val, tk)}</b></span>"
            f"<span>🛡️ وقف: <b style='color:#FF5252;'>{format_price(sl_val, tk)}</b></span>"
            f"</div>"
        )

    # Win rate from backtest (if available)
    _phase_for_bt = phase if phase in ("late", "strong", "distribute") else row.get('accum_raw_phase', phase)
    win_rate_html = ""
    if bt_win_rates and _phase_for_bt in bt_win_rates:
        _wr = bt_win_rates[_phase_for_bt]
        _wr_color = "#00E676" if _wr >= 60 else "#FFD700" if _wr >= 50 else "#FF5252"
        _wr_label = "نزول" if _phase_for_bt == "distribute" else "نجاح"
        win_rate_html = (
            f"<div style='text-align:center; margin:6px 0;'>"
            f"<span class='accum-winrate'>📊 {_wr_label} تاريخي: {_wr}% (20 يوم)</span>"
            f"</div>"
        )
    else:
        win_rate_html = (
            f"<div style='text-align:center; margin:6px 0;'>"
            f"<span class='accum-winrate-none'>📊 شغّل الباك تيست لمعرفة النسبة</span>"
            f"</div>"
        )

    # ══════════════════════════════════════
    # TIER 1: Wolf Hero (only ≥ 7)
    # ══════════════════════════════════════
    wolf_hero_html = ""
    if wolf_ready >= 7:
        _wolf_label = "🐺 وولف مؤكد 💎" if wolf_ready >= 8 else "🐺 وولف جاهز 🔥"
        wolf_hero_html = (
            f"<div style='text-align:center; margin:8px 0;'>"
            f"<span class='accum-wolf-hero'>{_wolf_label} {wolf_ready}/9</span>"
            f"</div>"
        )

    # ══════════════════════════════════════
    # TIER 1: Stock Signal History
    # ══════════════════════════════════════
    signal_history_html = ""
    _tk_hist = get_ticker_signal_history(tk)
    if _tk_hist['total'] > 0:
        _hist_completed = _tk_hist.get('completed', 0)
        if _hist_completed > 0:
            _hist_wp = _tk_hist['win_pct']
            _hist_color = "#00E676" if _hist_wp >= 60 else "#FFD700" if _hist_wp >= 50 else "#FF5252"
            signal_history_html = (
                f"<div style='text-align:center; margin:6px 0; font-size:12px; color:#888;'>"
                f"📋 سجل سابق: <b style='color:{_hist_color};'>{_tk_hist['wins']}/{_hist_completed}</b>"
                f" نجاح ({_hist_wp:.0f}%) من {_tk_hist['total']} إشارة"
                f"</div>"
            )
        else:
            signal_history_html = (
                f"<div style='text-align:center; margin:6px 0; font-size:11px; color:#555;'>"
                f"📋 {_tk_hist['total']} إشارة مسجلة — تنتظر النتائج"
                f"</div>"
            )

    # ══════════════════════════════════════
    # TIER 2: Details (collapsed)
    # ══════════════════════════════════════
    cmf_color = "#00E676" if cmf > 0 else "#FF5252"
    obv_color = "#00E676" if obv_slope > 0 else "#FF5252"

    # Pressure bar
    if pressure >= 80:
        pr_color, pr_cls = "#f44336", "pressure-bar-fill pressure-bar-fill-high"
    elif pressure >= 50:
        pr_color, pr_cls = "#FF9800", "pressure-bar-fill"
    else:
        pr_color, pr_cls = "#4CAF50", "pressure-bar-fill"

    # Wolf filters grid (always in tier 2)
    wolf_grid = ""
    if wolf_filters:
        wolf_grid = f"<div style='font-size:13px; color:{('#FF9800' if wolf_ready >= 5 else '#FF5252')}; font-weight:700; margin:8px 0;'>🐺 فلاتر وولف: {wolf_ready}/9</div>"
        wolf_grid += "<div class='wolf-ready-grid'>"
        for f_name, f_pass in wolf_filters:
            icon = "✅" if f_pass else "❌"
            cls = "wolf-ready-pass" if f_pass else "wolf-ready-fail"
            wolf_grid += f"<div class='wolf-ready-item {cls}'>{icon} {sanitize_text(f_name)}</div>"
        wolf_grid += "</div>"

    # Expected move (tier 2, with disclaimer)
    exp_t2 = ""
    if expected_move > 0 and phase != "distribute":
        exp_t2 = (
            f"<div style='margin:8px 0; font-size:13px; color:#aaa;'>"
            f"🎯 حركة متوقعة: <span style='color:#00E676;'>+{expected_move:.1f}%</span>"
            f" (هدف {expected_target:.2f} {currency})"
            f" <span style='font-size:11px; color:#555;'>— تقدير ATR</span>"
            f"</div>"
        )

    # Post-breakout details (tier 2)
    lifecycle_t2 = ""
    if is_post_bo and late_entry > 0:
        _parts = []
        if bo_price > 0:
            _parts.append(f"🚀 سعر الانطلاق: <b>{bo_price:.2f}</b>")
        _parts.append(f"🔝 القمة: <b>{peak_price:.2f}</b> (+{peak_gain:.1f}%)")
        if breakout_dt:
            _parts.append(f"تاريخ الانطلاق: <b>{breakout_dt}</b>")
        if peak_dt:
            _parts.append(f"تاريخ القمة: <b>{peak_dt}</b>")
        lifecycle_t2 = (
            f"<div style='margin:8px 0; padding:8px; background:rgba(0,0,0,0.2); "
            f"border-radius:8px; font-size:12px; color:#aaa; direction:rtl;'>"
            f"{' | '.join(_parts)}"
            f"</div>"
        )

    tier2_html = (
        f"<details class='accum-details'>"
        f"<summary class='accum-details-btn'>🔍 تفاصيل فنية</summary>"
        f"<div class='accum-tier2'>"
        # Pressure gauge
        f"<div style='display:flex; align-items:center; gap:8px; margin:6px 0;'>"
        f"<span style='font-size:12px; color:#aaa;'>⚡ الضغط</span>"
        f"<div class='pressure-bar-bg' style='flex:1;'>"
        f"<div class='{pr_cls}' style='width:{min(pressure,100)}%;'></div></div>"
        f"<span style='font-size:14px; font-weight:bold; color:{pr_color};'>{pressure:.0f}/100</span></div>"
        # Metrics row
        f"<div class='accum-metrics'>"
        f"<div class='accum-metric'><div class='accum-metric-label'>CMF</div>"
        f"<div class='accum-metric-value' style='color:{cmf_color};'>{cmf:+.3f}</div></div>"
        f"<div class='accum-metric'><div class='accum-metric-label'>OBV Slope</div>"
        f"<div class='accum-metric-value' style='color:{obv_color};'>{obv_slope:+.4f}</div></div>"
        f"<div class='accum-metric'><div class='accum-metric-label'>MASA</div>"
        f"<div class='accum-metric-value'>{masa_score}/100</div></div>"
        f"</div>"
        f"{exp_t2}"
        f"{wolf_grid}"
        f"{lifecycle_t2}"
        f"</div></details>"
    )

    # ══════════════════════════════════════
    # V2 Signal Banner
    # ══════════════════════════════════════
    v2_banner = ""
    if v2_signal == "sell_confirmed":
        # ── SELL CONFIRMED: Big prominent red banner (proven 87%) ──
        _triggers = []
        if has_above_ma50:
            _triggers.append("فوق MA50 ✓")
        _trigger_text = " | ".join(_triggers) if _triggers else ""
        v2_banner = (
            f"<div style='background:rgba(255,82,82,0.18); border:2px solid #FF5252; "
            f"border-radius:12px; padding:14px; margin:8px 0; text-align:center;'>"
            f"<div style='font-size:18px; font-weight:900; color:#FF5252;'>"
            f"🔴 بيع مؤكد — دقة {v2_confidence}%</div>"
            f"<div style='font-size:11px; color:#aaa; margin-top:4px;'>مثبت من اختبار Out-of-Sample | {_trigger_text}</div>"
            f"</div>"
        )
    elif v2_signal == "sell_warning":
        # ── SELL WARNING: Prominent orange banner (proven 57-59%) ──
        v2_banner = (
            f"<div style='background:rgba(255,82,82,0.12); border:2px solid #FF5252; "
            f"border-radius:10px; padding:10px; margin:8px 0; text-align:center;'>"
            f"<div style='font-size:16px; font-weight:800; color:#FF5252;'>"
            f"🔴 تحذير تصريف — دقة {v2_confidence}%</div>"
            f"<div style='font-size:11px; color:#aaa; margin-top:3px;'>إشارة مثبتة من اختبار Out-of-Sample</div>"
            f"</div>"
        )
    elif v2_signal in ("buy_confirmed", "buy_breakout"):
        # ── BUY: Subtle banner with experimental warning ──
        _triggers = []
        if has_cross_ma20:
            _triggers.append("تقاطع MA20 ↑")
        if has_break_20d:
            _triggers.append("كسر 20 يوم ↑")
        _trigger_text = " | ".join(_triggers) if _triggers else ""
        v2_banner = (
            f"<div style='background:rgba(255,215,0,0.06); border:1px solid rgba(255,215,0,0.25); "
            f"border-radius:8px; padding:8px; margin:8px 0; text-align:center;'>"
            f"<div style='font-size:13px; font-weight:700; color:#FFD700;'>"
            f"🟡 {sanitize_text(v2_label)} — تجريبي</div>"
            f"<div style='font-size:11px; color:#666; margin-top:3px;'>{_trigger_text} | دقة ~50% — غير مثبت</div>"
            f"</div>"
        )
    elif v2_signal == "watch":
        v2_banner = (
            f"<div style='background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); "
            f"border-radius:8px; padding:6px; margin:8px 0; text-align:center;'>"
            f"<div style='font-size:12px; color:#888;'>"
            f"👁️ مراقبة — انتظر تقاطع MA20 أو كسر 20 يوم</div>"
            f"</div>"
        )

    # ══════════════════════════════════════
    # News / Announcement Badge
    # ══════════════════════════════════════
    news_badge = ""
    _news_sent = row.get('news_sentiment', 'محايد')
    _news_kw_score = row.get('keyword_score', 0)
    _news_summary = str(row.get('news_summary', ''))
    _news_conf = int(row.get('news_confidence', 0))
    _has_real_news = (_news_sent != 'محايد') or (abs(_news_kw_score) >= 3) or (_news_conf > 20)

    if _has_real_news:
        if phase in ('distribute', 'exhausted') and (_news_sent == 'سلبي' or _news_kw_score <= -3):
            _nb_bg = "rgba(255,82,82,0.15)"
            _nb_border = "#FF5252"
            _nb_icon = "🔴📰"
            _nb_label = "تصريف مع إعلان سلبي"
        elif phase in ('strong', 'late') and (_news_sent == 'إيجابي' or _news_kw_score >= 3):
            _nb_bg = "rgba(0,230,118,0.12)"
            _nb_border = "#00E676"
            _nb_icon = "🟢📰"
            _nb_label = "تجميع مع إعلان إيجابي"
        elif _news_sent == 'سلبي' or _news_kw_score <= -3:
            _nb_bg = "rgba(255,82,82,0.08)"
            _nb_border = "#FF5252"
            _nb_icon = "📰⚠️"
            _nb_label = "إعلان سلبي"
        elif _news_sent == 'إيجابي' or _news_kw_score >= 3:
            _nb_bg = "rgba(0,230,118,0.06)"
            _nb_border = "#00E676"
            _nb_icon = "📰✅"
            _nb_label = "إعلان إيجابي"
        else:
            _nb_bg = "rgba(255,215,0,0.06)"
            _nb_border = "rgba(255,215,0,0.3)"
            _nb_icon = "📰"
            _nb_label = "يوجد إعلان"

        _nb_summary = sanitize_text(_news_summary[:60]) + "..." if len(_news_summary) > 60 else sanitize_text(_news_summary)

        news_badge = (
            f"<div style='background:{_nb_bg}; border:1px solid {_nb_border}; "
            f"border-radius:8px; padding:8px 12px; margin:6px 0; direction:rtl;'>"
            f"<div style='font-size:14px; font-weight:700; color:{_nb_border};'>"
            f"{_nb_icon} {_nb_label}</div>"
            f"<div style='font-size:12px; color:#aaa; margin-top:4px;'>{_nb_summary}</div>"
            f"</div>"
        )

    # ══════════════════════════════════════
    # ASSEMBLE CARD
    # ══════════════════════════════════════
    _card_html = (
        f"<div class='accum-card accum-card-{phase}'>"
        f"<div class='accum-icon'>🏗️</div>"
        # Header
        f"<div style='font-size:22px; color:white; font-weight:900; margin-bottom:5px;'>"
        f"{clean_name} <span style='font-size:13px; color:#888;'>({tk})</span></div>"
        f"{sector_html}"
        # Badges
        f"<div style='margin:8px 0;'>"
        f"<span class='accum-phase-badge accum-phase-{phase}'>{sanitize_text(phase_label)}</span> {loc_html} {zr_html}"
        f"</div>"
        # Confidence Score Badge (THE KEY DECISION AID)
        f"{confidence_badge}"
        # V2 Signal Banner
        f"{v2_banner}"
        # News / Announcement Badge
        f"{news_badge}"
        # Lifecycle summary
        f"{lifecycle_html}"
        # Price
        f"<div style='font-size:30px; color:white; font-weight:bold; margin:10px 0;'>"
        f"{row['السعر']} <span style='font-size:15px; color:#aaa;'>{currency}</span></div>"
        # Score bar
        f"<div style='display:flex; align-items:center; gap:10px; margin:8px 0;'>"
        f"<span style='font-size:13px; color:#aaa;'>سكور التجميع</span>"
        f"<div class='accum-bar-bg' style='flex:1;'>"
        f"<div class='{bar_cls}' style='width:{min(score,100)}%;'></div></div>"
        f"<span style='font-size:18px; font-weight:bold; color:{phase_color};'>{score:.0f}/100</span></div>"
        # Target + Stop
        f"{targets_html}"
        # Win Rate
        f"{win_rate_html}"
        # Wolf Hero (only ≥7)
        f"{wolf_hero_html}"
        # Signal history
        f"{signal_history_html}"
        # Footer
        f"<div style='margin-top:8px; font-size:13px; color:#aaa;'>"
        f"📅 {days} يوم تراكم | {row.get('الحالة اللحظية ⚡', '')}</div>"
        # Tier 2 details
        f"{tier2_html}"
        f"</div>"
    )
    # Strip invalid DOM characters that cause InvalidCharacterError
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', _card_html)


st.set_page_config(
    page_title="MASA QUANT | V95 PRO",
    layout="wide",
    page_icon="💎",
)

init_db()
init_signal_log()

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Inject viewport meta for mobile + fix iOS Safari rendering
_VIEWPORT_JS = """
<script>
(function(){
    if(!document.querySelector('meta[name="viewport"]')){
        var m=document.createElement('meta');
        m.name='viewport';
        m.content='width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no';
        document.head.appendChild(m);
    }
})();
</script>
"""
components.html(_VIEWPORT_JS, height=0)

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
    st.markdown(
        "<h4 style='color:#FFD700; text-align:right;'>📰 تحليل الأخبار بالذكاء الاصطناعي (Gemini AI)</h4>",
        unsafe_allow_html=True
    )
    c_gem1, c_gem2 = st.columns([2, 1])
    with c_gem1:
        gemini_key = st.text_input(
            "🔑 Gemini API Key", type="password",
            help="احصل على مفتاح مجاني من ai.google.dev — يتيح تحليل الأخبار تلقائياً"
        )
    with c_gem2:
        st.markdown(
            "<div style='padding-top:28px; font-size:13px; color:#888;'>"
            "📰 يحلل آخر الأخبار ويعدّل التقييم تلقائياً</div>",
            unsafe_allow_html=True
        )

    # ── Clear cache button ──
    _cc1, _cc2 = st.columns([1, 3])
    with _cc1:
        if st.button("🗑️ مسح الكاش", help="أعد تشغيل المنصة بدون بيانات مخزنة"):
            st.cache_data.clear()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


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
            gemini_api_key=gemini_key,
        )
        st.session_state['scan_results'] = {
            'df_loads': df_loads,
            'df_alerts': df_alerts,
            'df_ai_picks': df_ai_picks,
        }

        # ── Auto-log signals to Live Signal Tracker ──
        if not df_ai_picks.empty:
            _market_label = "السعودي" if "السعودي" in market_choice else "الأمريكي" if "الأمريكي" in market_choice else market_choice
            _n_logged = log_signals_from_scan(df_ai_picks, _market_label)
            if _n_logged > 0:
                st.toast(f"📋 تم تسجيل {_n_logged} إشارة جديدة في سجل الإشارات")

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

    # ── Compute current market breadth for alert system ──
    _market_breadth_pct = None
    if "السعودي" in market_choice:
        try:
            _alert_closes = fetch_breadth_closes(tuple(SAUDI_NAMES.keys()), period="1mo")
            if not _alert_closes.empty:
                _chg_1d = _alert_closes.pct_change(1).iloc[-1]
                _valid_1d = _chg_1d.dropna()
                if len(_valid_1d) > 0:
                    _market_breadth_pct = round((_valid_1d > 0).sum() / len(_valid_1d) * 100, 1)
        except Exception:
            pass
    elif "الأمريكي" in market_choice:
        try:
            _alert_closes = fetch_breadth_closes(tuple(US_NAMES.keys()), period="1mo")
            if not _alert_closes.empty:
                _chg_1d = _alert_closes.pct_change(1).iloc[-1]
                _valid_1d = _chg_1d.dropna()
                if len(_valid_1d) > 0:
                    _market_breadth_pct = round((_valid_1d > 0).sum() / len(_valid_1d) * 100, 1)
        except Exception:
            pass

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

    _sig_count = get_signal_count()
    _sig_tab_label = f"📋 سجل الإشارات ({_sig_count})" if _sig_count > 0 else "📋 سجل الإشارات"


    tab_accum, tab_vip, tab_news, tab_signal_log, tab_scan, tab_breakouts, tab_alerts, tab_chart, tab_tools = st.tabs([
        "🛡️ التجميع والتصريف", "👑 VIP ماسة", "📰 الإعلانات",
        _sig_tab_label, "🗂️ ماسح السوق", "🎯 الاختراقات",
        "🚨 التنبيهات", "📊 الشارت", "⚙️ أدوات"
    ])

    # ===========================================================
    # TAB: VIP
    # ===========================================================
    with tab_vip:
        # ── Market Breadth Alert ──
        if _market_breadth_pct is not None and ("السعودي" in market_choice or "الأمريكي" in market_choice):
            if _market_breadth_pct < 45:
                st.markdown(
                    f"<div style='background:rgba(255,82,82,0.1); border:1px solid #FF5252; border-radius:10px; "
                    f"padding:10px 16px; margin-bottom:15px; text-align:center; direction:rtl;'>"
                    f"<span style='font-size:15px; font-weight:700; color:#FF5252;'>"
                    f"🚨 السوق غير مناسب للشراء — الاتساع {_market_breadth_pct}% (تحت 45%)</span><br>"
                    f"<span style='font-size:12px; color:#888;'>إشارات التجميع ضعيفة في الأسواق الهابطة — ركّز على تجنّب أسهم التصريف</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            elif _market_breadth_pct < 55:
                st.markdown(
                    f"<div style='background:rgba(255,215,0,0.08); border:1px solid #FFD700; border-radius:10px; "
                    f"padding:10px 16px; margin-bottom:15px; text-align:center; direction:rtl;'>"
                    f"<span style='font-size:15px; font-weight:700; color:#FFD700;'>"
                    f"⚠️ السوق محايد — الاتساع {_market_breadth_pct}% (منطقة حيرة)</span><br>"
                    f"<span style='font-size:12px; color:#888;'>اشترِ فقط إشارات \"نهاية تجميع\" بحذر شديد</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='background:rgba(0,230,118,0.08); border:1px solid #00E676; border-radius:10px; "
                    f"padding:10px 16px; margin-bottom:15px; text-align:center; direction:rtl;'>"
                    f"<span style='font-size:15px; font-weight:700; color:#00E676;'>"
                    f"✅ السوق مناسب للشراء — الاتساع {_market_breadth_pct}% (فوق 55%)</span><br>"
                    f"<span style='font-size:12px; color:#888;'>إشارات التجميع موثوقة — ابحث عن \"نهاية تجميع\" و \"تجميع قوي\"</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        if not df_ai_picks.empty:
            df_vip_full = pd.DataFrame(df_ai_picks)

            # Dynamic VIP thresholds
            vip_score_th, vip_mom_th, vip_mode_label, vip_mode_cls = _get_vip_thresholds(macro_status)

            # ── Arbitrator-aware VIP selection ──────────────────
            # Use unified_score and respect vip_allowed flag
            def _effective_vip_threshold(row):
                """Apply per-stock threshold reduction from arbitrator."""
                reduction = row.get('vip_threshold_reduction', 0)
                return vip_score_th - reduction

            mask = (
                df_vip_full.apply(
                    lambda r: r.get('unified_score', r['raw_score']) >= _effective_vip_threshold(r),
                    axis=1
                )
                & (df_vip_full['raw_mom'] >= vip_mom_th)
                & (~df_vip_full['raw_events'].str.contains('كسر|هابط|تصحيح|🔻'))
                & (df_vip_full.get('vip_allowed', pd.Series(True, index=df_vip_full.index)).astype(bool))
            )
            # Sort: signal quality first (gold>silver>bronze), then Wolf, then stars, then score
            _quality_order = {"gold": 0, "silver": 1, "bronze": 2, "blocked": 3}
            df_vip = df_vip_full[mask].copy()
            df_vip['_quality_pri'] = df_vip.get('signal_quality', pd.Series("bronze")).map(
                _quality_order
            ).fillna(2)
            df_vip['_wolf_pri'] = df_vip.get('is_wolf', pd.Series(False)).apply(
                lambda x: 0 if x else 1
            )
            df_vip['_stars'] = df_vip.get('confluence_stars', pd.Series(0))
            df_vip = df_vip.sort_values(
                by=['_quality_pri', '_wolf_pri', '_stars', 'unified_score', 'raw_mom'],
                ascending=[True, True, False, False, False]
            )
            df_vip = df_vip.drop(columns=['_quality_pri', '_wolf_pri', '_stars'], errors='ignore')
            # Sector diversification
            df_vip = _diversify_vip(df_vip, max_picks=3, max_per_sector=2)

            if not df_vip.empty:
                st.markdown(
                    "<h3 style='text-align: center; color: #ffd700; font-weight: 900;'>"
                    "👑 الصندوق الأسود: أقوى الفرص الاستثمارية الآن</h3>",
                    unsafe_allow_html=True
                )
                # Show dynamic threshold badge
                st.markdown(
                    f"<div style='text-align:center;'>"
                    f"<span class='vip-threshold {vip_mode_cls}'>"
                    f"عتبة الدخول: Score ≥ {vip_score_th} | Momentum ≥ {vip_mom_th} "
                    f"({vip_mode_label})</span></div>",
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
                        # Build news line for Telegram
                        tg_news_line = ""
                        tg_news_sent = row.get('news_sentiment', 'محايد')
                        tg_news_sum = str(row.get('news_summary', ''))
                        if tg_news_sent != 'محايد' and tg_news_sum and tg_news_sum != 'لا توجد أخبار':
                            tg_news_line = f"📰 *News:* {tg_news_sum}\n"

                        # Build wolf line for Telegram
                        tg_wolf_line = ""
                        if row.get('is_wolf', False):
                            w_type = row.get('wolf_type', '')
                            w_rr = row.get('wolf_rr', 0)
                            if w_type == 'مؤكد':
                                tg_wolf_line = f"🐺 *Wolf Confirmed:* MASA×Wolf dual signal (R:R 1:{w_rr:.1f})\n"
                            else:
                                tg_wolf_line = f"🐺 *Wolf Breakout:* Momentum breakout (R:R 1:{w_rr:.1f})\n"

                        # Build keyword alert line for Telegram
                        tg_kw_line = ""
                        kw_v = str(row.get('keyword_verdict', ''))
                        if 'خطر' in kw_v:
                            kw_hits_list = row.get('killer_hits', [])
                            top_kw = ", ".join(str(h[0]) for h in kw_hits_list[:3]) if kw_hits_list else ""
                            tg_kw_line = f"💣 *Keywords:* {top_kw}\n"
                        elif 'إيجابي' in kw_v:
                            kw_hits_list = row.get('rocket_hits', [])
                            top_kw = ", ".join(str(h[0]) for h in kw_hits_list[:3]) if kw_hits_list else ""
                            tg_kw_line = f"🚀 *Keywords:* {top_kw}\n"

                        # Confluence line for Telegram
                        tg_conf_line = ""
                        tg_stars = int(row.get('confluence_stars', 0))
                        if tg_stars >= 3:
                            tg_signals = row.get('confluence_signals', [])
                            tg_sig_str = " + ".join(str(s) for s in tg_signals) if tg_signals else ""
                            tg_conf_line = f"{'⭐' * tg_stars} *Confluence:* {tg_sig_str}\n"

                        # Sector line for Telegram
                        tg_sector_line = ""
                        tg_sector = str(row.get('stock_sector', ''))
                        if tg_sector:
                            tg_sector_line = f"🏷️ *Sector:* {tg_sector}\n"

                        msg = (
                            f"🚨 *Masa VIP Alert!* 💎\n\n"
                            f"📌 *Asset:* {row['الشركة']} ({row['الرمز']})\n"
                            f"{tg_sector_line}"
                            f"⏱️ *Timeframe:* {tf_choice}\n"
                            f"💰 *Price:* {row['السعر']}\n"
                            f"🎯 *Target:* {row['الهدف 🎯']}\n"
                            f"🛡️ *SL (ATR):* {row['الوقف 🛡️']}\n"
                            f"⚖️ *R:R:* 1:{row['raw_rr']:.1f}\n"
                            f"{tg_conf_line}"
                            f"{tg_wolf_line}"
                            f"{tg_kw_line}"
                            f"{tg_news_line}\n"
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

                    # News badge for VIP card
                    news_badge_html = ""
                    vip_news_sent = row.get('news_sentiment', 'محايد')
                    vip_news_sum = sanitize_text(str(row.get('news_summary', '')))
                    if vip_news_sent != 'محايد' and vip_news_sum and vip_news_sum != 'لا توجد أخبار':
                        badge_cls = 'news-badge-pos' if vip_news_sent == 'إيجابي' else 'news-badge-neg'
                        news_badge_html = (
                            f"<div class='news-badge {badge_cls}' "
                            f"style='margin-bottom:10px;'>📰 {vip_news_sum}</div>"
                        )

                    # Wolf badge for VIP card
                    wolf_badge_html = ""
                    if row.get('is_wolf', False):
                        wtype = row.get('wolf_type', '')
                        if wtype == 'مؤكد':
                            wolf_badge_html = (
                                "<div class='wolf-badge wolf-badge-confirmed' "
                                "style='margin-bottom:10px;'>🐺💎 اختراق وولف مؤكد</div>"
                            )
                        elif wtype == 'فقط':
                            wolf_badge_html = (
                                "<div class='wolf-badge wolf-badge-only' "
                                "style='margin-bottom:10px;'>🐺 اختراق وولف</div>"
                            )

                    # Confluence stars for VIP card
                    confluence_html = ""
                    c_stars = int(row.get('confluence_stars', 0))
                    c_display = str(row.get('confluence_display', ''))
                    c_signals = row.get('confluence_signals', [])
                    if c_stars >= 3:
                        signals_text = " + ".join(str(s) for s in c_signals) if c_signals else ""
                        high_cls = " confluence-high" if c_stars >= 4 else ""
                        confluence_html = (
                            f"<div class='confluence-badge{high_cls}' style='margin-bottom:10px;'>"
                            f"<span class='confluence-stars'>{c_display}</span>"
                            f" تلاقي {c_stars} إشارات"
                            f"<div style='font-size:11px; margin-top:4px; color:#ccc;'>{signals_text}</div>"
                            f"</div>"
                        )

                    # Signal quality badge from Arbitrator (الحَكَم)
                    quality_badge_html = ""
                    sig_quality = row.get('signal_quality', 'bronze')
                    sig_label = row.get('quality_label', '')
                    sig_color = row.get('quality_color', '#CD7F32')
                    quality_badge_html = (
                        f"<div class='signal-quality-badge signal-quality-{sig_quality}'>"
                        f"{sig_label}</div>"
                    )

                    # Contradiction warnings from arbitrator
                    contradiction_html = ""
                    arb_contradictions = row.get('arb_contradictions', [])
                    if arb_contradictions and isinstance(arb_contradictions, list) and len(arb_contradictions) > 0:
                        warns = "<br>".join(str(c) for c in arb_contradictions)
                        contradiction_html = (
                            f"<div class='arb-warning'>{warns}</div>"
                        )

                    # Sector badge for VIP card
                    sector_html = ""
                    vip_sector = str(row.get('stock_sector', ''))
                    if vip_sector:
                        sector_html = f"<span class='sector-tag'>{sanitize_text(vip_sector)}</span>"

                    # Use unified score for display
                    display_score = row.get('unified_score', row['raw_score'])

                    cards_html += (
                        f"<div class='vip-card'>"
                        f"<div class='vip-crown'>👑</div>"
                        f"<div class='vip-title'>{clean_name} {sector_html}</div>"
                        f"<div class='vip-time'>{str(row['raw_time'])}</div><br>"
                        f"{quality_badge_html}"
                        f"{contradiction_html}"
                        f"{confluence_html}"
                        f"{news_badge_html}"
                        f"{wolf_badge_html}"
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
                        f"<div class='vip-score'>التقييم: {display_score}/100</div>"
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
    # ===========================================================
    # TAB: News / Announcements
    # ===========================================================
    with tab_news:
        st.markdown(
            "<h3 style='text-align: center; color: #FFD700; font-weight: bold;'>"
            "📰 تحليل الإعلانات + ماسح الكلمات المؤثرة (Gemini AI)</h3>",
            unsafe_allow_html=True
        )

        if not gemini_key:
            st.markdown(
                "<div class='empty-box' style='border-color:#FFD700;'>"
                "🔑 أدخل مفتاح Gemini API في الإعدادات أعلاه لتفعيل تحليل الأخبار الذكي.<br><br>"
                "ماسح الكلمات المؤثرة يعمل بدون مفتاح — لكن Gemini يحتاج مفتاح للتحليل العميق.<br>"
                "احصل على مفتاح مجاني من "
                "<a href='https://ai.google.dev' target='_blank' style='color:#00d2ff;'>ai.google.dev</a>"
                "</div>",
                unsafe_allow_html=True
            )
        if not df_ai_picks.empty:
            df_news_disp = pd.DataFrame(df_ai_picks)

            # Filter: has real news (non-default sentiment or keyword hits)
            _default_summaries = {"", "لا توجد أخبار", "لا يوجد ملخص"}
            _sent_col = df_news_disp.get('news_sentiment', pd.Series(['محايد'] * len(df_news_disp)))
            _sum_col = df_news_disp.get('news_summary', pd.Series([''] * len(df_news_disp)))
            _conf_col = df_news_disp.get('news_confidence', pd.Series([0] * len(df_news_disp)))
            has_sentiment = _sent_col != 'محايد'
            has_real_summary = ~_sum_col.isin(_default_summaries) & (_sum_col.str.len() > 5)
            has_confidence = _conf_col > 10
            has_keywords = df_news_disp.get('keyword_score', pd.Series([0] * len(df_news_disp))) != 0
            has_headlines = df_news_disp.get('news_headlines', pd.Series([[] for _ in range(len(df_news_disp))])).apply(
                lambda x: isinstance(x, list) and len(x) > 0
            )
            df_news_disp = df_news_disp[has_sentiment | has_real_summary | has_confidence | has_keywords | has_headlines]

            # Sort: by absolute keyword score, then confidence
            if not df_news_disp.empty:
                if 'keyword_score' in df_news_disp.columns:
                    df_news_disp['_abs_kw'] = df_news_disp['keyword_score'].abs()
                    df_news_disp = df_news_disp.sort_values(
                        by=['_abs_kw', 'news_confidence'], ascending=[False, False]
                    )
                    df_news_disp = df_news_disp.drop(columns=['_abs_kw'], errors='ignore')
                elif 'news_confidence' in df_news_disp.columns:
                    df_news_disp = df_news_disp.sort_values('news_confidence', ascending=False)

            if not df_news_disp.empty:
                # Summary stats
                n_pos = len(df_news_disp[df_news_disp.get('news_sentiment', '') == 'إيجابي'])
                n_neg = len(df_news_disp[df_news_disp.get('news_sentiment', '') == 'سلبي'])
                n_neu = len(df_news_disp) - n_pos - n_neg
                total_killers = int(df_news_disp.get('killer_count', pd.Series([0])).sum())
                total_rockets = int(df_news_disp.get('rocket_count', pd.Series([0])).sum())

                col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
                col_s1.metric("📈 إيجابي", f"{n_pos} سهم")
                col_s2.metric("📉 سلبي", f"{n_neg} سهم")
                col_s3.metric("➖ محايد", f"{n_neu} سهم")
                col_s4.metric("💣 كلمات قاتلة", f"{total_killers}")
                col_s5.metric("🚀 كلمات صاروخية", f"{total_rockets}")
                st.markdown("<br>", unsafe_allow_html=True)

                news_cards = ""
                for _, row in df_news_disp.iterrows():
                    n_sent = row.get('news_sentiment', 'محايد')
                    n_sum = sanitize_text(str(row.get('news_summary', '')))
                    n_conf = int(row.get('news_confidence', 0))
                    n_adj = int(row.get('news_adjustment', 0))
                    n_headlines = row.get('news_headlines', [])
                    n_name = sanitize_text(str(row.get('الشركة', '')))
                    n_ticker = str(row.get('الرمز', ''))
                    kw_hits = row.get('keyword_hits', [])
                    kw_score = int(row.get('keyword_score', 0))
                    kw_verdict = str(row.get('keyword_verdict', '⚖️ محايد'))
                    killer_hits = row.get('killer_hits', [])
                    rocket_hits = row.get('rocket_hits', [])

                    if n_sent == 'إيجابي':
                        card_cls = 'news-positive'
                        badge_cls = 'news-badge-pos'
                        sent_icon = '📈'
                        adj_color = '#00E676'
                    elif n_sent == 'سلبي':
                        card_cls = 'news-negative'
                        badge_cls = 'news-badge-neg'
                        sent_icon = '📉'
                        adj_color = '#FF5252'
                    else:
                        card_cls = 'news-neutral'
                        badge_cls = 'news-badge-neu'
                        sent_icon = '➖'
                        adj_color = '#FFD700'

                    adj_text = f"+{n_adj}" if n_adj > 0 else str(n_adj) if n_adj < 0 else "0"

                    # Confidence bar
                    bar_color = adj_color
                    conf_bar = (
                        f"<div style='background:#2d303e; border-radius:4px; height:8px; width:100%; margin-top:8px;'>"
                        f"<div style='background:{bar_color}; border-radius:4px; height:8px; width:{n_conf}%;'></div>"
                        f"</div>"
                    )

                    # Keyword tags HTML
                    kw_html = ""
                    if isinstance(kw_hits, list) and kw_hits:
                        kw_tags = ""
                        for kw, ktype, weight, effect in kw_hits[:8]:
                            kw_safe = sanitize_text(str(kw))
                            eff_safe = sanitize_text(str(effect))
                            if ktype == "💣":
                                kw_tags += (
                                    f"<span class='kw-tag kw-killer' title='{eff_safe}'>"
                                    f"💣 {kw_safe} ({weight}/10)</span>"
                                )
                            else:
                                kw_tags += (
                                    f"<span class='kw-tag kw-rocket' title='{eff_safe}'>"
                                    f"🚀 {kw_safe} ({weight}/10)</span>"
                                )

                        # Verdict badge
                        if kw_score <= -5:
                            v_cls = "kw-verdict-danger"
                        elif kw_score >= 5:
                            v_cls = "kw-verdict-rocket"
                        else:
                            v_cls = "kw-verdict-neutral"

                        kw_html = (
                            f"<div class='kw-section'>"
                            f"<div style='font-size:13px; color:#aaa; margin-bottom:8px;'>"
                            f"🔍 <b>ماسح الكلمات المؤثرة:</b></div>"
                            f"<div>{kw_tags}</div>"
                            f"<div style='margin-top:8px;'>"
                            f"<span class='{v_cls}'>{kw_verdict} (صافي: {kw_score:+d})</span>"
                            f"</div>"
                            f"</div>"
                        )

                    # Headlines list
                    headlines_html = ""
                    if isinstance(n_headlines, list) and n_headlines:
                        items = "".join(
                            f"<li style='color:#bbb; font-size:13px; margin-bottom:4px;'>"
                            f"{sanitize_text(str(h.get('title', '')))}"
                            f"<span style='color:#666; font-size:11px;'> — {sanitize_text(str(h.get('publisher', '')))}</span>"
                            f"</li>"
                            for h in n_headlines[:5] if h.get('title')
                        )
                        headlines_html = (
                            f"<details style='margin-top:10px;'>"
                            f"<summary style='color:#00d2ff; cursor:pointer; font-size:13px;'>"
                            f"📋 عناوين الأخبار ({len(n_headlines)})</summary>"
                            f"<ul style='margin-top:5px; padding-right:20px;'>{items}</ul>"
                            f"</details>"
                        )

                    news_cards += (
                        f"<div class='news-card {card_cls}' dir='rtl'>"
                        f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                        f"<div>"
                        f"<span style='font-size:20px; font-weight:900; color:white;'>{n_name}</span>"
                        f" <span style='font-size:14px; color:#888;'>({n_ticker})</span>"
                        f"</div>"
                        f"<div>"
                        f"<span class='news-badge {badge_cls}'>{sent_icon} {n_sent}</span>"
                        f" <span style='color:{adj_color}; font-weight:bold; font-size:16px;'>"
                        f"({adj_text} نقطة)</span>"
                        f"</div>"
                        f"</div>"
                        f"<div style='margin-top:12px; color:#ddd; font-size:15px;'>{n_sum}</div>"
                        f"<div style='margin-top:8px; font-size:12px; color:#888;'>"
                        f"الثقة: {n_conf}%</div>"
                        f"{conf_bar}"
                        f"{kw_html}"
                        f"{headlines_html}"
                        f"</div>"
                    )

                st.markdown(news_cards, unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div class='empty-box' style='border-color:#FFD700;'>"
                    "📭 لم يتم العثور على أخبار أو كلمات مؤثرة للأسهم الحالية.</div>",
                    unsafe_allow_html=True
                )
        elif not gemini_key:
            pass  # Already shown the API key message above
        else:
            st.markdown(
                "<div class='empty-box'>📭 اضغط على استخراج الفرص أولاً.</div>",
                unsafe_allow_html=True
            )

    # ===========================================================
    # TAB: Accumulation & Distribution
    # ===========================================================
    with tab_accum:
        # Combined decision matrix badge is rendered after pulse data is computed (below)

        import datetime as _dt
        _accum_now = _dt.datetime.now().strftime("%H:%M  %Y-%m-%d")
        st.markdown(
            "<h3 style='text-align: center; color: #2196F3; font-weight: bold;'>"
            "🛡️ ماسح التجميع والتصريف</h3>"
            f"<p style='text-align:center; color:#888; font-size:0.8rem;'>"
            f"آخر تحديث: {_accum_now} &nbsp;|&nbsp; الكاش: 5 دقائق &nbsp;|&nbsp; "
            f"بيانات حقيقية بدون شموع Vol=0</p>"
            "<div style='background:rgba(33,150,243,0.08); border:1px solid rgba(33,150,243,0.25); "
            "border-radius:10px; padding:10px 16px; margin:10px auto; max-width:700px; "
            "text-align:center; direction:rtl; font-size:13px;'>"
            "<span style='color:#FF5252; font-weight:700;'>🔴 إشارات التصريف مثبتة (59-97% دقة)</span>"
            " &nbsp;·&nbsp; "
            "<span style='color:#FFD700;'>🟡 إشارات الشراء تجريبية (~50%)</span>"
            "<div style='color:#666; font-size:11px; margin-top:4px;'>"
            "الدقة محسوبة من اختبار Out-of-Sample على بيانات 2025</div>"
            "</div>",
            unsafe_allow_html=True
        )

        # ═══════════════════════════════════════════
        # 🧭 مؤشر اتجاه السوق — TASI Regime Indicator
        # ═══════════════════════════════════════════
        if "السعودي" in market_choice:
            _tasi = get_tasi_regime()
            if _tasi["ok"]:
                _ma20_icon = "✅" if _tasi["above_ma20"] else "❌"
                _ma50_icon = "✅" if _tasi["above_ma50"] else "❌"
                _ret5_color = "#00E676" if _tasi["ret_5d"] > 0 else "#FF5252"
                _ret20_color = "#00E676" if _tasi["ret_20d"] > 0 else "#FF5252"
                _ret60_color = "#00E676" if _tasi["ret_60d"] > 0 else "#FF5252"

                st.markdown(f"""
                <div style='background:{_tasi["regime_bg"]}; border:2px solid {_tasi["regime_color"]};
                    border-radius:14px; padding:14px 20px; margin-bottom:18px; direction:rtl;'>
                    <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;'>
                        <div>
                            <span style='font-size:22px; font-weight:900; color:{_tasi["regime_color"]};'>
                                {_tasi["regime_emoji"]} اتجاه السوق: {_tasi["regime_ar"]}
                            </span>
                            <span style='font-size:14px; color:#aaa; margin-right:12px;'>
                                {_tasi["momentum_emoji"]} الزخم: {_tasi["momentum"]}
                            </span>
                        </div>
                        <div style='font-size:18px; font-weight:700; color:#ddd;'>
                            TASI {_tasi["tasi_price"]:,.0f}
                        </div>
                    </div>
                    <div style='margin-top:10px; display:flex; gap:20px; flex-wrap:wrap; justify-content:center; font-size:13px;'>
                        <span style='color:{_ret5_color};'>5 أيام: <b>{_tasi["ret_5d"]:+.1f}%</b></span>
                        <span style='color:{_ret20_color};'>20 يوم: <b>{_tasi["ret_20d"]:+.1f}%</b></span>
                        <span style='color:{_ret60_color};'>60 يوم: <b>{_tasi["ret_60d"]:+.1f}%</b></span>
                        <span style='color:#aaa;'>{_ma20_icon} MA20: {_tasi["ma20"]:,.0f}</span>
                        <span style='color:#aaa;'>{_ma50_icon} MA50: {_tasi["ma50"]:,.0f}</span>
                    </div>
                    <div style='text-align:center; margin-top:8px; font-size:13px; font-weight:600; color:{_tasi["regime_color"]};'>
                        💡 {_tasi["advice"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Store regime in session state for use elsewhere
                st.session_state['tasi_regime'] = _tasi["regime"]

        if not df_ai_picks.empty and 'accum_phase' in df_ai_picks.columns:
            df_accum = pd.DataFrame(df_ai_picks)
            df_accum = df_accum[df_accum['accum_phase'] != 'neutral'].copy()

            # Add confidence stars column for sorting
            if not df_accum.empty:
                df_accum['confidence_stars'] = df_accum.apply(
                    lambda r: _calc_confidence(r)[0], axis=1
                )

            if not df_accum.empty:
                # Phase counts for metrics
                phase_counts = df_accum['accum_phase'].value_counts().to_dict()
                _n_pb_buy = phase_counts.get('pullback_buy', 0)
                _n_breakout = phase_counts.get('breakout', 0)
                _n_lifecycle = _n_pb_buy + _n_breakout + phase_counts.get('pullback_wait', 0) + phase_counts.get('exhausted', 0)
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("🟢 نهاية تجميع", phase_counts.get('late', 0))
                m2.metric("🟢 ارتداد صحي", _n_pb_buy)
                m3.metric("🔵 تجميع قوي", phase_counts.get('strong', 0))
                m4.metric("🚀 انطلاق", _n_breakout)
                m5.metric("🔴 تصريف", phase_counts.get('distribute', 0))
                m6.metric("🔴 استنفاد", phase_counts.get('exhausted', 0))

                # ═══════════════════════════════════════════
                # ⚠️ Distribution Alert Banner
                # ═══════════════════════════════════════════
                _dist_list = get_distribution_summary()
                if _dist_list:
                    _dist_names = " · ".join(
                        f"<b>{d['company']}</b>" for d in _dist_list[:8]
                    )
                    _dist_extra = f" +{len(_dist_list) - 8} آخرين" if len(_dist_list) > 8 else ""
                    st.markdown(
                        f"<div style='background:rgba(255,82,82,0.1); border:2px solid rgba(255,82,82,0.4); "
                        f"border-radius:12px; padding:12px 18px; margin:12px 0; direction:rtl; text-align:center;'>"
                        f"<div style='font-size:16px; font-weight:800; color:#FF5252; margin-bottom:6px;'>"
                        f"⚠️ {len(_dist_list)} سهم تصريف نشط</div>"
                        f"<div style='font-size:13px; color:#ccc;'>{_dist_names}{_dist_extra}</div>"
                        f"<div style='font-size:11px; color:#666; margin-top:4px;'>"
                        f"إشارات التصريف مثبتة بدقة 59-97% — راجع سجل الإشارات للتفاصيل</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                # ═══════════════════════════════════════════
                # 📊 Market Pulse — هل السوق في تجميع أم تصريف؟
                # ═══════════════════════════════════════════
                _total_all = len(df_ai_picks)  # all stocks (including neutral)
                _n_accum = (phase_counts.get('late', 0) + phase_counts.get('strong', 0) +
                            phase_counts.get('mid', 0) + phase_counts.get('early', 0) +
                            phase_counts.get('pullback_buy', 0) + phase_counts.get('breakout', 0))
                _n_dist = phase_counts.get('distribute', 0) + phase_counts.get('exhausted', 0)
                _n_neutral = _total_all - _n_accum - _n_dist

                _pct_accum = round((_n_accum / max(_total_all, 1)) * 100, 1)
                _pct_dist = round((_n_dist / max(_total_all, 1)) * 100, 1)
                _pct_neutral = round(100 - _pct_accum - _pct_dist, 1)

                _avg_score = round(df_accum['accum_score'].mean(), 1) if not df_accum.empty else 0
                _avg_pressure = round(df_accum['accum_pressure'].mean(), 1) if 'accum_pressure' in df_accum.columns and not df_accum.empty else 0
                _avg_cmf = round(df_accum['accum_cmf'].mean(), 3) if not df_accum.empty else 0
                _n_strong_late = phase_counts.get('late', 0) + phase_counts.get('strong', 0)

                # Verdict
                if _pct_accum > 70:
                    _verdict = "🟢 السوق في تجميع مؤسساتي قوي"
                    _verdict_cls = "market-verdict-bull"
                elif _pct_accum > 50:
                    _verdict = "🟡 السوق متذبذب — تجميع معتدل"
                    _verdict_cls = "market-verdict-mid"
                elif _pct_accum > 30:
                    _verdict = "🟠 السوق ضعيف — حذر"
                    _verdict_cls = "market-verdict-warn"
                else:
                    _verdict = "🔴 السوق في تصريف — خطر"
                    _verdict_cls = "market-verdict-bear"

                _cmf_c = "#00E676" if _avg_cmf > 0 else "#FF5252"

                # ═══════════════════════════════════════════
                # 🧭 مصفوفة القرار المدمجة (اتساع + نبض)
                # ═══════════════════════════════════════════
                _br_pct = _market_breadth_pct if _market_breadth_pct is not None else 50
                _pulse_pct = _pct_accum

                _br_ok = "✅" if _br_pct >= 55 else ("⚠️" if _br_pct >= 45 else "❌")
                _pulse_ok = "✅" if _pulse_pct >= 70 else ("⚠️" if _pulse_pct >= 40 else "❌")

                if _br_pct >= 55 and _pulse_pct >= 70:
                    _matrix_emoji = "🟢"
                    _matrix_title = "السوق جاهز — اشتري نهاية التجميع"
                    _matrix_sub = "المؤسسات تشتري + أغلب السوق صاعد = أفضل وقت"
                    _matrix_bg = "rgba(0,230,118,0.1)"
                    _matrix_border = "#00E676"
                    _matrix_color = "#00E676"
                elif _br_pct < 45 and _pulse_pct >= 70:
                    _matrix_emoji = "🟡"
                    _matrix_title = "المؤسسات تشتري الانخفاض — انتظر الاتساع"
                    _matrix_sub = "التجميع قوي لكن السوق نازل — جهز القائمة وانتظر الاتساع فوق 50%"
                    _matrix_bg = "rgba(255,215,0,0.08)"
                    _matrix_border = "#FFD700"
                    _matrix_color = "#FFD700"
                elif _br_pct >= 55 and _pulse_pct < 40:
                    _matrix_emoji = "🟠"
                    _matrix_title = "صعود بدون مؤسسات — احذر الفقاعة"
                    _matrix_sub = "السوق صاعد لكن المؤسسات ما تشتري — صعود مؤقت وخطر"
                    _matrix_bg = "rgba(255,152,0,0.1)"
                    _matrix_border = "#FF9800"
                    _matrix_color = "#FF9800"
                elif _br_pct < 45 and _pulse_pct < 40:
                    _matrix_emoji = "🔴"
                    _matrix_title = "ابتعد — السوق ينهار"
                    _matrix_sub = "المؤسسات تبيع + السوق نازل = أسوأ وقت للشراء"
                    _matrix_bg = "rgba(255,82,82,0.1)"
                    _matrix_border = "#FF5252"
                    _matrix_color = "#FF5252"
                else:
                    _matrix_emoji = "⚠️"
                    _matrix_title = "السوق محايد — كن انتقائياً"
                    _matrix_sub = "اشترِ فقط إشارات نهاية تجميع 🟢 بحجم صغير"
                    _matrix_bg = "rgba(255,215,0,0.06)"
                    _matrix_border = "#FFD700"
                    _matrix_color = "#FFD700"

                st.markdown(f"""
                <div style='background:{_matrix_bg}; border:2px solid {_matrix_border}; border-radius:14px;
                    padding:16px 20px; margin-bottom:20px; text-align:center; direction:rtl;'>
                    <div style='font-size:20px; font-weight:900; color:{_matrix_color}; margin-bottom:6px;'>
                        {_matrix_emoji} {_matrix_title}
                    </div>
                    <div style='font-size:12px; color:#aaa; margin-bottom:12px;'>{_matrix_sub}</div>
                    <div style='display:flex; justify-content:center; gap:30px; flex-wrap:wrap;'>
                        <span style='font-size:14px; color:{_matrix_color};'>
                            {_br_ok} الاتساع: <b>{_br_pct:.1f}%</b>
                        </span>
                        <span style='font-size:14px; color:{_matrix_color};'>
                            {_pulse_ok} نبض التجميع: <b>{_pulse_pct:.0f}%</b>
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div class='market-pulse-box'>
                    <div class='market-pulse-title'>📊 نبض السوق {"الأمريكي" if "الأمريكي" in market_choice else "السعودي" if "السعودي" in market_choice else ""}</div>
                    <div class='market-bar-container'>
                        <span class='market-bar-label' style='color:#FF5252;'>◀ تصريف {_pct_dist:.0f}%</span>
                        <div class='market-bar-track'>
                            <div class='market-bar-dist' style='width:{_pct_dist}%;'></div>
                            <div class='market-bar-neutral' style='width:{_pct_neutral}%;'></div>
                            <div class='market-bar-accum' style='width:{_pct_accum}%;'></div>
                        </div>
                        <span class='market-bar-label' style='color:#00E676;'>تجميع {_pct_accum:.0f}% ▶</span>
                    </div>
                    <div class='market-pulse-metrics'>
                        <div class='market-pulse-metric'>
                            <div class='market-pulse-metric-label'>نبض السوق</div>
                            <div class='market-pulse-metric-value'>{_avg_score:.0f}<span style='font-size:12px;color:#888;'>/100</span></div>
                        </div>
                        <div class='market-pulse-metric'>
                            <div class='market-pulse-metric-label'>ضغط السوق</div>
                            <div class='market-pulse-metric-value'>{_avg_pressure:.0f}<span style='font-size:12px;color:#888;'>/100</span></div>
                        </div>
                        <div class='market-pulse-metric'>
                            <div class='market-pulse-metric-label'>CMF متوسط</div>
                            <div class='market-pulse-metric-value' style='color:{_cmf_c};'>{_avg_cmf:+.3f}</div>
                        </div>
                        <div class='market-pulse-metric'>
                            <div class='market-pulse-metric-label'>تجميع قوي 🔵🟢</div>
                            <div class='market-pulse-metric-value' style='color:#00E676;'>{_n_strong_late} <span style='font-size:12px;color:#888;'>سهم</span></div>
                        </div>
                        <div class='market-pulse-metric'>
                            <div class='market-pulse-metric-label'>تصريف 🔴</div>
                            <div class='market-pulse-metric-value' style='color:#FF5252;'>{_n_dist} <span style='font-size:12px;color:#888;'>سهم</span></div>
                        </div>
                    </div>
                    <div class='{_verdict_cls}'>{_verdict}</div>
                    <div style='text-align:center; font-size:11px; color:#555; margin-top:6px;'>
                        إجمالي: {_total_all} سهم | تجميع: {_n_accum} | محايد: {_n_neutral} | تصريف: {_n_dist}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # ═══════════════════════════════════════════
                # 📈 مؤشر اتساع السوق — Breadth Index (QAFAH-Style)
                # ═══════════════════════════════════════════
                if "السعودي" in market_choice or "الأمريكي" in market_choice:
                    try:
                        _br_col1, _br_col2 = st.columns(2)
                        with _br_col1:
                            _br_window = st.radio(
                                "📐 النافذة الأساسية",
                                options=[3, 4, 10, 15],
                                index=1,
                                horizontal=True,
                                key="breadth_window",
                            )
                        with _br_col2:
                            _br_period_map = {"1 يوم": 1, "5 أيام": 5, "10 أيام": 10}
                            _br_period_lbl = st.radio(
                                "📅 فترة القياس",
                                options=list(_br_period_map.keys()),
                                index=0,
                                horizontal=True,
                                key="breadth_period",
                            )
                            _br_lookback = _br_period_map[_br_period_lbl]

                        _breadth_tickers = tuple(SAUDI_NAMES.keys()) if "السعودي" in market_choice else tuple(US_NAMES.keys())
                        _breadth_market_name = "السعودي" if "السعودي" in market_choice else "الأمريكي"
                        with st.spinner(f"📈 جاري حساب مؤشر اتساع السوق {_breadth_market_name}..."):
                            _br_closes = fetch_breadth_closes(_breadth_tickers, period="6mo")

                        if not _br_closes.empty and len(_br_closes) > 20:
                            _br_data = compute_market_breadth(
                                _br_closes,
                                lookback=_br_lookback,
                                base_window=_br_window,
                                band_period=5,
                            )
                            _br_stats = get_breadth_stats(_br_closes)

                            if not _br_data.empty:
                                # ── Plotly Breadth Chart ──
                                _br_fig = go.Figure()

                                # Fill between High and Low bands
                                _br_fig.add_trace(go.Scatter(
                                    x=_br_data.index, y=_br_data["high"],
                                    mode="lines", line=dict(width=0),
                                    showlegend=False, hoverinfo="skip",
                                ))
                                _br_fig.add_trace(go.Scatter(
                                    x=_br_data.index, y=_br_data["low"],
                                    mode="lines", line=dict(width=0),
                                    fill="tonexty",
                                    fillcolor="rgba(0,210,255,0.07)",
                                    showlegend=False, hoverinfo="skip",
                                ))

                                # Low Band line
                                _br_fig.add_trace(go.Scatter(
                                    x=_br_data.index, y=_br_data["low"],
                                    mode="lines",
                                    name=f"Low {5} {_br_window}",
                                    line=dict(color="rgba(0,230,118,0.5)", width=1, dash="dot"),
                                ))

                                # High Band line
                                _br_fig.add_trace(go.Scatter(
                                    x=_br_data.index, y=_br_data["high"],
                                    mode="lines",
                                    name=f"High {5} {_br_window}",
                                    line=dict(color="rgba(255,82,82,0.5)", width=1, dash="dot"),
                                ))

                                # Main Breadth Line
                                _br_fig.add_trace(go.Scatter(
                                    x=_br_data.index, y=_br_data["breadth"],
                                    mode="lines",
                                    name=f"MASA {_br_window}",
                                    line=dict(color="#00d2ff", width=2.5),
                                    hovertemplate="<b>%{x|%Y-%m-%d}</b><br>الاتساع: %{y:.1f}%<extra></extra>",
                                ))

                                # 50% equilibrium line
                                _br_fig.add_hline(
                                    y=50, line_dash="dash",
                                    line_color="rgba(255,255,255,0.2)", line_width=1,
                                    annotation_text="50% توازن",
                                    annotation_position="bottom right",
                                    annotation_font_color="rgba(255,255,255,0.3)",
                                    annotation_font_size=10,
                                )

                                _br_fig.update_layout(
                                    title=dict(
                                        text=f"📈 مؤشر اتساع السوق {_breadth_market_name} — MASA {_br_window} ({_br_period_lbl})",
                                        font=dict(size=16, color="#00d2ff"),
                                        x=0.5,
                                    ),
                                    height=400,
                                    margin=dict(l=10, r=10, t=50, b=10),
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(14,17,23,1)",
                                    xaxis=dict(
                                        gridcolor="rgba(255,255,255,0.05)",
                                        showgrid=True,
                                    ),
                                    yaxis=dict(
                                        title="نسبة الرابحين %",
                                        range=[0, 100],
                                        gridcolor="rgba(255,255,255,0.05)",
                                        showgrid=True,
                                    ),
                                    legend=dict(
                                        orientation="h",
                                        yanchor="bottom", y=1.02,
                                        xanchor="center", x=0.5,
                                        font=dict(size=11, color="#ccc"),
                                    ),
                                    font=dict(color="#ccc"),
                                    hovermode="x unified",
                                )

                                st.plotly_chart(_br_fig, use_container_width=True)

                                # ── Breadth Stats Row ──
                                _w1 = _br_stats.get("winners_1d", 0)
                                _l1 = _br_stats.get("losers_1d", 0)
                                _w5 = _br_stats.get("winners_5d", 0)
                                _l5 = _br_stats.get("losers_5d", 0)
                                _w10 = _br_stats.get("winners_10d", 0)
                                _l10 = _br_stats.get("losers_10d", 0)
                                _br_total = _br_stats.get("total", 0)

                                # Current breadth value for verdict
                                _br_now = _br_data["breadth"].iloc[-1] if len(_br_data) > 0 else 50

                                if _br_now >= 65:
                                    _br_verdict = "🟢 السوق في اتساع — أغلب الأسهم رابحة"
                                    _br_v_cls = "breadth-verdict-bull"
                                elif _br_now >= 50:
                                    _br_verdict = "🟡 السوق متوازن — ميل إيجابي"
                                    _br_v_cls = "breadth-verdict-mid"
                                elif _br_now >= 35:
                                    _br_verdict = "🟠 السوق ضعيف — أغلب الأسهم خاسرة"
                                    _br_v_cls = "breadth-verdict-warn"
                                else:
                                    _br_verdict = "🔴 السوق في انكماش — بيع واسع"
                                    _br_v_cls = "breadth-verdict-bear"

                                st.markdown(f"""
                                <div class='breadth-chart-box'>
                                    <div class='breadth-stats-row'>
                                        <div class='breadth-stat-item'>
                                            <div class='breadth-stat-label'>🟢 رابحون 1 يوم</div>
                                            <div class='breadth-stat-value' style='color:#00E676;'>{_w1}<span class='breadth-stat-sub'>/{_br_total}</span></div>
                                        </div>
                                        <div class='breadth-stat-item'>
                                            <div class='breadth-stat-label'>🟢 رابحون 5 أيام</div>
                                            <div class='breadth-stat-value' style='color:#69F0AE;'>{_w5}<span class='breadth-stat-sub'>/{_br_total}</span></div>
                                        </div>
                                        <div class='breadth-stat-item'>
                                            <div class='breadth-stat-label'>🔴 خاسرون 1 يوم</div>
                                            <div class='breadth-stat-value' style='color:#FF5252;'>{_l1}<span class='breadth-stat-sub'>/{_br_total}</span></div>
                                        </div>
                                        <div class='breadth-stat-item'>
                                            <div class='breadth-stat-label'>🔴 خاسرون 5 أيام</div>
                                            <div class='breadth-stat-value' style='color:#FF8A80;'>{_l5}<span class='breadth-stat-sub'>/{_br_total}</span></div>
                                        </div>
                                    </div>
                                    <div class='{_br_v_cls}'>{_br_verdict} — الاتساع الآن: {_br_now:.1f}%</div>
                                </div>
                                """, unsafe_allow_html=True)

                    except Exception as _br_err:
                        st.caption(f"⚠️ مؤشر الاتساع غير متاح: {_br_err}")

                st.markdown("<br>", unsafe_allow_html=True)

                # Backtest win rates for card display
                _bt_rates = st.session_state.get('bt_win_rates', {})

                # ── Section 1: Late accumulation (ready to launch)
                df_late = df_accum[df_accum['accum_phase'] == 'late'].sort_values(['confidence_stars', 'accum_score'], ascending=[False, False])
                if not df_late.empty:
                    st.markdown(
                        "<h4 style='color:#00E676; margin-top:20px;'>"
                        "🟢 نهاية التجميع — جاهز للانطلاق</h4>",
                        unsafe_allow_html=True
                    )
                    cards_html = "<div class='accum-container'>"
                    for _, row in df_late.iterrows():
                        cards_html += _build_accum_card(row, currency, bt_win_rates=_bt_rates)
                    cards_html += "</div>"
                    st.markdown(cards_html, unsafe_allow_html=True)

                # ── Section 1b: Pullback Buy (healthy retest — second chance!)
                df_pb_buy = df_accum[df_accum['accum_phase'] == 'pullback_buy'].sort_values(['confidence_stars', 'accum_score'], ascending=[False, False])
                if not df_pb_buy.empty:
                    st.markdown(
                        "<h4 style='color:#4CAF50; margin-top:20px;'>"
                        "🟢 ارتداد صحي — فرصة دخول ثانية!</h4>"
                        "<p style='color:#888; font-size:13px; margin-top:-8px;'>"
                        "أسهم انطلقت بعد تجميع وتراجعت بشكل صحي — المؤسسات لسّى داخلة</p>",
                        unsafe_allow_html=True
                    )
                    cards_html = "<div class='accum-container'>"
                    for _, row in df_pb_buy.iterrows():
                        cards_html += _build_accum_card(row, currency, bt_win_rates=_bt_rates)
                    cards_html += "</div>"
                    st.markdown(cards_html, unsafe_allow_html=True)

                # ── Section 1c: Active Breakout
                df_bo = df_accum[df_accum['accum_phase'] == 'breakout'].sort_values(['confidence_stars', 'accum_score'], ascending=[False, False])
                if not df_bo.empty:
                    st.markdown(
                        "<h4 style='color:#FF9800; margin-top:20px;'>"
                        "🚀 انطلاق نشط — كسر بعد تجميع</h4>"
                        "<p style='color:#888; font-size:13px; margin-top:-8px;'>"
                        "أسهم في مرحلة الانطلاق الآن — اللحاق محفوف بالمخاطر</p>",
                        unsafe_allow_html=True
                    )
                    cards_html = "<div class='accum-container'>"
                    for _, row in df_bo.iterrows():
                        cards_html += _build_accum_card(row, currency, bt_win_rates=_bt_rates)
                    cards_html += "</div>"
                    st.markdown(cards_html, unsafe_allow_html=True)

                # ── Section 2: Strong accumulation
                df_strong = df_accum[df_accum['accum_phase'] == 'strong'].sort_values(['confidence_stars', 'accum_score'], ascending=[False, False])
                if not df_strong.empty:
                    st.markdown(
                        "<h4 style='color:#2196F3; margin-top:20px;'>"
                        "🔵 تجميع قوي — ضغط شرائي مستمر</h4>",
                        unsafe_allow_html=True
                    )
                    cards_html = "<div class='accum-container'>"
                    for _, row in df_strong.iterrows():
                        cards_html += _build_accum_card(row, currency, bt_win_rates=_bt_rates)
                    cards_html += "</div>"
                    st.markdown(cards_html, unsafe_allow_html=True)

                # ── Section 3: Early + Mid (table)
                df_early_mid = df_accum[
                    df_accum['accum_phase'].isin(['early', 'mid'])
                ].sort_values(['confidence_stars', 'accum_score'], ascending=[False, False])
                if not df_early_mid.empty:
                    st.markdown(
                        "<h4 style='color:#CE93D8; margin-top:20px;'>"
                        "🟣🟡 المراحل المبكرة والمتوسطة</h4>",
                        unsafe_allow_html=True
                    )
                    table_html = (
                        "<table class='whale-table'><thead><tr>"
                        "<th>الأصل</th><th>الثقة ⭐</th><th>المرحلة</th><th>السكور</th>"
                        "<th>CMF</th><th>أيام التراكم</th>"
                        "<th>الضغط ⚡</th><th>وولف 🐺</th><th>MASA</th>"
                        "</tr></thead><tbody>"
                    )
                    for _, row in df_early_mid.iterrows():
                        ph = row.get('accum_phase', 'neutral')
                        ph_label = sanitize_text(row.get('accum_phase_label', ''))
                        ph_color = row.get('accum_phase_color', '#888')
                        cmf_val = row.get('accum_cmf', 0)
                        cmf_c = "#00E676" if cmf_val > 0 else "#FF5252"
                        pr_val = row.get('accum_pressure', 0)
                        pr_c = "#f44336" if pr_val >= 80 else "#FF9800" if pr_val >= 50 else "#4CAF50"
                        wr_val = row.get('wolf_readiness', 0)
                        wr_c = "#00E676" if wr_val >= 7 else "#FF9800" if wr_val >= 5 else "#FF5252"
                        _row_stars = row.get('confidence_stars', 0)
                        _row_stars_display = "⭐" * _row_stars + "☆" * (5 - _row_stars)
                        _row_stars_color = "#00E676" if _row_stars >= 4 else "#69F0AE" if _row_stars >= 3 else "#FFD700" if _row_stars >= 2 else "#FF5252"
                        table_html += (
                            f"<tr>"
                            f"<td style='color:white; font-weight:bold;'>{sanitize_text(str(row['الشركة']))}</td>"
                            f"<td style='color:{_row_stars_color}; font-weight:bold; font-size:12px;'>{_row_stars_display} {_row_stars}/5</td>"
                            f"<td><span class='accum-phase-badge accum-phase-{ph}'>{ph_label}</span></td>"
                            f"<td style='color:{ph_color}; font-weight:bold;'>{row.get('accum_score', 0):.0f}/100</td>"
                            f"<td style='color:{cmf_c};'>{cmf_val:+.3f}</td>"
                            f"<td>{row.get('accum_days', 0)} يوم</td>"
                            f"<td style='color:{pr_c}; font-weight:bold;'>{pr_val:.0f}</td>"
                            f"<td style='color:{wr_c}; font-weight:bold;'>{wr_val}/9</td>"
                            f"<td style='font-weight:bold;'>{row.get('raw_score', 0)}/100</td>"
                            f"</tr>"
                        )
                    table_html += "</tbody></table>"
                    st.markdown(table_html, unsafe_allow_html=True)

                # ── Section 3b: Pullback Wait (uncertain)
                df_pb_wait = df_accum[df_accum['accum_phase'] == 'pullback_wait'].sort_values(['confidence_stars', 'accum_score'], ascending=[False, False])
                if not df_pb_wait.empty:
                    st.markdown(
                        "<h4 style='color:#FFC107; margin-top:20px;'>"
                        "🟡 ارتداد — انتظر التأكيد</h4>",
                        unsafe_allow_html=True
                    )
                    cards_html = "<div class='accum-container'>"
                    for _, row in df_pb_wait.iterrows():
                        cards_html += _build_accum_card(row, currency, bt_win_rates=_bt_rates)
                    cards_html += "</div>"
                    st.markdown(cards_html, unsafe_allow_html=True)

                # ── Section 3c: Exhausted (opportunity gone)
                df_exhaust = df_accum[df_accum['accum_phase'] == 'exhausted'].sort_values(['confidence_stars', 'accum_score'], ascending=[False, False])
                if not df_exhaust.empty:
                    st.markdown(
                        "<h4 style='color:#E91E63; margin-top:20px;'>"
                        "🔴 استنفاد — الفرصة انتهت</h4>"
                        "<p style='color:#888; font-size:13px; margin-top:-8px;'>"
                        "أسهم انطلقت وأعادت معظم حركتها — لا تدخل</p>",
                        unsafe_allow_html=True
                    )
                    cards_html = "<div class='accum-container'>"
                    for _, row in df_exhaust.iterrows():
                        cards_html += _build_accum_card(row, currency, bt_win_rates=_bt_rates)
                    cards_html += "</div>"
                    st.markdown(cards_html, unsafe_allow_html=True)

                # ── Section 4: Distribution warning
                df_dist = df_accum[df_accum['accum_phase'] == 'distribute'].sort_values('accum_cmf', ascending=True)
                if not df_dist.empty:
                    st.markdown(
                        "<h4 style='color:#FF5252; margin-top:20px;'>"
                        "🔴 تحذير: أسهم في مرحلة التصريف</h4>",
                        unsafe_allow_html=True
                    )
                    dist_html = (
                        "<table class='whale-table whale-dist'><thead><tr>"
                        "<th>الأصل</th><th>CMF</th><th>OBV Slope</th>"
                        "<th>الضغط ⚡</th><th>MASA</th><th>الحالة</th>"
                        "</tr></thead><tbody>"
                    )
                    for _, row in df_dist.iterrows():
                        pr_val = row.get('accum_pressure', 0)
                        dist_html += (
                            f"<tr>"
                            f"<td style='color:white; font-weight:bold;'>{sanitize_text(str(row['الشركة']))}</td>"
                            f"<td style='color:#FF5252;'>{row.get('accum_cmf', 0):+.3f}</td>"
                            f"<td style='color:#FF5252;'>{row.get('accum_obv_slope', 0):+.4f}</td>"
                            f"<td style='color:#FF5252; font-weight:bold;'>{pr_val:.0f}</td>"
                            f"<td>{row.get('raw_score', 0)}/100</td>"
                            f"<td>{row.get('الحالة اللحظية ⚡', '')}</td>"
                            f"</tr>"
                        )
                    dist_html += "</tbody></table>"
                    st.markdown(dist_html, unsafe_allow_html=True)

            else:
                st.markdown(
                    "<div class='empty-box'>⚪ لم يتم اكتشاف أي نمط تجميع في هذا المسح.</div>",
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                "<div class='empty-box'>📭 اضغط على استخراج الفرص أولاً.</div>",
                unsafe_allow_html=True
            )
    # ===========================================================
    # TAB: Live Signal Tracker
    # ===========================================================
    with tab_signal_log:
        st.markdown(
            "<h3 style='text-align:center; color:#2196F3;'>"
            "📋 سجل الإشارات الحي — Live Signal Tracker</h3>"
            "<p style='text-align:center; color:#666; font-size:13px;'>"
            "يسجل إشارات التجميع والتصريف تلقائياً ويتابع نتائجها بعد 5/10/20 يوم</p>",
            unsafe_allow_html=True
        )

        _sl_total = get_signal_count()

        if _sl_total == 0:
            st.info(
                "📋 السجل فارغ — شغّل سكان السوق وسيتم تسجيل الإشارات تلقائياً.\n\n"
                "كل إشارة تجميع أو تصريف تُسجل مع سعر الدخول، "
                "ثم تُتابع نتيجتها بعد 5 و 10 و 20 يوم تداول."
            )
        else:
            # ── Action bar + Filters ──
            _sl_col1, _sl_col2, _sl_col3, _sl_col4 = st.columns([1.5, 1.5, 1.5, 1.5])
            with _sl_col1:
                _sl_update_btn = st.button("🔄 تحديث النتائج", type="primary", use_container_width=True)
            with _sl_col2:
                _sl_phase_opts = ["الكل", "early", "mid", "strong", "late", "distribute"]
                _sl_phase = st.selectbox("المرحلة:", _sl_phase_opts, key="sl_phase_filter")
            with _sl_col3:
                _sl_v2_opts = ["الكل", "buy_confirmed", "buy_breakout", "sell_confirmed", "sell_warning", "watch"]
                _sl_v2 = st.selectbox("إشارة V2:", _sl_v2_opts, key="sl_v2_filter")
            with _sl_col4:
                _sl_mkt_opts = ["الكل", "السعودي", "الأمريكي"]
                _sl_mkt = st.selectbox("السوق:", _sl_mkt_opts, key="sl_mkt_filter")

            # Handle update button
            if _sl_update_btn:
                with st.spinner("📡 جاري تحديث أسعار المتابعة..."):
                    _n_updated = update_signal_outcomes(max_signals=50)
                if _n_updated > 0:
                    st.success(f"✅ تم تحديث {_n_updated} إشارة")
                else:
                    st.info("ℹ️ لا توجد إشارات تحتاج تحديث حالياً")

            # ── Summary Stats ──
            _sl_stats = compute_signal_stats(
                phase_filter=_sl_phase if _sl_phase != "الكل" else None,
                v2_filter=_sl_v2 if _sl_v2 != "الكل" else None,
                market_filter=_sl_mkt if _sl_mkt != "الكل" else None,
            )

            _sl_m1, _sl_m2, _sl_m3, _sl_m4 = st.columns(4)
            _sl_m1.metric("📊 إجمالي الإشارات", _sl_stats['total'])
            _ov = _sl_stats['overall']
            _sl_m2.metric("✅ نجاح 5 أيام", f"{_ov['win_5d']:.1f}%" if _ov['n_5d'] > 0 else "—", f"n={_ov['n_5d']}")
            _sl_m3.metric("✅ نجاح 10 أيام", f"{_ov['win_10d']:.1f}%" if _ov['n_10d'] > 0 else "—", f"n={_ov['n_10d']}")
            _sl_m4.metric("✅ نجاح 20 يوم", f"{_ov['win_20d']:.1f}%" if _ov['n_20d'] > 0 else "—", f"n={_ov['n_20d']}")

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Win Rate Breakdown by V2 Signal ──
            if _sl_stats['by_v2']:
                _v2_labels_map = {
                    'buy_confirmed': '🟢 شراء مؤكد', 'buy_breakout': '🔵 كسر مؤكد',
                    'sell_confirmed': '🔴 بيع مؤكد', 'sell_warning': '🟠 تحذير تصريف',
                    'watch': '👁️ مراقبة', 'phase_early': '⚪ مبكر',
                    'phase_mid': '🟡 متوسط', 'phase_strong': '🔵 قوي',
                    'phase_late': '🟢 نهاية', 'phase_distribute': '🔴 تصريف',
                }

                _v2_rows = ""
                for _sig, _sdata in sorted(_sl_stats['by_v2'].items(), key=lambda x: x[1]['count'], reverse=True):
                    _lbl = _v2_labels_map.get(_sig, _sig)
                    _c = _sdata['count']
                    _w5 = f"{_sdata['win_5d']:.0f}%" if _sdata.get('n_5d', 0) > 0 else "—"
                    _w10 = f"{_sdata['win_10d']:.0f}%" if _sdata.get('n_10d', 0) > 0 else "—"
                    _w20 = f"{_sdata['win_20d']:.0f}%" if _sdata.get('n_20d', 0) > 0 else "—"

                    # Color based on 20d win rate
                    _wr20 = _sdata.get('win_20d', 0)
                    _row_bg = "rgba(0,230,118,0.06)" if _wr20 >= 60 else "rgba(255,82,82,0.06)" if _wr20 > 0 and _wr20 < 50 else "transparent"

                    _v2_rows += (
                        f"<tr style='background:{_row_bg};'>"
                        f"<td style='text-align:right; padding:8px; font-weight:700;'>{_lbl}</td>"
                        f"<td style='text-align:center; padding:8px;'>{_c}</td>"
                        f"<td style='text-align:center; padding:8px;'>{_w5}</td>"
                        f"<td style='text-align:center; padding:8px;'>{_w10}</td>"
                        f"<td style='text-align:center; padding:8px; font-weight:700;'>{_w20}</td>"
                        f"</tr>"
                    )

                st.markdown(
                    "<div style='direction:rtl;'>"
                    "<h4 style='color:#aaa; margin:10px 0;'>📊 إحصائيات حسب نوع الإشارة</h4>"
                    "<table class='whale-table' style='width:100%; border-collapse:collapse;'>"
                    "<thead><tr>"
                    "<th style='text-align:right; padding:10px; color:#888; border-bottom:1px solid #333;'>الإشارة</th>"
                    "<th style='text-align:center; padding:10px; color:#888; border-bottom:1px solid #333;'>العدد</th>"
                    "<th style='text-align:center; padding:10px; color:#888; border-bottom:1px solid #333;'>5 أيام</th>"
                    "<th style='text-align:center; padding:10px; color:#888; border-bottom:1px solid #333;'>10 أيام</th>"
                    "<th style='text-align:center; padding:10px; color:#888; border-bottom:1px solid #333;'>20 يوم</th>"
                    "</tr></thead>"
                    f"<tbody>{_v2_rows}</tbody>"
                    "</table></div>",
                    unsafe_allow_html=True
                )

            # ── Win Rate by Phase ──
            if _sl_stats['by_phase']:
                _phase_labels_map = {
                    'early': '⚪ مبكر', 'mid': '🟡 متوسط', 'strong': '🔵 قوي',
                    'late': '🟢 نهاية', 'distribute': '🔴 تصريف',
                }
                _ph_rows = ""
                for _ph, _pdata in sorted(_sl_stats['by_phase'].items(), key=lambda x: x[1]['count'], reverse=True):
                    _lbl = _phase_labels_map.get(_ph, _ph)
                    _c = _pdata['count']
                    _w5 = f"{_pdata['win_5d']:.0f}%" if _pdata.get('n_5d', 0) > 0 else "—"
                    _w10 = f"{_pdata['win_10d']:.0f}%" if _pdata.get('n_10d', 0) > 0 else "—"
                    _w20 = f"{_pdata['win_20d']:.0f}%" if _pdata.get('n_20d', 0) > 0 else "—"
                    _ph_rows += (
                        f"<tr>"
                        f"<td style='text-align:right; padding:8px; font-weight:700;'>{_lbl}</td>"
                        f"<td style='text-align:center; padding:8px;'>{_c}</td>"
                        f"<td style='text-align:center; padding:8px;'>{_w5}</td>"
                        f"<td style='text-align:center; padding:8px;'>{_w10}</td>"
                        f"<td style='text-align:center; padding:8px; font-weight:700;'>{_w20}</td>"
                        f"</tr>"
                    )
                st.markdown(
                    "<div style='direction:rtl; margin-top:20px;'>"
                    "<h4 style='color:#aaa; margin:10px 0;'>🏗️ إحصائيات حسب المرحلة</h4>"
                    "<table class='whale-table' style='width:100%; border-collapse:collapse;'>"
                    "<thead><tr>"
                    "<th style='text-align:right; padding:10px; color:#888; border-bottom:1px solid #333;'>المرحلة</th>"
                    "<th style='text-align:center; padding:10px; color:#888; border-bottom:1px solid #333;'>العدد</th>"
                    "<th style='text-align:center; padding:10px; color:#888; border-bottom:1px solid #333;'>5 أيام</th>"
                    "<th style='text-align:center; padding:10px; color:#888; border-bottom:1px solid #333;'>10 أيام</th>"
                    "<th style='text-align:center; padding:10px; color:#888; border-bottom:1px solid #333;'>20 يوم</th>"
                    "</tr></thead>"
                    f"<tbody>{_ph_rows}</tbody>"
                    "</table></div>",
                    unsafe_allow_html=True
                )

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Signal Log Table ──
            st.markdown("<h4 style='color:#aaa;'>📋 سجل الإشارات</h4>", unsafe_allow_html=True)
            _sl_df = get_signal_log_df(
                phase_filter=_sl_phase if _sl_phase != "الكل" else None,
                v2_filter=_sl_v2 if _sl_v2 != "الكل" else None,
                market_filter=_sl_mkt if _sl_mkt != "الكل" else None,
            )
            if not _sl_df.empty:
                st.dataframe(_sl_df, use_container_width=True, hide_index=True, height=400)
            else:
                st.info("لا توجد إشارات تطابق الفلاتر المحددة.")

            # ── Status Bar ──
            st.markdown(
                f"<div style='text-align:center; margin:15px 0; font-size:12px; color:#555;'>"
                f"📊 {_sl_stats['total']} إشارة مسجلة | "
                f"🔄 {_sl_stats['active']} نشطة | "
                f"✅ {_sl_stats['completed']} مكتملة"
                f"</div>",
                unsafe_allow_html=True
            )

            # ── Danger Zone ──
            with st.expander("⚠️ منطقة الخطر"):
                st.warning("مسح السجل سيحذف جميع الإشارات المسجلة. هذا الإجراء لا يمكن التراجع عنه.")
                if st.button("🗑️ مسح سجل الإشارات بالكامل", type="secondary"):
                    clear_signal_log()
                    st.success("✅ تم مسح سجل الإشارات")
                    st.rerun()
    # ===========================================================
    # TAB: Market Scanner
    # ===========================================================
    with tab_scan:
        if not df_loads.empty:
            df_ls = pd.DataFrame(df_loads).copy()
            try:
                # Build clean table like البيانات tab
                _scan_table = {}

                # Basic columns
                if 'الشركة' in df_ls.columns:
                    _scan_table['الشركة'] = df_ls['الشركة'].tolist()
                if 'التاريخ' in df_ls.columns:
                    _scan_table['التاريخ'] = df_ls['التاريخ'].tolist()
                if 'الاتجاه' in df_ls.columns:
                    _scan_table['الاتجاه'] = df_ls['الاتجاه'].tolist()

                # Format change columns with colors (same style as البيانات)
                for src_col, cat_col in [
                    (col_change_name, '1d_cat'),
                    (f'تراكمي 3 {lbl}', '3d_cat'),
                    (f'تراكمي 5 {lbl}', '5d_cat'),
                    (f'تراكمي 10 {lbl}', '10d_cat'),
                ]:
                    if src_col in df_ls.columns:
                        cat_series = df_ls.get(cat_col, pd.Series([""] * len(df_ls)))
                        _scan_table[src_col] = [
                            _format_cat(v, c) for v, c in zip(df_ls[src_col], cat_series)
                        ]

                # Status columns (حالة)
                for st_col in [f'حالة 3 {lbl}', f'حالة 5 {lbl}', f'حالة 10 {lbl}']:
                    if st_col in df_ls.columns:
                        _scan_table[st_col] = df_ls[st_col].tolist()

                _df_scan = pd.DataFrame(_scan_table)
                _df_scan = _df_scan.fillna('')

                _style_cols = [
                    c for c in [
                        col_change_name,
                        f'تراكمي 3 {lbl}', f'حالة 3 {lbl}',
                        f'تراكمي 5 {lbl}', f'حالة 5 {lbl}',
                        f'تراكمي 10 {lbl}', f'حالة 10 {lbl}',
                    ]
                    if c in _df_scan.columns
                ]
                if _style_cols:
                    st.dataframe(
                        _df_scan.style.map(safe_color_table, subset=_style_cols),
                        use_container_width=True, height=550,
                    )
                else:
                    st.dataframe(_df_scan, use_container_width=True, height=550)
            except Exception:
                st.dataframe(df_ls.astype(str), use_container_width=True, height=550)
        else:
            st.markdown(
                "<div class='empty-box'>📭 لا توجد بيانات للتحليل.</div>",
                unsafe_allow_html=True
            )
    # ===========================================================
    # TAB: Breakouts
    # ===========================================================
    with tab_breakouts:
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

    # ===========================================================
    # TAB: Alerts
    # ===========================================================
    with tab_alerts:
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

    # ===========================================================
    # TAB: Charts (merged)
    # ===========================================================
    with tab_chart:
        chart_view = st.radio("", ["📊 الشارت", "🌐 TradingView", "📋 البيانات"], horizontal=True, key="chart_view_radio")
        if chart_view == "📊 الشارت":
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
                height=600, template='plotly_dark', showlegend=False,
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
        elif chart_view == "🌐 TradingView":
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
                f'<div class="tradingview-widget-container" style="height:480px;width:100%">'
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
            components.html(tv_html, height=500)
        else:
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

    # ===========================================================
    # TAB: Tools (merged)
    # ===========================================================
    with tab_tools:
        with st.expander("📂 المراقبة", expanded=True):
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
        with st.expander("⏳ الباك تيست"):
            st.markdown(
                "<h3 style='text-align: center; color: #FFD700;'>"
                "🔬 اختبار رجعي — دقة إشارات التجميع والتصريف</h3>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='text-align:center; color:#888; font-size:13px; margin-top:-10px;'>"
                "يختبر دقة إشارات المنصة تاريخياً: كم إشارة نجحت فعلاً؟</p>",
                unsafe_allow_html=True,
            )

            # Determine tickers for current market
            if "السعودي" in market_choice:
                _bt_tickers = tuple(SAUDI_NAMES.keys())
                _bt_market_label = "السوق السعودي"
            elif "الأمريكي" in market_choice:
                _bt_tickers = tuple(US_NAMES.keys())
                _bt_market_label = "السوق الأمريكي"
            else:
                _bt_tickers = ()
                _bt_market_label = ""

            if not _bt_tickers:
                st.info("الباك تيست متاح فقط للأسهم (السعودي والأمريكي).")
            else:
                _bt_run = st.button("📊 شغّل الباك تيست", use_container_width=True, type="primary")

                if _bt_run:
                    with st.spinner("جاري تحليل الإشارات التاريخية + اتساع السوق... قد يستغرق 2-5 دقائق"):
                        _bt_signals = backtest_accumulation_signals(_bt_tickers, period="2y")

                    if _bt_signals.empty:
                        st.warning("لم يتم العثور على إشارات تاريخية كافية.")
                    else:
                        _bt_summary_all = compute_backtest_summary(_bt_signals, aligned_only=False)
                        _bt_summary_filtered = compute_backtest_summary(_bt_signals, aligned_only=True)
                        _bt_total_all = len(_bt_signals)
                        _bt_total_filtered = int(_bt_signals["aligned"].sum()) if "aligned" in _bt_signals.columns else _bt_total_all

                        # Store win rates for accumulation cards
                        st.session_state['bt_win_rates'] = {
                            phase: stats.get("headline_win", 0)
                            for phase, stats in _bt_summary_filtered.items()
                        }

                        _phase_labels = {
                            "late": ("نهاية تجميع", "🟢", "#00E676"),
                            "strong": ("تجميع قوي", "🔵", "#00d2ff"),
                            "distribute": ("تصريف", "🔴", "#FF5252"),
                        }

                        # ══════════════════════════════════════════════
                        # SECTION 1: COMPARISON — Before vs After Filter
                        # ══════════════════════════════════════════════
                        st.markdown(
                            "<div class='scanner-header-gray' style='margin-top:10px; background:linear-gradient(90deg, #1a1c24, #2d303e);'>"
                            "⚡ المقارنة: بدون فلتر vs مع فلتر اتساع السوق</div>",
                            unsafe_allow_html=True,
                        )

                        # Build comparison cards: each phase shows BEFORE → AFTER
                        _cmp_html = "<div class='backtest-cards-row'>"
                        for _ph_key, (_ph_label, _ph_icon, _ph_color) in _phase_labels.items():
                            _s_all = _bt_summary_all.get(_ph_key, {})
                            _s_flt = _bt_summary_filtered.get(_ph_key, {})
                            _win_all = _s_all.get("headline_win", 0)
                            _win_flt = _s_flt.get("headline_win", 0)
                            _avg_all = _s_all.get("headline_avg", 0)
                            _avg_flt = _s_flt.get("headline_avg", 0)
                            _cnt_all = _s_all.get("count", 0)
                            _cnt_flt = _s_flt.get("count", 0)
                            _delta_win = _win_flt - _win_all
                            _delta_sign = "+" if _delta_win > 0 else ""
                            _delta_color = "#00E676" if _delta_win > 0 else "#FF5252" if _delta_win < 0 else "#888"
                            _avg_flt_class = "backtest-win" if (_ph_key != "distribute" and _avg_flt > 0) or (_ph_key == "distribute" and _avg_flt < 0) else "backtest-lose"

                            _cmp_html += f"""
                            <div class='backtest-summary-card' style='border-top: 3px solid {_ph_color};'>
                                <div style='font-size:24px; margin-bottom:2px;'>{_ph_icon}</div>
                                <div style='font-size:14px; font-weight:700; color:{_ph_color};'>{_ph_label}</div>
                                <div style='display:flex; align-items:center; justify-content:center; gap:8px; margin:8px 0;'>
                                    <div style='text-align:center;'>
                                        <div style='font-size:11px; color:#666;'>بدون فلتر</div>
                                        <div style='font-size:22px; font-weight:700; color:#888;'>{_win_all}%</div>
                                        <div style='font-size:11px; color:#555;'>{_cnt_all} إشارة</div>
                                    </div>
                                    <div style='font-size:20px; color:#FFD700;'>→</div>
                                    <div style='text-align:center;'>
                                        <div style='font-size:11px; color:#FFD700;'>مع الفلتر</div>
                                        <div style='font-size:28px; font-weight:900; color:white;'>{_win_flt}%</div>
                                        <div style='font-size:11px; color:#888;'>{_cnt_flt} إشارة</div>
                                    </div>
                                </div>
                                <div style='color:{_delta_color}; font-size:14px; font-weight:700;'>{_delta_sign}{_delta_win:.1f}% تحسّن</div>
                                <div class='{_avg_flt_class}' style='font-size:13px; margin-top:4px;'>
                                    {"+" if _avg_flt > 0 else ""}{_avg_flt}% متوسط
                                </div>
                            </div>"""

                        # Total card
                        _cmp_html += f"""
                        <div class='backtest-summary-card' style='border-top: 3px solid #FFD700;'>
                            <div style='font-size:24px; margin-bottom:2px;'>📊</div>
                            <div style='font-size:14px; font-weight:700; color:#FFD700;'>إجمالي</div>
                            <div style='display:flex; align-items:center; justify-content:center; gap:8px; margin:8px 0;'>
                                <div style='text-align:center;'>
                                    <div style='font-size:11px; color:#666;'>بدون فلتر</div>
                                    <div style='font-size:22px; font-weight:700; color:#888;'>{_bt_total_all}</div>
                                </div>
                                <div style='font-size:20px; color:#FFD700;'>→</div>
                                <div style='text-align:center;'>
                                    <div style='font-size:11px; color:#FFD700;'>مع الفلتر</div>
                                    <div style='font-size:28px; font-weight:900; color:white;'>{_bt_total_filtered}</div>
                                </div>
                            </div>
                            <div style='font-size:13px; color:#aaa;'>{_bt_market_label}</div>
                            <div style='font-size:11px; color:#666; margin-top:2px;'>فترة: سنتين</div>
                        </div>"""
                        _cmp_html += "</div>"
                        st.markdown(_cmp_html, unsafe_allow_html=True)

                        # ══════════════════════════════════════════════
                        # SECTION 2: Filtered Period Win Rate Table
                        # ══════════════════════════════════════════════
                        st.markdown(
                            "<div class='scanner-header-gray' style='margin-top:25px;'>"
                            "📋 نسبة النجاح بعد الفلتر — حسب الفترة الزمنية</div>",
                            unsafe_allow_html=True,
                        )

                        _period_labels = {5: "5 أيام", 10: "10 أيام", 20: "20 يوم", 40: "40 يوم"}
                        _tbl = "<table class='whale-table' dir='rtl'><thead><tr>"
                        _tbl += "<th>المرحلة</th>"
                        for _d, _dl in _period_labels.items():
                            _tbl += f"<th>{_dl}</th>"
                        _tbl += "<th>العدد</th></tr></thead><tbody>"

                        for _ph_key, (_ph_label, _ph_icon, _ph_color) in _phase_labels.items():
                            _ph_stats = _bt_summary_filtered.get(_ph_key, {})
                            _periods = _ph_stats.get("periods", {})
                            _tbl += f"<tr><td style='color:{_ph_color}; font-weight:700;'>{_ph_icon} {_ph_label}</td>"
                            for _d in [5, 10, 20, 40]:
                                _p = _periods.get(_d, {})
                                _wr = _p.get("win_rate", 0)
                                _ar = _p.get("avg_return", 0)
                                _wr_color = "#00E676" if _wr >= 60 else "#FFD700" if _wr >= 50 else "#FF5252"
                                _tbl += f"<td><span style='color:{_wr_color}; font-weight:700;'>{_wr}%</span>"
                                _tbl += f"<br><span style='font-size:11px; color:#888;'>{'+'if _ar>0 else ''}{_ar}%</span></td>"
                            _ph_total = _ph_stats.get("count", 0)
                            _tbl += f"<td>{_ph_total}</td></tr>"

                        _tbl += "</tbody></table>"
                        st.markdown(_tbl, unsafe_allow_html=True)

                        # ══════════════════════════════════════════════
                        # SECTION 3: Profit Factor (Filtered)
                        # ══════════════════════════════════════════════
                        st.markdown(
                            "<div class='scanner-header-gray' style='margin-top:20px;'>"
                            "💰 معامل الربح بعد الفلتر (Profit Factor) — 20 يوم</div>",
                            unsafe_allow_html=True,
                        )
                        _pf_html = "<div style='display:flex; gap:15px; justify-content:center; flex-wrap:wrap; margin:15px 0;'>"
                        for _ph_key, (_ph_label, _ph_icon, _ph_color) in _phase_labels.items():
                            _ph_all = _bt_summary_all.get(_ph_key, {}).get("periods", {}).get(20, {})
                            _ph_flt = _bt_summary_filtered.get(_ph_key, {}).get("periods", {}).get(20, {})
                            _pf_old = _ph_all.get("profit_factor", 0)
                            _pf_new = _ph_flt.get("profit_factor", 0)
                            _best = _ph_flt.get("best", 0)
                            _worst = _ph_flt.get("worst", 0)
                            _pf_color = "#00E676" if _pf_new >= 1.5 else "#FFD700" if _pf_new >= 1.0 else "#FF5252"
                            _pf_html += f"""
                            <div style='background:#1a1c24; border:1px solid #2d303e; border-radius:10px;
                                        padding:15px 20px; text-align:center; min-width:150px;'>
                                <div style='color:{_ph_color}; font-weight:700; font-size:13px;'>{_ph_icon} {_ph_label}</div>
                                <div style='color:{_pf_color}; font-size:30px; font-weight:900; margin:8px 0;'>{_pf_new}x</div>
                                <div style='font-size:11px; color:#666;'>كان: <span style="color:#888">{_pf_old}x</span></div>
                                <div style='font-size:11px; color:#888; margin-top:4px;'>أفضل: <span style="color:#00E676">+{_best}%</span></div>
                                <div style='font-size:11px; color:#888;'>أسوأ: <span style="color:#FF5252">{_worst}%</span></div>
                            </div>"""
                        _pf_html += "</div>"
                        st.markdown(_pf_html, unsafe_allow_html=True)

                        # ══════════════════════════════════════════════
                        # SECTION 4: Histogram (Filtered late signals)
                        # ══════════════════════════════════════════════
                        _late_filtered = _bt_signals[(_bt_signals["phase"] == "late") & (_bt_signals["aligned"] == True)]
                        if not _late_filtered.empty and "ret_20d" in _late_filtered.columns:
                            _ret_20 = _late_filtered["ret_20d"].dropna()
                            if len(_ret_20) >= 3:
                                st.markdown(
                                    "<div class='scanner-header-gray' style='margin-top:20px;'>"
                                    "📈 توزيع العوائد بعد 20 يوم — نهاية تجميع (مع فلتر الاتساع)</div>",
                                    unsafe_allow_html=True,
                                )
                                _fig_hist = go.Figure()
                                _fig_hist.add_trace(go.Histogram(
                                    x=_ret_20.values,
                                    marker_color="#00d2ff",
                                    opacity=0.8,
                                    nbinsx=25,
                                    name="العائد %",
                                ))
                                _fig_hist.add_vline(x=0, line_dash="dash", line_color="#FFD700", line_width=2)
                                _fig_hist.add_vline(
                                    x=_ret_20.mean(), line_dash="dot",
                                    line_color="#00E676", line_width=2,
                                    annotation_text=f"المتوسط: {_ret_20.mean():.1f}%",
                                    annotation_font_color="#00E676",
                                )
                                _fig_hist.update_layout(
                                    template="plotly_dark",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    height=350,
                                    margin=dict(l=40, r=20, t=30, b=40),
                                    xaxis_title="العائد %",
                                    yaxis_title="عدد الإشارات",
                                    showlegend=False,
                                    bargap=0.05,
                                )
                                st.plotly_chart(_fig_hist, use_container_width=True)

                        # ══════════════════════════════════════════════
                        # SECTION 5: Last 30 Aligned Signals
                        # ══════════════════════════════════════════════
                        st.markdown(
                            "<div class='scanner-header-gray' style='margin-top:20px;'>"
                            "📋 آخر 30 إشارة متوافقة مع اتجاه السوق</div>",
                            unsafe_allow_html=True,
                        )
                        _aligned_signals = _bt_signals[_bt_signals["aligned"] == True] if "aligned" in _bt_signals.columns else _bt_signals
                        _display_cols = ["stock", "date", "phase", "score", "cmf", "breadth", "entry_price"]
                        _display_cols = [c for c in _display_cols if c in _aligned_signals.columns]
                        for _d in [5, 10, 20, 40]:
                            _col_name = f"ret_{_d}d"
                            if _col_name in _aligned_signals.columns:
                                _display_cols.append(_col_name)

                        _df_display = _aligned_signals[_display_cols].head(30).copy()
                        _rename_map = {
                            "stock": "السهم", "date": "التاريخ", "phase": "المرحلة",
                            "score": "السكور", "cmf": "CMF", "breadth": "الاتساع",
                            "entry_price": "سعر الدخول",
                            "ret_5d": "عائد 5د", "ret_10d": "عائد 10د",
                            "ret_20d": "عائد 20د", "ret_40d": "عائد 40د",
                        }
                        _df_display = _df_display.rename(columns=_rename_map)

                        _phase_map = {"late": "نهاية تجميع 🟢", "strong": "تجميع قوي 🔵", "distribute": "تصريف 🔴"}
                        if "المرحلة" in _df_display.columns:
                            _df_display["المرحلة"] = _df_display["المرحلة"].map(_phase_map).fillna(_df_display["المرحلة"])
                        if "التاريخ" in _df_display.columns:
                            _df_display["التاريخ"] = pd.to_datetime(_df_display["التاريخ"]).dt.strftime("%Y-%m-%d")

                        st.dataframe(_df_display, use_container_width=True, height=500, hide_index=True)
        with st.expander("📊 تقرير الاستراتيجيات"):
            st.markdown(
                "<h3 style='text-align: center; color: #FFD700;'>"
                "📊 تقرير باك تيست: زيرو انعكاس + السماء الزرقاء</h3>",
                unsafe_allow_html=True,
            )

            import json as _json
            _bt_report_path = os.path.join(os.path.dirname(__file__), "backtest_report.json")
            if os.path.exists(_bt_report_path):
                try:
                    with open(_bt_report_path, 'r', encoding='utf-8') as _f:
                        _report = _json.load(_f)

                    st.markdown(
                        f"<p style='text-align:center; color:#888;'>الفترة: {_report.get('period','')} | "
                        f"السوق: {_report.get('market','')}</p>",
                        unsafe_allow_html=True,
                    )

                    # ── Summary Cards ──
                    _zr = _report.get('zr_reversal', {}).get('metrics', {})
                    _bs = _report.get('blue_sky', {}).get('metrics', {})
                    _cb = _report.get('combined', {}).get('metrics', {})

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        _pf_zr = _zr.get('profit_factor', 0)
                        _rating_zr = "⭐⭐⭐" if _pf_zr >= 2.0 else "⭐⭐" if _pf_zr >= 1.5 else "⭐" if _pf_zr >= 1.0 else "❌"
                        st.markdown(
                            f"<div style='background:linear-gradient(135deg,#1a1a3e,#0d0d2b);border:1px solid #4a90d9;"
                            f"border-radius:12px;padding:18px;text-align:center;'>"
                            f"<h4 style='color:#4a90d9;margin:0;'>🔄 زيرو انعكاس</h4>"
                            f"<p style='font-size:28px;color:#FFD700;margin:8px 0;'>{_zr.get('win_rate',0):.1f}%</p>"
                            f"<p style='color:#aaa;margin:2px 0;'>نسبة النجاح</p>"
                            f"<p style='color:#fff;margin:5px 0;'>PF: {_pf_zr:.2f} | العائد: {_zr.get('total_return',0):+.1f}%</p>"
                            f"<p style='margin:5px 0;'>{_rating_zr}</p>"
                            f"<p style='color:#888;font-size:12px;'>{_zr.get('total_trades',0)} صفقة</p>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    with c2:
                        _pf_bs = _bs.get('profit_factor', 0)
                        _rating_bs = "⭐⭐⭐" if _pf_bs >= 2.0 else "⭐⭐" if _pf_bs >= 1.5 else "⭐" if _pf_bs >= 1.0 else "❌"
                        st.markdown(
                            f"<div style='background:linear-gradient(135deg,#1a3e1a,#0d2b0d);border:1px solid #00E676;"
                            f"border-radius:12px;padding:18px;text-align:center;'>"
                            f"<h4 style='color:#00E676;margin:0;'>🌌 السماء الزرقاء</h4>"
                            f"<p style='font-size:28px;color:#FFD700;margin:8px 0;'>{_bs.get('win_rate',0):.1f}%</p>"
                            f"<p style='color:#aaa;margin:2px 0;'>نسبة النجاح</p>"
                            f"<p style='color:#fff;margin:5px 0;'>PF: {_pf_bs:.2f} | العائد: {_bs.get('total_return',0):+.1f}%</p>"
                            f"<p style='margin:5px 0;'>{_rating_bs}</p>"
                            f"<p style='color:#888;font-size:12px;'>{_bs.get('total_trades',0)} صفقة</p>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    with c3:
                        _pf_cb = _cb.get('profit_factor', 0)
                        _rating_cb = "⭐⭐⭐" if _pf_cb >= 2.0 else "⭐⭐" if _pf_cb >= 1.5 else "⭐" if _pf_cb >= 1.0 else "❌"
                        st.markdown(
                            f"<div style='background:linear-gradient(135deg,#3e3e1a,#2b2b0d);border:1px solid #FFD700;"
                            f"border-radius:12px;padding:18px;text-align:center;'>"
                            f"<h4 style='color:#FFD700;margin:0;'>💼 المحفظة المدمجة</h4>"
                            f"<p style='font-size:28px;color:#FFD700;margin:8px 0;'>{_cb.get('win_rate',0):.1f}%</p>"
                            f"<p style='color:#aaa;margin:2px 0;'>نسبة النجاح</p>"
                            f"<p style='color:#fff;margin:5px 0;'>PF: {_pf_cb:.2f} | العائد: {_cb.get('total_return',0):+.1f}%</p>"
                            f"<p style='margin:5px 0;'>{_rating_cb}</p>"
                            f"<p style='color:#888;font-size:12px;'>{_cb.get('total_trades',0)} صفقة</p>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown("<br>", unsafe_allow_html=True)

                    # ── Detailed Comparison Table ──
                    st.markdown(
                        "<h4 style='color:#FFD700;text-align:center;'>📊 مقارنة الاستراتيجيات</h4>",
                        unsafe_allow_html=True,
                    )
                    _comp_rows = []
                    _metric_labels = [
                        ("إجمالي الصفقات", "total_trades"),
                        ("نسبة النجاح %", "win_rate"),
                        ("عامل الربح", "profit_factor"),
                        ("العائد الكلي %", "total_return"),
                        ("متوسط الصفقة %", "avg_pnl"),
                        ("أقصى تراجع %", "max_drawdown"),
                        ("متوسط الربح %", "avg_win"),
                        ("متوسط الخسارة %", "avg_loss"),
                        ("أفضل صفقة %", "best_trade"),
                        ("أسوأ صفقة %", "worst_trade"),
                        ("مدة الاحتفاظ (يوم)", "avg_hold_days"),
                    ]
                    for label, key in _metric_labels:
                        _comp_rows.append({
                            "المقياس": label,
                            "🔄 زيرو انعكاس": _zr.get(key, 0),
                            "🌌 السماء الزرقاء": _bs.get(key, 0),
                            "💼 المدمج": _cb.get(key, 0),
                        })
                    _comp_df = pd.DataFrame(_comp_rows).set_index("المقياس")
                    st.dataframe(_comp_df, use_container_width=True)

                    # ── Exit Analysis ──
                    st.markdown(
                        "<h4 style='color:#FFD700;text-align:center;'>🔬 تحليل أسباب الخروج</h4>",
                        unsafe_allow_html=True,
                    )
                    _exit_c1, _exit_c2 = st.columns(2)
                    with _exit_c1:
                        st.markdown("**🔄 زيرو انعكاس:**")
                        _exit_data_zr = {
                            "خروج": ["وقف خسارة (SL)", "جني أرباح (TP)", "انتهاء وقت"],
                            "العدد": [_zr.get("sl_exits", 0), _zr.get("tp_exits", 0), _zr.get("time_exits", 0)],
                        }
                        st.dataframe(pd.DataFrame(_exit_data_zr), use_container_width=True, hide_index=True)
                    with _exit_c2:
                        st.markdown("**🌌 السماء الزرقاء:**")
                        _exit_data_bs = {
                            "خروج": ["وقف خسارة (SL)", "جني أرباح (TP)", "انتهاء وقت", "رفض السقف"],
                            "العدد": [
                                _bs.get("sl_exits", 0), _bs.get("tp_exits", 0),
                                _bs.get("time_exits", 0), _bs.get("ceiling_reject_exits", 0),
                            ],
                        }
                        st.dataframe(pd.DataFrame(_exit_data_bs), use_container_width=True, hide_index=True)

                    # ── Yearly Breakdown ──
                    st.markdown(
                        "<h4 style='color:#FFD700;text-align:center;'>📅 الأداء السنوي</h4>",
                        unsafe_allow_html=True,
                    )
                    _yr_c1, _yr_c2 = st.columns(2)

                    _zr_yearly = _report.get('zr_reversal', {}).get('yearly', {})
                    _bs_yearly = _report.get('blue_sky', {}).get('yearly', {})

                    with _yr_c1:
                        st.markdown("**🔄 زيرو انعكاس:**")
                        if _zr_yearly:
                            _yr_rows_zr = []
                            for yr, yd in _zr_yearly.items():
                                _yr_rows_zr.append({
                                    "السنة": yr,
                                    "الصفقات": yd.get("trades", 0),
                                    "النجاح%": yd.get("win_rate", 0),
                                    "PF": yd.get("pf", 0),
                                    "العائد%": yd.get("return", 0),
                                })
                            st.dataframe(pd.DataFrame(_yr_rows_zr), use_container_width=True, hide_index=True)
                        else:
                            st.info("لا توجد بيانات سنوية")

                    with _yr_c2:
                        st.markdown("**🌌 السماء الزرقاء:**")
                        if _bs_yearly:
                            _yr_rows_bs = []
                            for yr, yd in _bs_yearly.items():
                                _yr_rows_bs.append({
                                    "السنة": yr,
                                    "الصفقات": yd.get("trades", 0),
                                    "النجاح%": yd.get("win_rate", 0),
                                    "PF": yd.get("pf", 0),
                                    "العائد%": yd.get("return", 0),
                                })
                            st.dataframe(pd.DataFrame(_yr_rows_bs), use_container_width=True, hide_index=True)
                        else:
                            st.info("لا توجد بيانات سنوية")

                    # ── Variant Comparison ──
                    st.markdown(
                        "<h4 style='color:#FFD700;text-align:center;'>🧪 تأثير الفلاتر</h4>",
                        unsafe_allow_html=True,
                    )
                    _var_c1, _var_c2 = st.columns(2)
                    _zr_vars = _report.get('zr_reversal', {}).get('variants', {})
                    _bs_vars = _report.get('blue_sky', {}).get('variants', {})

                    with _var_c1:
                        st.markdown("**🔄 زيرو انعكاس:**")
                        if _zr_vars:
                            _var_rows_zr = []
                            for vn, vd in _zr_vars.items():
                                _var_rows_zr.append({
                                    "الإصدار": vn,
                                    "الصفقات": vd.get("total_trades", 0),
                                    "النجاح%": vd.get("win_rate", 0),
                                    "PF": vd.get("profit_factor", 0),
                                    "العائد%": vd.get("total_return", 0),
                                })
                            st.dataframe(pd.DataFrame(_var_rows_zr), use_container_width=True, hide_index=True)

                    with _var_c2:
                        st.markdown("**🌌 السماء الزرقاء:**")
                        if _bs_vars:
                            _var_rows_bs = []
                            for vn, vd in _bs_vars.items():
                                _var_rows_bs.append({
                                    "الإصدار": vn,
                                    "الصفقات": vd.get("total_trades", 0),
                                    "النجاح%": vd.get("win_rate", 0),
                                    "PF": vd.get("profit_factor", 0),
                                    "العائد%": vd.get("total_return", 0),
                                })
                            st.dataframe(pd.DataFrame(_var_rows_bs), use_container_width=True, hide_index=True)

                    # ── Sample Trades ──
                    with st.expander("📋 عينة من الصفقات (آخر 20)", expanded=False):
                        _bs_samples = _report.get('blue_sky', {}).get('sample_trades', [])
                        _zr_samples = _report.get('zr_reversal', {}).get('sample_trades', [])
                        _all_samples = sorted(
                            _zr_samples + _bs_samples,
                            key=lambda x: str(x.get('entry_date', '')),
                            reverse=True,
                        )[:20]
                        if _all_samples:
                            _sample_rows = []
                            for t in _all_samples:
                                _sample_rows.append({
                                    "التاريخ": str(t.get('entry_date', ''))[:10],
                                    "السهم": t.get('ticker', ''),
                                    "الاستراتيجية": "🔄 زيرو" if t.get('strategy') == 'ZR_REVERSAL' else "🌌 سماء",
                                    "الدخول": t.get('entry_price', 0),
                                    "الخروج": t.get('exit_price', 0),
                                    "الربح%": t.get('pnl_pct', 0),
                                    "السبب": t.get('exit_reason', ''),
                                    "R:R": t.get('rr_ratio', 0),
                                })
                            st.dataframe(pd.DataFrame(_sample_rows), use_container_width=True, hide_index=True)

                    # ── Equity Curve Chart ──
                    _all_trades_for_chart = sorted(
                        _zr_samples + _bs_samples,
                        key=lambda x: str(x.get('entry_date', '')),
                    )
                    if _all_trades_for_chart:
                        _cum = 0
                        _cum_vals = []
                        _dates = []
                        for t in _all_trades_for_chart:
                            _cum += t.get('pnl_pct', 0)
                            _cum_vals.append(_cum)
                            _dates.append(str(t.get('entry_date', ''))[:10])

                        _fig_eq = go.Figure()
                        _fig_eq.add_trace(go.Scatter(
                            x=_dates, y=_cum_vals,
                            mode='lines+markers',
                            line=dict(color='#FFD700', width=2),
                            marker=dict(
                                color=['#00E676' if v >= 0 else '#FF5252' for v in [t.get('pnl_pct', 0) for t in _all_trades_for_chart]],
                                size=6,
                            ),
                            name='العائد التراكمي %',
                        ))
                        _fig_eq.update_layout(
                            title="📈 منحنى الأرباح التراكمي",
                            xaxis_title="التاريخ",
                            yaxis_title="العائد التراكمي %",
                            plot_bgcolor='#0e1117',
                            paper_bgcolor='#0e1117',
                            font=dict(color='white'),
                            height=400,
                        )
                        st.plotly_chart(_fig_eq, use_container_width=True)

                    st.markdown(
                        f"<p style='text-align:center;color:#555;font-size:12px;'>"
                        f"تم إنشاء التقرير: {_report.get('generated_at','')[:19]}</p>",
                        unsafe_allow_html=True,
                    )

                except Exception as e:
                    st.error(f"⚠️ خطأ في قراءة التقرير: {e}")
            else:
                st.info(
                    "📊 لم يتم إنشاء تقرير باك تيست بعد.\n\n"
                    "شغّل الأمر التالي لإنشاء التقرير:\n\n"
                    "`python zr_bluesky_backtest.py all`"
                )
elif not scan_results:
    st.markdown(
        "<div style='text-align:center; padding:50px; color:#888; font-size:18px;'>"
        "اضغط على زر <b style='color:#00d2ff;'>استخراج الفرص 💎</b> لبدء المسح والتحليل"
        "</div>",
        unsafe_allow_html=True
    )


def _format_cat_row(row, src_col, cat_col):
    return _format_cat(row[src_col], row[cat_col])
