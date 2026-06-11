"""Tiny stand-in for the provider API, used by the demo recordings.

It prints every request body it receives (so the demo can show exactly
what would have reached the cloud) and echoes the body back as the
response, which lets Exodus demonstrate transparent restoration.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Echo(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        print("[cloud] received:")
        try:
            print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
        except Exception:
            print(body.decode("utf-8", "replace"))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9999), Echo).serve_forever()
