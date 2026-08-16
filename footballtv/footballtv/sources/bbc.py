"""BBC schedules source, reading the JSON behind bbc.co.uk/schedules.

This is optional: the UK XMLTV feed already carries the BBC channels. It
exists because the BBC's own data is cleaner (proper episode subtitles,
synopses and a canonical programme URL), which makes for much nicer calendar
entries for *Match of the Day* and friends.

The endpoint is undocumented, so the parser walks the payload defensively
and simply yields nothing if the BBC changes shape — the XMLTV source keeps
the guide working in that case.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Iterator

from ..http import DownloadError, fetch_json
from ..models import Channel, Programme

log = logging.getLogger(__name__)

# Service ids as used by bbc.co.uk/schedules/<sid>.
BBC_SERVICES: dict[str, str] = {
    "p00fzl6p": "BBC One",
    "p00fzl8d": "BBC Two",
    "p00fzl95": "BBC Three",
    "p00fzl015": "BBC Four",
    "p00fzl9p": "BBC Scotland",
    "p00fzl7b": "BBC One Wales",
    "p00fzl74": "BBC One Northern Ireland",
    "p00fzl64": "BBC One Scotland",
}


class BbcSource:
    """Fetches one JSON schedule document per channel per day."""

    type = "bbc"

    def __init__(
        self,
        name: str = "bbc",
        *,
        services: dict[str, str] | list[str] | None = None,
        days_ahead: int = 14,
        days_back: int = 0,
        max_age: int = 6 * 3600,
    ) -> None:
        self.name = name
        if isinstance(services, list):
            self.services = {sid: BBC_SERVICES.get(sid, sid) for sid in services}
        else:
            self.services = dict(services or BBC_SERVICES)
        self.days_ahead = days_ahead
        self.days_back = days_back
        self.max_age = max_age
        self.channels: dict[str, Channel] = {
            sid: Channel(sid, [label], name) for sid, label in self.services.items()
        }

    def load(self) -> Iterator[Programme]:
        today = date.today()
        days = [
            today + timedelta(days=offset)
            for offset in range(-self.days_back, self.days_ahead + 1)
        ]
        for sid, label in self.services.items():
            for day in days:
                url = f"https://www.bbc.co.uk/schedules/{sid}/{day.isoformat()}.json"
                try:
                    payload = fetch_json(url, max_age=self.max_age)
                except (DownloadError, ValueError) as exc:
                    log.debug("bbc: %s unavailable (%s)", url, exc)
                    continue
                yield from self._parse(payload, sid, label)

    def _parse(self, payload: Any, sid: str, label: str) -> Iterator[Programme]:
        for broadcast in _find_broadcasts(payload):
            start = _iso(broadcast.get("start"))
            if start is None:
                continue
            programme = broadcast.get("programme") or {}
            titles = programme.get("display_titles") or {}
            title = (titles.get("title") or programme.get("title") or "").strip()
            if not title:
                continue
            pid = programme.get("pid") or ""
            yield Programme(
                channel_id=sid,
                channel_name=label,
                start=start,
                stop=_iso(broadcast.get("end")),
                title=title,
                subtitle=(titles.get("subtitle") or "").strip(),
                description=(
                    programme.get("medium_synopsis")
                    or programme.get("short_synopsis")
                    or ""
                ).strip(),
                is_repeat=bool(broadcast.get("is_repeat")),
                source=self.name,
                url=f"https://www.bbc.co.uk/programmes/{pid}" if pid else "",
            )


def _find_broadcasts(payload: Any) -> list[dict]:
    """Locate the broadcasts list wherever the BBC nests it."""
    if isinstance(payload, dict):
        broadcasts = payload.get("broadcasts")
        if isinstance(broadcasts, list):
            return [entry for entry in broadcasts if isinstance(entry, dict)]
        for value in payload.values():
            if isinstance(value, (dict, list)) and (found := _find_broadcasts(value)):
                return found
    elif isinstance(payload, list):
        for entry in payload:
            if found := _find_broadcasts(entry):
                return found
    return []


def _iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
