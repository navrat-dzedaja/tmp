"""RFC 5545 iCalendar output.

The .ics file is the universal target: Proton Calendar, Google Calendar,
Apple Calendar on macOS/iOS and every Android calendar app can either import
it or subscribe to it over HTTP.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .models import Match

PRODID = "-//footballtv//Football on TV//EN"


def escape(value: str) -> str:
    """Escape TEXT values per RFC 5545 section 3.3.11."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold(line: str) -> list[str]:
    """Fold a content line to 75 octets, never splitting a UTF-8 sequence."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return [line]

    chunks: list[bytes] = []
    remaining = encoded
    limit = 75
    while len(remaining) > limit:
        cut = limit
        # Do not cut in the middle of a multi-byte character.
        while cut > 0 and (remaining[cut] & 0xC0) == 0x80:
            cut -= 1
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
        limit = 74  # continuation lines carry a leading space
    chunks.append(remaining)

    head, *tail = [chunk.decode("utf-8") for chunk in chunks]
    return [head, *(f" {part}" for part in tail)]


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_calendar(
    matches: Iterable[Match],
    *,
    name: str = "Football on TV",
    description: str = "",
    reminder_minutes: int = 15,
    event_prefix: str = "",
    refresh_hours: int = 12,
    now: datetime | None = None,
) -> str:
    """Render matches as a complete VCALENDAR document."""
    now = now or datetime.now(timezone.utc)
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        f"NAME:{escape(name)}",
        f"X-WR-CALNAME:{escape(name)}",
        f"REFRESH-INTERVAL;VALUE=DURATION:PT{refresh_hours}H",
        f"X-PUBLISHED-TTL:PT{refresh_hours}H",
    ]
    if description:
        lines += [f"DESCRIPTION:{escape(description)}", f"X-WR-CALDESC:{escape(description)}"]

    for match in matches:
        lines.extend(_event_lines(match, now, reminder_minutes, event_prefix))

    lines.append("END:VCALENDAR")

    folded: list[str] = []
    for line in lines:
        folded.extend(fold(line))
    return "\r\n".join(folded) + "\r\n"


def _event_lines(
    match: Match, now: datetime, reminder_minutes: int, event_prefix: str
) -> list[str]:
    programme = match.programme
    summary = f"{event_prefix}{match.show}" if event_prefix else match.show
    if programme.subtitle and programme.subtitle.lower() not in match.show.lower():
        summary = f"{summary} — {programme.subtitle}"

    body = [
        part
        for part in (
            programme.description,
            f"Channel: {programme.channel_name or programme.channel_id}",
            f"Original title: {programme.title}" if programme.title != match.show else "",
            programme.url,
            f"Source: {programme.source}",
        )
        if part
    ]

    lines = [
        "BEGIN:VEVENT",
        f"UID:{match.uid}@footballtv",
        f"DTSTAMP:{_stamp(now)}",
        f"DTSTART:{_stamp(programme.start)}",
        f"DTEND:{_stamp(programme.end)}",
        f"SUMMARY:{escape(summary)}",
        f"LOCATION:{escape(programme.channel_name or programme.channel_id)}",
        f"DESCRIPTION:{escape(chr(10).join(body))}",
        f"CATEGORIES:{escape('Football')},{escape(match.group or 'tv')}",
        "TRANSP:TRANSPARENT",
        "STATUS:CONFIRMED",
        f"X-FOOTBALLTV-SHOW:{escape(match.show)}",
    ]
    if programme.url:
        lines.append(f"URL:{programme.url}")
    if reminder_minutes > 0:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{escape(summary)}",
            f"TRIGGER:-PT{reminder_minutes}M",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines
