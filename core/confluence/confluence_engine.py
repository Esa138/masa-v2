"""
Main engine: orchestrates ZR, gamma, clustering, and strength tiers.
"""
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List

from .zero_reversal import compute_zr1_zr2
from .gamma import compute_gamma, gamma_slope
from .clustering import cluster_levels, Cluster, TF_BITS
from .strength_tier import classify_strength, StrengthInfo


@dataclass
class ConfluenceZone:
    """Ready-to-display confluence zone."""
    price: float
    is_resistance: bool
    tf_count: int
    tf_names: str
    mask: int
    strength: StrengthInfo
    distance_from_price_pct: float
    is_touched: bool
    status: str = "⏸️ بعيد"      # ✅ ملموس / 🎯 قريب / ⚡ مكسور / ⏸️ بعيد
    signed_distance_pct: float = 0.0  # +ve = price above zone, -ve = below

    def to_dict(self) -> dict:
        return {
            'الحالة': self.status,
            'السعر': round(self.price, 2),
            'النوع': 'مقاومة' if self.is_resistance else 'دعم',
            'البعد': f"{self.signed_distance_pct:+.2f}%",
            'الفريمات': self.tf_names,
            'القوة': self.strength.label,
            'النجوم': self.strength.stars,
            'الموثوقية': self.strength.reliability,
            'المخاطرة_المقترحة': f"{self.strength.risk_pct}%",
            'مدة_الاحتفاظ': self.strength.holding_days,
            'اللون': self.strength.color,
        }


