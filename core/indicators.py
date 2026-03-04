import pandas as pd
import numpy as np
from core.utils import safe_div


def calculate_zero_reflection(
    high_col: pd.Series,
    low_col: pd.Series,
    bars: int = 400,
    confirm_len: int = 25
) -> tuple[pd.Series, pd.Series]:
    try:
        n = len(high_col)
        ph_val = np.full(n, np.nan)
        pl_val = np.full(n, np.nan)

        window_size = int(2 * confirm_len + 1)
        if n > window_size:
            roll_max = high_col.rolling(window=window_size, min_periods=1, center=True).max().values
            roll_min = low_col.rolling(window=window_size, min_periods=1, center=True).min().values

            shifted_high = high_col.shift(int(confirm_len)).values
            shifted_low = low_col.shift(int(confirm_len)).values

            with np.errstate(invalid='ignore'):
                is_ph = (shifted_high == roll_max) & ~np.isnan(shifted_high)
                is_pl = (shifted_low == roll_min) & ~np.isnan(shifted_low)

            ph_val[is_ph] = shifted_high[is_ph]
            pl_val[is_pl] = shifted_low[is_pl]

        ph_series = pd.Series(ph_val, index=high_col.index)
        pl_series = pd.Series(pl_val, index=low_col.index)

        ph_filled = ph_series.ffill()
        pl_filled = pl_series.ffill()

        ceiling = ph_filled.rolling(window=int(bars), min_periods=1).max()
        floor_s = pl_filled.rolling(window=int(bars), min_periods=1).min()

        fallback_ceiling = high_col.rolling(window=int(bars), min_periods=1).max()
        fallback_floor = low_col.rolling(window=int(bars), min_periods=1).min()

        ceiling = ceiling.where(ceiling.notna() & (ceiling > 0), fallback_ceiling)
        floor_s = floor_s.where(floor_s.notna() & (floor_s > 0), fallback_floor)

        return ceiling, floor_s

    except Exception:
        fallback_ceiling = high_col.rolling(window=int(bars), min_periods=1).max()
        fallback_floor = low_col.rolling(window=int(bars), min_periods=1).min()
        return fallback_ceiling, fallback_floor


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    diff = close.diff()
    up = diff.clip(lower=0)
    down = (-diff).clip(lower=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    ema_down_safe = ema_down.replace(0, np.nan)
    rs = ema_up / ema_down_safe
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def compute_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int = 20) -> pd.Series:
    if volume.sum() == 0:
        return close.rolling(window).mean()
    typical_price = (high + low + close) / 3
    vol_sum = volume.rolling(window).sum().replace(0, np.nan)
    return (typical_price * volume).rolling(window).sum() / vol_sum


def compute_direction_counter(close: pd.Series) -> list[int]:
    diff = close.diff()
    direction = np.where(diff > 0, 1, np.where(diff < 0, -1, 0))
    counters = []
    curr = 0
    for d in direction:
        if d == 1:
            curr = curr + 1 if curr > 0 else 1
        elif d == -1:
            curr = curr - 1 if curr < 0 else -1
        else:
            curr = 0
        counters.append(curr)
    return counters


def calc_momentum_score(
    pct_1d: float, pct_5d: float, pct_10d: float, vol_ratio: float
) -> int:
    def get_points(val, weights):
        if pd.isna(val) or val == 0:
            return weights[3]
        abs_val = abs(val)
        if val > 0:
            if abs_val >= 1.0:
                return weights[0]
            elif abs_val >= 0.1:
                return weights[1]
            return weights[2]
        else:
            if abs_val >= 1.0:
                return weights[6]
            elif abs_val >= 0.1:
                return weights[5]
            return weights[4]

    s5 = get_points(pct_5d, [40, 35, 28, 20, 12, 6, 0])
    s10 = get_points(pct_10d, [25, 22, 18, 12, 8, 4, 0])
    s1 = get_points(pct_1d, [15, 13, 10, 7, 4, 2, 0])

    if pd.isna(pct_1d) or pct_1d == 0:
        svol = 10
    elif pct_1d > 0:
        svol = 20 if vol_ratio > 1.0 else 16
    else:
        svol = 6 if vol_ratio <= 1.0 else 0

    return int(min(100, max(0, s5 + s10 + s1 + svol)))


