"""Narrow host bridge for signed Finance recommendation callbacks."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CALLBACK_PATH = re.compile(
    r"/api/v1/investments/internal/recommendation-jobs/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/callback"
)
MAX_BODY = 1024 * 1024
FORWARDED_HEADERS = (
    "Content-Type",
    "X-Finance-Timestamp",
    "X-Finance-Nonce",
    "X-Finance-Signature",
)


def handler_for(subnet: ipaddress.IPv4Network):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def _allowed_source(self) -> bool:
            try:
                return ipaddress.ip_address(self.client_address[0]) in subnet
            except ValueError:
                return False

        def _reject(self, status: int):
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if not self._allowed_source() or self.path != "/healthz":
                self._reject(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            if not self._allowed_source() or not CALLBACK_PATH.fullmatch(self.path):
                self._reject(404)
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._reject(400)
                return
            if length < 0 or length > MAX_BODY:
                self._reject(413)
                return
            if any(not self.headers.get(key) for key in FORWARDED_HEADERS[1:]):
                self._reject(400)
                return
            body = self.rfile.read(length)
            if len(body) != length:
                self._reject(400)
                return
            headers = {key: self.headers[key] for key in FORWARDED_HEADERS if key in self.headers}
            headers["Content-Length"] = str(length)
            connection = http.client.HTTPConnection("127.0.0.1", 8081, timeout=10)
            try:
                connection.request("POST", self.path, body=body, headers=headers)
                response = connection.getresponse()
                payload = response.read(MAX_BODY + 1)
                if len(payload) > MAX_BODY:
                    self._reject(502)
                    return
                self.send_response(response.status)
                self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (OSError, http.client.HTTPException):
                self._reject(502)
            finally:
                connection.close()

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", required=True)
    parser.add_argument("--subnet", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    subnet = ipaddress.ip_network(args.subnet, strict=True)
    bind = ipaddress.ip_address(args.bind)
    if not isinstance(subnet, ipaddress.IPv4Network) or bind != subnet.network_address + 1:
        parser.error("bind must be the first usable IPv4 address of the approved bridge subnet")
    if not 1024 <= args.port <= 65535:
        parser.error("port must be unprivileged")
    ThreadingHTTPServer((str(bind), args.port), handler_for(subnet)).serve_forever()


if __name__ == "__main__":
    main()
