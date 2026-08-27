"""Common types shared by all source implementations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsItem:
    title: str
    link: str
    published: datetime | None
    source: str
