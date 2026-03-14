"""
MASA V2 — Order Flow Indicators
Built on one principle: Who is initiating — the buyer or the seller?

Core Indicators:
- Delta Volume: Buy pressure vs sell pressure per bar
- Cumulative Delta Volume (CDV): The single most powerful indicator
- Absorption: Effort vs Result — smart money absorbing supply/demand
- Aggressive Ratio: Who is attacking — buyers or sellers

Supporting:
- RSI, ATR, VWAP, Zero Reflection, Volume Ratio, MA
"""

import pandas as pd
import numpy as np


# ══════════════════════════════════════════════════════════════
# ORDER FLOW — THE CORE
# ══════════════════════════════════════════════════════════════

def compute_delta_volume(high: pd.Series, low: pd.Series,
                         close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Delta Volume — approximation of buy vs sell volume per bar.

    Logic:
        Where Close falls within the bar's range tells us who won.
        Close near High = buyers dominated = positive delta
        Close near Low = sellers dominated = negative delta

    Formula:
        delta = Volume × ((Close - Low) - (High - Close)) / (High - Low)
        Simplified: Volume × (2*Close - High - Low) / (High - Low)

    This is the most direct measure available from OHLCV data.
    """
    hl_range = high - low
    hl_range = hl_range.replace(0, np.nan)

    # Position of close within the bar: -1 (at low) to +1 (at high)
    position = (2 * close - high - low) / hl_range

    delta = position * volume
    return delta.fillna(0)


def compute_cdv(high: pd.Series, low: pd.Series,
                close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Cumulative Delta Volume — running sum of delta.

    THE single most powerful indicator.
    Rising CDV = buyers accumulating — they are the aggressor
    Falling CDV = sellers distributing — they are the aggressor

    Key divergences:
    - Price down + CDV up = ABSORPTION (smart money buying the dip)
    - Price up + CDV down = DISTRIBUTION (smart money selling into strength)
    """
    delta = compute_delta_volume(high, low, close, volume)
    return delta.cumsum()


def compute_cdv_slope(high: pd.Series, low: pd.Series,
                      close: pd.Series, volume: pd.Series,
                      period: int = 10) -> pd.Series:
    """CDV trend direction over N bars. Positive = net buying."""
    cdv = compute_cdv(high, low, close, volume)
    slope = cdv.diff(period) / period
    return slope.fillna(0)


def compute_rolling_delta(high: pd.Series, low: pd.Series,
                          close: pd.Series, volume: pd.Series,
                          period: int = 20) -> pd.Series:
    """
    Rolling Delta Sum — sum of delta over last N bars.
    More responsive than CDV for detecting recent shifts.
    Positive = recent net buying, Negative = recent net selling.
    """
    delta = compute_delta_volume(high, low, close, volume)
    return delta.rolling(period).sum().fillna(0)


def compute_absorption(high: pd.Series, low: pd.Series,
                       close: pd.Series, volume: pd.Series,
                       period: int = 20) -> pd.Series:
    """
    Absorption Detection — Effort vs Result (Wyckoff).

    Principle: When there is high EFFORT (volume) but low RESULT (price movement),
    someone is absorbing the other side's orders.

    High absorption at support = smart money absorbing selling (bullish)
    High absorption at resistance = smart money absorbing buying (bearish)

    Returns: absorption score per bar (0-100)
        High score = lots of effort, little result = absorption happening
    """
    # Effort: volume relative to average
    avg_vol = volume.rolling(period).mean()
    effort = (volume / avg_vol.replace(0, np.nan)).fillna(1)

    # Result: price spread relative to ATR
    spread = (high - low).abs()
    avg_spread = spread.rolling(period).mean()
    result = (spread / avg_spread.replace(0, np.nan)).fillna(1)

    # Absorption = high effort / low result
    # When effort >> result, absorption is happening
    raw = (effort / result.replace(0, np.nan)).fillna(1)

    # Normalize to 0-100 using rolling percentile
    min_val = raw.rolling(period * 5, min_periods=period).min()
    max_val = raw.rolling(period * 5, min_periods=period).max()
    rng = (max_val - min_val).replace(0, np.nan)
    normalized = ((raw - min_val) / rng * 100).fillna(50)

    return normalized.clip(0, 100)


def compute_absorption_bias(high: pd.Series, low: pd.Series,
                            close: pd.Series, open_: pd.Series,
                            volume: pd.Series, period: int = 20) -> pd.Series:
    """
    Absorption Bias — is absorption bullish or bearish?

    When absorption is happening (high volume, small spread):
    - If close > open on those bars = bullish absorption (buying the dip)
    - If close < open on those bars = bearish absorption (selling into strength)

    Returns: rolling ratio (-1 to +1)
        Positive = bullish absorption dominates
        Negative = bearish absorption dominates
    """
    spread = high - low
    avg_spread = spread.rolling(period).mean()
    avg_vol = volume.rolling(period).mean()

    # Identify absorption bars: high volume + narrow spread
    vol_ratio = volume / avg_vol.replace(0, np.nan)
    spread_ratio = spread / avg_spread.replace(0, np.nan)

    is_absorption = (vol_ratio > 1.3) & (spread_ratio < 0.8)

    # Direction of absorption bars
    direction = np.where(close > open_, 1.0, np.where(close < open_, -1.0, 0.0))
    direction = pd.Series(direction, index=close.index)

    # Weighted by volume on absorption bars only
    weighted = np.where(is_absorption, direction * vol_ratio, 0.0)
    weighted = pd.Series(weighted, index=close.index)

    # Rolling sum
    bullish = weighted.clip(lower=0).rolling(period).sum()
    bearish = weighted.clip(upper=0).abs().rolling(period).sum()
    total = (bullish + bearish).replace(0, np.nan)
    bias = ((bullish - bearish) / total).fillna(0)

    return bias


def compute_aggressive_ratio(high: pd.Series, low: pd.Series,
                             close: pd.Series, open_: pd.Series,
                             volume: pd.Series, period: int = 20) -> pd.Series:
    """
    Aggressive Order Ratio — who is initiating?

    Aggressive buyer bar: Close > Open AND Close in upper 30% of range AND above-avg volume
    Aggressive seller bar: Close < Open AND Close in lower 30% of range AND above-avg volume

    Returns: ratio (-1 to +1)
        > 0.3 = buyers are the aggressor
        < -0.3 = sellers are the aggressor
        Near 0 = balanced
    """
    avg_vol = volume.rolling(period).mean()
    above_avg = volume > avg_vol * 0.8  # At least 80% of average

    hl_range = (high - low).replace(0, np.nan)
    close_position = (close - low) / hl_range  # 0 = at low, 1 = at high

    # Aggressive buyers: green bar + close in upper 30% + decent volume
    agg_buy = (close > open_) & (close_position > 0.7) & above_avg
    # Aggressive sellers: red bar + close in lower 30% + decent volume
    agg_sell = (close < open_) & (close_position < 0.3) & above_avg

    buy_vol = (volume * agg_buy.astype(float)).rolling(period).sum()
    sell_vol = (volume * agg_sell.astype(float)).rolling(period).sum()
    total = (buy_vol + sell_vol).replace(0, np.nan)

    ratio = ((buy_vol - sell_vol) / total).fillna(0)
    return ratio


def compute_divergence(close: pd.Series, cdv: pd.Series,
                       period: int = 20) -> pd.Series:
    """
    Price-CDV Divergence — the most powerful signal.

    - Price falling + CDV rising = BULLISH divergence (accumulation)
    - Price rising + CDV falling = BEARISH divergence (distribution)

    Returns: divergence score (-100 to +100)
        Positive = bullish divergence (accumulation signal)
        Negative = bearish divergence (distribution signal)
    """
    # Normalize price and CDV changes to comparable scales
    price_change = close.pct_change(period).fillna(0)
    cdv_change = cdv.diff(period)
    cdv_std = cdv_change.rolling(period * 3, min_periods=period).std()
    cdv_norm = (cdv_change / cdv_std.replace(0, np.nan)).fillna(0)

    # Price normalized
    price_std = price_change.rolling(period * 3, min_periods=period).std()
    price_norm = (price_change / price_std.replace(0, np.nan)).fillna(0)

    # Divergence = CDV direction minus price direction
    # Positive: CDV up while price down = bullish
    # Negative: CDV down while price up = bearish
    divergence = (cdv_norm - price_norm) * 25  # Scale to roughly -100 to +100
    return divergence.clip(-100, 100)


# ══════════════════════════════════════════════════════════════
# SUPPORTING INDICATORS
# ══════════════════════════════════════════════════════════════

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index — overbought/oversold."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> pd.Series:
    """Average True Range — volatility measure for stop-loss sizing."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr


def compute_vwap(high: pd.Series, low: pd.Series, close: pd.Series,
                 volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume Weighted Average Price — average cost basis."""
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).rolling(period).sum() / volume.rolling(period).sum()
    return vwap


