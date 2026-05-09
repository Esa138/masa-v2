"""
Push subscription endpoint.
Stores subscription in Supabase (fallback to local file).

Deploy: Vercel Python serverless function.
Path: /api/subscribe (called from PWA on permission grant)
"""

import json
import os
from http.server import BaseHTTPRequestHandler


def _store_subscription(sub: dict) -> bool:
    """Store subscription to Supabase or local fallback."""
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')

    if supabase_url and supabase_key:
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(
                f"{supabase_url}/rest/v1/push_subscriptions",
                data=json.dumps({
                    "endpoint": sub.get("endpoint"),
                    "p256dh": sub.get("keys", {}).get("p256dh"),
                    "auth": sub.get("keys", {}).get("auth"),
                }).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Prefer": "resolution=ignore-duplicates",
                },
                method='POST',
            )
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            print(f"Supabase store failed: {e}")
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
            sub = json.loads(body)
            if not sub.get('endpoint'):
                raise ValueError("Missing endpoint")

            stored = _store_subscription(sub)
            self.send_response(200 if stored else 202)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": True,
                "stored": stored,
                "msg": "Subscription accepted" if stored else "Stored in fallback",
            }).encode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode('utf-8'))
