"""Small dependency-free HTTP helper with an on-disk cache.

EPG files are large (the UK feed is ~100 MB uncompressed) and the upstream
servers are volunteer-run, so every download is cached and re-used until it
goes stale.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import os
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

log = logging.getLogger(__name__)

USER_AGENT = "footballtv/1.0 (+https://github.com/navrat-dzedaja/tmp)"
DEFAULT_CACHE_DIR = Path(
    os.environ.get("FOOTBALLTV_CACHE_DIR")
    or Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "footballtv"
)


class DownloadError(RuntimeError):
    pass


def cache_dir() -> Path:
    DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_CACHE_DIR


def _cache_path(url: str, suffix: str = ".bin") -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return cache_dir() / f"{digest}{suffix}"


def fetch(
    url: str,
    *,
    max_age: int = 6 * 3600,
    timeout: int = 120,
    retries: int = 3,
    headers: dict[str, str] | None = None,
) -> bytes:
    """Download `url`, transparently decompressing gzip/deflate responses.

    Results are cached for `max_age` seconds. A stale cache entry is still
    preferred over an error, so a source going down degrades the guide rather
    than breaking the run.
    """
    path = _cache_path(url)
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age:
        log.debug("cache hit %s", url)
        return path.read_bytes()

    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        **(headers or {}),
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                encoding = (response.headers.get("Content-Encoding") or "").lower()
            data = _decompress(raw, encoding, url)
            path.write_bytes(data)
            return data
        except (urllib.error.URLError, OSError, zlib.error) as exc:  # noqa: PERF203
            last_error = exc
            wait = 2**attempt
            log.warning("fetch failed (%s), retry in %ss: %s", exc, wait, url)
            if attempt < retries - 1:
                time.sleep(wait)

    if path.exists():
        age_h = (time.time() - path.stat().st_mtime) / 3600
        log.warning("using stale cache (%.1fh old) for %s", age_h, url)
        return path.read_bytes()
    raise DownloadError(f"could not download {url}: {last_error}")


def _decompress(raw: bytes, encoding: str, url: str) -> bytes:
    """Handle both Content-Encoding and `.gz` payloads (servers disagree)."""
    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(raw)
        except (OSError, EOFError, zlib.error):
            # Truncated multi-member gzip: salvage what decoded cleanly.
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as fh:
                return _read_partial(fh, url)
    if encoding == "deflate":
        return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


def _read_partial(fh: io.BufferedIOBase, url: str) -> bytes:
    chunks: list[bytes] = []
    try:
        while chunk := fh.read(1 << 20):
            chunks.append(chunk)
    except (OSError, EOFError, zlib.error):
        log.warning("truncated gzip stream for %s, using %d bytes", url, sum(map(len, chunks)))
    return b"".join(chunks)


def fetch_json(url: str, *, max_age: int = 6 * 3600, timeout: int = 60) -> object:
    payload = fetch(url, max_age=max_age, timeout=timeout, headers={"Accept": "application/json"})
    return json.loads(payload.decode("utf-8", errors="replace"))