def compute_zero_reflection(high: pd.Series, low: pd.Series,
                            bars: int = 400,
                            confirm_len: int = 25) -> tuple:
    """
    خوارزمية التجميد الهيكلي (زيرو انعكاس)
    Exact 1:1 translation of Pine Script f_get_structural_zr(bars, confirm_len)

    Pine Script:
        float ph = ta.pivothigh(high, confirm_len, confirm_len)
        float pl = ta.pivotlow(low, confirm_len, confirm_len)
        float ph_val = na(ph) ? 0.0 : ph
        float pl_val = na(pl) ? 10e10 : pl
        float ceiling = ta.highest(ph_val, bars)
        float floor   = ta.lowest(pl_val, bars)
        if ceiling == 0.0 or na(ceiling)
            ceiling := ta.highest(high, bars)[1]
        if floor == 10e10 or na(floor)
            floor := ta.lowest(low, bars)[1]

    Returns: (ceiling, floor)
    """
    n = len(high)
    if n < confirm_len * 2 + 10:
        return np.nan, np.nan

    h_vals = high.values
    l_vals = low.values

    # ── Step 1: Build ph_val / pl_val series (like Pine bar-by-bar) ──
    # ta.pivothigh on bar i confirms a pivot at bar (i - confirm_len)
    # ph_val[i] = pivot value if confirmed on this bar, else 0.0
    # pl_val[i] = pivot value if confirmed on this bar, else 10e10
    ph_val = np.zeros(n, dtype=np.float64)
    pl_val = np.full(n, 1e11, dtype=np.float64)

    for i in range(confirm_len, n - confirm_len):
        # Check if bar i is a pivot high
        window_h = h_vals[i - confirm_len: i + confirm_len + 1]
        if h_vals[i] >= np.nanmax(window_h):
            # Pivot at bar i, confirmed at bar i + confirm_len
            cb = i + confirm_len
            if cb < n:
                ph_val[cb] = float(h_vals[i])

        # Check if bar i is a pivot low
        window_l = l_vals[i - confirm_len: i + confirm_len + 1]
        if l_vals[i] <= np.nanmin(window_l):
            cb = i + confirm_len
            if cb < n:
                pl_val[cb] = float(l_vals[i])

    # ── Step 2: ta.highest(ph_val, bars) / ta.lowest(pl_val, bars) ──
    # On the last bar, look back `bars` bars
    end = n
    start = max(0, end - bars)

    ceiling = float(np.max(ph_val[start:end]))
    floor = float(np.min(pl_val[start:end]))

    # ── Step 3: صمام الأمان (Safety fallback) ──
    # if ceiling == 0.0 → no pivot highs found → use ta.highest(high, bars)[1]
    if ceiling == 0.0 or np.isnan(ceiling):
        ceiling = float(np.nanmax(h_vals[max(0, start): end - 1]))

    # if floor == 10e10 → no pivot lows found → use ta.lowest(low, bars)[1]
    if floor >= 1e11 or np.isnan(floor):
        floor = float(np.nanmin(l_vals[max(0, start): end - 1]))

    return ceiling, floor


