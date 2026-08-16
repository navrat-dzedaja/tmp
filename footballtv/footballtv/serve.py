"""Serve the generated calendar over HTTP.

Useful for pointing a local Apple Calendar / Android / Thunderbird client at
`http://127.0.0.1:8777/football.ics`. Proton Calendar needs a publicly
reachable URL instead — see the GitHub Pages workflow in the README.
"""

from __future__ import annotations

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import Config
from .ics import build_calendar

log = logging.getLogger(__name__)


class _Cache:
    def __init__(self, config: Config, refresh_seconds: int) -> None:
        self.config = config
        self.refresh_seconds = refresh_seconds
        self.lock = threading.Lock()
        self.body = b""
        self.generated_at = 0.0

    def get(self) -> bytes:
        with self.lock:
            if self.body and (time.time() - self.generated_at) < self.refresh_seconds:
                return self.body
            from .cli import _collect  # imported late to avoid a circular import

            log.info("regenerating calendar")
            matches = _collect(self.config)
            calendar = build_calendar(
                matches,
                name=self.config.calendar_name,
                description=self.config.calendar_description,
                reminder_minutes=self.config.reminder_minutes,
                event_prefix=self.config.event_prefix,
            )
            self.body = calendar.encode("utf-8")
            self.generated_at = time.time()
            log.info("serving %d events", len(matches))
            return self.body


def serve(config: Config, *, host: str = "127.0.0.1", port: int = 8777, refresh_minutes: int = 360) -> None:
    cache = _Cache(config, refresh_minutes * 60)

    class Handler(BaseHTTPRequestHandler):
        server_version = "footballtv"

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path.rstrip("/") in ("", "/index.html"):
                self._respond(
                    b"Subscribe your calendar to /football.ics\n", "text/plain; charset=utf-8"
                )
                return
            if not self.path.startswith("/football.ics"):
                self.send_error(404)
                return
            try:
                body = cache.get()
            except Exception as exc:
                log.error("calendar generation failed: %s", exc)
                self.send_error(503, "calendar generation failed")
                return
            self._respond(body, "text/calendar; charset=utf-8")

        def _respond(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            log.debug("%s - %s", self.address_string(), fmt % args)

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving calendar at http://{host}:{port}/football.ics (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
