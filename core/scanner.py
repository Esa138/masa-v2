import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.utils import localize_timezone, format_price, safe_div, SAUDI_TZ
from core.indicators import (
    calculate_zero_reflection, compute_rsi, compute_atr,
    compute_vwap, compute_direction_counter, calc_momentum_score,
    detect_rsi_divergence, detect_volume_price_divergence, compute_atr_regime,
    compute_obv, compute_cmf, compute_linear_slope,
    compute_range_contraction, compute_accumulation_score,
    detect_accumulation_phase, ACCUM_PHASES,
    compute_accumulation_pressure, compute_expected_move,
)
from core.analysis import get_ai_analysis, compute_confluence_stars
from core.news import batch_news_analysis, calculate_news_adjustment
from core.wolf import detect_wolf_signal, classify_wolf_signal
from core.arbitrator import arbitrate_signals
from core.lifecycle import apply_lifecycle
from data.markets import get_stock_name, get_stock_sector

MIN_BARS = 35


def _fetch_single(tk: str, period: str, interval: str):
    try:
        t_obj = yf.Ticker(tk)
        df = t_obj.history(period=period, interval=interval)
        if df.empty or len(df) < MIN_BARS:
            return tk, None, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = localize_timezone(df)

        df_1d = None
        if interval != "1d":
            try:
                df_1d_raw = t_obj.history(period="1y", interval="1d")
                if not df_1d_raw.empty:
                    if isinstance(df_1d_raw.columns, pd.MultiIndex):
                        df_1d_raw.columns = df_1d_raw.columns.get_level_values(0)
                    df_1d = localize_timezone(df_1d_raw)
            except Exception:
                pass
        return tk, df, df_1d
    except Exception:
        return tk, None, None


def _safe_pct(close: pd.Series, offset: int) -> float:
    if len(close) <= offset:
        return 0.0
    prev_val = close.iloc[-(offset + 1)]
    if prev_val == 0 or pd.isna(prev_val):
        return 0.0
    return (close.iloc[-1] / prev_val - 1) * 100


def _get_cat(val) -> str:
    try:
        if pd.isna(val) or np.isinf(float(val)):
            return ""
        v = abs(float(val))
        if v >= 1.0:
            return "MAJOR"
        elif v >= 0.1:
            return "HIGH"
        return "MEDIUM"
    except (ValueError, TypeError):
        return ""


def _format_cat(val, cat: str) -> str:
    try:
        if pd.isna(val) or np.isinf(float(val)):
            return "⚪ 0.00%"
        f_val = float(val)
        cat_str = f" {cat}" if cat else ""
        if f_val > 0:
            return f"🟢 +{f_val:.2f}%{cat_str}"
        elif f_val < 0:
            return f"🔴 {f_val:.2f}%{cat_str}"
        return f"⚪ 0.00%{cat_str}"
    except (ValueError, TypeError):
        return "⚪ 0.00%"


# ── Accumulation Location Classifier ────────────────────────────
# Classifies WHERE on the chart accumulation is happening:
#   bottom      = near MA200 / ZR Low (best — buying at cheapest levels)
#   blue_sky    = above ZR High (strong — no overhead resistance)
#   middle      = between MA50 and MA200 (decent — some overhead supply)
#   resistance  = near ZR High from below (riskiest — sellers above)

ACCUM_LOCATIONS = {
    "bottom":     {"label": "📦 تجميع في القاع",    "color": "#00E676", "rank": 1},
    "blue_sky":   {"label": "🔵 تجميع سماء زرقاء",  "color": "#00B0FF", "rank": 2},
    "middle":     {"label": "🟣 تجميع في الوسط",    "color": "#CE93D8", "rank": 3},
    "resistance": {"label": "🟠 تجميع عند المقاومة", "color": "#FF9800", "rank": 4},
}


def classify_accum_location(
    last_c: float,
    ma50_val: float,
    ma200_val: float,
    zr_high: float,
    zr_low: float,
    is_blue_sky: bool,
    zr_bonus: int,
) -> dict:
    """
    Classify accumulation location on the chart.

    Returns dict with: location, label, color, rank
    """
    # ── Rule 1: Blue Sky — above ZR High, no resistance ──
    if is_blue_sky:
        loc = "blue_sky"
        return {**ACCUM_LOCATIONS[loc], "location": loc}

    # ── Rule 2: Bottom — near MA200, near ZR Low, or below MA200 ──
    near_ma200 = False
    below_ma200 = False
    if pd.notna(ma200_val) and ma200_val > 0:
        dist_ma200 = (last_c - ma200_val) / ma200_val
        near_ma200 = -0.05 <= dist_ma200 <= 0.08  # within -5% to +8% of MA200
        below_ma200 = last_c < ma200_val

    near_zr_low = zr_bonus > 0  # already computed: dist_to_floor <= 10%

    if below_ma200 or near_zr_low or near_ma200:
        loc = "bottom"
        return {**ACCUM_LOCATIONS[loc], "location": loc}

    # ── Rule 3: Resistance — near ZR High from below ──
    if pd.notna(zr_high) and zr_high > 0:
        dist_to_ceiling = (zr_high - last_c) / zr_high
        if 0 < dist_to_ceiling <= 0.08:  # within 8% below ZR High
            loc = "resistance"
            return {**ACCUM_LOCATIONS[loc], "location": loc}

    # ── Rule 4: Middle — everything else ──
    loc = "middle"
    return {**ACCUM_LOCATIONS[loc], "location": loc}


