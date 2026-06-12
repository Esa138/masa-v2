"""
6-filter quality gate for golden buy signals.
"""
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityFilters:
    trend_ok_buy: bool
    trend_count_up: int
    trend_count_down: int

    slope_ok_buy: bool
    gamma_slope_d: str
    gamma_slope_h4: str

    confluence_ok_buy: bool
    floor_at_gamma_count: int

    distance_ok_buy: bool
    current_distance_pct: float

    candle_ok_buy: bool
    candle_type: Optional[str]

    volume_ok: bool
    volume_ratio: Optional[float]

    base_buy_signal: bool
    final_buy_signal: bool

    def passed_count(self) -> int:
        return sum([
            self.trend_ok_buy, self.slope_ok_buy, self.confluence_ok_buy,
            self.distance_ok_buy, self.candle_ok_buy, self.volume_ok,
        ])

    def summary(self) -> dict:
        return {
            '1️⃣ الاتجاه': '✅' if self.trend_ok_buy else '❌',
            '2️⃣ ميل قاما': '✅' if self.slope_ok_buy else '❌',
            '3️⃣ التلاقي': '⭐' if self.confluence_ok_buy else '❌',
            '4️⃣ المسافة': '✅' if self.distance_ok_buy else '❌',
            '5️⃣ الشمعة': '✅' if self.candle_ok_buy else '❌',
            '6️⃣ الحجم': '✅' if self.volume_ok else '➖',
            'الإشارة': '🟢 شراء ⭐' if self.final_buy_signal else '⏸️ انتظار',
            'نسبة_التحقق': f"{self.passed_count()}/6",
        }


def check_trend_filter(
    per_tf_data: dict,
    require_daily: bool = True,
    require_h4: bool = True,
    require_h1: bool = False,
    min_trend_count: int = 1,
) -> tuple:
    """Filter 1: Long-term trend (price above gamma on key TFs)."""
    up_count = 0
    down_count = 0
    active = 0

    checks = [
        (require_daily, 'D'),
        (require_h4, '240'),
        (require_h1, '60'),
    ]

    for required, tf in checks:
        if not required or tf not in per_tf_data:
            continue
        active += 1
        if per_tf_data[tf].get('price_above_gamma'):
            up_count += 1
        else:
            down_count += 1

    return (up_count >= min_trend_count, up_count, down_count, active)


def check_slope_filter(per_tf_data: dict) -> tuple:
    """Filter 2: Gamma slope direction."""
    d_slope = per_tf_data.get('D', {}).get('gamma_slope', 'غير محدد')
    h4_slope = per_tf_data.get('240', {}).get('gamma_slope', 'غير محدد')
    slope_up = (d_slope == 'صاعد') or (h4_slope == 'صاعد')
    return slope_up, d_slope, h4_slope


def check_confluence_filter(
    per_tf_data: dict,
    support_zones: list,
    tol_pct: float = 1.0,
) -> tuple:
    """Filter 3: ZR floor confluence with gamma."""
    floor_at_gamma_count = 0

    for tf_name, data in per_tf_data.items():
        gamma = data.get('gamma_current')
        if gamma is None or gamma <= 0:
            continue
        zr = data.get('zr', {})
        for floor_key in ['z1l', 'z2l']:
            floor_price = zr.get(floor_key)
            if floor_price is None or pd.isna(floor_price) or floor_price <= 0:
                continue
            diff_pct = abs(floor_price - gamma) / gamma * 100
            if diff_pct <= tol_pct:
                floor_at_gamma_count += 1
                break

    has_touch = any(z.is_touched for z in support_zones)
    return (floor_at_gamma_count > 0 and has_touch), floor_at_gamma_count


def check_distance_filter(
    current_price: float,
    current_gamma: float,
    buy_max_dist: float = 1.5,
) -> tuple:
    """Filter 4: Distance from gamma (not too far stretched)."""
    if current_gamma is None or current_gamma <= 0:
        return False, 0.0
    dist_pct = (current_price - current_gamma) / current_gamma * 100
    return (dist_pct <= buy_max_dist), dist_pct


