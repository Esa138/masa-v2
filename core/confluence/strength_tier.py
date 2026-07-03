"""
Classify confluence zones into 6 strength tiers (Weekly adds السيادي).
"""
from enum import Enum
from dataclasses import dataclass


class StrengthTier(Enum):
    SOVEREIGN = 0        # Weekly + (Daily or 4H) — strongest possible
    PURE_STRONG = 1
    MIXED_STRONG = 2
    PURE_MEDIUM = 3
    MIXED_MEDIUM = 4
    PURE_FAST = 5


@dataclass
class StrengthInfo:
    tier: StrengthTier
    label: str
    stars: str
    color: str
    border_width: int
    reliability: int
    risk_pct: float
    holding_days: str


TIER_INFO = {
    StrengthTier.SOVEREIGN: StrengthInfo(
        tier=StrengthTier.SOVEREIGN,
        label="قوي سيادي",
        stars="⭐⭐⭐⭐",
        color="#ffb300",
        border_width=5,
        reliability=5,
        risk_pct=2.5,
        holding_days="أشهر - سنوات",
    ),
    StrengthTier.PURE_STRONG: StrengthInfo(
        tier=StrengthTier.PURE_STRONG,
        label="قوي خالص",
        stars="⭐⭐⭐",
        color="#ba68c8",
        border_width=4,
        reliability=5,
        risk_pct=2.0,
        holding_days="أسابيع - أشهر",
    ),
    StrengthTier.MIXED_STRONG: StrengthInfo(
        tier=StrengthTier.MIXED_STRONG,
        label="مختلط قوي",
        stars="⭐⭐",
        color="#7e57c2",
        border_width=3,
        reliability=4,
        risk_pct=1.5,
        holding_days="أيام - أسابيع",
    ),
    StrengthTier.PURE_MEDIUM: StrengthInfo(
        tier=StrengthTier.PURE_MEDIUM,
        label="متوسط خالص",
        stars="⭐",
        color="#00acc1",
        border_width=2,
        reliability=3,
        risk_pct=1.0,
        holding_days="يوم - 5 أيام",
    ),
    StrengthTier.MIXED_MEDIUM: StrengthInfo(
        tier=StrengthTier.MIXED_MEDIUM,
        label="مختلط متوسط",
        stars="",
        color="#43a047",
        border_width=1,
        reliability=2,
        risk_pct=0.5,
        holding_days="ساعات - يوم",
    ),
    StrengthTier.PURE_FAST: StrengthInfo(
        tier=StrengthTier.PURE_FAST,
        label="سريع خالص",
        stars="",
        color="#c0ca33",
        border_width=1,
        reliability=1,
        risk_pct=0.0,
        holding_days="دقائق - ساعات",
    ),
}


def classify_strength(mask: int) -> StrengthInfo:
    """
    Classify zone strength from bit-mask.

    Mask bits:
      D=1, 240=2, 60=4, 15=8, 5=16, W=32

    Logic:
      has_weekly = W
      has_high   = D or 240
      has_med    = 60
      has_fast   = 15 or 5

      Weekly + (D or 4H) confluence, without intraday noise → SOVEREIGN.
      Weekly alone (or with intraday) folds into the high group.
    """
    has_weekly = bool(mask & 32)
    has_high = bool(mask & 1) or bool(mask & 2)
    has_med = bool(mask & 4)
    has_fast = bool(mask & 8) or bool(mask & 16)

    # Sovereign: weekly confirmed by daily/4H, no intraday dilution
    if has_weekly and has_high and not has_med and not has_fast:
        return TIER_INFO[StrengthTier.SOVEREIGN]

    # Weekly participates as a 'high' timeframe in all other combos
    has_high = has_high or has_weekly

    if has_high and not has_med and not has_fast:
        return TIER_INFO[StrengthTier.PURE_STRONG]
    if has_high and (has_med or has_fast):
        return TIER_INFO[StrengthTier.MIXED_STRONG]
    if has_med and not has_high and not has_fast:
        return TIER_INFO[StrengthTier.PURE_MEDIUM]
    if has_med and has_fast and not has_high:
        return TIER_INFO[StrengthTier.MIXED_MEDIUM]
    if has_fast and not has_high and not has_med:
        return TIER_INFO[StrengthTier.PURE_FAST]
    return TIER_INFO[StrengthTier.PURE_FAST]