# ── RSI Divergence Detection ─────────────────────────────────
def detect_rsi_divergence(
    close: pd.Series, rsi: pd.Series, lookback: int = 10
) -> dict:
    """
    Detect RSI divergence (bearish or bullish).
    - Bearish: price makes higher high but RSI makes lower high
    - Bullish: price makes lower low but RSI makes higher low
    Returns: {type, strength(0-1), description_ar}
    """
    result = {"type": "none", "strength": 0.0, "description_ar": ""}

    try:
        if len(close) < lookback + 2 or len(rsi) < lookback + 2:
            return result

        c = close.values
        r = rsi.values

        # Current vs lookback-ago
        curr_price = c[-1]
        prev_price = np.nanmax(c[-(lookback + 1):-1])  # highest in lookback
        curr_rsi = r[-1]
        prev_rsi_at_peak = r[-(lookback + 1):-1]

        # Find the index of the price peak in lookback window
        peak_idx = np.nanargmax(c[-(lookback + 1):-1])
        prev_rsi_peak = prev_rsi_at_peak[peak_idx] if not np.isnan(prev_rsi_at_peak[peak_idx]) else 50

        # Bearish divergence: price higher high + RSI lower high
        if curr_price > prev_price and curr_rsi < prev_rsi_peak:
            rsi_drop = (prev_rsi_peak - curr_rsi) / max(prev_rsi_peak, 1)
            strength = min(1.0, max(0.0, rsi_drop * 2))
            if strength >= 0.15:
                result = {
                    "type": "bearish",
                    "strength": round(strength, 2),
                    "description_ar": f"📉 تباين RSI هبوطي: السعر يصنع قمة جديدة لكن RSI يتراجع (قوة {strength:.0%})"
                }
                return result

        # Bullish divergence: price lower low + RSI higher low
        prev_low = np.nanmin(c[-(lookback + 1):-1])
        trough_idx = np.nanargmin(c[-(lookback + 1):-1])
        prev_rsi_trough = prev_rsi_at_peak[trough_idx] if not np.isnan(prev_rsi_at_peak[trough_idx]) else 50

        if curr_price < prev_low and curr_rsi > prev_rsi_trough:
            rsi_rise = (curr_rsi - prev_rsi_trough) / max(100 - prev_rsi_trough, 1)
            strength = min(1.0, max(0.0, rsi_rise * 2))
            if strength >= 0.15:
                result = {
                    "type": "bullish",
                    "strength": round(strength, 2),
                    "description_ar": f"📈 تباين RSI صعودي: السعر يصنع قاع جديد لكن RSI يرتفع (قوة {strength:.0%})"
                }

    except Exception:
        pass

    return result


# ── Volume-Price Divergence Detection ─────────────────────────
def detect_volume_price_divergence(
    close: pd.Series, volume: pd.Series, bars: int = 3
) -> dict:
    """
    Detect volume-price divergence.
    - Bearish: price rises N bars but volume decreasing = fake breakout
    - Bullish: price falls N bars but volume decreasing = selling exhaustion
    Returns: {type, description_ar}
    """
    result = {"type": "none", "description_ar": ""}

    try:
        if len(close) < bars + 1 or len(volume) < bars + 1:
            return result

        c = close.values
        v = volume.values

        # Check last N bars
        price_changes = [c[-(i)] - c[-(i + 1)] for i in range(1, bars + 1)]
        vol_changes = [v[-(i)] - v[-(i + 1)] for i in range(1, bars + 1)]

        price_rising = all(pc > 0 for pc in price_changes)
        price_falling = all(pc < 0 for pc in price_changes)
        vol_decreasing = all(vc < 0 for vc in vol_changes)
        vol_increasing = all(vc > 0 for vc in vol_changes)

        # Bearish: price up + volume down
        if price_rising and vol_decreasing:
            result = {
                "type": "bearish",
                "description_ar": f"📉 تباين حجم هبوطي: السعر يصعد {bars} شموع لكن الحجم يتناقص (اختراق وهمي محتمل)"
            }
        # Bullish: price down + volume down
        elif price_falling and vol_decreasing:
            result = {
                "type": "bullish",
                "description_ar": f"📈 تباين حجم صعودي: السعر يهبط {bars} شموع لكن الحجم يتناقص (استنفاد بيعي)"
            }
        # Extra: price up + volume surging = healthy breakout (confirmation)
        elif price_rising and vol_increasing:
            result = {
                "type": "confirmed",
                "description_ar": f"✅ تأكيد حجم: السعر يصعد مع تزايد الحجم ({bars} شموع متوافقة)"
            }

    except Exception:
        pass

    return result