def compute_zr_status(close: pd.Series, zr_high: float, zr_low: float,
                      days_for_bluesky: int = 5) -> dict:
    """
    Determine stock's relationship to Zero Reflection levels.

    Returns dict with:
        status: str — "zr_floor" | "zr_breakout" | "zr_bluesky" | "normal"
        label: str — Arabic display label
        color: str — hex color
    """
    if pd.isna(zr_high) or pd.isna(zr_low) or zr_high == 0 or zr_low == 0:
        return {"status": "normal", "label": "", "color": "#808080"}

    last_close = float(close.iloc[-1])

    # ── قاع زيرو انعكاس — at or near the ZR floor ──
    if last_close <= zr_low * 1.03:
        return {
            "status": "zr_floor",
            "label": "🔻 قاع زيرو انعكاس",
            "color": "#FF9800",
        }

    # ── Above ZR ceiling — check breakout vs blue sky ──
    if last_close > zr_high:
        # Count consecutive days above ZR ceiling
        days_above = 0
        for val in reversed(close.values):
            if float(val) > zr_high:
                days_above += 1
            else:
                break

        if days_above >= days_for_bluesky:
            # سماء زرقا — stabilized above ceiling
            return {
                "status": "zr_bluesky",
                "label": "🔵 سماء زرقا",
                "color": "#2196F3",
            }
        else:
            # اختراق زيرو انعكاس — just broke out
            return {
                "status": "zr_breakout",
                "label": "🚀 اختراق زيرو انعكاس",
                "color": "#00E676",
            }

    # ── Normal range — between floor and ceiling ──
    return {"status": "normal", "label": "", "color": "#808080"}


