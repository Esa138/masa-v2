"""
MASA QUANT — Daily Auto-Scan
Runs market scan + logs all signals to DB.

Designed to run on:
- GitHub Actions cron (daily after market close)
- Local cron job
- Manual: python scripts/daily_scan.py [saudi|us]

Logs ALL decisions (enter/watch/avoid) for full data analysis.
"""

import sys
import os
import datetime
import sqlite3

# Ensure project root in path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Suppress streamlit warnings when running headless
os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"

import warnings
warnings.filterwarnings("ignore")


def run_scan(market: str = "saudi") -> dict:
    """Run full market scan and log all signals."""
    from data.markets import get_all_tickers, get_stock_name, get_stock_sector
    from core.scanner import scan_market
    from core.database import log_signal, init_database

    init_database()

    tickers = get_all_tickers(market)
    print(f"📡 جاري مسح {len(tickers)} سهم من السوق {market}...")

    start = datetime.datetime.now()
    results = scan_market(tickers, period="2y", market_health=50.0, max_workers=8)
    elapsed = (datetime.datetime.now() - start).total_seconds()

    if not results:
        print("⚠️  لا توجد نتائج من المسح")
        return {"scanned": 0, "logged": 0, "by_decision": {}}

    print(f"✅ تم مسح {len(results)} سهم في {elapsed:.0f}s")

    # Log all decisions
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    counts = {"enter": 0, "watch": 0, "avoid": 0, "other": 0}
    for r in results:
        dec = r.get("decision", "")
        if dec not in ("enter", "watch", "avoid"):
            counts["other"] += 1
            continue
        ok = log_signal({
            "date_logged": today,
            "ticker": r["ticker"],
            "company": r.get("name", ""),
            "sector": r.get("sector", ""),
            "decision": dec,
            "accum_level": r.get("phase", ""),
            "accum_days": r.get("days", 0),
            "location": r.get("location", ""),
            "cmf": r.get("flow_bias", 0),
            "entry_price": r.get("price", 0),
            "stop_loss": r.get("stop_loss", 0),
            "target": r.get("target", 0),
            "rr_ratio": r.get("rr_ratio", 0),
            "reasons_for": r.get("reasons_for", []),
            "reasons_against": r.get("reasons_against", []),
            "rsi": r.get("rsi"),
        })
        if ok:
            counts[dec] += 1

    total_logged = sum(v for k, v in counts.items() if k != "other")
    print(f"💾 تم حفظ {total_logged} إشارة:")
    print(f"   ✅ ادخل: {counts['enter']}")
    print(f"   ⚠️  راقب: {counts['watch']}")
    print(f"   ❌ تجنب: {counts['avoid']}")

    return {"scanned": len(results), "logged": total_logged, "by_decision": counts}


def update_outcomes() -> int:
    """Update outcomes for past signals."""
    from core.tracker import update_signal_outcomes
    print("\n🔄 تحديث نتائج الإشارات السابقة...")
    res = update_signal_outcomes()
    n = res.get("updated", 0)
    print(f"✅ تم تحديث {n} إشارة سابقة")
    return n


def main():
    market = sys.argv[1] if len(sys.argv) > 1 else "saudi"
    print(f"═══════════════════════════════════════════")
    print(f"🚀 MASA QUANT — مسح يومي تلقائي")
    print(f"   السوق: {market}")
    print(f"   التاريخ: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"═══════════════════════════════════════════\n")

    try:
        result = run_scan(market)
        update_outcomes()

        print(f"\n═══════════════════════════════════════════")
        print(f"✅ المسح اليومي اكتمل بنجاح")
        print(f"═══════════════════════════════════════════")
        return 0
    except Exception as e:
        import traceback
        print(f"\n❌ فشل المسح: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
