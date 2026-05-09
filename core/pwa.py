"""
MASA QUANT — PWA Helper
Injects manifest, service worker registration, and meta tags into Streamlit.
"""

import streamlit as st


PWA_HEAD_HTML = """
<link rel="manifest" href="/app/static/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MASA">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#00d2ff">
<meta name="application-name" content="MASA QUANT">
<link rel="apple-touch-icon" href="/app/static/icon-192.png">
<link rel="icon" type="image/png" sizes="192x192" href="/app/static/icon-192.png">
<link rel="icon" type="image/png" sizes="512x512" href="/app/static/icon-512.png">
"""

PWA_REGISTER_JS = """
<script>
(function() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/app/static/sw.js', { scope: '/app/' })
        .then(reg => {
          console.log('[MASA PWA] Service Worker registered:', reg.scope);
          window._masaSWRegistration = reg;
        })
        .catch(err => console.error('[MASA PWA] SW registration failed:', err));
    });
  }
})();
</script>
"""


def inject_pwa():
    """Inject PWA manifest link, meta tags, and SW registration into Streamlit page."""
    st.markdown(PWA_HEAD_HTML + PWA_REGISTER_JS, unsafe_allow_html=True)


# ── Push Notification Subscription Helpers ─────────────────────

def get_push_ui_html(vapid_public_key: str, server_url: str) -> str:
    """
    Build the HTML+JS UI for push notification subscription.
    Returns inline HTML with JavaScript that:
    1. Asks for notification permission
    2. Subscribes to push using VAPID key
    3. Sends subscription to backend server
    """
    return f"""
    <div id="masa-push-ui" style="direction:rtl;text-align:right">
      <div id="masa-push-status" style="padding:12px;border-radius:8px;margin-bottom:10px;
           background:rgba(255,193,7,0.1);border:1px solid #FFC107;color:#FFC107">
        ⏳ جاري التحقق من حالة الإشعارات...
      </div>
      <button id="masa-push-toggle"
              style="background:linear-gradient(135deg,#00d2ff,#0066ff);
                     color:#fff;border:none;padding:12px 28px;
                     border-radius:10px;font-weight:700;cursor:pointer;
                     font-size:1em;width:100%">
        🔔 تفعيل الإشعارات
      </button>
      <button id="masa-push-test" style="margin-top:8px;
              background:rgba(255,255,255,0.05);color:#9ca3af;border:1px solid #374151;
              padding:8px 20px;border-radius:8px;cursor:pointer;
              font-size:0.85em;width:100%;display:none">
        🧪 إرسال إشعار تجريبي
      </button>
    </div>

    <script>
    (function() {{
      const VAPID_PUBLIC_KEY = "{vapid_public_key}";
      const SERVER_URL = "{server_url}";

      const status = document.getElementById('masa-push-status');
      const toggleBtn = document.getElementById('masa-push-toggle');
      const testBtn = document.getElementById('masa-push-test');

      function setStatus(html, color = '#FFC107') {{
        status.style.background = `${{color}}1a`;
        status.style.borderColor = color;
        status.style.color = color;
        status.innerHTML = html;
      }}

      function urlBase64ToUint8Array(base64String) {{
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const raw = atob(base64);
        return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
      }}

      async function checkSubscription() {{
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {{
          setStatus('❌ المتصفح لا يدعم الإشعارات', '#FF5252');
          toggleBtn.disabled = true;
          return;
        }}
        try {{
          const reg = await navigator.serviceWorker.ready;
          const sub = await reg.pushManager.getSubscription();
          if (sub) {{
            setStatus('✅ الإشعارات مفعّلة', '#00E676');
            toggleBtn.textContent = '🔕 إلغاء التفعيل';
            testBtn.style.display = 'block';
          }} else {{
            setStatus('⚪ الإشعارات غير مفعّلة', '#9ca3af');
            toggleBtn.textContent = '🔔 تفعيل الإشعارات';
          }}
        }} catch (err) {{
          setStatus('⚠️ ' + err.message, '#FF5252');
        }}
      }}

      async function subscribe() {{
        try {{
          const permission = await Notification.requestPermission();
          if (permission !== 'granted') {{
            setStatus('🚫 رُفض الإذن — لا يمكن إرسال إشعارات', '#FF5252');
            return;
          }}

          const reg = await navigator.serviceWorker.ready;
          const sub = await reg.pushManager.subscribe({{
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
          }});

          // Send to backend
          if (SERVER_URL) {{
            const resp = await fetch(SERVER_URL + '/subscribe', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify(sub),
            }});
            if (!resp.ok) throw new Error('فشل الاشتراك في السيرفر');
          }}

          setStatus('✅ تم تفعيل الإشعارات بنجاح!', '#00E676');
          toggleBtn.textContent = '🔕 إلغاء التفعيل';
          testBtn.style.display = 'block';
        }} catch (err) {{
          setStatus('⚠️ خطأ: ' + err.message, '#FF5252');
        }}
      }}

      async function unsubscribe() {{
        try {{
          const reg = await navigator.serviceWorker.ready;
          const sub = await reg.pushManager.getSubscription();
          if (sub) {{
            await sub.unsubscribe();
            if (SERVER_URL) {{
              await fetch(SERVER_URL + '/unsubscribe', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ endpoint: sub.endpoint }}),
              }}).catch(() => {{}});
            }}
          }}
          setStatus('🔕 تم إلغاء الإشعارات', '#9ca3af');
          toggleBtn.textContent = '🔔 تفعيل الإشعارات';
          testBtn.style.display = 'none';
        }} catch (err) {{
          setStatus('⚠️ ' + err.message, '#FF5252');
        }}
      }}

      async function sendTest() {{
        if (!SERVER_URL) {{
          alert('⚠️ سيرفر الإشعارات غير مهيأ');
          return;
        }}
        try {{
          const reg = await navigator.serviceWorker.ready;
          const sub = await reg.pushManager.getSubscription();
          await fetch(SERVER_URL + '/test', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ endpoint: sub.endpoint }}),
          }});
          setStatus('📨 تم إرسال إشعار تجريبي — تحقق من جوالك', '#4FC3F7');
        }} catch (err) {{
          setStatus('⚠️ ' + err.message, '#FF5252');
        }}
      }}

      toggleBtn.addEventListener('click', async () => {{
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (sub) await unsubscribe();
        else await subscribe();
      }});

      testBtn.addEventListener('click', sendTest);

      // Initial check
      setTimeout(checkSubscription, 500);
    }})();
    </script>
    """