def compute_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Current volume vs average — how active is trading."""
    avg = volume.rolling(period).mean()
    ratio = volume / avg.replace(0, np.nan)
    return ratio.fillna(1.0)


def compute_ma(close: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return close.rolling(period).mean()


def compute_range_contraction(high: pd.Series, low: pd.Series,
                              period: int = 20) -> pd.Series:
    """
    Bollinger bandwidth squeeze — measures volatility compression.
    Low values = price is coiling, potential breakout ahead.
    """
    close_approx = (high + low) / 2
    sma = close_approx.rolling(period).mean()
    std = close_approx.rolling(period).std()
    bandwidth = (2 * std) / sma.replace(0, np.nan) * 100
    max_bw = bandwidth.rolling(100, min_periods=20).max()
    contraction = 100 * (1 - bandwidth / max_bw.replace(0, np.nan))
    return contraction.fillna(50)


# Legacy compatibility
def compute_cmf(high, low, close, volume, period=20):
    """Kept for backward compatibility. Use compute_rolling_delta instead."""
    hl_range = high - low
    hl_range = hl_range.replace(0, np.nan)
    mf_multiplier = ((close - low) - (high - close)) / hl_range
    mf_volume = mf_multiplier * volume
    cmf = mf_volume.rolling(period).sum() / volume.rolling(period).sum()
    return cmf.fillna(0)


def compute_obv(close, volume):
    """Kept for backward compatibility. Use compute_cdv instead."""
    direction = np.sign(close.diff())
    return (direction * volume).cumsum()


def compute_obv_slope(close, volume, period=10):
    """Kept for backward compatibility."""
    obv = compute_obv(close, volume)
    return (obv.diff(period) / period).fillna(0)


# ══════════════════════════════════════════════════════════════
# ADAPTIVE PARAMETERS — ATR-Based Dynamic Thresholds
# ══════════════════════════════════════════════════════════════

def compute_adaptive_params(high: pd.Series, low: pd.Series,
                            close: pd.Series, period: int = 14) -> dict:
    """
    Compute ATR-based adaptive parameters for dynamic indicator tuning.

    ATR% = ATR / Price × 100 → measures volatility as % of price.
    Low-volatility stocks get longer lookbacks, tighter thresholds.
    High-volatility stocks get shorter lookbacks, wider thresholds.

    Returns dict with adjusted parameters:
        atr_pct, volatility, volatility_label, volatility_color,
        flow_lookback, bounce_drop_threshold, bounce_rise_threshold,
        maturity_speed
    """
    atr = compute_atr(high, low, close, period)
    last_atr = float(atr.iloc[-1]) if len(atr) > 0 and pd.notna(atr.iloc[-1]) else 0
    last_close = float(close.iloc[-1]) if len(close) > 0 else 1

    atr_pct = (last_atr / last_close * 100) if last_close > 0 else 2.0

    if atr_pct < 1.5:
        # Low volatility — slow mover (e.g., Aramco, large caps)
        return {
            "atr_pct": round(atr_pct, 2),
            "volatility": "low",
            "volatility_label": "🐌 تذبذب منخفض",
            "volatility_color": "#4FC3F7",
            "flow_lookback": 25,
            "bounce_drop_threshold": -15,
            "bounce_rise_threshold": 3,
            "maturity_speed": 0.75,
        }
    elif atr_pct > 3.0:
        # High volatility — fast mover (e.g., small caps, crypto)
        return {
            "atr_pct": round(atr_pct, 2),
            "volatility": "high",
            "volatility_label": "⚡ تذبذب عالي",
            "volatility_color": "#FF9800",
            "flow_lookback": 14,
            "bounce_drop_threshold": -30,
            "bounce_rise_threshold": 8,
            "maturity_speed": 1.5,
        }
    else:
        # Medium volatility — normal behavior (default)
        return {
            "atr_pct": round(atr_pct, 2),
            "volatility": "medium",
            "volatility_label": "",
            "volatility_color": "#9ca3af",
            "flow_lookback": 20,
            "bounce_drop_threshold": -20,
            "bounce_rise_threshold": 5,
            "maturity_speed": 1.0,
        }


# ══════════════════════════════════════════════════════════════
# VOLUME PROFILE + PIVOT POINTS — Price Context
# ══════════════════════════════════════════════════════════════

def compute_volume_profile(close: pd.Series, volume: pd.Series,
                           bins: int = 20, lookback: int = 60) -> dict:
    """
    Volume Profile — find POC, HVN, LVN from last N days.

    POC = Point of Control (price level with highest volume)
    HVN = High Volume Nodes (top 3 price levels)
    LVN = Low Volume Nodes (bottom 3 price levels — volume gaps)

    Returns:
        poc: float, hvn: list[float], lvn: list[float], vp_data: list[dict]
    """
    c = close.iloc[-lookback:] if len(close) >= lookback else close
    v = volume.iloc[-lookback:] if len(volume) >= lookback else volume

    if len(c) < 10:
        return {"poc": float(c.iloc[-1]) if len(c) > 0 else 0,
                "hvn": [], "lvn": [], "vp_data": []}

    price_min = float(c.min())
    price_max = float(c.max())
    price_range = price_max - price_min

    if price_range == 0:
        return {"poc": float(c.iloc[-1]), "hvn": [], "lvn": [], "vp_data": []}

    bin_size = price_range / bins
    bin_volumes = np.zeros(bins)
    bin_centers = np.zeros(bins)

    for i in range(bins):
        bin_low = price_min + i * bin_size
        bin_high = bin_low + bin_size
        bin_centers[i] = (bin_low + bin_high) / 2

        # Sum volume for bars where close falls in this bin
        mask = (c >= bin_low) & (c < bin_high)
        bin_volumes[i] = float(v[mask].sum())

    # Handle last bin boundary (include max value)
    mask_last = c >= price_max
    bin_volumes[-1] += float(v[mask_last].sum())

    # POC
    poc_idx = int(np.argmax(bin_volumes))
    poc = float(bin_centers[poc_idx])

    # Sort by volume
    sorted_indices = np.argsort(bin_volumes)
    # Top 3 volume nodes
    hvn = [float(bin_centers[i]) for i in sorted_indices[-3:][::-1]]
    # Bottom 3 volume nodes (excluding zero-volume bins)
    non_zero = [i for i in sorted_indices if bin_volumes[i] > 0]
    lvn = [float(bin_centers[i]) for i in non_zero[:3]]

    vp_data = [
        {"price": round(float(bin_centers[i]), 2), "volume": int(bin_volumes[i])}
        for i in range(bins)
    ]

    return {
        "poc": round(poc, 2),
        "hvn": [round(h, 2) for h in hvn],
        "lvn": [round(l, 2) for l in lvn],
        "vp_data": vp_data,
    }


def compute_pivot_points(high: pd.Series, low: pd.Series,
                         close: pd.Series) -> dict:
    """
    Classic Pivot Points from last complete trading day.

    Returns: pivot, r1, r2, s1, s2
    """
    idx = -2 if len(close) >= 2 else -1
    h = float(high.iloc[idx])
    l = float(low.iloc[idx])
    c = float(close.iloc[idx])

    pivot = (h + l + c) / 3
    r1 = 2 * pivot - l
    s1 = 2 * pivot - h
    r2 = pivot + (h - l)
    s2 = pivot - (h - l)

    return {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
    }


def classify_price_location(close_price: float, poc: float, hvn: list,
                             lvn: list, pivot: float, s1: float,
                             r1: float) -> dict:
    """
    Classify where the stock price is relative to volume profile and pivots.

    Returns: vp_location, vp_location_label, vp_location_color
    """
    tol = close_price * 0.015  # 1.5% tolerance

    # At POC
    if abs(close_price - poc) <= tol:
        return {"vp_location": "poc", "vp_location_label": "عند POC",
                "vp_location_color": "#FFD700"}

    # At volume support (HVN below price, close to it)
    hvn_below = [h for h in hvn if h < close_price and close_price - h <= tol * 2]
    if hvn_below:
        return {"vp_location": "vol_support", "vp_location_label": "عند دعم حجمي",
                "vp_location_color": "#00E676"}

    # At volume resistance (HVN above price, close to it)
    hvn_above = [h for h in hvn if h > close_price and h - close_price <= tol * 2]
    if hvn_above:
        return {"vp_location": "vol_resistance", "vp_location_label": "عند مقاومة حجمية",
                "vp_location_color": "#FF5252"}

    # In volume gap (near LVN)
    for lv in lvn:
        if abs(close_price - lv) <= tol * 2:
            return {"vp_location": "vol_gap", "vp_location_label": "في فراغ حجمي",
                    "vp_location_color": "#FF9800"}

    # At pivot support/resistance
    if abs(close_price - s1) <= tol:
        return {"vp_location": "pivot_support", "vp_location_label": "عند دعم بيفوت",
                "vp_location_color": "#4FC3F7"}

    if abs(close_price - r1) <= tol:
        return {"vp_location": "pivot_resistance", "vp_location_label": "عند مقاومة بيفوت",
                "vp_location_color": "#FF8A80"}

    return {"vp_location": "none", "vp_location_label": "",
            "vp_location_color": "#808080"}
