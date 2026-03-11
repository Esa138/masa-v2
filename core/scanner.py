"""
MASA V2 — Order Flow Market Scanner
Scans stocks, detects Order Flow patterns + Wyckoff phases, scores them honestly.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.accumulation import detect_orderflow, compute_accumulation_maturity, compute_distribution_maturity
from core.scorer import score_stock
from core.indicators import compute_rolling_delta, compute_cdv, compute_rsi, compute_ma
from core.institutional import get_ownership_batch, interpret_ownership
from data.markets import get_stock_name, get_sector

MIN_BARS = 50


# ── Accumulation/Distribution Type Classifier ─────────────────
def _classify_flow_type(phase: str, location: str, divergence: float,
                        last_close: float = 0, ma200: float = 0,
                        maturity_days: int = 0) -> tuple:
    """
    Classify the TYPE of accumulation or distribution.
    Returns (type_key, type_label, type_color, scope).

    Scope requires TWO conditions:
      Primary accumulation:  price < MA200  AND  duration >= 30 days
      Secondary (re-accum):  price > MA200  OR   duration < 30 days
      Primary distribution:  price > MA200  AND  duration >= 30 days
      Secondary (re-dist):   price < MA200  OR   duration < 30 days
    """
    # ── Scope: primary vs secondary ──
    scope = "none"
    scope_label = ""

    # ── Accumulation types ──
    if phase in ("accumulation", "spring"):
        if ma200 > 0 and last_close > 0:
            if last_close < ma200 and maturity_days >= 30:
                scope = "primary"
                scope_label = "رئيسي"
            elif last_close > ma200:
                scope = "secondary"
                scope_label = "فرعي"
            elif last_close < ma200 and maturity_days < 30:
                scope = "early_primary"
                scope_label = "بداية رئيسي"

        _s = f" — {scope_label}" if scope_label else ""
        if phase == "spring":
            return "spring", f"🎯 سبرنق{_s}", "#00E676", scope
        if location == "bottom":
            return "bottom", f"📦 تجميع قاعي{_s}", "#00E676", scope
        if divergence > 25:
            return "hidden", f"🕵️ تجميع خفي{_s}", "#7C4DFF", scope
        return "visible", f"🟢 تجميع ظاهر{_s}", "#4FC3F7", scope

    # ── Distribution types ──
    if phase in ("distribution", "upthrust", "markdown"):
        if ma200 > 0 and last_close > 0:
            if last_close > ma200 and maturity_days >= 30:
                scope = "primary"
                scope_label = "رئيسي"
            elif last_close < ma200:
                scope = "secondary"
                scope_label = "فرعي"
            elif last_close > ma200 and maturity_days < 30:
                scope = "early_primary"
                scope_label = "بداية رئيسي"

        _s = f" — {scope_label}" if scope_label else ""
        if phase == "upthrust":
            return "upthrust", f"⚠️ أبثرست{_s}", "#FF9800", scope
        if location in ("resistance", "above"):
            return "top", f"🔺 تصريف قمّي{_s}", "#FF1744", scope
        if divergence < -25:
            return "hidden_dist", f"🕵️ تصريف خفي{_s}", "#FF6D00", scope
        return "visible_dist", f"🔴 تصريف ظاهر{_s}", "#FF5252", scope

    return "none", "", "#808080", "none"


def _fetch_ticker(ticker: str, period: str = "1y") -> tuple:
    """Fetch OHLCV data for a single ticker."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval="1d")
        if df is None or df.empty or len(df) < MIN_BARS:
            return ticker, None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return ticker, df
    except Exception:
        return ticker, None