@st.cache_data(ttl=300, show_spinner=False)  # 5 min cache (was 15 min)
def scan_market(
    watchlist_tuple: tuple,
    period: str = "1y",
    interval: str = "1d",
    lbl: str = "أيام",
    tf_label: str = "يومي",
    macro_status: str = "تذبذب ⛅",
    gemini_api_key: str = "",
):
    loads_list, alerts_list, ai_picks = [], [], []

    now_internal = datetime.datetime.now(SAUDI_TZ)
    col_change = "تغير 1 يوم" if interval == "1d" else "تغير 1 شمعة"
    col_count = "عدد الأيام" if interval == "1d" else "عدد الشموع"

    histories = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(_fetch_single, tk, period, interval)
            for tk in watchlist_tuple
        ]
        for future in as_completed(futures):
            tk, df_s, df_1d = future.result()
            if df_s is not None:
                histories[tk] = (df_s, df_1d)

    # --- News Sentiment Analysis (Keywords always + Gemini if key provided) ---
    news_results = {}
    try:
        news_results = batch_news_analysis(
            list(histories.keys()), gemini_api_key, max_calls=12
        )
    except Exception:
        news_results = {}

    # ── Parallel per-ticker analysis (was sequential loop) ─────────
    def _analyze_ticker(tk):
        """Process a single ticker — returns (loads_row, alerts, ai_pick) or None."""
        data = histories.get(tk)
        if data is None:
            return None
        try:
            df_s, df_1d = data
            is_forex = "=X" in tk
            is_crypto = "-USD" in tk

            c = df_s['Close']
            h = df_s['High']
            l_col = df_s['Low']
            vol = df_s.get('Volume', pd.Series(np.zeros(len(c)), index=c.index))
            stock_name = get_stock_name(tk)

            ma50 = c.rolling(50).mean()
            ma200 = c.rolling(200).mean() if len(c) >= 200 else c.rolling(50).mean()
            v_sma20 = vol.rolling(20).mean()
            v_sma10 = vol.rolling(10).mean()

            atr = compute_atr(h, l_col, c)
            last_atr = atr.iloc[-1]
            if pd.isna(last_atr) or last_atr <= 0:
                last_atr = c.iloc[-1] * 0.02

            vwap = compute_vwap(h, l_col, c, vol) if not is_forex else c.rolling(20).mean()
            last_vwap = vwap.iloc[-1] if pd.notna(vwap.iloc[-1]) else c.iloc[-1]

            h3 = h.rolling(3).max().shift(1)
            l3 = l_col.rolling(3).min().shift(1)
            h4 = h.rolling(4).max().shift(1)
            h10 = h.rolling(10).max().shift(1)

            zr1_h, zr1_l = calculate_zero_reflection(h, l_col, 400, 25)

            last_zr_h = zr1_h.iloc[-1] if not zr1_h.empty else np.nan
            prev_zr_h = zr1_h.iloc[-2] if len(zr1_h) > 1 else last_zr_h
            last_zr_l = zr1_l.iloc[-1] if not zr1_l.empty else np.nan
            prev_zr_l = zr1_l.iloc[-2] if len(zr1_l) > 1 else last_zr_l

            rsi = compute_rsi(c)

            last_c = c.iloc[-1]
            prev_c = c.iloc[-2]
            prev2_c = c.iloc[-3] if len(c) > 2 else prev_c

            counters = compute_direction_counter(c)
            cur_count = counters[-1]

            daily_trend = "صاعد ☀️"
            if interval == "1d":
                if pd.notna(ma50.iloc[-1]) and last_c < ma50.iloc[-1]:
                    daily_trend = "هابط ⛈️"
            else:
                if df_1d is not None and not df_1d.empty and len(df_1d) > 50:
                    d_c = df_1d['Close'].dropna()
                    if not d_c.empty:
                        d_ma50 = d_c.rolling(50).mean().iloc[-1]
                        if pd.notna(d_ma50) and d_c.iloc[-1] < d_ma50:
                            daily_trend = "هابط ⛈️"

            if is_forex or is_crypto:
                vol_ratio, vol_accel_ratio = 1.0, 1.0
            else:
                last_vol = vol.iloc[-1] if pd.notna(vol.iloc[-1]) and vol.iloc[-1] > 0 else 1e6
                avg_vol = v_sma20.iloc[-1] if pd.notna(v_sma20.iloc[-1]) and v_sma20.iloc[-1] > 0 else 1e6
                avg_vol_10 = v_sma10.iloc[-1] if pd.notna(v_sma10.iloc[-1]) and v_sma10.iloc[-1] > 0 else 1e6
                vol_ratio = safe_div(last_vol, avg_vol, 1.0)
                vol_accel_ratio = safe_div(last_vol, avg_vol_10, 1.0)

            # ── Accumulation Detection (skip forex/crypto) ────────
            accum_data = None
            if not is_forex and not is_crypto and len(c) >= 30:
                try:
                    _vol_mask = vol > 0
                    if _vol_mask.sum() >= 30:
                        _h  = h[_vol_mask]
                        _l  = l_col[_vol_mask]
                        _c  = c[_vol_mask]
                        _v  = vol[_vol_mask]
                        _rsi_a = compute_rsi(_c, period=14)
                        _v_sma20 = _v.rolling(20, min_periods=1).mean()
                    else:
                        _h, _l, _c, _v = h, l_col, c, vol
                        _rsi_a = rsi
                        _v_sma20 = v_sma20

                    obv = compute_obv(_c, _v)
                    cmf_s = compute_cmf(_h, _l, _c, _v, period=20)
                    obv_slope = compute_linear_slope(obv, window=20)
                    price_slope = compute_linear_slope(_c, window=20)
                    range_ratio = compute_range_contraction(_h, _l, window=20)
                    vol_ratio_s = _v / _v_sma20.replace(0, np.nan)
                    vol_ratio_s = vol_ratio_s.fillna(1.0)

                    a_score = compute_accumulation_score(
                        cmf_s, obv_slope, _rsi_a, vol_ratio_s,
                        range_ratio, price_slope
                    )
                    a_phase_raw = detect_accumulation_phase(a_score, cmf_s, obv_slope)

                    # ── Lifecycle Engine (post-breakout detection) ──
                    # Align ZR High with the filtered close series
                    _zr_h_aligned = None
                    if not zr1_h.empty and len(zr1_h) == len(c):
                        _zr_h_aligned = zr1_h[_vol_mask] if _vol_mask.sum() >= 30 else zr1_h
                    a_phase, _lifecycle_meta = apply_lifecycle(
                        close=_c,
                        phase=a_phase_raw,
                        cmf=cmf_s,
                        obv_slope=obv_slope,
                        atr_last=last_atr,
                        zr_high=_zr_h_aligned,
                    )

                    last_phase = a_phase.iloc[-1]
                    accum_days = 0
                    _accum_count_phases = ("early", "mid", "strong", "late",
                                           "breakout", "pullback_buy", "pullback_wait")
                    if last_phase not in ("neutral", "distribute", "exhausted"):
                        for i in range(len(a_phase) - 1, -1, -1):
                            if a_phase.iloc[i] in _accum_count_phases:
                                accum_days += 1
                            else:
                                break

                    zr_bonus = 0
                    if pd.notna(last_zr_l) and last_zr_l > 0:
                        dist_to_floor = (last_c - last_zr_l) / last_zr_l
                        if dist_to_floor <= 0.10:
                            zr_bonus = 10

                    final_accum_score = min(100, a_score.iloc[-1] + zr_bonus)

                    # ── Pressure Gauge ────────────────────────
                    _cmf_slope = compute_linear_slope(cmf_s, window=10).iloc[-1]
                    _score_slope = compute_linear_slope(a_score, window=10).iloc[-1]
                    _pressure = compute_accumulation_pressure(
                        accum_days, range_ratio.iloc[-1],
                        vol_ratio_s.iloc[-1], _cmf_slope, _score_slope
                    )
                    _expected = compute_expected_move(
                        last_atr, accum_days, _pressure, last_c
                    )

                    # ── Location Classification ──────────
                    _ma50_val = ma50.iloc[-1] if pd.notna(ma50.iloc[-1]) else 0
                    _ma200_val = ma200.iloc[-1] if pd.notna(ma200.iloc[-1]) else 0
                    _is_blue_sky = pd.notna(last_zr_h) and last_c > last_zr_h
                    _loc_info = classify_accum_location(
                        last_c, _ma50_val, _ma200_val,
                        last_zr_h, last_zr_l,
                        _is_blue_sky, zr_bonus,
                    )

                    # ── V2 Signal Engine — confirmed buy/sell signals ──
                    _ma20_close = _c.rolling(20).mean()
                    _ma50_close = _c.rolling(50).mean()
                    _last_ma20 = _ma20_close.iloc[-1] if not np.isnan(_ma20_close.iloc[-1]) else 0
                    _last_ma50 = _ma50_close.iloc[-1] if not np.isnan(_ma50_close.iloc[-1]) else 0
                    _prev_close = _c.iloc[-2] if len(_c) >= 2 else _c.iloc[-1]
                    _prev_ma20 = _ma20_close.iloc[-2] if len(_ma20_close) >= 2 and not np.isnan(_ma20_close.iloc[-2]) else 0

                    # Cross MA20: today above, yesterday below
                    _cross_ma20 = (last_c > _last_ma20 > 0) and (_prev_close <= _prev_ma20) and (_prev_ma20 > 0)

                    # Break 20d high
                    _high_20 = _c.rolling(20).max().shift(1)
                    _break_20d = last_c > _high_20.iloc[-1] if not np.isnan(_high_20.iloc[-1]) else False

                    # Above MA50
                    _above_ma50 = last_c > _last_ma50 if _last_ma50 > 0 else False

                    # Signal classification
                    _is_accum = last_phase in ("strong", "late")
                    _is_dist = last_phase == "distribute"

                    _v2_signal = "none"
                    _v2_label = ""
                    _v2_color = "#808080"
                    _v2_confidence = 0

                    # BUY: accum + cross_ma20 + score >= 70 (works in neutral market)
                    if _is_accum and _cross_ma20 and final_accum_score >= 70:
                        _v2_signal = "buy_confirmed"
                        _v2_label = "🟢 شراء مؤكد"
                        _v2_color = "#00E676"
                        _v2_confidence = 55
                    # BUY: accum + break_20d + score >= 70 (high avg return)
                    elif _is_accum and _break_20d and final_accum_score >= 70:
                        _v2_signal = "buy_breakout"
                        _v2_label = "🔵 كسر مؤكد"
                        _v2_color = "#2196F3"
                        _v2_confidence = 47
                    # SELL: distribute + above_ma50 + score >= 60 (94.7% in bull market!)
                    elif _is_dist and _above_ma50 and final_accum_score >= 60:
                        _v2_signal = "sell_confirmed"
                        _v2_label = "🔴 بيع مؤكد"
                        _v2_color = "#FF5252"
                        _v2_confidence = 87
                    # SELL: distribute (general)
                    elif _is_dist:
                        _v2_signal = "sell_warning"
                        _v2_label = "🟠 تحذير تصريف"
                        _v2_color = "#FF9800"
                        _v2_confidence = 57
                    # WATCH: accumulation but no entry trigger
                    elif _is_accum and final_accum_score >= 65:
                        _v2_signal = "watch"
                        _v2_label = "👁️ مراقبة"
                        _v2_color = "#FFD700"
                        _v2_confidence = 0

                    accum_data = {
                        "score": round(final_accum_score, 1),
                        "phase": last_phase,
                        "raw_phase": a_phase_raw.iloc[-1],
                        "phase_label": ACCUM_PHASES.get(last_phase, {}).get("label", "محايد ⚪"),
                        "phase_color": ACCUM_PHASES.get(last_phase, {}).get("color", "#808080"),
                        "cmf": round(cmf_s.iloc[-1], 4),
                        "obv_slope": round(obv_slope.iloc[-1], 6),
                        "days": accum_days,
                        "zr_bonus": zr_bonus,
                        "pressure": _pressure,
                        "cmf_slope": round(_cmf_slope, 6),
                        "score_slope": round(_score_slope, 6),
                        "expected_move": _expected["move_pct"],
                        "expected_target": _expected["target_price"],
                        # ── V2 Signal ──
                        "v2_signal": _v2_signal,
                        "v2_label": _v2_label,
                        "v2_color": _v2_color,
                        "v2_confidence": _v2_confidence,
                        "cross_ma20": _cross_ma20,
                        "break_20d": _break_20d,
                        "above_ma50": _above_ma50,
                        # ── Location ──
                        "location": _loc_info["location"],
                        "location_label": _loc_info["label"],
                        "location_color": _loc_info["color"],
                        "location_rank": _loc_info["rank"],
                        # ── Lifecycle metadata ──
                        "is_post_breakout": _lifecycle_meta["is_post_breakout"],
                        "late_entry_price": _lifecycle_meta["late_entry_price"],
                        "breakout_price": _lifecycle_meta["breakout_price"],
                        "peak_price": _lifecycle_meta["peak_price"],
                        "peak_gain_pct": _lifecycle_meta["peak_gain_pct"],
                        "current_retracement": _lifecycle_meta["current_retracement"],
                        "bars_since_breakout": _lifecycle_meta["bars_since_breakout"],
                        "accum_start_date": _lifecycle_meta.get("accum_start_date", ""),
                        "breakout_date": _lifecycle_meta.get("breakout_date", ""),
                        "peak_date": _lifecycle_meta.get("peak_date", ""),
                    }
                except Exception:
                    accum_data = None

            try:
                candle_time = (
                    now_internal.strftime("⏱️ %H:%M | %Y-%m-%d")
                    if interval == "1d"
                    else df_s.index[-1].strftime("⏱️ %H:%M | %Y-%m-%d")
                )
            except Exception:
                candle_time = now_internal.strftime("⏱️ %H:%M | %Y-%m-%d")

            pct_1d = _safe_pct(c, 1)
            pct_3d = _safe_pct(c, 3)
            pct_5d = _safe_pct(c, 5)
            pct_10d = _safe_pct(c, 10)

            cat_1d = _get_cat(pct_1d)
            cat_3d = _get_cat(pct_3d)
            cat_5d = _get_cat(pct_5d)
            cat_10d = _get_cat(pct_10d)

            loads_row = {
                "الشركة": stock_name, "التاريخ": candle_time,
                "الاتجاه": int(cur_count), col_count: abs(cur_count),
                col_change: pct_1d, "1d_cat": cat_1d,
                f"تراكمي 3 {lbl}": pct_3d, "3d_cat": cat_3d,
                f"تراكمي 5 {lbl}": pct_5d, "5d_cat": cat_5d,
                f"تراكمي 10 {lbl}": pct_10d, "10d_cat": cat_10d,
                f"حالة 3 {lbl}": "✅" if pct_3d > 0 else "❌",
                f"حالة 5 {lbl}": "✅" if pct_5d > 0 else "❌",
                f"حالة 10 {lbl}": "✅" if pct_10d > 0 else "❌",
                "raw_3d": pct_3d, "raw_5d": pct_5d, "raw_10d": pct_10d,
            }

            tk_alerts = []
            bo_today, bd_today = [], []
            _pullback_from_high = False   # above ZR High but declining
            _rebound_from_low = False     # below ZR Low but rising

            if pd.notna(last_zr_h) and last_c > last_zr_h:
                if pd.notna(prev_zr_h) and prev_c <= prev_zr_h:
                    # Fresh ZR High breakout TODAY — always strong signal
                    tk_alerts.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "اختراق سقف زيرو 👑🚀"
                    })
                    bo_today.append("اختراق زيرو 👑")
                elif pct_3d > 0:
                    # Above ZR High + 3-day momentum positive = true blue sky
                    tk_alerts.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "سماء زرقاء 🌌"
                    })
                    bo_today.append("سماء زرقاء 🌌")
                else:
                    # Above ZR High but 3-day momentum negative = pullback warning
                    tk_alerts.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "تراجع من القمة ⚠️"
                    })
                    _pullback_from_high = True

            if pd.notna(last_zr_l) and last_c < last_zr_l:
                if pd.notna(prev_zr_l) and prev_c >= prev_zr_l:
                    # Fresh ZR Low breakdown TODAY — always strong signal
                    tk_alerts.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "كسر قاع زيرو 🩸📉"
                    })
                    bd_today.append("كسر زيرو 🩸")
                elif pct_3d < 0:
                    # Below ZR Low + 3-day momentum negative = true deep breakdown
                    tk_alerts.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "انهيار سحيق 🔻"
                    })
                    bd_today.append("سقوط 🩸")
                else:
                    # Below ZR Low but 3-day momentum positive = rebound attempt
                    tk_alerts.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "ارتداد من الانهيار 🟢"
                    })
                    _rebound_from_low = True

            if (
                pd.notna(h3.iloc[-1]) and pd.notna(h3.iloc[-2])
                and last_c > h3.iloc[-1] and prev_c <= h3.iloc[-2]
            ):
                bo_today.append(f"3{lbl}")
                tk_alerts.append({
                    "الشركة": stock_name, "التاريخ": candle_time,
                    "الفريم": tf_label, "التنبيه": f"اختراق 3 {lbl} 🟢"
                })
            if pd.notna(h4.iloc[-1]) and pd.notna(h4.iloc[-2]) and last_c > h4.iloc[-1] and prev_c <= h4.iloc[-2]:
                bo_today.append(f"4{lbl}")
            if pd.notna(h10.iloc[-1]) and pd.notna(h10.iloc[-2]) and last_c > h10.iloc[-1] and prev_c <= h10.iloc[-2]:
                bo_today.append(f"10{lbl}")
            if (
                pd.notna(l3.iloc[-1]) and pd.notna(l3.iloc[-2])
                and last_c < l3.iloc[-1] and prev_c >= l3.iloc[-2]
            ):
                bd_today.append(f"3{lbl}")
                tk_alerts.append({
                    "الشركة": stock_name, "التاريخ": candle_time,
                    "الفريم": tf_label, "التنبيه": f"كسر 3 {lbl} 🔴"
                })

            bo_yest, bd_yest = [], []
            if len(c) > 3:
                if pd.notna(h3.iloc[-2]) and pd.notna(h3.iloc[-3]) and prev_c > h3.iloc[-2] and prev2_c <= h3.iloc[-3]:
                    bo_yest.append(f"3{lbl}")
                if pd.notna(l3.iloc[-2]) and pd.notna(l3.iloc[-3]) and prev_c < l3.iloc[-2] and prev2_c >= l3.iloc[-3]:
                    bd_yest.append(f"3{lbl}")

            events = []
            bo_score_add = 0

            if pct_1d > 0 and vol_accel_ratio > 1.2 and not is_forex and not is_crypto:
                events.append("تسارع سيولة 🌊🔥")
                bo_score_add += 10
            elif pct_1d > 0 and cur_count > 0 and (is_forex or is_crypto):
                events.append("زخم سعري 🌊🔥")
                bo_score_add += 10

            if bo_today:
                events.append(f"انطلاق 🚀 ({'+'.join(bo_today)})")
                bo_score_add += 15
            elif bd_today:
                events.append(f"سقوط 🩸 ({'+'.join(bd_today)})")
                bo_score_add -= 20
            elif _pullback_from_high:
                # Above channel but declining — warning, not bullish
                events.append("تراجع من القمة ⚠️")
                bo_score_add -= 5
            elif _rebound_from_low:
                # Below channel but rising — recovery attempt
                events.append("ارتداد من الانهيار 🟢")
                bo_score_add += 5
            elif bo_yest and pd.notna(h3.iloc[-1]) and last_c > h3.iloc[-1]:
                events.append("اختراق سابق 🟢")
                bo_score_add += 10
            elif bd_yest and pd.notna(l3.iloc[-1]) and last_c < l3.iloc[-1]:
                events.append("كسر سابق 🔴")
                bo_score_add -= 15
            else:
                dist_m50 = (
                    safe_div((last_c - ma50.iloc[-1]) * 100, ma50.iloc[-1], 100)
                    if pd.notna(ma50.iloc[-1]) else 100
                )
                if 0 <= dist_m50 <= 2.5 and cur_count > 0:
                    events.append("ارتداد MA50 💎")
                    bo_score_add += 10
                elif -2.5 <= dist_m50 < 0 and cur_count < 0:
                    events.append("كسر MA50 ⚠️")
                    bo_score_add -= 15

            if not events:
                if cur_count > 1:
                    events.append(f"مسار صاعد ({cur_count} {lbl}) 📈")
                    bo_score_add += 5
                elif cur_count < -1:
                    events.append(f"مسار هابط ({abs(cur_count)} {lbl}) 📉")
                    bo_score_add -= 5
                else:
                    events.append("استقرار ➖")

            event_text = " | ".join(events)

            if "👑" in event_text or "🌌" in event_text:
                bg_c, txt_c, bord_c = "rgba(255, 215, 0, 0.15)", "#FFD700", "rgba(255, 215, 0, 0.8)"
            elif any(x in event_text for x in ["🚀", "🟢", "💎", "📈", "🔥"]):
                bg_c, txt_c, bord_c = "rgba(0, 230, 118, 0.12)", "#00E676", "rgba(0, 230, 118, 0.5)"
            elif "🔻" in event_text:
                bg_c, txt_c, bord_c = "#f44336", "#fff", "#fff"
            elif any(x in event_text for x in ["🩸", "🔴", "🛑", "📉"]):
                bg_c, txt_c, bord_c = "rgba(255, 82, 82, 0.12)", "#FF5252", "rgba(255, 82, 82, 0.5)"
            elif "⚠️" in event_text:
                bg_c, txt_c, bord_c = "rgba(255, 215, 0, 0.12)", "#FFD700", "rgba(255, 215, 0, 0.5)"
            else:
                bg_c, txt_c, bord_c = "transparent", "gray", "gray"

            ch_badge = (
                f"<span class='bo-badge' style='background-color:{bg_c}; "
                f"color:{txt_c}; border: 1px solid {bord_c};'>{event_text}</span>"
            )

            sl_atr = last_c - (last_atr * 1.5)
            sl_fallback = ma50.iloc[-1] if pd.notna(ma50.iloc[-1]) else last_c * 0.95
            sl = sl_atr if sl_atr < last_c else sl_fallback
            if sl >= last_c:
                sl = last_c * 0.98

            risk = last_c - sl
            if risk <= 0:
                risk = last_c * 0.01

            min_target = last_c + (risk * 2.0)

            if pd.notna(last_zr_h) and last_c > last_zr_h:
                target_val = last_c + (risk * 3.0)
                target_disp = "سماء مفتوحة 🚀"
            else:
                natural_target = last_zr_h if pd.notna(last_zr_h) else last_c * 1.05
                target_val = max(natural_target, min_target)
                target_disp = format_price(target_val, tk)

            rr_ratio = safe_div(target_val - last_c, risk, 0)
            mom_score = calc_momentum_score(pct_1d, pct_5d, pct_10d, vol_ratio)

            stock_sector = get_stock_sector(tk)
            rsi_div = detect_rsi_divergence(c, rsi, lookback=10)
            vol_price_div = detect_volume_price_divergence(c, vol, bars=3)
            atr_reg = compute_atr_regime(atr, c, ma50)

            news_data = news_results.get(tk, {})
            news_adj = calculate_news_adjustment(news_data, sector=stock_sector) if news_data else 0

            wolf_data = {
                "last_close": last_c, "pct_1d": pct_1d, "pct_5d": pct_5d,
                "vol_accel_ratio": vol_accel_ratio, "vol_ratio": vol_ratio,
                "macro_status": macro_status, "is_forex": is_forex,
                "rsi": rsi.iloc[-1], "last_vwap": last_vwap,
                "ma50": ma50.iloc[-1], "zr_high": last_zr_h,
                "momentum_score": mom_score, "last_atr": last_atr,
            }
            is_wolf, wolf_details = detect_wolf_signal(wolf_data)

            ai_score, ai_dec, ai_col, reasons_list = get_ai_analysis(
                last_c, ma50.iloc[-1], ma200.iloc[-1], rsi.iloc[-1],
                cur_count, last_zr_l, last_zr_h, event_text,
                bo_score_add, mom_score, vol_accel_ratio, pct_1d,
                macro_status, is_forex, is_crypto, last_vwap,
                rr_ratio, daily_trend, interval,
                news_adjustment=news_adj, is_wolf=is_wolf,
                rsi_divergence=rsi_div,
                vol_price_divergence=vol_price_div,
                atr_regime=atr_reg,
                accumulation_data=accum_data,
            )

            wolf_type = classify_wolf_signal(is_wolf, ai_score)

            is_blue_sky_flag = pd.notna(last_zr_h) and last_c > last_zr_h
            accum_phase_for_stars = accum_data["phase"] if accum_data else "neutral"
            confluence = compute_confluence_stars(
                is_wolf=is_wolf,
                keyword_verdict=news_data.get("keyword_verdict", ""),
                is_blue_sky=is_blue_sky_flag,
                vol_accel_ratio=vol_accel_ratio,
                final_score=ai_score,
                news_adjustment=news_adj,
                accum_phase=accum_phase_for_stars,
            )

            if confluence["multiplier"] > 1.0:
                _pre_mult = ai_score
                ai_score = min(100, int(ai_score * confluence["multiplier"]))
                # Re-apply veto caps: multiplier must not bypass veto protections
                if _pre_mult <= 59:
                    ai_score = min(ai_score, 59)
                elif _pre_mult <= 79:
                    ai_score = min(ai_score, 79)

            # ── Signal Arbitrator (الحَكَم) ──────────────────────
            arbitration = arbitrate_signals(
                ai_score=ai_score,
                mom_score=mom_score,
                is_wolf=is_wolf,
                wolf_details=wolf_details,
                accum_data=accum_data,
                is_blue_sky=is_blue_sky_flag,
                vol_accel_ratio=vol_accel_ratio,
            )

            if is_wolf:
                wolf_label = (
                    "🐺 اختراق وولف مؤكد 💎"
                    if wolf_type == "مؤكد"
                    else "🐺 اختراق وولف 🔥"
                )
                tk_alerts.append({
                    "الشركة": stock_name, "التاريخ": candle_time,
                    "الفريم": tf_label, "التنبيه": wolf_label,
                })

            ai_pick = {
                "الشركة": stock_name, "الرمز": tk,
                "السعر": format_price(last_c, tk),
                "Score 💯": ai_score,
                "الحالة اللحظية ⚡": ch_badge,
                "الهدف 🎯": target_disp,
                "الوقف 🛡️": format_price(sl, tk),
                "التوصية 🚦": ai_dec, "اللون": ai_col,
                "raw_score": ai_score, "raw_mom": mom_score,
                "raw_events": event_text, "raw_time": candle_time,
                "raw_target": target_val, "raw_sl": sl,
                "raw_price": last_c, "raw_reasons": reasons_list,
                "raw_rr": rr_ratio,
                "news_sentiment": news_data.get("sentiment", "محايد"),
                "news_summary": news_data.get("summary_ar", ""),
                "news_confidence": news_data.get("confidence", 0),
                "news_headlines": news_data.get("headlines", []),
                "news_adjustment": news_adj,
                "keyword_hits": news_data.get("keyword_hits", []),
                "keyword_score": news_data.get("keyword_score", 0),
                "keyword_verdict": news_data.get("keyword_verdict", "⚖️ محايد"),
                "killer_count": news_data.get("killer_count", 0),
                "rocket_count": news_data.get("rocket_count", 0),
                "killer_hits": news_data.get("killer_hits", []),
                "rocket_hits": news_data.get("rocket_hits", []),
                "is_wolf": is_wolf,
                "wolf_type": wolf_type,
                "wolf_sl": wolf_details.get("wolf_sl", sl),
                "wolf_target": wolf_details.get("wolf_target", target_val),
                "wolf_rr": wolf_details.get("wolf_rr", 0),
                "wolf_filters": wolf_details.get("filters_passed", []),
                "wolf_filters_count": wolf_details.get("filters_count", 0),
                "wolf_soft_pass": wolf_details.get("is_soft_pass", False),
                "confluence_stars": confluence["stars"],
                "confluence_display": confluence["display"],
                "confluence_signals": confluence["signals"],
                "rsi_divergence_type": rsi_div.get("type", "none"),
                "vol_price_div_type": vol_price_div.get("type", "none"),
                "atr_regime": atr_reg.get("regime", "normal"),
                "stock_sector": stock_sector,
                "accum_score": accum_data["score"] if accum_data else 0,
                "accum_phase": accum_data["phase"] if accum_data else "neutral",
                "accum_phase_label": accum_data["phase_label"] if accum_data else "محايد ⚪",
                "accum_phase_color": accum_data["phase_color"] if accum_data else "#808080",
                "accum_cmf": accum_data["cmf"] if accum_data else 0,
                "accum_obv_slope": accum_data["obv_slope"] if accum_data else 0,
                "accum_days": accum_data["days"] if accum_data else 0,
                "accum_zr_bonus": accum_data["zr_bonus"] if accum_data else 0,
                "accum_pressure": accum_data["pressure"] if accum_data else 0,
                "accum_expected_move": accum_data["expected_move"] if accum_data else 0,
                "accum_expected_target": accum_data["expected_target"] if accum_data else 0,
                # ── Location fields ──
                "accum_location": accum_data.get("location", "middle") if accum_data else "middle",
                "accum_location_label": accum_data.get("location_label", "🟣 تجميع في الوسط") if accum_data else "🟣 تجميع في الوسط",
                "accum_location_color": accum_data.get("location_color", "#CE93D8") if accum_data else "#CE93D8",
                "accum_location_rank": accum_data.get("location_rank", 3) if accum_data else 3,
                # ── Lifecycle fields ──
                "accum_raw_phase": accum_data.get("raw_phase", "neutral") if accum_data else "neutral",
                "accum_is_post_breakout": accum_data.get("is_post_breakout", False) if accum_data else False,
                "accum_late_entry_price": accum_data.get("late_entry_price", 0) if accum_data else 0,
                "accum_breakout_price": accum_data.get("breakout_price", 0) if accum_data else 0,
                "accum_peak_price": accum_data.get("peak_price", 0) if accum_data else 0,
                "accum_peak_gain_pct": accum_data.get("peak_gain_pct", 0) if accum_data else 0,
                "accum_retracement": accum_data.get("current_retracement", 0) if accum_data else 0,
                "accum_bars_since_bo": accum_data.get("bars_since_breakout", 0) if accum_data else 0,
                "accum_start_date": accum_data.get("accum_start_date", "") if accum_data else "",
                "accum_breakout_date": accum_data.get("breakout_date", "") if accum_data else "",
                "accum_peak_date": accum_data.get("peak_date", "") if accum_data else "",
                # ── V2 Signal fields ──
                "accum_v2_signal": accum_data.get("v2_signal", "none") if accum_data else "none",
                "accum_v2_label": accum_data.get("v2_label", "") if accum_data else "",
                "accum_v2_color": accum_data.get("v2_color", "#808080") if accum_data else "#808080",
                "accum_v2_confidence": accum_data.get("v2_confidence", 0) if accum_data else 0,
                "accum_cross_ma20": accum_data.get("cross_ma20", False) if accum_data else False,
                "accum_break_20d": accum_data.get("break_20d", False) if accum_data else False,
                "accum_above_ma50": accum_data.get("above_ma50", False) if accum_data else False,
                "wolf_readiness": wolf_details.get("filters_count", 0),
                "wolf_readiness_filters": wolf_details.get("filters_passed", []),
                # ── Arbitrator fields ──
                "unified_score": arbitration["unified_score"],
                "signal_quality": arbitration["signal_quality"],
                "quality_label": arbitration["quality_label"],
                "quality_color": arbitration["quality_color"],
                "vip_allowed": arbitration["vip_allowed"],
                "wolf_allowed": arbitration["wolf_allowed"],
                "wolf_downgraded": arbitration["wolf_downgraded"],
                "arb_contradictions": arbitration["contradictions"],
                "arb_adjustments": arbitration["adjustments"],
                "vip_threshold_reduction": arbitration["vip_threshold_reduction"],
            }

            return loads_row, tk_alerts, ai_pick

        except Exception:
            return None

    # Run analysis in parallel (6 workers — numpy/pandas release the GIL)
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_analyze_ticker, tk): tk
            for tk in watchlist_tuple
        }
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                continue
            loads_row, tk_alerts, ai_pick = result
            loads_list.append(loads_row)
            alerts_list.extend(tk_alerts)
            ai_picks.append(ai_pick)

    return (
        pd.DataFrame(loads_list),
        pd.DataFrame(alerts_list),
        pd.DataFrame(ai_picks),
    )