# ── ATR Regime Detection ──────────────────────────────────────
def compute_atr_regime(
    atr: pd.Series, close: pd.Series, ma50: pd.Series
) -> dict:
    """
    Classify ATR regime: expanding (volatile), contracting (squeeze), normal.
    Returns: {regime, atr_ratio, score_modifier, description_ar}
    """
    result = {
        "regime": "normal",
        "atr_ratio": 1.0,
        "score_modifier": 0,
        "description_ar": ""
    }

    try:
        if len(atr) < 20 or len(close) < 2:
            return result

        last_atr = atr.values[-1]
        avg_atr = np.nanmean(atr.values[-20:])

        if pd.isna(last_atr) or pd.isna(avg_atr) or avg_atr <= 0:
            return result

        ratio = last_atr / avg_atr
        result["atr_ratio"] = round(ratio, 2)

        last_close = close.values[-1]
        last_ma50 = ma50.values[-1] if len(ma50) > 0 else last_close
        is_uptrend = last_close > last_ma50 if pd.notna(last_ma50) else True

        if ratio > 1.3:
            if is_uptrend:
                result.update({
                    "regime": "expanding_bull",
                    "score_modifier": 5,
                    "description_ar": f"🔥 تذبذب متوسع صاعد (ATR ×{ratio:.1f}) — زخم قوي مع ترند"
                })
            else:
                result.update({
                    "regime": "expanding_bear",
                    "score_modifier": -5,
                    "description_ar": f"⚠️ تذبذب متوسع هابط (ATR ×{ratio:.1f}) — ذعر بيعي"
                })
        elif ratio < 0.7:
            result.update({
                "regime": "contracting",
                "score_modifier": 3,
                "description_ar": f"🔋 ضغط تذبذبي (ATR ×{ratio:.1f}) — انفجار سعري قادم"
            })
        else:
            result.update({
                "regime": "normal",
                "score_modifier": 0,
                "description_ar": ""
            })

    except Exception:
        pass

    return result


# ══════════════════════════════════════════════════════════════
# 🏗️ Institutional Accumulation Detection System
# ══════════════════════════════════════════════════════════════

