"""
MASA V2 — Signal Outcome Tracker
Checks past signals and records actual results.

This is the HONESTY ENGINE:
- Every "enter" signal gets tracked
- After 5, 10, 20 days → check current price
- Record: did it win (reached target or +%) or lose (hit stop)?
- These real win rates feed back into the system

No cherry-picking. No hiding bad signals. Full transparency.
"""

import sqlite3
import datetime
import yfinance as yf
import pandas as pd

DB_FILE = "masa_v2.db"


def update_signal_outcomes(lookback_days: int = 30) -> dict:
    """
    Check and update outcomes for signals that need tracking.

    Logic:
    - Find signals where outcome_5d/10d/20d is NULL
    - If enough days have passed since date_logged, fetch current price
    - Compare with entry_price → compute return
    - Win = return > 0%, Loss = return <= 0%
    - If stop_loss was hit → definite loss

    Returns:
        updated: int — number of signals updated
        errors: int — number of fetch failures
        details: list — summary of what was updated
    """
    updated = 0
    errors = 0
    details = []

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            # Get signals that need outcome tracking
            today = datetime.date.today()
            rows = conn.execute("""
                SELECT id, date_logged, ticker, entry_price, stop_loss, target,
                       outcome_5d, outcome_10d, outcome_20d
                FROM signals
                WHERE decision = 'enter'
                AND date_logged >= date('now', ?)
                AND (outcome_5d IS NULL OR outcome_10d IS NULL OR outcome_20d IS NULL)
                ORDER BY date_logged ASC
            """, (f"-{lookback_days} days",)).fetchall()

            if not rows:
                return {"updated": 0, "errors": 0, "details": ["لا توجد إشارات تحتاج تحديث"]}

            # Group by ticker to minimize API calls
            ticker_signals = {}
            for row in rows:
                tk = row["ticker"]
                if tk not in ticker_signals:
                    ticker_signals[tk] = []
                ticker_signals[tk].append(dict(row))

            # Fetch recent price data for each ticker
            for tk, signals in ticker_signals.items():
                try:
                    # Fetch enough history to cover all pending checks
                    t = yf.Ticker(tk)
                    hist = t.history(period="2mo", interval="1d")
                    if hist is None or hist.empty:
                        errors += 1
                        continue

                    if isinstance(hist.columns, pd.MultiIndex):
                        hist.columns = hist.columns.get_level_values(0)

                    closes = hist["Close"]
                    lows = hist["Low"]

                    for sig in signals:
                        entry_price = sig["entry_price"]
                        stop_loss = sig["stop_loss"]
                        target = sig["target"]
                        logged = datetime.date.fromisoformat(sig["date_logged"])

                        updates = {}

                        # Check each timeframe
                        for days, col_price, col_return, col_outcome in [
                            (5, "price_5d", "return_5d", "outcome_5d"),
                            (10, "price_10d", "return_10d", "outcome_10d"),
                            (20, "price_20d", "return_20d", "outcome_20d"),
                        ]:
                            if sig[col_outcome] is not None:
                                continue  # Already tracked

                            check_date = logged + datetime.timedelta(days=days)
                            if check_date > today:
                                continue  # Not enough time passed

                            # Find the closest trading day price
                            price_at_check = _get_price_on_or_before(
                                closes, check_date, lookback=3
                            )
                            if price_at_check is None:
                                continue

                            # Check if stop loss was hit during the period
                            stop_hit = _check_stop_hit(
                                lows, logged, check_date, stop_loss
                            )

                            ret = (price_at_check - entry_price) / entry_price * 100

                            if stop_hit:
                                outcome = "loss"
                                # Use stop loss as the exit price
                                ret = (stop_loss - entry_price) / entry_price * 100
                                price_at_check = stop_loss
                            elif price_at_check >= target:
                                outcome = "win"
                            elif ret > 0:
                                outcome = "win"
                            else:
                                outcome = "loss"

                            updates[col_price] = round(price_at_check, 2)
                            updates[col_return] = round(ret, 2)
                            updates[col_outcome] = outcome

                        if updates:
                            # Build update query
                            now = datetime.datetime.now().isoformat()
                            set_parts = []
                            values = []
                            for k, v in updates.items():
                                set_parts.append(f"{k} = ?")
                                values.append(v)
                            set_parts.append("last_updated = ?")
                            values.append(now)
                            values.append(sig["id"])

                            conn.execute(
                                f"UPDATE signals SET {', '.join(set_parts)} WHERE id = ?",
                                values,
                            )
                            updated += 1

                            # Build detail message
                            for k, v in updates.items():
                                if k.startswith("outcome_"):
                                    period = k.replace("outcome_", "")
                                    ret_key = f"return_{period}"
                                    ret_val = updates.get(ret_key, 0)
                                    emoji = "✅" if v == "win" else "❌"
                                    details.append(
                                        f"{emoji} {sig['ticker']} ({period}): "
                                        f"{ret_val:+.1f}% — {v}"
                                    )

                except Exception:
                    errors += 1
                    continue

            conn.commit()

    except Exception:
        errors += 1

    if not details:
        details = ["لا توجد تحديثات جديدة"]

    return {"updated": updated, "errors": errors, "details": details}


def _get_price_on_or_before(
    closes: pd.Series, target_date: datetime.date, lookback: int = 3
) -> float:
    """Get closing price on target_date or nearest prior trading day."""
    for i in range(lookback + 1):
        check = target_date - datetime.timedelta(days=i)
        # Find matching date in index
        for idx in closes.index:
            idx_date = idx.date() if hasattr(idx, "date") else idx
            if idx_date == check:
                return float(closes[idx])
    return None


def _check_stop_hit(
    lows: pd.Series, start_date: datetime.date, end_date: datetime.date,
    stop_loss: float
) -> bool:
    """Check if the low price touched the stop loss during the period."""
    if stop_loss <= 0:
        return False

    for idx, low_val in lows.items():
        idx_date = idx.date() if hasattr(idx, "date") else idx
        if start_date < idx_date <= end_date:
            if float(low_val) <= stop_loss:
                return True
    return False


def get_tracking_status() -> dict:
    """
    Get summary of signal tracking status.

    Returns:
        total_enter: int — total "enter" signals
        pending_5d: int — awaiting 5-day outcome
        pending_10d: int — awaiting 10-day outcome
        pending_20d: int — awaiting 20-day outcome
        completed: int — fully tracked signals
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome_5d IS NULL AND date_logged <= date('now', '-5 days') THEN 1 ELSE 0 END) as pending_5d,
                    SUM(CASE WHEN outcome_10d IS NULL AND date_logged <= date('now', '-10 days') THEN 1 ELSE 0 END) as pending_10d,
                    SUM(CASE WHEN outcome_20d IS NULL AND date_logged <= date('now', '-20 days') THEN 1 ELSE 0 END) as pending_20d,
                    SUM(CASE WHEN outcome_5d IS NOT NULL AND outcome_10d IS NOT NULL AND outcome_20d IS NOT NULL THEN 1 ELSE 0 END) as completed
                FROM signals
                WHERE decision = 'enter'
            """).fetchone()

            if row is None:
                return {"total_enter": 0, "pending_5d": 0, "pending_10d": 0, "pending_20d": 0, "completed": 0}

            return {
                "total_enter": row[0] or 0,
                "pending_5d": row[1] or 0,
                "pending_10d": row[2] or 0,
                "pending_20d": row[3] or 0,
                "completed": row[4] or 0,
            }
    except Exception:
        return {"total_enter": 0, "pending_5d": 0, "pending_10d": 0, "pending_20d": 0, "completed": 0}