@st.cache_data(ttl=1800, show_spinner=False)
def get_macro_status(market_choice: str):
    if "السعودي" in market_choice:
        ticker, name = "^TASI.SR", "تاسي (TASI)"
    elif "الأمريكي" in market_choice:
        ticker, name = "^GSPC", "إس آند بي (S and P 500)"
    elif "الفوركس" in market_choice:
        ticker, name = "DX-Y.NYB", "مؤشر الدولار (DXY)"
    else:
        ticker, name = "BTC-USD", "البيتكوين (BTC)"

    try:
        df = yf.Ticker(ticker).history(period="6mo", interval="1d")
        if df is None or df.empty:
            return "تذبذب ⛅", name, 0.0, 0.0

        close = df['Close']
        ma50_val = close.rolling(50).mean().iloc[-1]
        if pd.isna(ma50_val):
            ma50_val = close.mean()

        last_c = close.iloc[-1]
        prev_c = close.iloc[-2] if len(close) > 1 else last_c
        pct_change = safe_div((last_c - prev_c) * 100, prev_c, 0)

        if "الفوركس" in market_choice:
            status = "سوق لامركزي 💱"
        elif last_c > ma50_val:
            status = "إيجابي ☀️"
        elif last_c < ma50_val:
            status = "سلبي ⛈️"
        else:
            status = "تذبذب ⛅"

        return status, name, pct_change, last_c
    except Exception:
        return "تذبذب ⛅", name, 0.0, 0.0


@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(ticker_symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    try:
        tk = yf.Ticker(str(ticker_symbol))
        df = tk.history(period=period, interval=interval)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return localize_timezone(df)
    except Exception:
        return pd.DataFrame()
