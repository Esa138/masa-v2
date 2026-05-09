"""Unsubscribe endpoint — removes subscription from store."""

import json
import os
from http.server import BaseHTTPRequestHandler


def _remove_subscription(endpoint: str) -> bool:
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    if supabase_url and supabase_key:
        try:
            import urllib.request
            import urllib.parse
            ep_enc = urllib.parse.quote(endpoint, safe='')
            req = urllib.request.Request(
                f"{supabase_url}/rest/v1/push_subscriptions?endpoint=eq.{ep_enc}",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                },
                method='DELETE',
            )
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            print(f"Supabase delete failed: {e}")
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
            removed = _remove_subscription(endpoint) if endpoint else False
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "removed": removed}).encode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode('utf-8'))
