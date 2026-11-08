#!/usr/bin/env python3
"""HTTP server for the Kindle dashboard.

Serves the generated image and receives battery reports from the Kindle:

    GET /dashboard.png   -> the current dashboard image (DATA_DIR/dashboard.png)
    GET /batt?level=73   -> store the Kindle's battery level in battery.json
    GET /status          -> the latest battery.json ({"level":..,"ts":..,"ip":..})

The /status endpoint is what a Home Assistant REST sensor can poll to
drive a smart-plug charge loop (see README, optional section).
Stdlib only.
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DATA_DIR = os.environ.get("DATA_DIR", "/data")
PORT = int(os.environ.get("PORT", "8080"))
PNG = os.path.join(DATA_DIR, "dashboard.png")
STORE = os.path.join(DATA_DIR, "battery.json")


def save(level, ip):
    data = {"level": level, "ts": int(time.time()), "ip": ip}
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, STORE)
    return data


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/dashboard.png":
            try:
                with open(PNG, "rb") as fh:
                    body = fh.read()
                self._send(200, body, "image/png")
            except OSError:
                self._send(404, b"dashboard.png not generated yet")
        elif u.path == "/batt":
            qs = parse_qs(u.query)
            try:
                level = int(qs.get("level", [""])[0])
            except ValueError:
                level = -1
            if 0 <= level <= 100:
                save(level, self.client_address[0])
                self._send(200, b"ok")
            else:
                self._send(400, b"bad level")
        elif u.path == "/status":
            try:
                with open(STORE, "rb") as fh:
                    body = fh.read()
            except OSError:
                body = b"{}"
            self._send(200, body, "application/json")
        else:
            self._send(404, b"not found")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
