"""Core data types shared by sources, matcher and calendar writers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(slots=True)
class Channel:
    """A channel as advertised by an EPG source."""

    id: str
    names: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def display(self) -> str:
        return self.names[0] if self.names else self.id

    def aliases(self) -> list[str]:
        """Every string a channel rule may reasonably be written against."""
        return [self.id, *self.names]


@dataclass(slots=True)
class Programme:
    """A single broadcast of a programme on a channel."""

    channel_id: str
    start: datetime
    title: str
    stop: datetime | None = None
    subtitle: str = ""
    description: str = ""
    categories: list[str] = field(default_factory=list)
    is_repeat: bool = False
    channel_name: str = ""
    source: str = ""
    url: str = ""

    @property
    def end(self) -> datetime:
        """Best-effort end time; sources occasionally omit the stop attribute."""
        return self.stop or (self.start + timedelta(minutes=60))

    @property
    def duration_minutes(self) -> int:
        return max(0, int((self.end - self.start).total_seconds() // 60))

    @property
    def full_title(self) -> str:
        return f"{self.title}: {self.subtitle}" if self.subtitle else self.title

    def key(self) -> str:
        """Stable identity of this broadcast, used for calendar UIDs."""
        raw = "|".join(
            [
                self.channel_id.lower(),
                self.start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                _norm(self.title),
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class Match:
    """A programme that satisfied a show rule."""

    programme: Programme
    show: str
    group: str = ""
    rule_id: str = ""

    @property
    def uid(self) -> str:
        return self.programme.key()


def _norm(value: str) -> str:
    """Lowercase, strip punctuation/whitespace noise — for comparisons only."""
    value = value.lower().replace("&", "and")
    value = re.sub(r"[^\w\s]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()
