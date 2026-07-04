"""
MASA Confluence Engine — Multi-timeframe support/resistance detection
with Zero Reversal levels and Gamma 600 confluence.

Modules:
- zero_reversal: ZR1/ZR2 calculation
- gamma: Gamma 600 (multi-MA type)
- clustering: cluster nearby levels across timeframes
- strength_tier: 5-tier strength classification
- confluence_engine: main orchestrator
- signal_filter: 6-filter quality gate
"""

# Bump on EVERY engine change — app.py compares this against its expected
# version and force-reloads the package when the cached module is stale
# (Streamlit keeps imported modules across deploys until process restart).
ENGINE_SIGNATURE = "rr-age-v7"

from .confluence_engine import ConfluenceEngine, ConfluenceZone
from .signal_filter import apply_all_filters, QualityFilters
from .strength_tier import classify_strength, StrengthTier, TIER_INFO
from .data_fetcher import fetch_multi_tf_data, fetch_multi_tf_data_cached, fetch_daily_batch, fetch_single_tf, fetch_60_and_240
from .gann import compute_gann_box, match_gann_level, gann_targets, GannBox

__all__ = [
    "ConfluenceEngine",
    "ConfluenceZone",
    "apply_all_filters",
    "QualityFilters",
    "classify_strength",
    "StrengthTier",
    "TIER_INFO",
    "fetch_multi_tf_data",
    "fetch_multi_tf_data_cached",
]
