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


def _is_golden_signal(r: dict) -> bool:
    """Golden: accum/spring + buyer + div>=25 + 0 against + RSI>50 + price>SMA600."""
    is_accum = r.get("phase") in ("accumulation", "spring")
    is_buyer = r.get("aggressor") == "buyers"
    has_div = abs(r.get("divergence", 0)) >= 25
    zero_against = len(r.get("reasons_against", []) or []) == 0
    rsi_ok = (r.get("rsi", 0) or 0) > 50
    above_ma600 = r.get("above_ma600", False) is True
    return is_accum and is_buyer and has_div and zero_against and rsi_ok and above_ma600


def run_scan(market: str = "saudi") -> dict:
    """Run full market scan and log all signals."""
    from data.markets import get_all_tickers, get_stock_name, get_sector
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
        return {"scanned": 0, "logged": 0, "by_decision": {}, "golden": [], "breakouts": []}

    print(f"✅ تم مسح {len(results)} سهم في {elapsed:.0f}s")

    # Log all decisions
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    counts = {"enter": 0, "watch": 0, "avoid": 0, "other": 0}
    golden_signals = []
    breakouts = []
    sector_flow = {}

    for r in results:
        dec = r.get("decision", "")

        # Track sectors
        sec = r.get("sector", "")
        if sec:
            sector_flow.setdefault(sec, []).append(r.get("flow_bias", 0))

        # Track breakouts (independent of decision)
        zr_status = r.get("zr_status", "")
        if zr_status in ("zr_breakout", "zr_bluesky"):
            breakouts.append({
                "name": r.get("name", ""),
                "ticker": r.get("ticker", ""),
                "price": r.get("price", 0),
                "zr_high": r.get("zr_high", 0),
                "flow": r.get("flow_bias", 0),
                "change_pct": r.get("change_pct", 0),
            })

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
            "above_ma600": r.get("above_ma600"),
        })
        if ok:
            counts[dec] += 1

        # Identify golden signals among enters
        if dec == "enter" and _is_golden_signal(r):
            golden_signals.append({
                "name": r.get("name", ""),
                "ticker": r.get("ticker", ""),
                "sector": r.get("sector", ""),
                "price": r.get("price", 0),
                "target": r.get("target", 0),
                "stop_loss": r.get("stop_loss", 0),
                "rr": r.get("rr_ratio", 0),
                "flow": r.get("flow_bias", 0),
                "rsi": r.get("rsi", 50),
                "phase": r.get("phase", ""),
            })

    total_logged = sum(v for k, v in counts.items() if k != "other")
    print(f"💾 تم حفظ {total_logged} إشارة:")
    print(f"   ✅ ادخل: {counts['enter']}")
    print(f"   ⚠️  راقب: {counts['watch']}")
    print(f"   ❌ تجنب: {counts['avoid']}")
    print(f"   🥇 ذهبية: {len(golden_signals)}")
    print(f"   🚀 اختراقات: {len(breakouts)}")

    # Top sector by avg flow
    top_sector = "—"
    if sector_flow:
        top_sec = max(sector_flow.items(),
                      key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0)
        top_sector = top_sec[0]

    return {
        "scanned": len(results),
        "logged": total_logged,
        "by_decision": counts,
        "golden": golden_signals,
        "breakouts": breakouts,
        "top_sector": top_sector,
    }


def send_alerts(scan_result: dict) -> None:
    """Send Telegram alerts for golden signals + breakouts."""
    try:
        from core.telegram_notify import (
            is_configured, send_signals_batch, send_breakout_alert,
            send_daily_summary,
        )
    except Exception as e:
        print(f"⚠️ Telegram module load failed: {e}")
        return

    if not is_configured():
        print("ℹ️  Telegram not configured — skipping alerts")
        return

    print("\n📱 جاري إرسال إشعارات Telegram...")

    # 1) Daily summary first
    send_daily_summary({
        "enter_count": scan_result.get("by_decision", {}).get("enter", 0),
        "watch_count": scan_result.get("by_decision", {}).get("watch", 0),
        "golden_count": len(scan_result.get("golden", [])),
        "breakouts_count": len(scan_result.get("breakouts", [])),
        "top_sector": scan_result.get("top_sector", "—"),
    }, period="evening")

    # 2) Golden signals (top 3)
    golden = scan_result.get("golden", [])
    if golden:
        sent = send_signals_batch(golden, signal_type="golden", max_alerts=3)
        print(f"   🥇 تم إرسال {sent} إشارة ذهبية")

    # 3) Top breakouts (top 3 by flow)
    breakouts = scan_result.get("breakouts", [])
    if breakouts:
        breakouts.sort(key=lambda x: -x.get("flow", 0))
        sent = 0
        import time
        for bo in breakouts[:3]:
            if send_breakout_alert(bo):
                sent += 1
            time.sleep(1.1)
        print(f"   🚀 تم إرسال {sent} اختراق")


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

        # Send Telegram alerts (if configured)
        send_alerts(result)

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
