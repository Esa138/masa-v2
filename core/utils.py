import sqlite3
import html as html_mod
import datetime
import pandas as pd
import numpy as np

DB_FILE = "masa_database.db"

SAUDI_TZ = datetime.timezone(datetime.timedelta(hours=3))


def get_now() -> datetime.datetime:
    return datetime.datetime.now(SAUDI_TZ)


def get_today_str() -> str:
    return get_now().strftime("%Y-%m-%d")


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tracker (
                date_time TEXT, market TEXT, ticker TEXT, company TEXT,
                entry REAL, target REAL, stop_loss REAL, score TEXT,
                mom TEXT, date_only TEXT, timeframe TEXT DEFAULT 'غير محدد'
            )"""
        )
        conn.commit()


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
    if df_vip.empty:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            for _, row in df_vip.iterrows():
                date_time = str(row['raw_time']).replace('⏱️ ', '')
                date_only = date_time.split(' | ')[1] if ' | ' in date_time else date_time
                ticker = str(row['الرمز'])

                c.execute(
                    "SELECT 1 FROM tracker WHERE date_only=? AND ticker=? AND timeframe=?",
                    (date_only, ticker, tf_label)
                )
                if not c.fetchone():
                    c.execute(
                        """INSERT INTO tracker
                           (date_time, market, ticker, company, entry, target,
                            stop_loss, score, mom, date_only, timeframe)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (date_time, market_name, ticker, str(row['الشركة']),
                         float(row['raw_price']), float(row['raw_target']),
                         float(row['raw_sl']), str(row['raw_score']),
                         str(row['raw_mom']), date_only, tf_label)
                    )
            conn.commit()
        return True
    except Exception:
        return False


def safe_div(a, b, default=0.0):
    if b is None or b == 0 or pd.isna(b) or (isinstance(b, float) and np.isinf(b)):
        return default
    return a / b
