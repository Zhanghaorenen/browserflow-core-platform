"""Per-run HTTP CONNECT proxy. Resolve, validate and pin each outbound socket.

The browser's route gate controls HTTP methods; this proxy controls destination
IPs including redirects, subresources and DNS rebinding. No shared credentials.
"""

import http.client, select, socket, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .security import validate_url


class GuardProxy:
    def __init__(self, domains):
        self.domains = domains

    def __enter__(self):
        domains = self.domains

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def target(self, url):
                validate_url(url, domains)
                u = urlsplit(url)
                port = u.port or (443 if u.scheme == "https" else 80)
                # Validate exactly the addresses used for the outbound connection.
                records = socket.getaddrinfo(u.hostname, port, type=socket.SOCK_STREAM)
                from django.conf import settings
                import ipaddress

                demo = urlsplit(settings.DEMO_ORIGIN)
                exception = settings.ALLOW_DEMO and (u.scheme, u.hostname, u.port) == (
                    demo.scheme,
                    demo.hostname,
                    demo.port,
                )
                if not exception and any(
                    not ipaddress.ip_address(r[4][0]).is_global for r in records
                ):
                    raise ValueError("Blocked address")
                return u, records[0][4][0], port

            def do_CONNECT(self):
                try:
                    _, ip, port = self.target("https://" + self.path)
                    with socket.create_connection((ip, port), timeout=15) as remote:
                        self.send_response(200)
                        self.end_headers()
                        self.connection.settimeout(30)
                        remote.settimeout(30)
                        while True:
                            ready, _, _ = select.select(
                                [self.connection, remote], [], [], 20
                            )
                            if not ready:
                                break
                            for src in ready:
                                data = src.recv(65536)
                                if not data:
                                    return
                                (
                                    remote
                                    if src is self.connection
                                    else self.connection
                                ).sendall(data)
                except Exception:
                    try:
                        self.send_error(403)
                    except Exception:
                        pass

            def forward(self):
                try:
                    u, ip, port = self.target(self.path)
                    if int(self.headers.get("Content-Length", "0")) > 100000:
                        raise ValueError("Body too large")
                    body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    headers = {
                        k: v
                        for k, v in self.headers.items()
                        if k.lower()
                        not in [
                            "proxy-connection",
                            "connection",
                            "proxy-authorization",
                            "transfer-encoding",
                        ]
                    }
                    headers["Host"] = u.netloc
                    conn = http.client.HTTPConnection(ip, port, timeout=20)
                    try:
                        conn.request(
                            self.command,
                            u.path + ("?" + u.query if u.query else ""),
                            body,
                            headers,
                        )
                        response = conn.getresponse()
                        self.send_response(response.status)
                        for k, v in response.getheaders():
                            if k.lower() not in [
                                "connection",
                                "transfer-encoding",
                                "content-length",
                            ]:
                                self.send_header(k, v)
                        data = response.read(5_000_001)
                        if len(data) > 5_000_000:
                            raise ValueError("Response too large")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                    finally:
                        conn.close()
                except Exception:
                    try:
                        self.send_error(403)
                    except Exception:
                        pass

            do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = forward

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
