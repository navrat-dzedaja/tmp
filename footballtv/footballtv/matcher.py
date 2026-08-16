"""Turn a stream of EPG programmes into the shows we actually want."""

from __future__ import annotations

import fnmatch
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterable, Iterator

from .catalogue import DISCOVERY_FORMAT_HINTS, DISCOVERY_KEYWORDS, ShowRule
from .models import Match, Programme

log = logging.getLogger(__name__)


class CompiledRule:
    """A `ShowRule` with its regexes compiled and channel globs normalised."""

    __slots__ = ("rule", "pattern", "exclude", "channels")

    def __init__(self, rule: ShowRule) -> None:
        self.rule = rule
        try:
            self.pattern = re.compile(rule.pattern, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"show {rule.name!r}: invalid pattern {rule.pattern!r}: {exc}") from exc
        self.exclude = re.compile(rule.exclude, re.IGNORECASE) if rule.exclude else None
        self.channels = [glob.lower() for glob in rule.channels]

    def matches(self, programme: Programme) -> bool:
        haystack = programme.full_title if self.rule.match_subtitle else programme.title
        if not self.pattern.search(haystack):
            return False
        if self.exclude and self.exclude.search(haystack):
            return False
        if self.rule.min_minutes and programme.duration_minutes < self.rule.min_minutes:
            return False
        return self._channel_ok(programme)

    def _channel_ok(self, programme: Programme) -> bool:
        if not self.channels:
            return True
        candidates = [programme.channel_id.lower(), programme.channel_name.lower()]
        return any(
            fnmatch.fnmatch(candidate, glob) for glob in self.channels for candidate in candidates
        )


class Matcher:
    """Applies show rules to programmes and cleans up the results."""

    def __init__(
        self,
        rules: Iterable[ShowRule],
        *,
        days_ahead: int = 14,
        days_back: int = 0,
        include_repeats: bool = False,
        dedupe_window_hours: int = 6,
        channel_allowlist: list[str] | None = None,
        channel_blocklist: list[str] | None = None,
    ) -> None:
        self.rules = [CompiledRule(rule) for rule in rules]
        if not self.rules:
            raise ValueError("no show rules configured — nothing to match")
        self.days_ahead = days_ahead
        self.days_back = days_back
        self.include_repeats = include_repeats
        self.dedupe_window = timedelta(hours=dedupe_window_hours)
        self.channel_allowlist = [c.lower() for c in (channel_allowlist or [])]
        self.channel_blocklist = [c.lower() for c in (channel_blocklist or [])]
        self.stats: Counter[str] = Counter()

    def window(self, now: datetime | None = None) -> tuple[datetime, datetime]:
        now = now or datetime.now(timezone.utc)
        return now - timedelta(days=self.days_back), now + timedelta(days=self.days_ahead)

    def run(self, programmes: Iterable[Programme], now: datetime | None = None) -> list[Match]:
        start_window, end_window = self.window(now)
        matches = list(self._select(programmes, start_window, end_window))
        matches.sort(key=lambda m: (m.programme.start, m.programme.channel_name, m.show))
        deduped = self._dedupe(matches)
        self.stats["matched"] = len(matches)
        self.stats["kept"] = len(deduped)
        return deduped

    def _select(
        self, programmes: Iterable[Programme], start_window: datetime, end_window: datetime
    ) -> Iterator[Match]:
        for programme in programmes:
            self.stats["scanned"] += 1
            if not start_window <= programme.start <= end_window:
                continue
            if programme.is_repeat and not self.include_repeats:
                self.stats["skipped_repeat"] += 1
                continue
            if not self._channel_allowed(programme):
                self.stats["skipped_channel"] += 1
                continue
            for compiled in self.rules:
                if compiled.matches(programme):
                    yield Match(
                        programme=programme,
                        show=compiled.rule.name,
                        group=compiled.rule.group,
                        rule_id=compiled.rule.rule_id,
                    )
                    break

    def _channel_allowed(self, programme: Programme) -> bool:
        candidates = [programme.channel_id.lower(), programme.channel_name.lower()]
        if self.channel_blocklist and any(
            fnmatch.fnmatch(candidate, glob)
            for glob in self.channel_blocklist
            for candidate in candidates
        ):
            return False
        if not self.channel_allowlist:
            return True
        return any(
            fnmatch.fnmatch(candidate, glob)
            for glob in self.channel_allowlist
            for candidate in candidates
        )

    def _dedupe(self, matches: list[Match]) -> list[Match]:
        """Drop the same episode showing up twice.

        National feeds list a show on the SD channel, the HD channel and the
        +1 channel, and several sources overlap, so without this the calendar
        fills up with four copies of one *Match of the Day*.
        """
        kept: list[Match] = []
        last_seen: dict[tuple[str, str], datetime] = {}
        for match in matches:
            programme = match.programme
            key = (match.show.lower(), _episode_key(programme))
            previous = last_seen.get(key)
            if previous is not None and programme.start - previous <= self.dedupe_window:
                self.stats["deduped"] += 1
                continue
            last_seen[key] = programme.start
            kept.append(match)
        return kept


def _episode_key(programme: Programme) -> str:
    """Identify an episode across channels: subtitle if there is one, else the day."""
    if programme.subtitle:
        return programme.subtitle.strip().lower()
    return programme.start.astimezone(timezone.utc).strftime("%Y-%m-%d")


def discover(
    programmes: Iterable[Programme],
    *,
    known: Iterable[ShowRule] = (),
    min_occurrences: int = 2,
    limit: int = 60,
) -> list[tuple[str, int, str]]:
    """Find recurring football-magazine-looking shows missing from the catalogue.

    Returns `(title, occurrences, example channel)` sorted by frequency. A show
    that recurs and mentions football plus a magazine-format word is almost
    always a magazine; live matches rarely repeat under an identical title.
    """
    compiled = [CompiledRule(rule) for rule in known]
    counts: Counter[str] = Counter()
    channels: dict[str, str] = {}

    for programme in programmes:
        title = programme.title.strip()
        if not title or any(rule.matches(programme) for rule in compiled):
            continue
        haystack = f"{title} {programme.subtitle} {' '.join(programme.categories)}".lower()
        if not any(keyword in haystack for keyword in DISCOVERY_KEYWORDS):
            continue
        if not any(hint in haystack for hint in DISCOVERY_FORMAT_HINTS):
            continue
        if _looks_like_a_fixture(title):
            continue
        counts[title] += 1
        channels.setdefault(title, programme.channel_name or programme.channel_id)

    return [
        (title, count, channels.get(title, ""))
        for title, count in counts.most_common(limit)
        if count >= min_occurrences
    ]


_FIXTURE = re.compile(r"\bv(?:s)?\.?\b|\bagainst\b|\s[-–]\s.*\b\d+\s*[-:]\s*\d+", re.IGNORECASE)


def _looks_like_a_fixture(title: str) -> bool:
    """'Arsenal v Chelsea' is a match, not a magazine."""
    return bool(_FIXTURE.search(title))
