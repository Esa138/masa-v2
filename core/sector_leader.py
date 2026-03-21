"""
MASA QUANT — محرك القطاع القائد
sector_leader.py

يحسب لكل قطاع:
- العائد من الافتتاح (كل فريم)
- Alpha (الفرق عن المؤشر المركب)
- تصنيف: قائد / متزامن / تابع / سلبي
- Cross-Correlation للتوقيت
- يخزن النتائج في CSV للتاريخ
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

# ═══════════════════════════════════════════
# تعريف القطاعات
# ═══════════════════════════════════════════

SECTORS_CONFIG = {
    'البنوك': {
        'symbols': ['1180.SR','1150.SR','1120.SR','1140.SR','1010.SR',
                    '1020.SR','1030.SR','1050.SR','1060.SR','1080.SR'],
        'weight': 38.5,
    },
    'المواد الأساسية': {
        'symbols': ['2010.SR','2020.SR','2060.SR','2090.SR','2150.SR',
                    '2170.SR','2180.SR','2200.SR','2210.SR','2240.SR'],
        'weight': 14.2,
    },
    'الطاقة': {
        'symbols': ['2222.SR','2030.SR'],
        'weight': 5.8,
    },
    'الاتصالات': {
        'symbols': ['7010.SR','7020.SR','7030.SR','7040.SR'],
        'weight': 6.1,
    },
    'العقارات': {
        'symbols': ['4300.SR','4310.SR','4320.SR','4321.SR','4322.SR','4323.SR'],
        'weight': 4.5,
    },
    'الخدمات المالية': {
        'symbols': ['4280.SR','4081.SR','4082.SR','4130.SR'],
        'weight': 3.4,
    },
    'إنتاج الأغذية': {
        'symbols': ['2270.SR','2280.SR','6010.SR','6020.SR','6040.SR','6050.SR'],
        'weight': 2.8,
    },
    'تجزئة السلع الاستهلاكية': {
        'symbols': ['4001.SR','4003.SR','4006.SR','4007.SR'],
        'weight': 2.3,
    },
    'النقل': {
        'symbols': ['4030.SR','4031.SR','4040.SR','4260.SR'],
        'weight': 2.1,
    },
    'المرافق العامة': {
        'symbols': ['2080.SR','2082.SR','2083.SR'],
        'weight': 1.9,
    },
    'التقنية': {
        'symbols': ['7200.SR','7201.SR','7202.SR','7203.SR','7204.SR'],
        'weight': 1.8,
    },
    'الرعاية الصحية': {
        'symbols': ['4004.SR','4005.SR','4014.SR'],
        'weight': 1.6,
    },
    'التأمين': {
        'symbols': ['8010.SR','8020.SR','8030.SR','8040.SR','8050.SR','8060.SR'],
        'weight': 1.5,
    },
    'القطاع الصناعي': {
        'symbols': ['2300.SR','2310.SR','2320.SR','2330.SR','2340.SR','2350.SR'],
        'weight': 1.2,
    },
    'السلع طويلة الأجل': {
        'symbols': ['4180.SR','4141.SR','4142.SR','4143.SR'],
        'weight': 0.9,
    },
    'الخدمات التجارية': {
        'symbols': ['4270.SR','1832.SR','4291.SR'],
        'weight': 0.8,
    },
    'الخدمات الاستهلاكية': {
        'symbols': ['6002.SR','6004.SR','6012.SR','6013.SR'],
        'weight': 0.7,
    },
    'الإعلام والترفيه': {
        'symbols': ['4070.SR','4071.SR','4072.SR'],
        'weight': 0.6,
    },
    'السلع الكمالية': {
        'symbols': ['4090.SR','4091.SR'],
        'weight': 0.5,
    },
    'الأدوية': {
        'symbols': ['4165.SR','4163.SR','4164.SR'],
        'weight': 0.5,
    },
    'المنتجات المنزلية والشخصية': {
        'symbols': ['4061.SR','4008.SR'],
        'weight': 0.4,
    },
}


# ═══════════════════════════════════════════
# التصنيف
# ═══════════════════════════════════════════

def classify_sector(alpha, sector_return):
    """
    تصنيف القطاع بناءً على Alpha

    Parameters:
        alpha: float — الفرق بين عائد القطاع وعائد المؤشر
        sector_return: float — عائد القطاع

    Returns:
        str — التصنيف
        str — اللون
    """
    if sector_return < 0:
        return 'سلبي', '#E24B4A'
    if alpha > 0.5:
        return 'قائد', '#1D9E75'
    if alpha > -0.5:
        return 'متزامن', '#EF9F27'
    return 'تابع', '#E24B4A'


def classify_pattern(status_15m, status_1h, status_daily):
    """
    اكتشاف النمط بناءً على التصنيف عبر 3 فريمات

    Returns:
        str — اسم النمط
        str — اللون
        str — التوصية
    """
    leader_count = sum(1 for s in [status_15m, status_1h, status_daily]
                       if s == 'قائد')
    negative_count = sum(1 for s in [status_15m, status_1h, status_daily]
                         if s == 'سلبي')

    # نمط 1: قائد ثابت — فوق المؤشر على فريمين+
    if leader_count >= 2:
        return 'قائد ثابت', '#1D9E75', 'مضاربة + سوينق'

    # نمط 2: مضاربة نقية — قوي قصير ضعيف طويل
    if status_15m in ('قائد', 'متزامن') and status_daily in ('تابع', 'سلبي'):
        return 'مضاربة نقية', '#7F77DD', 'ادخل واطلع نفس اليوم'

    # نمط 3: تجميع بطيء — ضعيف قصير قوي طويل
    if status_15m in ('تابع', 'سلبي') and status_daily == 'قائد':
        return 'تجميع بطيء', '#185FA5', 'سوينق فقط'

    # نمط 4: ضعيف دائماً
    if leader_count == 0 and negative_count >= 2:
        return 'ضعيف دائماً', '#E24B4A', 'تجنّب'

    # مختلط
    if negative_count >= 1:
        return 'مختلط', '#EF9F27', 'حذر'

    return 'متزامن', '#888780', 'محايد'


# ═══════════════════════════════════════════
# حساب العائد
# ═══════════════════════════════════════════

def compute_sector_returns(sector_data_dict, index_returns):
    """
    يحسب العائد والـ Alpha لكل قطاع

    Parameters:
        sector_data_dict: dict — {sector_name: pd.Series of returns}
        index_returns: float — عائد المؤشر المركب

    Returns:
        pd.DataFrame — جدول النتائج مرتب بالـ Alpha
    """
    results = []

    for sector_name, returns in sector_data_dict.items():
        if returns is None:
            continue
        if isinstance(returns, (pd.Series, list)) and len(returns) == 0:
            continue

        sector_return = float(returns.iloc[-1]) if isinstance(returns, pd.Series) else float(returns)
        alpha = sector_return - index_returns
        status, color = classify_sector(alpha, sector_return)
        weight = SECTORS_CONFIG.get(sector_name, {}).get('weight', 0)

        results.append({
            'القطاع': sector_name,
            'الوزن': weight,
            'العائد': round(sector_return, 2),
            'Alpha': round(alpha, 2),
            'الحالة': status,
            'اللون': color,
        })

    df = pd.DataFrame(results)
    if len(df) > 0:
        df = df.sort_values('Alpha', ascending=False).reset_index(drop=True)
        df.index = df.index + 1
    return df


# ═══════════════════════════════════════════
# Cross-Correlation (توقيت التقدم/التأخر)
# ═══════════════════════════════════════════

def cross_correlation(sector_series, index_series, max_lag=4):
    """
    يحسب Cross-Correlation بين القطاع والمؤشر

    Parameters:
        sector_series: pd.Series — سلسلة عوائد القطاع (كل 15 دقيقة)
        index_series: pd.Series — سلسلة عوائد المؤشر
        max_lag: int — أقصى فترة تقدم/تأخر (بالشموع)

    Returns:
        best_lag: int — أفضل فترة (سالب = القطاع يسبق)
        best_corr: float — أقوى ارتباط
    """
    aligned = pd.concat([sector_series, index_series], axis=1).dropna()
    if len(aligned) < max_lag + 5:
        return 0, 0.0

    s = aligned.iloc[:, 0].values
    idx = aligned.iloc[:, 1].values

    s_norm = (s - s.mean()) / (s.std() + 1e-10)
    idx_norm = (idx - idx.mean()) / (idx.std() + 1e-10)

    best_lag = 0
    best_corr = 0.0

    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            c = np.corrcoef(s_norm[:lag], idx_norm[-lag:])[0, 1]
        elif lag > 0:
            c = np.corrcoef(s_norm[lag:], idx_norm[:-lag])[0, 1]
        else:
            c = np.corrcoef(s_norm, idx_norm)[0, 1]

        if not np.isnan(c) and c > best_corr:
            best_corr = c
            best_lag = lag

    return best_lag, round(best_corr, 3)


# ═══════════════════════════════════════════
# دمج مع Order Flow
# ═══════════════════════════════════════════

def merge_order_flow(sector_df, order_flow_dict):
    """
    يضيف بيانات Order Flow لكل قطاع

    Parameters:
        sector_df: pd.DataFrame — جدول القطاعات
        order_flow_dict: dict — {sector_name: {accumulation, distribution, neutral, masa_score}}

    Returns:
        pd.DataFrame — الجدول محدّث
    """
    if order_flow_dict is None:
        return sector_df

    acc_list = []
    dis_list = []
    ratio_list = []
    masa_list = []

    for _, row in sector_df.iterrows():
        name = row['القطاع']
        of = order_flow_dict.get(name, {})
        acc = of.get('accumulation', 0)
        dis = of.get('distribution', 0)
        total = acc + dis
        ratio = round(acc / total * 100, 0) if total > 0 else 50

        acc_list.append(acc)
        dis_list.append(dis)
        ratio_list.append(f"{int(ratio)}%")
        masa_list.append(of.get('masa_score', 0))

    sector_df['تجميع'] = acc_list
    sector_df['تصريف'] = dis_list
    sector_df['نسبة_تجميع'] = ratio_list
    sector_df['MASA_Score'] = masa_list

    return sector_df


# ═══════════════════════════════════════════
# حفظ التاريخ
# ═══════════════════════════════════════════

import pathlib as _pathlib
HISTORY_FILE = str(_pathlib.Path(__file__).resolve().parent.parent / 'data' / 'sector_leader_history.csv')

def save_session(sector_df, timeframe, index_return):
    """
    يحفظ نتائج الجلسة في CSV

    Parameters:
        sector_df: pd.DataFrame
        timeframe: str — '15m', '1h', 'daily'
        index_return: float
    """
    os.makedirs('data', exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    records = []

    for _, row in sector_df.iterrows():
        records.append({
            'التاريخ': today,
            'الفريم': timeframe,
            'المؤشر': index_return,
            'القطاع': row['القطاع'],
            'العائد': row['العائد'],
            'Alpha': row['Alpha'],
            'الحالة': row['الحالة'],
            'تجميع': row.get('تجميع', ''),
            'تصريف': row.get('تصريف', ''),
            'MASA_Score': row.get('MASA_Score', ''),
        })

    new_df = pd.DataFrame(records)

    if os.path.exists(HISTORY_FILE):
        existing = pd.read_csv(HISTORY_FILE)
        # حذف بيانات نفس اليوم والفريم (تحديث)
        mask = ~((existing['التاريخ'] == today) & (existing['الفريم'] == timeframe))
        existing = existing[mask]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')


def load_history(days=30):
    """
    يقرأ تاريخ الجلسات السابقة

    Parameters:
        days: int — عدد الأيام

    Returns:
        pd.DataFrame
    """
    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame()

    df = pd.read_csv(HISTORY_FILE)
    df['التاريخ'] = pd.to_datetime(df['التاريخ'])
    cutoff = datetime.now() - timedelta(days=days)
    return df[df['التاريخ'] >= cutoff]


# ═══════════════════════════════════════════
# إحصائيات تاريخية
# ═══════════════════════════════════════════

def compute_historical_stats(history_df, timeframe='daily'):
    """
    يحسب إحصائيات تاريخية: كم مرة كل قطاع كان قائد

    Returns:
        pd.DataFrame — ترتيب القطاعات حسب نسبة القيادة
    """
    if len(history_df) == 0:
        return pd.DataFrame()

    tf_data = history_df[history_df['الفريم'] == timeframe]
    if len(tf_data) == 0:
        return pd.DataFrame()

    stats = []
    sessions = tf_data['التاريخ'].nunique()

    for sector in tf_data['القطاع'].unique():
        sec_data = tf_data[tf_data['القطاع'] == sector]
        leader_count = (sec_data['الحالة'] == 'قائد').sum()
        follower_count = (sec_data['الحالة'] == 'تابع').sum()
        negative_count = (sec_data['الحالة'] == 'سلبي').sum()
        avg_alpha = sec_data['Alpha'].mean()

        stats.append({
            'القطاع': sector,
            'جلسات': sessions,
            'قائد': leader_count,
            'نسبة_القيادة': round(leader_count / max(len(sec_data), 1) * 100, 1),
            'تابع': follower_count,
            'سلبي': negative_count,
            'متوسط_Alpha': round(avg_alpha, 2),
        })

    result = pd.DataFrame(stats)
    if len(result) > 0:
        result = result.sort_values('نسبة_القيادة', ascending=False).reset_index(drop=True)
    return result
