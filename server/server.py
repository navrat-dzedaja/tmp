"""NAS-side endpoint for the YouTube Music → NAS Downloader userscript.

Receives POSTs from the browser script and runs yt-dlp in a background worker
to save the audio to disk. Intended to run on your own server/NAS.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import re
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# ---- Config via environment variables --------------------------------------
HOST = os.environ.get("YTMD_HOST", "0.0.0.0")
PORT = int(os.environ.get("YTMD_PORT", "8787"))
API_KEY = os.environ.get("YTMD_API_KEY", "change-me")
OUTPUT_DIR = Path(os.environ.get("YTMD_OUTPUT_DIR", "./downloads")).resolve()
AUDIO_FORMAT = os.environ.get("YTMD_AUDIO_FORMAT", "mp3")       # mp3, opus, m4a, flac...
AUDIO_QUALITY = os.environ.get("YTMD_AUDIO_QUALITY", "0")       # 0 = best for VBR
YTDLP_BIN = os.environ.get("YTMD_YTDLP_BIN", "yt-dlp")
COOKIES_FILE = os.environ.get("YTMD_COOKIES_FILE")              # optional

ARCHIVE_FILE = OUTPUT_DIR / ".downloaded-archive.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ytmd")


# ---- Worker ----------------------------------------------------------------
job_queue: "queue.Queue[dict]" = queue.Queue()
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def download(job: dict) -> None:
    video_id = job["videoId"]
    url = job["url"]
    title = job.get("title") or video_id

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        YTDLP_BIN,
        "--no-playlist",
        "--extract-audio",
        "--audio-format", AUDIO_FORMAT,
        "--audio-quality", AUDIO_QUALITY,
        "--embed-thumbnail",
        "--embed-metadata",
        "--download-archive", str(ARCHIVE_FILE),
        "--output", str(OUTPUT_DIR / "%(uploader)s - %(title)s [%(id)s].%(ext)s"),
        url,
    ]
    if COOKIES_FILE:
        cmd[1:1] = ["--cookies", COOKIES_FILE]

    log.info("downloading %s (%s)", title, video_id)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        log.error("yt-dlp not found at %r — install it or set YTMD_YTDLP_BIN", YTDLP_BIN)
        return

    if result.returncode == 0:
        log.info("done %s", video_id)
    else:
        log.error("yt-dlp failed for %s (rc=%s)\nstderr: %s",
                  video_id, result.returncode, result.stderr.strip())


def worker_loop() -> None:
    while True:
        job = job_queue.get()
        try:
            download(job)
        except Exception:
            log.exception("worker crashed on job %r", job)
        finally:
            job_queue.task_done()


# ---- HTTP handler ----------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        # CORS so the userscript can reach us from youtube.com in strict setups.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Api-Key")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # route access logs through logging
        log.info("%s - %s", self.address_string(), fmt % args)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(HTTPStatus.OK, {"ok": True, "queue": job_queue.qsize()})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/download":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        if self.headers.get("X-Api-Key") != API_KEY:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "bad api key"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 64 * 1024:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "empty or oversized body"})
            return

        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid json"})
            return

        video_id = str(payload.get("videoId") or "")
        if not VIDEO_ID_RE.match(video_id):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid videoId"})
            return

        # Rebuild the URL ourselves — never trust a URL supplied by the client
        # (prevents the endpoint being used to download arbitrary sites).
        job = {
            "videoId": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": str(payload.get("title") or "")[:300],
        }
        job_queue.put(job)
        log.info("queued %s (%s) [queue=%d]",
                 job["title"] or "?", video_id, job_queue.qsize())
        self._json(HTTPStatus.ACCEPTED, {"queued": True, "videoId": video_id})


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if API_KEY == "change-me":
        log.warning("YTMD_API_KEY is still the default — set a real secret!")

    threading.Thread(target=worker_loop, daemon=True, name="ytdlp-worker").start()

    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("listening on http://%s:%d  output=%s", HOST, PORT, OUTPUT_DIR)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        httpd.server_close()
        # Give the worker a moment to finish the in-flight job.
        time.sleep(0.2)


if __name__ == "__main__":
    main()
