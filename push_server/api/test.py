"""Test endpoint — sends a test notification to a single subscriber."""

import json
import os
from http.server import BaseHTTPRequestHandler


def _get_subscription(endpoint: str) -> dict:
    """Fetch subscription details from Supabase by endpoint."""
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    if not supabase_url or not supabase_key:
        return None
    try:
        import urllib.request
        import urllib.parse
        ep_enc = urllib.parse.quote(endpoint, safe='')
        req = urllib.request.Request(
            f"{supabase_url}/rest/v1/push_subscriptions?endpoint=eq.{ep_enc}&select=*",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data:
                row = data[0]
                return {
                    "endpoint": row["endpoint"],
                    "keys": {
                        "p256dh": row["p256dh"],
                        "auth": row["auth"],
                    },
                }
    except Exception as e:
        print(f"Get sub failed: {e}")
    return None


def _send_push(sub: dict, payload: dict) -> bool:
    """Send Web Push using pywebpush."""
    try:
        from pywebpush import webpush, WebPushException
        webpush(
            subscription_info=sub,
            data=json.dumps(payload),
            vapid_private_key=os.environ['VAPID_PRIVATE_KEY'],
            vapid_claims={
                "sub": os.environ.get('VAPID_CLAIMS_EMAIL', 'mailto:admin@example.com'),
            },
        )
        return True
    except Exception as e:
        print(f"Push send failed: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            endpoint = data.get('endpoint')

            sub = _get_subscription(endpoint)
            if not sub:
                raise ValueError("Subscription not found")

            payload = {
                "title": "🧪 MASA — اختبار إشعار",
                "body": "إذا وصلك هذا الإشعار فالتفعيل تم بنجاح ✅",
                "icon": "/app/static/icon-192.png",
                "tag": "masa-test",
                "url": "/",
            }
            sent = _send_push(sub, payload)

            self.send_response(200 if sent else 500)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": sent}).encode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode('utf-8'))
