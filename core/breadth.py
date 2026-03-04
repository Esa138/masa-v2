"""
MASA QUANT V95 — Market Breadth Index (QAFAH-Style)
Computes historical market breadth: % of winning stocks over time.
Uses batch yfinance download for efficiency.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st


@st.cache_data(ttl=600, show_spinner=False)
def fetch_breadth_closes(tickers: tuple, period: str = "6mo") -> pd.DataFrame:
    """
    Batch-download daily close prices for all tickers.
    Returns DataFrame: index=dates, columns=tickers, values=Close.
    Cached 10 minutes (daily data doesn't change fast).
    """
    try:
        raw = yf.download(
            tickers=list(tickers),
            period=period,
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()

        # Extract Close prices for each ticker
        closes = {}
        for tk in tickers:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if tk in raw.columns.get_level_values(0):
                        s = raw[tk]["Close"].dropna()
                        if len(s) >= 20:
                            closes[tk] = s
                else:
                    # Single ticker fallback
                    if "Close" in raw.columns:
                        closes[tk] = raw["Close"].dropna()
            except (KeyError, TypeError):
                continue

        if not closes:
            return pd.DataFrame()

        df = pd.DataFrame(closes)
        df = df.sort_index()
        return df

    except Exception:
        return pd.DataFrame()


def compute_market_breadth(
    closes: pd.DataFrame,
    lookback: int = 1,
    base_window: int = 4,
    band_period: int = 5,
) -> pd.DataFrame:
    """
    Compute market breadth index over time.

    Parameters:
        closes:      DataFrame of close prices (cols=tickers, index=dates)
        lookback:    Period for % change (1=daily, 5=weekly, 10=biweekly)
        base_window: SMA smoothing window (3, 4, 10, 15)
        band_period: Multiplier for band lookback (band = band_period × base_window)

    Returns:
        DataFrame with columns: breadth, high, low, raw_pct
    """
    if closes.empty or len(closes) < lookback + base_window:
        return pd.DataFrame()

    # Percentage change over lookback period
    changes = closes.pct_change(lookback)

    # Count winners (positive change) per day
    winners = (changes > 0).sum(axis=1)
    total_valid = changes.notna().sum(axis=1)

    # Raw breadth percentage (0-100)
    raw_pct = (winners / total_valid.replace(0, np.nan) * 100).fillna(50)

    # Smooth with SMA
    breadth_sma = raw_pct.rolling(window=base_window, min_periods=1).mean()

    # High/Low bands
    band_window = max(band_period * base_window, 5)
    high_band = breadth_sma.rolling(window=band_window, min_periods=1).max()
    low_band = breadth_sma.rolling(window=band_window, min_periods=1).min()

    result = pd.DataFrame({
        "breadth": breadth_sma.round(2),
        "high": high_band.round(2),
        "low": low_band.round(2),
        "raw_pct": raw_pct.round(2),
    })

    # Drop initial NaN rows from lookback
    result = result.iloc[lookback + base_window - 1:]

    return result


def get_breadth_stats(closes: pd.DataFrame) -> dict:
    """
    Get current-day winners/losers counts for 1d, 5d, 10d periods.
    Returns dict with counts and total.
    """
    if closes.empty:
        return {
            "winners_1d": 0, "losers_1d": 0,
            "winners_5d": 0, "losers_5d": 0,
            "winners_10d": 0, "losers_10d": 0,
            "total": 0,
        }

    total = closes.iloc[-1].notna().sum()
    stats = {"total": int(total)}

    for label, lb in [("1d", 1), ("5d", 5), ("10d", 10)]:
        if len(closes) > lb:
            changes = closes.iloc[-1] / closes.iloc[-1 - lb] - 1
            valid = changes.dropna()
            stats[f"winners_{label}"] = int((valid > 0).sum())
            stats[f"losers_{label}"] = int((valid < 0).sum())
        else:
            stats[f"winners_{label}"] = 0
            stats[f"losers_{label}"] = 0

    return stats


# ═══════════════════════════════════════════════════════
# 📊 TASI Market Regime Indicator
# ═══════════════════════════════════════════════════════

@st.cache_data(ttl=900, show_spinner=False)
def get_tasi_regime() -> dict:
    """
    Fetch TASI index data and determine current market regime.
    Returns dict with regime info for display.

    Regime logic (based on 20-day TASI return):
      - Bull:    20d return > +2% AND price > MA50
      - Bear:    20d return < -2% OR price < MA50 and falling
      - Neutral: everything else

    Also includes 5d momentum for short-term direction.
    """
    try:
        tasi = yf.Ticker("^TASI.SR")
        hist = tasi.history(period="6mo", interval="1d")
        if hist is None or hist.empty or len(hist) < 50:
            return _default_regime()

        close = hist["Close"]
        last_close = close.iloc[-1]

        # Moving averages
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]

        # Returns
        ret_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0
        ret_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
        ret_60d = (close.iloc[-1] / close.iloc[-60] - 1) * 100 if len(close) >= 60 else 0

        # Recent high/low (20d)
        high_20d = close.tail(20).max()
        low_20d = close.tail(20).min()
        dist_from_high = (last_close / high_20d - 1) * 100
        dist_from_low = (last_close / low_20d - 1) * 100

        # MA trend direction
        ma20_slope = (ma20 - close.rolling(20).mean().iloc[-5]) if len(close) >= 25 else 0
        above_ma20 = last_close > ma20
        above_ma50 = last_close > ma50

        # ── Regime Classification ──
        if ret_20d > 2 and above_ma50:
            regime = "bull"
            regime_ar = "صاعد"
            regime_emoji = "🟢"
            regime_color = "#00E676"
            regime_bg = "rgba(0,230,118,0.08)"
            advice = "التصريف يعمل بدقة 69% — راقب إشارات البيع"
        elif ret_20d < -2 or (not above_ma50 and ret_5d < -1):
            regime = "bear"
            regime_ar = "هابط"
            regime_emoji = "🔴"
            regime_color = "#FF5252"
            regime_bg = "rgba(255,82,82,0.08)"
            advice = "لا تشتري — إشارات الشراء ضارّة في السوق الهابط"
        else:
            regime = "neutral"
            regime_ar = "محايد"
            regime_emoji = "⚪"
            regime_color = "#FFD700"
            regime_bg = "rgba(255,215,0,0.06)"
            advice = "كن انتقائياً — التصريف يعمل بدقة 57%"

        # ── Short-term momentum ──
        if ret_5d > 1:
            momentum = "صاعد"
            momentum_emoji = "📈"
        elif ret_5d < -1:
            momentum = "هابط"
            momentum_emoji = "📉"
        else:
            momentum = "مستقر"
            momentum_emoji = "➡️"

        return {
            "regime": regime,
            "regime_ar": regime_ar,
            "regime_emoji": regime_emoji,
            "regime_color": regime_color,
            "regime_bg": regime_bg,
            "advice": advice,
            "tasi_price": round(last_close, 2),
            "ret_5d": round(ret_5d, 2),
            "ret_20d": round(ret_20d, 2),
            "ret_60d": round(ret_60d, 2),
            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "above_ma20": above_ma20,
            "above_ma50": above_ma50,
            "momentum": momentum,
            "momentum_emoji": momentum_emoji,
            "dist_from_high": round(dist_from_high, 2),
            "dist_from_low": round(dist_from_low, 2),
            "ok": True,
        }

    except Exception:
        return _default_regime()


def _default_regime() -> dict:
    """Fallback when TASI data unavailable."""
    return {
        "regime": "unknown",
        "regime_ar": "غير متوفر",
        "regime_emoji": "❓",
        "regime_color": "#888",
        "regime_bg": "rgba(128,128,128,0.06)",
        "advice": "تعذر جلب بيانات TASI",
        "tasi_price": 0,
        "ret_5d": 0, "ret_20d": 0, "ret_60d": 0,
        "ma20": 0, "ma50": 0,
        "above_ma20": False, "above_ma50": False,
        "momentum": "—", "momentum_emoji": "❓",
        "dist_from_high": 0, "dist_from_low": 0,
        "ok": False,
    }
