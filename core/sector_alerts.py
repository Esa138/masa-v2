"""
MASA QUANT — اكتشاف التناقضات تلقائياً
sector_alerts.py

يكتشف 3 أنواع من التناقضات:
1. تجميع خفي (مثل البنوك): تابع بالعائد لكن تجميع نظيف
2. صعود كاذب (مثل الطاقة): قائد بالعائد لكن تصريف نشط
3. انفجار قادم: متزامن + تجميع طويل + MASA عالي
"""

import streamlit as st
import pandas as pd


def detect_contradictions(sector_df):
    alerts = []

    for _, row in sector_df.iterrows():
        name = row['القطاع']
        status = row['الحالة']
        ret = row['العائد']
        alpha = row['Alpha']
        acc = row.get('تجميع', 0)
        dis = row.get('تصريف', 0)
        masa = row.get('MASA_Score', 0)

        try:
            acc = int(acc) if acc != '' else 0
            dis = int(dis) if dis != '' else 0
            masa = float(masa) if masa != '' else 0
        except (ValueError, TypeError):
            continue

        total = acc + dis
        if total == 0:
            continue

        ratio = acc / total * 100

        # نوع 1: تجميع خفي — تابع بالعائد + تجميع نظيف
        if status in ('تابع', 'متزامن') and ratio >= 80 and dis == 0:
            alerts.append({
                'النوع': 'تجميع_خفي',
                'الأهمية': 'عالية',
                'القطاع': name,
                'الأيقونة': '🔍',
                'العنوان': f'تجميع خفي في {name}!',
                'التفاصيل': (
                    f'العائد ضعيف ({ret:+.2f}%) لكن {acc} أسهم تجميع '
                    f'مع 0 تصريف (نقاء 100%). '
                    f'المؤسسات تجمّع بهدوء — السعر ما تحرك بعد. '
                    f'هذي فرصة سوينق!'
                ),
                'الإجراء': 'راقب وانتظر بداية الحركة — لما يتحول من تابع لقائد = إشارة الدخول',
            })
        elif status in ('تابع', 'متزامن') and ratio >= 70 and dis <= 1 and masa > 10:
            alerts.append({
                'النوع': 'تجميع_خفي',
                'الأهمية': 'متوسطة',
                'القطاع': name,
                'الأيقونة': '🔎',
                'العنوان': f'تجميع محتمل في {name}',
                'التفاصيل': (
                    f'العائد ({ret:+.2f}%) أضعف من المؤشر لكن '
                    f'نسبة التجميع {ratio:.0f}% مع MASA Score {masa:+.1f}. '
                    f'ممكن يكون بداية تجميع مؤسسي.'
                ),
                'الإجراء': 'راقب — إذا استمر التجميع 3+ أيام يتأكد',
            })

        # نوع 2: صعود كاذب — قائد بالعائد + تصريف نشط
        if status == 'قائد' and ratio < 40:
            alerts.append({
                'النوع': 'صعود_كاذب',
                'الأهمية': 'عالية',
                'القطاع': name,
                'الأيقونة': '⚠️',
                'العنوان': f'صعود كاذب في {name}!',
                'التفاصيل': (
                    f'العائد قوي ({ret:+.2f}%) لكن {dis} أسهم تصريف '
                    f'مقابل {acc} تجميع فقط (نسبة {ratio:.0f}%). '
                    f'المؤسسات تبيع بينما السعر يرتفع — فخ!'
                ),
                'الإجراء': 'لا تدخل! الصعود غير مستدام',
            })
        elif status == 'قائد' and masa < -15:
            alerts.append({
                'النوع': 'صعود_كاذب',
                'الأهمية': 'متوسطة',
                'القطاع': name,
                'الأيقونة': '⚠️',
                'العنوان': f'تحذير: {name} قائد لكن MASA سلبي!',
                'التفاصيل': (
                    f'العائد قوي ({ret:+.2f}%) وAlpha ({alpha:+.2f}%) لكن '
                    f'MASA Score {masa:.1f} (سلبي). '
                    f'القطاع يصعد لكنه مريض من الداخل.'
                ),
                'الإجراء': 'حذر — مناسب للمضاربة السريعة فقط',
            })

        # نوع 3: انفجار قادم — متزامن + تجميع طويل + MASA عالي
        if status == 'متزامن' and ratio >= 60 and masa > 20:
            alerts.append({
                'النوع': 'انفجار_قادم',
                'الأهمية': 'متوسطة',
                'القطاع': name,
                'الأيقونة': '💎',
                'العنوان': f'{name} جاهز للانفجار',
                'التفاصيل': (
                    f'متزامن مع المؤشر الحين لكن MASA Score {masa:+.1f} '
                    f'مع نسبة تجميع {ratio:.0f}%. '
                    f'لو يتحول من متزامن لقائد = فرصة.'
                ),
                'الإجراء': 'ضعه في المراقبة — إذا صار قائد الجلسة الجاية ادخل',
            })

    priority = {'عالية': 0, 'متوسطة': 1}
    alerts.sort(key=lambda x: priority.get(x['الأهمية'], 2))
    return alerts


def render_alerts(sector_df):
    alerts = detect_contradictions(sector_df)
    if not alerts:
        return

    st.markdown("---")
    st.markdown("### 🔍 اكتشاف التناقضات")
    st.markdown(f"*تم اكتشاف **{len(alerts)}** تناقض بين العائد وOrder Flow*")

    for alert in alerts:
        if alert['النوع'] == 'تجميع_خفي':
            st.success(
                f"**{alert['الأيقونة']} {alert['العنوان']}**\n\n"
                f"{alert['التفاصيل']}\n\n"
                f"**الإجراء:** {alert['الإجراء']}"
            )
        elif alert['النوع'] == 'صعود_كاذب':
            st.error(
                f"**{alert['الأيقونة']} {alert['العنوان']}**\n\n"
                f"{alert['التفاصيل']}\n\n"
                f"**الإجراء:** {alert['الإجراء']}"
            )
        elif alert['النوع'] == 'انفجار_قادم':
            st.info(
                f"**{alert['الأيقونة']} {alert['العنوان']}**\n\n"
                f"{alert['التفاصيل']}\n\n"
                f"**الإجراء:** {alert['الإجراء']}"
            )
