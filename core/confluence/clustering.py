"""
Cluster nearby support/resistance levels across timeframes.
Each cluster tracks which timeframes contributed via bit-mask.
"""
import pandas as pd
from dataclasses import dataclass, field
from typing import List


# Bit-mask for timeframe tracking
TF_BITS = {
    'D':    1,   # TF1 - Daily
    '240':  2,   # TF2 - 4 hours
    '60':   4,   # TF3 - 1 hour
    '15':   8,   # TF4 - 15 minutes
    '5':    16,  # TF5 - 5 minutes
    'W':    32,  # TF6 - Weekly (sovereign horizon)
}
TF_LABELS = {32: 'W', 1: 'D', 2: '4H', 4: '1H', 8: '15m', 16: '5m'}


@dataclass
class Cluster:
    """Support/resistance zone aggregated from multiple timeframes."""
    price: float
    is_resistance: bool
    mask: int = 0
    levels: List[float] = field(default_factory=list)
    floor_count: int = 0    # levels sourced from pivot LOWS (z1l/z2l)
    ceil_count: int = 0     # levels sourced from pivot HIGHS (z1h/z2h)

    @property
    def origin(self) -> str:
        """What the zone is MADE OF — independent of current price side."""
        if self.floor_count > self.ceil_count:
            return 'floor'
        if self.ceil_count > self.floor_count:
            return 'ceiling'
        return 'mixed'

    @property
    def tf_count(self) -> int:
        return bin(self.mask).count('1')

    @property
    def tf_names(self) -> List[str]:
        return [name for bit, name in TF_LABELS.items() if self.mask & bit]

    @property
    def tf_names_str(self) -> str:
        return '·'.join(self.tf_names)


def cluster_levels(raw_levels: List[dict], cluster_pct: float = 0.5,
                   abs_threshold: float = None) -> List[Cluster]:
    """
    Cluster nearby levels into aggregated zones.

    raw_levels: list of {'price': float, 'is_resistance': bool, 'tf_bit': int}
    cluster_pct: merge threshold as % of price (fallback)
    abs_threshold: absolute price distance (e.g. 0.5×ATR) — takes
        precedence over cluster_pct when provided
    """
    clusters: List[Cluster] = []

    for level in raw_levels:
        price = level.get('price')
        is_res = level.get('is_resistance', False)
        tf_bit = level.get('tf_bit', 0)
        kind = level.get('kind', '')  # 'floor' / 'ceiling'

        if price is None or pd.isna(price) or price <= 0:
            continue

        threshold = abs_threshold if abs_threshold else price * cluster_pct / 100
        merged = False

        for cluster in clusters:
            same_type = cluster.is_resistance == is_res
            close_enough = abs(cluster.price - price) <= threshold

            if same_type and close_enough:
                # Average prices (weighted by count)
                count = cluster.tf_count
                cluster.price = (cluster.price * count + price) / (count + 1)
                cluster.mask |= tf_bit
                cluster.levels.append(price)
                if kind == 'floor':
                    cluster.floor_count += 1
                elif kind == 'ceiling':
                    cluster.ceil_count += 1
                merged = True
                break

        if not merged:
            clusters.append(Cluster(
                price=price,
                is_resistance=is_res,
                mask=tf_bit,
                levels=[price],
                floor_count=1 if kind == 'floor' else 0,
                ceil_count=1 if kind == 'ceiling' else 0,
            ))

    return clusters
