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
)
from core.analysis import get_ai_analysis
from data.markets import get_stock_name

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


@st.cache_data(ttl=900, show_spinner=False)
def scan_market(
    watchlist_tuple: tuple,
    period: str = "1y",
    interval: str = "1d",
    lbl: str = "أيام",
    tf_label: str = "يومي",
    macro_status: str = "تذبذب ⛅",
):
    loads_list, alerts_list, ai_picks = [], [], []

    now_internal = datetime.datetime.now(SAUDI_TZ)
    col_change = "تغير 1 يوم" if interval == "1d" else "تغير 1 شمعة"
    col_count = "عدد الأيام" if interval == "1d" else "عدد الشموع"

    histories = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(_fetch_single, tk, period, interval)
            for tk in watchlist_tuple
        ]
        for future in as_completed(futures):
            tk, df_s, df_1d = future.result()
            if df_s is not None:
                histories[tk] = (df_s, df_1d)

    for tk in watchlist_tuple:
        data = histories.get(tk)
        if data is None:
            continue
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

            loads_list.append({
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
            })

            bo_today, bd_today = [], []

            if pd.notna(last_zr_h) and last_c > last_zr_h:
                if pd.notna(prev_zr_h) and prev_c <= prev_zr_h:
                    alerts_list.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "اختراق سقف زيرو 👑🚀"
                    })
                    bo_today.append("اختراق زيرو 👑")
                else:
                    alerts_list.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "سماء زرقاء 🌌"
                    })
                    bo_today.append("سماء زرقاء 🌌")

            if pd.notna(last_zr_l) and last_c < last_zr_l:
                if pd.notna(prev_zr_l) and prev_c >= prev_zr_l:
                    alerts_list.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "كسر قاع زيرو 🩸📉"
                    })
                    bd_today.append("كسر زيرو 🩸")
                else:
                    alerts_list.append({
                        "الشركة": stock_name, "التاريخ": candle_time,
                        "الفريم": tf_label, "التنبيه": "انهيار سحيق 🔻"
                    })
                    bd_today.append("سقوط 🩸")

            if (
                pd.notna(h3.iloc[-1]) and pd.notna(h3.iloc[-2])
                and last_c > h3.iloc[-1] and prev_c <= h3.iloc[-2]
            ):
                bo_today.append(f"3{lbl}")
                alerts_list.append({
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
                alerts_list.append({
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

            ai_score, ai_dec, ai_col, reasons_list = get_ai_analysis(
                last_c, ma50.iloc[-1], ma200.iloc[-1], rsi.iloc[-1],
                cur_count, last_zr_l, last_zr_h, event_text,
                bo_score_add, mom_score, vol_accel_ratio, pct_1d,
                macro_status, is_forex, is_crypto, last_vwap,
                rr_ratio, daily_trend, interval,
            )

            ai_picks.append({
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
            })

        except Exception:
            continue

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