# ── Accumulation Phase Configuration ─────────────────────────
ACCUM_PHASES = {
    "neutral":       {"label": "محايد ⚪",                "color": "#808080", "priority": 0},
    "early":         {"label": "بداية تجميع 🟡",         "color": "#FFD700", "priority": 1},
    "mid":           {"label": "وسط التجميع 🟣",          "color": "#CE93D8", "priority": 2},
    "strong":        {"label": "تجميع قوي 🔵",           "color": "#2196F3", "priority": 3},
    "late":          {"label": "نهاية تجميع 🟢",         "color": "#00E676", "priority": 4},
    "distribute":    {"label": "تصريف 🔴",               "color": "#FF5252", "priority": 5},
    # ── Lifecycle phases (post-breakout) ──
    "breakout":      {"label": "انطلاق 🚀",              "color": "#FF9800", "priority": 6},
    "pullback_buy":  {"label": "ارتداد صحي — فرصة 🟢",   "color": "#4CAF50", "priority": 7},
    "pullback_wait": {"label": "ارتداد — انتظر 🟡",      "color": "#FFC107", "priority": 8},
    "exhausted":     {"label": "استنفاد الحركة 🔴",       "color": "#E91E63", "priority": 9},
}


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    On Balance Volume — cumulative volume direction tracker.
    Rising OBV = accumulation / institutional buying.
    Falling OBV = distribution / selling.
    """
    direction = np.where(close.diff() > 0, 1, np.where(close.diff() < 0, -1, 0))
    obv = (volume * direction).cumsum()
    return obv


def compute_cmf(
    high: pd.Series, low: pd.Series, close: pd.Series,
    volume: pd.Series, period: int = 20
) -> pd.Series:
    """
    Chaikin Money Flow — buying/selling pressure indicator.
    Range: -1 to +1.  Positive = buying pressure, Negative = selling.
    Formula: SUM(MFV, period) / SUM(Volume, period)
    where MFV = ((close-low) - (high-close)) / (high-low) * volume
    """
    hl_range = high - low
    hl_range = hl_range.replace(0, np.nan)  # avoid division by zero
    mf_multiplier = ((close - low) - (high - close)) / hl_range
    mf_volume = mf_multiplier * volume
    cmf = mf_volume.rolling(period, min_periods=1).sum() / \
          volume.rolling(period, min_periods=1).sum().replace(0, np.nan)
    return cmf.fillna(0)


def compute_linear_slope(series: pd.Series, window: int = 20) -> pd.Series:
    """
    Rolling linear regression slope — measures trend direction.
    Positive = uptrend, Negative = downtrend, ~0 = flat/sideways.
    Normalized by the mean of the window for comparability.
    """
    def _slope(arr):
        arr = arr[~np.isnan(arr)]
        n = len(arr)
        if n < 3:
            return 0.0
        x = np.arange(n)
        mean_x = x.mean()
        mean_y = arr.mean()
        denom = ((x - mean_x) ** 2).sum()
        if denom == 0:
            return 0.0
        slope = ((x - mean_x) * (arr - mean_y)).sum() / denom
        # Normalize: slope per bar as % of mean value
        if abs(mean_y) > 0:
            slope = slope / abs(mean_y)
        return slope

    return series.rolling(window, min_periods=5).apply(_slope, raw=True).fillna(0)


def compute_range_contraction(
    high: pd.Series, low: pd.Series, window: int = 20
) -> pd.Series:
    """
    Range contraction ratio — detects price squeeze.
    Current range / average range over window.
    < 0.6 = tight squeeze (accumulation signal).
    > 1.3 = expansion (breakout or distribution).
    """
    daily_range = high - low
    avg_range = daily_range.rolling(window, min_periods=5).mean()
    avg_range = avg_range.replace(0, np.nan)
    # Use last 5 bars range vs full window average
    recent_range = daily_range.rolling(5, min_periods=1).mean()
    ratio = recent_range / avg_range
    return ratio.fillna(1.0)


def compute_accumulation_score(
    cmf: pd.Series, obv_slope: pd.Series, rsi: pd.Series,
    vol_ratio: pd.Series, range_ratio: pd.Series,
    price_slope: pd.Series
) -> pd.Series:
    """
    Composite accumulation score 0-100.
    Detects institutional accumulation via 6 weighted factors:
      CMF (25) + OBV Slope (25) + RSI Zone (15) + Range (15) + Volume (10) + Price (10)
    Higher = stronger accumulation evidence.
    """
    score = pd.Series(0.0, index=cmf.index)

    # ── Factor 1: CMF (25 points) ─────────────────────────────
    # Positive CMF = buying pressure. Range clamp [-0.3, +0.3]
    cmf_clamped = cmf.clip(-0.3, 0.3)
    # Map [-0.3, +0.3] → [0, 25]
    cmf_pts = ((cmf_clamped + 0.3) / 0.6) * 25
    score += cmf_pts

    # ── Factor 2: OBV Slope (25 points) ───────────────────────
    # Rising OBV = accumulation. Clamp [-0.05, +0.05]
    obv_clamped = obv_slope.clip(-0.05, 0.05)
    obv_pts = ((obv_clamped + 0.05) / 0.10) * 25
    score += obv_pts

    # ── Factor 3: RSI Zone (15 points) ────────────────────────
    # Sweet spot: RSI 30-50 (accumulation zone) = max points
    # RSI < 30 or > 70 = low points
    rsi_pts = pd.Series(7.5, index=rsi.index)  # default mid
    rsi_pts = rsi_pts.where(~((rsi >= 30) & (rsi <= 50)), 15.0)   # optimal
    rsi_pts = rsi_pts.where(~((rsi > 50) & (rsi <= 60)), 10.0)    # decent
    rsi_pts = rsi_pts.where(~((rsi > 60) & (rsi <= 70)), 5.0)     # elevated
    rsi_pts = rsi_pts.where(~(rsi > 70), 2.0)                      # overbought
    rsi_pts = rsi_pts.where(~(rsi < 30), 8.0)                      # oversold (possible)
    score += rsi_pts

    # ── Factor 4: Range Contraction (15 points) ───────────────
    # Tight range (< 0.6) = squeeze = accumulation. Expansion = less likely
    range_pts = pd.Series(7.5, index=range_ratio.index)
    range_pts = range_pts.where(~(range_ratio < 0.5), 15.0)       # extreme squeeze
    range_pts = range_pts.where(~((range_ratio >= 0.5) & (range_ratio < 0.7)), 12.0)
    range_pts = range_pts.where(~((range_ratio >= 0.7) & (range_ratio < 0.9)), 8.0)
    range_pts = range_pts.where(~((range_ratio >= 0.9) & (range_ratio < 1.1)), 5.0)
    range_pts = range_pts.where(~(range_ratio >= 1.1), 2.0)       # expanding
    score += range_pts

    # ── Factor 5: Volume Dryup (10 points) ────────────────────
    # Low volume during sideways = accumulation (institutions buy quietly)
    vol_pts = pd.Series(5.0, index=vol_ratio.index)
    vol_pts = vol_pts.where(~(vol_ratio < 0.5), 10.0)             # very dry
    vol_pts = vol_pts.where(~((vol_ratio >= 0.5) & (vol_ratio < 0.8)), 8.0)
    vol_pts = vol_pts.where(~((vol_ratio >= 0.8) & (vol_ratio < 1.2)), 5.0)
    vol_pts = vol_pts.where(~(vol_ratio >= 1.2), 3.0)             # high volume
    score += vol_pts

    # ── Factor 6: Price Slope (10 points) ─────────────────────
    # Flat/slightly positive price = ideal accumulation
    p_slope_abs = price_slope.abs()
    price_pts = pd.Series(5.0, index=price_slope.index)
    price_pts = price_pts.where(~(p_slope_abs < 0.002), 10.0)     # very flat
    price_pts = price_pts.where(~((p_slope_abs >= 0.002) & (p_slope_abs < 0.005)), 8.0)
    price_pts = price_pts.where(~((p_slope_abs >= 0.005) & (p_slope_abs < 0.01)), 5.0)
    price_pts = price_pts.where(~(p_slope_abs >= 0.01), 2.0)      # trending
    score += price_pts

    return score.clip(0, 100).round(1)


def compute_accumulation_pressure(
    accum_days: int,
    range_ratio: float,
    vol_ratio: float,
    cmf_slope: float,
    score_slope: float,
) -> float:
    """
    Accumulation Pressure Gauge — composite score 0-100.
    Measures how much "energy" is built up during accumulation.
    Higher pressure = closer to breakout.

    5 weighted factors:
      Time (30) + Range Squeeze (25) + Volume Dryup (20) + CMF Accel (15) + Score Velocity (10)
    """
    # ── Factor 1: Time Pressure (30 pts) ─────────────────────
    # Longer accumulation = more compressed spring
    # 40+ days = max pressure
    time_pts = min(1.0, accum_days / 40.0) * 30.0

    # ── Factor 2: Range Squeeze (25 pts) ─────────────────────
    # Tighter range = more pressure. range_ratio < 0.5 = max
    range_raw = max(0.0, (1.0 - range_ratio) / 0.5)
    range_pts = min(1.0, range_raw) * 25.0

    # ── Factor 3: Volume Dryup (20 pts) ──────────────────────
    # Lower volume = institutions accumulating quietly
    vol_raw = max(0.0, (1.0 - vol_ratio) / 0.5)
    vol_pts = min(1.0, vol_raw) * 20.0

    # ── Factor 4: CMF Acceleration (15 pts) ──────────────────
    # Rising CMF slope = buying pressure increasing
    # Clamp slope to [-0.05, +0.05] then normalize
    cmf_clamped = max(-0.05, min(0.05, cmf_slope))
    cmf_pts = ((cmf_clamped + 0.05) / 0.10) * 15.0

    # ── Factor 5: Score Velocity (10 pts) ────────────────────
    # Rising accumulation score = momentum building
    # Clamp slope to [-0.03, +0.03] then normalize
    score_clamped = max(-0.03, min(0.03, score_slope))
    score_pts = ((score_clamped + 0.03) / 0.06) * 10.0

    pressure = time_pts + range_pts + vol_pts + cmf_pts + score_pts
    return round(max(0.0, min(100.0, pressure)), 1)


def compute_expected_move(
    last_atr: float,
    accum_days: int,
    pressure_score: float,
    last_close: float,
) -> dict:
    """
    Estimate the expected breakout move based on accumulation characteristics.

    Formula: move = ATR × (1 + days/20) × (pressure/50)
    Capped at 30% of current price.

    Returns: {move_value, move_pct, target_price}
    """
    if last_close <= 0 or last_atr <= 0:
        return {"move_value": 0.0, "move_pct": 0.0, "target_price": last_close}

    # Duration multiplier: longer accumulation → bigger expected move
    duration_mult = 1.0 + (accum_days / 20.0)

    # Pressure multiplier: higher pressure → bigger expected move
    pressure_mult = max(0.1, pressure_score / 50.0)

    # Raw expected move
    move = last_atr * duration_mult * pressure_mult

    # Cap at 30% of price
    max_move = last_close * 0.30
    move = min(move, max_move)

    move_pct = (move / last_close) * 100.0
    target = last_close + move

    return {
        "move_value": round(move, 4),
        "move_pct": round(move_pct, 1),
        "target_price": round(target, 4),
    }


def detect_accumulation_phase(
    accum_score: pd.Series, cmf: pd.Series, obv_slope: pd.Series
) -> pd.Series:
    """
    Classify accumulation phase from score + CMF + OBV slope.
    6 phases: neutral, early, mid, strong, late, distribute.

    Phase logic (strict thresholds for higher accuracy):
      - distribute: CMF < -0.05 AND OBV slope < 0  (selling despite any score)
      - late:       score >= 80 AND CMF > 0.10 AND OBV slope > 0
      - strong:     score >= 68 AND CMF > 0.05 AND OBV slope > 0
      - mid:        score >= 45
      - early:      score >= 30
      - neutral:    score < 30
    """
    phase = pd.Series("neutral", index=accum_score.index)

    # Layer by priority (lowest first, highest overwrites)
    phase = phase.where(~(accum_score >= 30), "early")
    phase = phase.where(~(accum_score >= 45), "mid")
    phase = phase.where(~((accum_score >= 68) & (cmf > 0.05) & (obv_slope > 0)), "strong")
    phase = phase.where(~((accum_score >= 80) & (cmf > 0.10) & (obv_slope > 0)), "late")

    # Distribution override: CMF negative + OBV falling = institutional selling
    distribute_mask = (cmf < -0.05) & (obv_slope < 0)
    phase = phase.where(~distribute_mask, "distribute")

    return phase
