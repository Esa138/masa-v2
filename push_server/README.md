# MASA Push Notification Server

خادم إشعارات Push للمنصة — يُنشر على Vercel Serverless مجاناً.

---

## 🔧 خطوات النشر (15 دقيقة)

### 1. مفاتيح VAPID (تم توليدها مسبقاً)

```
PUBLIC:  BDSdrmtenzcQW2mt54J6MXu18Bni1yj-ryFIT6FmoGQgi2DO3W21dWVvAUMf1wS2R-KLI0UKLCIZseaXtnq63ZY
PRIVATE: pqnFutWsG4dA_W-6K2-8UaSYhzNcLatrcoWaE_AzQkQ
EMAIL:   mailto:admin@masaquant.app
```

### 2. إنشاء قاعدة Supabase (5 دقائق)

1. روح [supabase.com](https://supabase.com) → New Project
2. في **SQL Editor** نفذ:

```sql
CREATE TABLE push_subscriptions (
  id BIGSERIAL PRIMARY KEY,
  endpoint TEXT UNIQUE NOT NULL,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON push_subscriptions FOR ALL USING (true);
```

3. اخذ من **Settings → API**:
   - `Project URL`
   - `service_role` key (السري — لا تشاركه)

### 3. نشر على Vercel (5 دقائق)

```bash
# على ماك
cd push_server
npx vercel deploy --prod
```

أو من واجهة Vercel:
1. Import GitHub repo
2. Root Directory = `push_server`
3. أضف Environment Variables:
   - `VAPID_PUBLIC_KEY`
   - `VAPID_PRIVATE_KEY`
   - `VAPID_CLAIMS_EMAIL`
   - `SUPABASE_URL`
   - `SUPABASE_KEY` (service_role)
   - `SECRET_TOKEN` (أي string عشوائي قوي للحماية)

### 4. حفظ في Streamlit Secrets

في Streamlit Cloud → Settings → Secrets:

```toml
VAPID_PUBLIC_KEY = "BDSdrmtenzcQW2mt54J6MXu18Bni1yj-ryFIT6FmoGQgi2DO3W21dWVvAUMf1wS2R-KLI0UKLCIZseaXtnq63ZY"
PUSH_SERVER_URL = "https://YOUR-VERCEL-APP.vercel.app/api"
PUSH_SECRET_TOKEN = "نفس_السر_اللي_حطيته_في_Vercel"
```

---

## 📡 API Endpoints

| Endpoint | Method | الوظيفة |
|----------|--------|---------|
| `/api/subscribe` | POST | تسجيل اشتراك جديد |
| `/api/unsubscribe` | POST | إلغاء اشتراك |
| `/api/test` | POST | إرسال إشعار تجريبي |
| `/api/broadcast` | POST | إرسال لكل المشتركين (يحتاج `Authorization: Bearer SECRET_TOKEN`) |

---

## 🧪 اختبار يدوي

```bash
curl -X POST https://YOUR-VERCEL-APP.vercel.app/api/broadcast \
  -H "Authorization: Bearer YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "🥇 إشارة ذهبية",
    "body": "الراجحي - دخول 87.2 ر، هدف 92",
    "url": "/?page=الفلتر+الذهبي"
  }'
```

---

## 🤖 الإرسال التلقائي من سكربت المسح

في `scripts/daily_scan.py`، أضف:

```python
import requests
import os

def send_alerts(golden_signals):
    if not golden_signals:
        return
    server = os.environ.get('PUSH_SERVER_URL')
    secret = os.environ.get('PUSH_SECRET_TOKEN')
    if not server or not secret:
        return

    for s in golden_signals[:3]:
        requests.post(
            f"{server}/broadcast",
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
            },
            json={
                "title": f"🥇 إشارة ذهبية: {s['name']}",
                "body": f"دخول {s['price']:.2f} ر | هدف {s['target']:.2f}",
                "url": "/?page=الفلتر+الذهبي",
            },
        )
```
