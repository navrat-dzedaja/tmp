"""Generic, config-driven scraping source using httpx + selectolax.

Selectors are supplied per-target in config.yaml - this module has no
site-specific knowledge, so it only works as well as the configured selectors do.
"""
from __future__ import annotations

import logging

import httpx
from selectolax.parser import HTMLParser

from ..config import ScrapeTarget
from .base import NewsItem

logger = logging.getLogger(__name__)


def fetch_scrape_items(target: ScrapeTarget) -> list[NewsItem]:
    """Fetch one scrape target and extract items via configured CSS selectors.

    No publish-date extraction here (pages vary too much) - scraped items are
    always treated as "recent" by the pipeline. A failure returns an empty list.
    """
    try:
        resp = httpx.get(target.url, timeout=15.0, follow_redirects=True, headers={
            "User-Agent": "sports-digest/0.1 (+https://example.local)"
        })
        resp.raise_for_status()
    except Exception:
        logger.exception("Failed to fetch scrape target %s (%s)", target.name, target.url)
        return []

    try:
        tree = HTMLParser(resp.text)
    except Exception:
        logger.exception("Failed to parse HTML for scrape target %s", target.name)
        return []

    items: list[NewsItem] = []
    for node in tree.css(target.item_selector):
        title_node = node.css_first(target.title_selector)
        link_node = node.css_first(target.link_selector)
        if title_node is None or link_node is None:
            continue
        title = title_node.text(strip=True)
        href = link_node.attributes.get(target.link_attr)
        if not title or not href:
            continue
        link = href if href.startswith("http") else f"{target.base_url.rstrip('/')}/{href.lstrip('/')}"
        items.append(NewsItem(title=title, link=link, published=None, source=target.name))
    return items
