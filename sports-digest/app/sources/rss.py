"""RSS news source using feedparser."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import feedparser

from .base import NewsItem

logger = logging.getLogger(__name__)


def fetch_rss_items(feed_url: str, max_age_hours: int, source_label: str) -> list[NewsItem]:
    """Fetch and parse one RSS feed, filtering to items published within max_age_hours.

    A single bad/unreachable feed must not raise - callers keep going with an empty list.
    """
    try:
        parsed = feedparser.parse(feed_url)
    except Exception:
        logger.exception("Failed to fetch/parse RSS feed %s", feed_url)
        return []

    if getattr(parsed, "bozo", False) and not parsed.entries:
        logger.warning("RSS feed %s returned no usable entries (bozo=%s)", feed_url, parsed.get("bozo_exception"))
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    items: list[NewsItem] = []
    for entry in parsed.entries:
        published = _parse_entry_date(entry)
        # Entries with no date are kept (better to over-include than silently drop news).
        if published is not None and published < cutoff:
            continue
        items.append(
            NewsItem(
                title=entry.get("title", "").strip(),
                link=entry.get("link", ""),
                published=published,
                source=source_label,
            )
        )
    return items


def _parse_entry_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            try:
                return datetime(*struct[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None
