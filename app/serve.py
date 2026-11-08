#!/usr/bin/env python3
"""HTTP server for the Kindle dashboard.

Serves the generated image, receives battery reports from the Kindle,
and offers a token-protected API to replace the reminders:

    GET  /dashboard.png  -> the current dashboard image (DATA_DIR/dashboard.png)
    GET  /batt?level=73  -> store the Kindle's battery level in battery.json
    GET  /status         -> the latest battery.json ({"level":..,"ts":..,"ip":..})
    GET  /reminders      -> the current reminders list        (needs token)
    POST /reminders      -> replace the reminders with the JSON array in
                            the request body, then regenerate the image
                            immediately                    (needs token)

Auth for /reminders: header "X-Token: <token>" or
"Authorization: Bearer <token>", where <token> is the API_TOKEN
environment variable. When API_TOKEN is not set, /reminders is disabled.

The /status endpoint is what a Home Assistant REST sensor can poll to
drive a smart-plug charge loop (see README, optional section).
Stdlib only.
"""
import hmac
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import date as _date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", "/data")
PORT = int(os.environ.get("PORT", "8080"))
PNG = os.path.join(DATA_DIR, "dashboard.png")
STORE = os.path.join(DATA_DIR, "battery.json")
REMINDERS = os.environ.get("REMINDERS_FILE", os.path.join(DATA_DIR, "reminders.json"))
API_TOKEN = os.environ.get("API_TOKEN", "")
GENERATOR = os.path.join(BASE, "generate.py")
_write_lock = threading.Lock()

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def save(level, ip):
    data = {"level": level, "ts": int(time.time()), "ip": ip}
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, STORE)
    return data


def validate_reminders(items):
    if not isinstance(items, list):
        raise ValueError("body must be a JSON array")
    if len(items) > 50:
        raise ValueError("at most 50 items")
    out = []
    for it in items:
        if not isinstance(it, dict):
            raise ValueError("each item must be an object {date, time, text}")
        d = str(it.get("date", "")).strip()
        t = str(it.get("time", "")).strip()
        x = str(it.get("text", "")).strip()
        if not DATE_RE.match(d):
            raise ValueError("bad date (want YYYY-MM-DD): %r" % d)
        y, m, dd = (int(p) for p in d.split("-"))
        _date(y, m, dd)  # raises ValueError on impossible dates
        if t and not TIME_RE.match(t):
            raise ValueError("bad time (want HH:MM or empty): %r" % t)
        if not x or len(x) > 60:
            raise ValueError("text must be 1-60 characters")
        out.append({"date": d, "time": t, "text": x})
    out.sort(key=lambda r: (r["date"], r["time"] or "99:99"))
    return out


def write_reminders(items):
    if os.path.exists(REMINDERS):
        with open(REMINDERS, "rb") as fh:
            old = fh.read()
        with open(REMINDERS + ".bak", "wb") as fh:
            fh.write(old)
    tmp = REMINDERS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, REMINDERS)


def regenerate():
    try:
        r = subprocess.run([sys.executable, GENERATOR],
                           capture_output=True, text=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def _reminders_auth(self):
        """Gate for /reminders. Returns True when the request may proceed."""
        if not API_TOKEN:
            self._send(404, b"not found")
            return False
        given = self.headers.get("X-Token") or ""
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            given = auth[len("Bearer "):]
        if not hmac.compare_digest(given, API_TOKEN):
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return False
        return True

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
        elif u.path == "/reminders":
            if not self._reminders_auth():
                return
            try:
                with open(REMINDERS, "rb") as fh:
                    body = fh.read()
            except OSError:
                body = b"[]"
            self._send(200, body, "application/json; charset=utf-8")
        else:
            self._send(404, b"not found")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/reminders":
            self._send(404, b"not found")
            return
        if not self._reminders_auth():
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > 65536:
            self._send_json(400, {"ok": False, "error": "bad content length"})
            return
        raw = self.rfile.read(n)
        try:
            items = validate_reminders(json.loads(raw.decode("utf-8")))
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})
            return
        with _write_lock:
            write_reminders(items)
            ok = regenerate()
        self._send_json(200, {"ok": True, "count": len(items), "regenerated": ok})


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
