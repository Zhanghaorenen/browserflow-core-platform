"""Isolated repeatable business fixtures; SQLite-backed idempotent form receipts."""

import json, sqlite3, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DB = Path(__file__).with_name("demo.sqlite3")


def init():
    with sqlite3.connect(DB) as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS applications (id TEXT PRIMARY KEY, payload TEXT NOT NULL, receipt TEXT NOT NULL)"
        )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/slow":
            import time

            time.sleep(10)
        if path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()
            return
        filename = {
            "/": "products.html",
            "/products": "products.html",
            "/dynamic": "dynamic.html",
            "/form": "form.html",
            "/empty": "empty.html",
            "/slow": "products.html",
        }.get(path)
        if not filename:
            self.send_error(404)
            return
        data = Path(__file__).with_name(filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            pass

    def do_POST(self):
        if self.path != "/api/applications":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 10000:
                raise ValueError()
            body = json.loads(self.rfile.read(size))
            key = body.pop("idempotency_key")
            uuid.UUID(key)
            if set(body) != {"applicant", "department", "reason"} or not all(
                isinstance(v, str) and v.strip() and len(v) <= 500
                for v in body.values()
            ):
                raise ValueError()
            payload = json.dumps(body, sort_keys=True)
            with sqlite3.connect(DB) as c:
                c.execute(
                    "INSERT OR IGNORE INTO applications VALUES (?,?,?)",
                    (key, payload, str(uuid.uuid4())),
                )
                old, receipt = c.execute(
                    "SELECT payload,receipt FROM applications WHERE id=?", (key,)
                ).fetchone()
                if old != payload:
                    self.send_error(409)
                    return
            data = json.dumps({"receipt": receipt}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(400)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    init()
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
