def safe_color_table(val):
    val_str = str(val)
    if any(s in val_str for s in ["👑", "🌌", "🚀"]):
        return (
            'color: #ffd700; font-weight: bold; '
            'background-color: rgba(255, 215, 0, 0.1); border: 1px solid #ffd700;'
        )
    if any(s in val_str for s in ["🟢", "✅", "💎"]):
        return 'color: #00E676; font-weight: bold;'
    if any(s in val_str for s in ["🔴", "❌", "🩸", "⚠️"]):
        return 'color: #FF5252; font-weight: bold;'
    if any(s in val_str for s in ["🕳️", "🔻"]):
        return (
            'color: #fff; font-weight: bold; '
            'background-color: #f44336; border: 1px solid #f44336;'
        )
    if "MAJOR" in val_str:
        return 'color: #00d2ff; font-weight: bold;'
    if "HIGH" in val_str:
        return 'color: #FFD700; font-weight: bold;'
    if "⏱️" in val_str:
        return 'color: #00d2ff; font-weight: bold;'

    try:
        cleaned = (
            val_str.replace('MAJOR', '').replace('HIGH', '')
            .replace('MEDIUM', '').replace('LOW', '').replace('%', '')
            .replace(',', '').replace('+', '').replace('🟢', '')
            .replace('🔴', '').replace('⚪', '').strip()
        )
        if cleaned.replace('.', '', 1).replace('-', '', 1).isdigit():
            num = float(cleaned)
            if num > 0:
                return 'color: #00E676; font-weight: bold;'
            if num < 0:
                return 'color: #FF5252; font-weight: bold;'
    except (ValueError, TypeError):
        pass
    return ''


def style_live_tracker(val):
    v = str(val)
    if "🎯" in v or ("+" in v and "%" in v):
        return (
            'color: #00E676; font-weight: bold; '
            'background-color: rgba(0,230,118,0.1);'
        )
    if "🩸" in v or ("-" in v and "%" in v):
        return (
            'color: #FF5252; font-weight: bold; '
            'background-color: rgba(255,82,82,0.1);'
        )
    if "⏳" in v:
        return 'color: #FFD700; font-weight: bold;'
    return ''
