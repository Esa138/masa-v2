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
        cluster_pct: float = 0.5,
        touch_pct: float = 0.5,
        max_dist_pct: float = 10.0,
        min_box_tfs: int = 2,
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

            zr = compute_zr1_zr2(df)
            gamma = compute_gamma(df, length=600, ma_type='HMA')

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

        # 4. Build zones
        zones = self._build_zones(clusters, current_price)

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
        """Gather all ZR levels from all timeframes."""
        levels = []
        for tf_name, data in per_tf_data.items():
            tf_bit = TF_BITS[tf_name]
            zr = data['zr']
            for key, price in zr.items():
                if price is None or pd.isna(price) or price <= 0:
                    continue
                # Level above current = resistance, below = support
                is_res = current_price < price
                levels.append({
                    'price': price,
                    'is_resistance': is_res,
                    'tf_bit': tf_bit,
                    'source': f"{tf_name}-{key}",
                })
        return levels

    def _build_zones(self, clusters: List[Cluster], current_price: float) -> List[ConfluenceZone]:
        """Convert clusters to ConfluenceZones with strength tiers."""
        zones = []
        for cluster in clusters:
            # Skip weak single-TF clusters unless from D/240
            if cluster.tf_count < self.min_box_tfs and not self._is_strong_single(cluster):
                continue

            strength = classify_strength(cluster.mask)
            dist_pct = abs(current_price - cluster.price) / current_price * 100 if current_price else 0
            signed_dist = (current_price - cluster.price) / current_price * 100 if current_price else 0
            touch_threshold = current_price * self.touch_pct / 100 if current_price else 0
            is_touched = abs(current_price - cluster.price) <= touch_threshold

            # Status: broken / touched / approaching / far
            if is_touched:
                status = "✅ ملموس"
            elif cluster.is_resistance and current_price > cluster.price + touch_threshold:
                status = "⚡ مكسور (اختراق)"
            elif (not cluster.is_resistance) and current_price < cluster.price - touch_threshold:
                status = "⚡ مكسور (هبوط)"
            elif dist_pct <= max(self.touch_pct * 6, 3.0):  # within ~3%
                status = "🎯 قريب"
            else:
                status = "⏸️ بعيد"

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