def check_candle_filter(df: pd.DataFrame, min_wick_ratio: float = 1.5) -> tuple:
    """Filter 5: Reversal candle (engulfing or long lower wick)."""
    if df is None or df.empty or len(df) < 2:
        return False, None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    body = abs(last['close'] - last['open'])
    lower_wick = min(last['open'], last['close']) - last['low']
    upper_wick = last['high'] - max(last['open'], last['close'])

    long_lower_wick = (body > 0 and lower_wick >= body * min_wick_ratio
                       and lower_wick > upper_wick)

    bull_engulf = (last['close'] > last['open']
                   and prev['close'] < prev['open']
                   and last['close'] >= prev['open']
                   and last['open'] <= prev['close'])

    if bull_engulf:
        return True, "ابتلاع صاعد"
    if long_lower_wick:
        return True, "ذيل سفلي قوي"
    return False, None


def check_volume_filter(
    df: pd.DataFrame,
    sma_len: int = 20,
    multiplier: float = 1.2,
) -> tuple:
    """Filter 6: Volume confirmation."""
    if df is None or 'volume' not in df.columns or len(df) < sma_len:
        return True, None
    vol_sma = df['volume'].tail(sma_len).mean()
    last_vol = df['volume'].iloc[-1]
    if vol_sma == 0:
        return True, None
    ratio = last_vol / vol_sma
    return (ratio >= multiplier), ratio


def apply_all_filters(
    engine_result: dict,
    current_tf_df: pd.DataFrame,
    config: dict = None,
) -> QualityFilters:
    """Apply all 6 quality filters."""
    if config is None:
        config = {}

    per_tf = engine_result['per_tf']
    current_price = engine_result['current_price']

    trend_ok, up_cnt, dn_cnt, active = check_trend_filter(
        per_tf,
        require_daily=config.get('require_daily', True),
        require_h4=config.get('require_h4', True),
        require_h1=config.get('require_h1', False),
        min_trend_count=config.get('min_trend_count', 1),
    )

    slope_ok, d_slope, h4_slope = check_slope_filter(per_tf)

    conf_ok, conf_count = check_confluence_filter(
        per_tf,
        engine_result['support_zones'],
        tol_pct=config.get('gamma_conf_tol', 1.0),
    )

    # Pine measures currDistPct against the CURRENT chart-TF gamma
    # (gammaCurrent), not the daily one. Compute SMA600 on the supplied
    # chart df; fall back to daily gamma when the df is too short.
    current_gamma = None
    if current_tf_df is not None and not current_tf_df.empty and 'close' in current_tf_df.columns:
        from .gamma import compute_gamma
        _g_series = compute_gamma(current_tf_df, length=600, ma_type='SMA')
        if len(_g_series) and pd.notna(_g_series.iloc[-1]):
            current_gamma = float(_g_series.iloc[-1])
    if current_gamma is None:
        current_gamma = per_tf.get('D', {}).get('gamma_current')
    dist_ok, dist_pct = check_distance_filter(
        current_price,
        current_gamma,
        buy_max_dist=config.get('buy_max_dist', 1.5),
    )

    candle_ok, candle_type = check_candle_filter(
        current_tf_df,
        min_wick_ratio=config.get('min_wick_ratio', 1.5),
    )

    vol_ok, vol_ratio = check_volume_filter(
        current_tf_df,
        sma_len=config.get('vol_sma_len', 20),
        multiplier=config.get('vol_multiplier', 1.2),
    )

    sup_touched = sum(1 for z in engine_result['support_zones'] if z.is_touched)
    gamma_above = engine_result['gamma_above_count']

    # Pine defaults: minConfluence=3, minGammaTFs=3 — the golden signal
    # requires zero-floor touches on 3+ TFs AND price above gamma on 3+ TFs.
    base_buy = (
        sup_touched >= config.get('min_confluence', 3)
        and gamma_above >= config.get('min_gamma_tfs', 3)
    )

    final_buy = (
        base_buy and trend_ok and slope_ok and conf_ok
        and dist_ok and candle_ok and vol_ok
    )

    return QualityFilters(
        trend_ok_buy=trend_ok,
        trend_count_up=up_cnt,
        trend_count_down=dn_cnt,
        slope_ok_buy=slope_ok,
        gamma_slope_d=d_slope,
        gamma_slope_h4=h4_slope,
        confluence_ok_buy=conf_ok,
        floor_at_gamma_count=conf_count,
        distance_ok_buy=dist_ok,
        current_distance_pct=dist_pct,
        candle_ok_buy=candle_ok,
        candle_type=candle_type,
        volume_ok=vol_ok,
        volume_ratio=vol_ratio,
        base_buy_signal=base_buy,
        final_buy_signal=final_buy,
    )
