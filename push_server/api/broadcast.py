"""
Broadcast endpoint — sends notification to ALL subscribers.
Protected by SECRET_TOKEN env var (set in Vercel).

Use this from your scan cron job:
  curl -X POST https://your-vercel.app/api/broadcast \
    -H "Authorization: Bearer YOUR_SECRET" \
    -H "Content-Type: application/json" \
    -d '{"title":"🥇 إشارة ذهبية","body":"الراجحي - دخول 87.2","url":"/"}'
"""

import json
import os
from http.server import BaseHTTPRequestHandler


def _get_all_subscriptions() -> list:
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    if not supabase_url or not supabase_key:
        return []
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{supabase_url}/rest/v1/push_subscriptions?select=*",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return [{
                "endpoint": r["endpoint"],
                "keys": {"p256dh": r["p256dh"], "auth": r["auth"]},
            } for r in data]
    except Exception as e:
        print(f"List subs failed: {e}")
        return []


def _send_push(sub: dict, payload: dict) -> bool:
    try:
        from pywebpush import webpush
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
        print(f"Push fail: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Auth check
        auth = self.headers.get('Authorization', '')
        expected = os.environ.get('SECRET_TOKEN', '')
        if not expected or not auth.endswith(expected):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"ok":false,"error":"unauthorized"}')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body)
            payload.setdefault('icon', '/app/static/icon-192.png')

            subs = _get_all_subscriptions()
            sent = 0
            for s in subs:
                if _send_push(s, payload):
                    sent += 1

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True, "total": len(subs), "sent": sent,
            }).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode('utf-8'))
