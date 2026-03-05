import html as html_mod
import datetime
import pandas as pd
import numpy as np

from core.database import init_database, db_insert, db_select, is_cloud, DB_FILE

SAUDI_TZ = datetime.timezone(datetime.timedelta(hours=3))


def get_now() -> datetime.datetime:
    return datetime.datetime.now(SAUDI_TZ)


def get_today_str() -> str:
    return get_now().strftime("%Y-%m-%d")


def init_db():
    """Initialize database (Supabase or SQLite fallback)."""
    init_database()


def sanitize_text(text) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in '\n\r\t')
    return html_mod.escape(text)


def format_price(val, ticker: str) -> str:
    if pd.isna(val):
        return "0.00"
    try:
        v = float(val)
        if "=X" in str(ticker):
            return f"{v:.3f}" if "JPY" in str(ticker) else f"{v:.5f}"
        elif "-USD" in str(ticker):
            if v < 2:
                return f"{v:.5f}"
            elif v < 50:
                return f"{v:.3f}"
            return f"{v:.2f}"
        return f"{v:.2f}"
    except (ValueError, TypeError):
        return str(val)


def localize_timezone(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    try:
        if isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC').tz_convert(
                    'Asia/Riyadh'
                ).tz_localize(None)
            else:
                df.index = df.index.tz_convert(
                    'Asia/Riyadh'
                ).tz_localize(None)
    except Exception:
        pass
    return df


def save_to_tracker(df_vip: pd.DataFrame, market_name: str, tf_label: str) -> bool:
    """Save VIP picks to tracker table."""
    if df_vip.empty:
        return False
    try:
        for _, row in df_vip.iterrows():
            date_time = str(row['raw_time']).replace('\u23f1\ufe0f ', '')
            date_only = date_time.split(' | ')[1] if ' | ' in date_time else date_time
            ticker = str(row['\u0627\u0644\u0631\u0645\u0632'])

            # Check for duplicate
            existing = db_select("tracker", {
                "date_only": date_only,
                "ticker": ticker,
                "timeframe": tf_label,
            })
            if not existing:
                db_insert("tracker", {
                    "date_time": date_time,
                    "market": market_name,
                    "ticker": ticker,
                    "company": str(row['\u0627\u0644\u0634\u0631\u0643\u0629']),
                    "entry": float(row['raw_price']),
                    "target": float(row['raw_target']),
                    "stop_loss": float(row['raw_sl']),
                    "score": str(row['raw_score']),
                    "mom": str(row['raw_mom']),
                    "date_only": date_only,
                    "timeframe": tf_label,
                })
        return True
    except Exception:
        return False


def safe_div(a, b, default=0.0):
    if b is None or b == 0 or pd.isna(b) or (isinstance(b, float) and np.isinf(b)):
        return default
    return a / b