class ConfluenceEngine:
    """Detect multi-timeframe confluence zones."""

    def __init__(
        self,
        cluster_pct: float = 0.5,    # Pine default
        touch_pct: float = 0.5,      # Pine default
        max_dist_pct: float = 100.0, # Pine default = no filtering
        min_box_tfs: int = 2,        # Pine default
    ):
        self.cluster_pct = cluster_pct
        self.touch_pct = touch_pct
        self.max_dist_pct = max_dist_pct
        self.min_box_tfs = min_box_tfs

    def analyze(self, tf_data: Dict[str, pd.DataFrame], current_price: float) -> dict:
        """Run full multi-timeframe confluence analysis."""
        # 1. Compute ZR + Gamma per timeframe
        per_tf_data = {}
        for tf_name, df in tf_data.items():
            if tf_name not in TF_BITS or df is None or df.empty:
                continue

            # Match Pine exactly: only ZR1 + ZR2 ceiling/floor per TF.
            # ZR1 = highest pivot high & lowest pivot low in last 400 bars (confirm=25).
            # ZR2 = same with bars=300, confirm=30.
            zr = compute_zr1_zr2(df)
            gamma = compute_gamma(df, length=600, ma_type='SMA')

            gamma_val = float(gamma.iloc[-1]) if len(gamma) > 0 and pd.notna(gamma.iloc[-1]) else None

            per_tf_data[tf_name] = {
                'zr': zr,
                'gamma_current': gamma_val,
                'gamma_slope': gamma_slope(gamma, lookback=5),
                'price_above_gamma': (current_price > gamma_val) if gamma_val else None,
                'last_close': float(df['close'].iloc[-1]),
                'last_low': float(df['low'].iloc[-1]),
                'last_high': float(df['high'].iloc[-1]),
            }

        # 2. Collect raw levels
        raw_levels = self._collect_raw_levels(per_tf_data, current_price)

        # 3. Cluster
        clusters = cluster_levels(raw_levels, cluster_pct=self.cluster_pct)

        # 4. Build zones — use 60m for interaction tracking (covers ~5-10 days
        # of price action with the 50-bar lookback, capturing bounces/breaks
        # that intraday 5m would miss).
        _ref_tf = next((t for t in ['60', '15', '240', 'D', '5'] if t in tf_data), None)
        _ref_df = tf_data.get(_ref_tf) if _ref_tf else None
        zones = self._build_zones(clusters, current_price, ref_df=_ref_df)

        # 5. Filter by max distance
        zones = [z for z in zones if z.distance_from_price_pct <= self.max_dist_pct]

        # 6. Sort: strength tier (ascending = strongest first) then distance
        zones.sort(key=lambda z: (z.strength.tier.value, z.distance_from_price_pct))

        return {
            'current_price': current_price,
            'per_tf': per_tf_data,
            'zones': zones,
            'support_zones': [z for z in zones if not z.is_resistance],
            'resistance_zones': [z for z in zones if z.is_resistance],
            'gamma_above_count': sum(1 for t in per_tf_data.values() if t.get('price_above_gamma')),
            'active_tfs': len(per_tf_data),
        }

    def _collect_raw_levels(self, per_tf_data: dict, current_price: float) -> List[dict]:
        """Gather z1h/z1l/z2h/z2l from each TF — matches Pine f_addCluster calls."""
        levels = []
        for tf_name, data in per_tf_data.items():
            tf_bit = TF_BITS[tf_name]
            zr = data.get('zr', {})
            for key, price in zr.items():
                if price is None or pd.isna(price) or price <= 0:
                    continue
                # Pine: bool isRes = close < price
                is_res = current_price < price
                levels.append({
                    'price': price,
                    'is_resistance': is_res,
                    'tf_bit': tf_bit,
                    'source': f"{tf_name}-{key}",
                })
        return levels

    def _compute_interaction(self, zone_price, current_price, ref_df, touch_threshold, lookback_bars: int = 20):
        """
        Determine how price has been interacting with the zone over recent bars:
        - ✅ داخل المنطقة (still in zone)
        - 🔄 ارتد من الدعم  (touched and bounced up — support held)
        - 🔄 ارتد من المقاومة (touched and bounced down — resistance held)
        - 💥 اخترق صعوداً (broke up through zone)
        - 💥 كسر هبوطاً (broke down through zone)
        - 🎯 يقترب (close but no recent touch)
        - ⏸️ بعيد (far)
        """
        if abs(current_price - zone_price) <= touch_threshold:
            return "✅ داخل المنطقة"

        if ref_df is None or len(ref_df) < 3:
            # fallback to static
            dist_pct = abs(current_price - zone_price) / current_price * 100
            if dist_pct <= max(self.touch_pct * 6, 3.0):
                return "🎯 يقترب"
            return "⏸️ بعيد"

        # Look back N bars for a touch event
        N = min(lookback_bars, len(ref_df))
        recent = ref_df.tail(N)

        touched_idx = None
        for i in range(N - 1, -1, -1):  # newest to oldest
            bar = recent.iloc[i]
            if (bar['low'] - touch_threshold) <= zone_price <= (bar['high'] + touch_threshold):
                touched_idx = i
                break

        is_above = current_price > zone_price

        if touched_idx is None:
            dist_pct = abs(current_price - zone_price) / current_price * 100
            if dist_pct <= max(self.touch_pct * 6, 3.0):
                return "🎯 يقترب من " + ("الأعلى" if is_above else "الأسفل")
            return "⏸️ بعيد"

        # Determine which side price came from before the touch
        if touched_idx > 0:
            before = recent.iloc[:touched_idx]
            avg_close = float(before['close'].mean())
            was_above = avg_close > zone_price
        else:
            was_above = is_above

        if was_above and is_above:
            return "🔄 ارتد من الدعم"
        if (not was_above) and (not is_above):
            return "🔄 ارتد من المقاومة"
        if was_above and (not is_above):
            return "💥 كسر هبوطاً"
        if (not was_above) and is_above:
            return "💥 اخترق صعوداً"

        return "⏸️ بعيد"

    def _build_zones(self, clusters: List[Cluster], current_price: float, ref_df=None) -> List[ConfluenceZone]:
        """Convert clusters to ConfluenceZones with strength tiers."""
        zones = []
        for cluster in clusters:
            if cluster.tf_count < self.min_box_tfs and not self._is_strong_single(cluster):
                continue

            strength = classify_strength(cluster.mask)
            dist_pct = abs(current_price - cluster.price) / current_price * 100 if current_price else 0
            signed_dist = (current_price - cluster.price) / current_price * 100 if current_price else 0
            touch_threshold = current_price * self.touch_pct / 100 if current_price else 0
            is_touched = abs(current_price - cluster.price) <= touch_threshold

            # Dynamic interaction status. Lookback=50 bars on 60m TF =
            # ~5-10 trading days, enough to capture multi-day bounces.
            status = self._compute_interaction(
                cluster.price, current_price, ref_df, touch_threshold,
                lookback_bars=50,
            )

            zones.append(ConfluenceZone(
                price=cluster.price,
                is_resistance=cluster.is_resistance,
                tf_count=cluster.tf_count,
                tf_names=cluster.tf_names_str,
                mask=cluster.mask,
                strength=strength,
                distance_from_price_pct=dist_pct,
                is_touched=is_touched,
                status=status,
                signed_distance_pct=signed_dist,
            ))
        return zones

    def _is_strong_single(self, cluster: Cluster) -> bool:
        """D or 240 alone counts as strong."""
        return cluster.mask in (1, 2)