def scan_market(
    tickers: list,
    period: str = "2y",
    market_health: float = 50.0,
    max_workers: int = 10,
    progress_callback=None,
) -> list:
    """
    Scan a list of tickers using Order Flow analysis.

    Returns:
        List of dicts, sorted by decision quality (enter first)
    """
    # ── Fetch data in parallel ────────────────────────────
    histories = {}
    total = len(tickers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_ticker, tk, period): tk
            for tk in tickers
        }
        done = 0
        for future in as_completed(futures):
            tk, df = future.result()
            if df is not None:
                histories[tk] = df
            done += 1
            if progress_callback:
                progress_callback(done, total)

    # ── Fetch institutional data (Saudi only) ─────────────────
    all_tickers = list(histories.keys())
    is_saudi = any(tk.endswith(".SR") for tk in all_tickers[:5])
    if is_saudi:
        ownership_data = get_ownership_batch(all_tickers, delay=0.2)
    else:
        ownership_data = {tk: None for tk in all_tickers}

    # ── Analyze each ticker with Order Flow ───────────────
    results = []

    for tk, df in histories.items():
        try:
            close = df["Close"]
            high = df["High"]
            low = df["Low"]
            open_ = df["Open"]
            volume = df.get("Volume", pd.Series(0, index=close.index))

            # Detect Order Flow + Wyckoff phase
            orderflow = detect_orderflow(high, low, close, open_, volume)

            # Get institutional data
            inst_data = ownership_data.get(tk)
            inst_interpretation = interpret_ownership(inst_data, orderflow["phase"])

            # Score the stock
            scored = score_stock(
                close=close,
                high=high,
                low=low,
                orderflow_data=orderflow,
                market_health=market_health,
                institutional_data=inst_data,
            )

            # ── Accumulation maturity ─────────────────────
            from core.indicators import (
                compute_rolling_delta as _rd, compute_cdv as _cdv,
                compute_absorption as _abs, compute_range_contraction as _rc,
                compute_rsi as _rsi2,
            )
            _rolling = _rd(high, low, close, volume, 20)
            _cdv_s = _cdv(high, low, close, volume)
            _abs_s = _abs(high, low, close, volume, 20)
            _rc_s = _rc(high, low, 20)
            _rsi_s = _rsi2(close, 14)
            _all_dates = [d.strftime("%Y-%m-%d") for d in close.index]
            maturity = compute_accumulation_maturity(
                _all_dates, close, _rolling, _cdv_s, _abs_s, _rc_s, _rsi_s, volume
            )

            # ── Sync maturity ↔ decision ──────────────────
            phase = orderflow["phase"]
            today_str = _all_dates[-1] if _all_dates else "—"

            # Spring phase → maturity = late (always)
            if phase == "spring" and maturity["stage"] != "late":
                maturity = {
                    "stage": "late",
                    "stage_label": "🟢 سبرنق — جاهز للانطلاق",
                    "stage_color": "#00E676",
                    "timeline": [{"stage": "late", "date": today_str,
                                   "label": "🟢 سبرنق", "action": "ادخل"}],
                    "current_days": maturity["current_days"],
                }

            # Maturity controls final decision (no contradiction)
            m_stage = maturity["stage"]
            if m_stage in ("early", "mid") and scored["decision"] == "enter":
                # Downgrade: enter → watch (not mature enough)
                scored["decision"] = "watch"
                scored["decision_info"] = {
                    "label": "⚠️ راقب",
                    "color": "#FFD700",
                    "description": "تجميع نشط لكن لم ينضج بعد — انتظر",
                }
                scored["reasons_against"].append(
                    "التجميع لم ينضج بعد — انتظر نهاية التجميع"
                )
            # markup/markdown/neutral without accumulation → hide maturity
            if m_stage == "none" and phase not in ("accumulation", "spring"):
                pass  # maturity stays "none", won't show in UI

            # ── Distribution maturity ───────────────────────
            dist_maturity = compute_distribution_maturity(
                _all_dates, close, _rolling, _cdv_s, _abs_s, _rc_s, _rsi_s, volume
            )

            # Upthrust phase → distribution maturity = late (always)
            if phase == "upthrust" and dist_maturity["stage"] != "late":
                dist_maturity = {
                    "stage": "late",
                    "stage_label": "🔴 أبثرست — تصريف حاد",
                    "stage_color": "#FF5252",
                    "timeline": [{"stage": "late", "date": today_str,
                                   "label": "🔴 أبثرست", "action": "اخرج فوراً"}],
                    "current_days": dist_maturity["current_days"],
                }

            # Distribution maturity controls decision for distribution stocks
            d_stage = dist_maturity["stage"]
            if d_stage in ("mid", "late") and phase in ("distribution", "upthrust", "markdown"):
                if scored["decision"] == "enter":
                    scored["decision"] = "avoid"
                    scored["decision_info"] = {
                        "label": "🔴 تجنب",
                        "color": "#FF5252",
                        "description": "تصريف نشط — لا تدخل",
                    }
                    scored["reasons_against"].append(
                        "تصريف نشط — ابتعد عن السهم"
                    )
                elif scored["decision"] == "watch":
                    scored["decision"] = "avoid"
                    scored["decision_info"] = {
                        "label": "🔴 تجنب",
                        "color": "#FF5252",
                        "description": "تصريف مستمر — لا تدخل",
                    }
                    scored["reasons_against"].append(
                        "تصريف مستمر — ابتعد عن السهم"
                    )

            last_close = float(close.iloc[-1])
            prev_close = float(close.iloc[-2]) if len(close) >= 2 else last_close
            change_pct = (last_close - prev_close) / prev_close * 100

            # ── Flow type classification ────────────────────
            flow_type, flow_type_label, flow_type_color, flow_scope = _classify_flow_type(
                phase, orderflow["location"], orderflow["divergence"],
                last_close, orderflow["ma200"], maturity["current_days"]
            )

            # ── Chart data (last 180 days / 6 months) ──
            chart_days = 180
            chart_dates = [d.strftime("%Y-%m-%d") for d in close.index[-chart_days:]]
            chart_open = [round(float(v), 2) for v in open_.iloc[-chart_days:]]
            chart_high = [round(float(v), 2) for v in high.iloc[-chart_days:]]
            chart_low = [round(float(v), 2) for v in low.iloc[-chart_days:]]
            chart_close = [round(float(v), 2) for v in close.iloc[-chart_days:]]
            chart_volume = [int(float(v)) for v in volume.iloc[-chart_days:]]

            # Pre-computed MAs & RSI (full history then slice last 90)
            _ma20 = compute_ma(close, 20)
            _ma50 = compute_ma(close, 50)
            n_bars = len(close)
            _ma200 = compute_ma(close, min(200, n_bars - 1)) if n_bars >= 50 else _ma50
            _rsi = compute_rsi(close, 14)

            chart_ma20 = [round(float(v), 2) if pd.notna(v) else None for v in _ma20.iloc[-chart_days:]]
            chart_ma50 = [round(float(v), 2) if pd.notna(v) else None for v in _ma50.iloc[-chart_days:]]
            chart_ma200 = [round(float(v), 2) if pd.notna(v) else None for v in _ma200.iloc[-chart_days:]]
            chart_rsi = [round(float(v), 1) if pd.notna(v) else None for v in _rsi.iloc[-chart_days:]]

            results.append({
                "ticker": tk,
                "name": get_stock_name(tk),
                "sector": get_sector(tk),
                "price": round(last_close, 2),
                "change_pct": round(change_pct, 2),
                # Order Flow
                "phase": orderflow["phase"],
                "phase_label": orderflow["phase_info"]["label"],
                "phase_color": orderflow["phase_info"]["color"],
                "phase_desc": orderflow["phase_info"]["description"],
                "flow_bias": orderflow["flow_bias"],
                "cdv_trend": orderflow["cdv_trend"],
                "aggressor": orderflow["aggressor"],
                "aggressive_ratio": orderflow["aggressive_ratio"],
                "absorption_score": orderflow["absorption_score"],
                "absorption_bias": orderflow["absorption_bias"],
                "divergence": orderflow["divergence"],
                "evidence": orderflow["evidence"],
                "days": orderflow["days"],
                "rsi": orderflow["rsi"],
                "volume_ratio": orderflow["volume_ratio"],
                "contraction": orderflow["contraction"],
                # Location
                "location": orderflow["location"],
                "location_label": orderflow["location_info"]["label"],
                "location_color": orderflow["location_info"]["color"],
                "zr_high": orderflow["zr_high"],
                "zr_low": orderflow["zr_low"],
                "zr_status": orderflow["zr_status"],
                "zr_status_label": orderflow["zr_status_label"],
                "zr_status_color": orderflow["zr_status_color"],
                # Flow type
                "flow_type": flow_type,
                "flow_type_label": flow_type_label,
                "flow_type_color": flow_type_color,
                "flow_scope": flow_scope,
                # Decision
                "decision": scored["decision"],
                "decision_label": scored["decision_info"]["label"],
                "decision_color": scored["decision_info"]["color"],
                "reasons_for": scored["reasons_for"],
                "reasons_against": scored["reasons_against"],
                "veto": scored["veto"],
                "stop_loss": scored["stop_loss"],
                "target": scored["target"],
                "rr_ratio": scored["rr_ratio"],
                # Institutional
                "inst_label": inst_interpretation["label"],
                "inst_confidence": inst_interpretation["confidence"],
                "inst_detail": inst_interpretation["detail"],
                "inst_is_institutional": inst_interpretation["is_institutional"],
                "foreign_pct": inst_data["foreign_pct"] if inst_data else None,
                "foreign_change": inst_data.get("foreign_change_pct", 0) if inst_data else None,
                # Chart data
                "chart_dates": chart_dates,
                "chart_open": chart_open,
                "chart_high": chart_high,
                "chart_low": chart_low,
                "chart_close": chart_close,
                "chart_volume": chart_volume,
                "chart_ma20": chart_ma20,
                "chart_ma50": chart_ma50,
                "chart_ma200": chart_ma200,
                "chart_rsi": chart_rsi,
                "chart_delta": orderflow["delta_series"],
                "chart_cdv": orderflow["cdv_series"],
                "chart_absorption": orderflow["absorption_series"],
                # Accumulation maturity
                "maturity_stage": maturity["stage"],
                "maturity_label": maturity["stage_label"],
                "maturity_color": maturity["stage_color"],
                "maturity_timeline": maturity["timeline"],
                "maturity_days": maturity["current_days"],
                # Distribution maturity
                "dist_maturity_stage": dist_maturity["stage"],
                "dist_maturity_label": dist_maturity["stage_label"],
                "dist_maturity_color": dist_maturity["stage_color"],
                "dist_maturity_timeline": dist_maturity["timeline"],
                "dist_maturity_days": dist_maturity["current_days"],
            })

        except Exception:
            continue

    # Sort: enter first, then watch, then avoid — by flow_bias strength
    order = {"enter": 0, "watch": 1, "avoid": 2}
    results.sort(key=lambda x: (order.get(x["decision"], 9), -abs(x["flow_bias"])))

    return results


def compute_market_health(tickers: list, period: str = "6mo") -> float:
    """
    Compute market breadth — percentage of stocks above their MA50.
    Simple, honest measure of market health.
    """
    try:
        above = 0
        total = 0

        data = yf.download(
            tickers=tickers[:50],
            period=period,
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
        )

        if data is None or data.empty:
            return 50.0

        for tk in tickers[:50]:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if tk in data.columns.get_level_values(0):
                        closes = data[tk]["Close"].dropna()
                    else:
                        continue
                else:
                    closes = data["Close"].dropna()

                if len(closes) < 50:
                    continue

                ma50 = closes.rolling(50).mean().iloc[-1]
                if pd.notna(ma50) and closes.iloc[-1] > ma50:
                    above += 1
                total += 1
            except (KeyError, TypeError):
                continue

        if total == 0:
            return 50.0

        return round(above / total * 100, 1)

    except Exception:
        return 50.0
