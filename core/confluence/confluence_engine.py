"""
Main engine: orchestrates ZR, gamma, clustering, and strength tiers.
"""
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List

from .zero_reversal import compute_zr1_zr2
from .gamma import compute_gamma, gamma_slope
from .clustering import cluster_levels, Cluster, TF_BITS
from .strength_tier import classify_strength, StrengthInfo
from .gann import compute_gann_box, match_gann_level


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
    triggered_tfs: dict = field(default_factory=dict)  # {tf_name: bars_ago}
    touch_count: int = 0        # distinct touch events in lookback window
    inst_touches: int = 0       # touches on institutional volume (≥1.5× avg)
    flipped: bool = False       # broke through recently → role reversed
    gann_level: str = ''        # '61.8% ⭐' when zone sits on a Gann fib

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
        cluster_pct: float = 0.5,    # Pine default (fallback when ATR off)
        touch_pct: float = 0.5,      # Pine default
        max_dist_pct: float = 100.0, # Pine default = no filtering
        min_box_tfs: int = 2,        # Pine default
        use_atr_cluster: bool = True,  # volatility-adaptive merging
        atr_mult: float = 0.5,         # merge threshold = 0.5 × ATR(D,14)
        vol_factor: float = 1.5,       # institutional-volume touch multiplier
    ):
        self.cluster_pct = cluster_pct
        self.touch_pct = touch_pct
        self.max_dist_pct = max_dist_pct
        self.min_box_tfs = min_box_tfs
        self.use_atr_cluster = use_atr_cluster
        self.atr_mult = atr_mult
        self.vol_factor = vol_factor

    @staticmethod
    def _daily_atr(df: pd.DataFrame, period: int = 14):
        """ATR(14) on the daily frame — volatility reference for clustering."""
        if df is None or len(df) < period + 1:
            return None
        h, l, c = df['high'], df['low'], df['close']
        prev_c = c.shift(1)
        tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else None

    def _count_touches(self, zone_price: float, df: pd.DataFrame,
                       touch_threshold: float, lookback: int = 200):
        """
        Count distinct touch events of a zone in the recent window.
        A touch event = one or more consecutive bars whose [low, high]
        range reaches the zone, separated by non-touching bars.
        Returns (touches, institutional_touches) — the latter are touches
        that happened on volume ≥ vol_factor × 20-bar average.
        """
        if df is None or len(df) < 5:
            return 0, 0
        recent = df.tail(lookback)
        vols = recent['volume'].fillna(0)
        vol_ma = vols.rolling(20, min_periods=5).mean()
        touching = ((recent['low'] - touch_threshold) <= zone_price) & \
                   (zone_price <= (recent['high'] + touch_threshold))
        touches = inst = 0
        prev = False
        t_vals = touching.values
        for i in range(len(t_vals)):
            if t_vals[i] and not prev:
                touches += 1
                vm = vol_ma.iloc[i]
                if pd.notna(vm) and vm > 0 and vols.iloc[i] >= self.vol_factor * vm:
                    inst += 1
            prev = t_vals[i]
        return touches, inst

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

        # 3. Cluster — ATR-adaptive threshold when daily data available.
        # 0.5×ATR(D) widens merging for volatile tickers (TSLA) and
        # tightens it for calm ones (KO) without per-market tuning.
        _atr_d = self._daily_atr(tf_data.get('D'))  # also used for stop-loss/R:R
        _abs_thr = (self.atr_mult * _atr_d) if (_atr_d and self.use_atr_cluster) else None
        clusters = cluster_levels(raw_levels, cluster_pct=self.cluster_pct,
                                  abs_threshold=_abs_thr)

        # 4. Build zones — use 60m for interaction tracking (covers ~5-10 days
        # of price action with the 50-bar lookback, capturing bounces/breaks
        # that intraday 5m would miss).
        _ref_tf = next((t for t in ['60', '15', '240', 'D', '5'] if t in tf_data), None)
        _ref_df = tf_data.get(_ref_tf) if _ref_tf else None
        zones = self._build_zones(clusters, current_price, ref_df=_ref_df, tf_data=tf_data)

        # 5. Filter by max distance
        zones = [z for z in zones if z.distance_from_price_pct <= self.max_dist_pct]

        # 5b. Gann box on the daily frame; annotate zones that coincide
        # with a fib level (gold 50/61.8 confirm independently of ZR).
        gann_box = compute_gann_box(tf_data.get('D'))
        if gann_box:
            for z in zones:
                m = match_gann_level(z.price, gann_box)
                if m:
                    z.gann_level = m

        # 6. Sort: strength tier (ascending = strongest first) then distance
        zones.sort(key=lambda z: (z.strength.tier.value, z.distance_from_price_pct))

        # 7. Recent price direction on the reference TF — used by Esa
        # approach scenarios ('price falling toward support' needs the
        # price to actually be falling, not just near).
        recent_trend = 'flat'
        if _ref_df is not None and len(_ref_df) >= 8:
            _now = float(_ref_df['close'].iloc[-1])
            _then = float(_ref_df['close'].iloc[-7])  # ~6 bars back
            if _then > 0:
                _chg = (_now - _then) / _then * 100
                if _chg < -0.3:
                    recent_trend = 'down'
                elif _chg > 0.3:
                    recent_trend = 'up'

        return {
            'current_price': current_price,
            'per_tf': per_tf_data,
            'zones': zones,
            'support_zones': [z for z in zones if not z.is_resistance],
            'resistance_zones': [z for z in zones if z.is_resistance],
            'gamma_above_count': sum(1 for t in per_tf_data.values() if t.get('price_above_gamma')),
            'active_tfs': len(per_tf_data),
            'recent_trend': recent_trend,
            'recent_trend_tf': _ref_tf,
            'gann': gann_box,
            'atr_d': _atr_d,
        }

    def _detect_trigger_tfs(self, zone_price: float, tf_data: dict, touch_threshold: float,
                             tf_lookback: dict = None) -> dict:
        """
        For a given zone price, check WHICH TFs actually had bars touch
        (or break through) the zone recently. Returns a dict:
          {tf_name: bars_since_touch}  for TFs that touched.

        A TF "triggered" if any bar in its recent lookback window had
        [low, high] range containing zone_price ± touch_threshold.
        """
        if tf_lookback is None:
            # tuned for each TF — covers ~5 trading days each
            tf_lookback = {'W': 3, 'D': 5, '240': 30, '60': 50, '15': 100, '5': 200}

        triggers = {}
        for tf_name, df in (tf_data or {}).items():
            if df is None or df.empty:
                continue
            N = min(tf_lookback.get(tf_name, 20), len(df))
            recent = df.tail(N)
            for i in range(N - 1, -1, -1):
                bar = recent.iloc[i]
                if (bar['low'] - touch_threshold) <= zone_price <= (bar['high'] + touch_threshold):
                    triggers[tf_name] = N - 1 - i  # bars ago
                    break
        return triggers

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

    def _build_zones(self, clusters: List[Cluster], current_price: float, ref_df=None, tf_data=None) -> List[ConfluenceZone]:
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

            # Which TFs actually had bars touching this zone recently?
            triggered = self._detect_trigger_tfs(
                cluster.price, tf_data, touch_threshold,
            ) if tf_data else {}

            # Historical touch strength on the reference TF: how many
            # distinct times was this zone defended, and how many of
            # those defenses came on institutional volume?
            touch_count, inst_touches = self._count_touches(
                cluster.price, ref_df, touch_threshold, lookback=200,
            )

            # Flip: a 💥 break means the zone's role reversed —
            # broken support acts as resistance and vice versa.
            flipped = status.startswith('💥')

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
                triggered_tfs=triggered,
                touch_count=touch_count,
                inst_touches=inst_touches,
                flipped=flipped,
            ))
        return zones

    def _is_strong_single(self, cluster: Cluster) -> bool:
        """D or 240 alone counts as strong."""
        return cluster.mask in (1, 2)
