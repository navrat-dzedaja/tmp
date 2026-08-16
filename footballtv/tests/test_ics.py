from datetime import datetime, timedelta, timezone

from footballtv.ics import build_calendar, escape, fold
from footballtv.models import Match, Programme

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def make_match(**overrides):
    defaults = dict(
        channel_id="bbcone.uk",
        channel_name="BBC One",
        start=datetime(2026, 8, 16, 21, 40, tzinfo=timezone.utc),
        stop=datetime(2026, 8, 16, 23, 5, tzinfo=timezone.utc),
        title="Match of the Day",
        subtitle="16/08/2026",
        description="Highlights; analysis, and goals.",
        url="https://www.bbc.co.uk/programmes/m00abcde",
        source="uk",
    )
    defaults.update(overrides)
    return Match(programme=Programme(**defaults), show="Match of the Day", group="bbc")


def unfold(text: str) -> str:
    return text.replace("\r\n ", "")


def test_escape_handles_special_characters():
    assert escape("a,b;c\\d") == "a\\,b\\;c\\\\d"
    assert escape("line1\nline2") == "line1\\nline2"
    assert escape("line1\r\nline2") == "line1\\nline2"


def test_fold_short_line_untouched():
    assert fold("SUMMARY:short") == ["SUMMARY:short"]


def test_fold_respects_75_octets_and_utf8():
    line = "SUMMARY:" + "ě" * 200  # 2 bytes per character
    parts = fold(line)
    assert all(len(part.encode()) <= 75 for part in parts)
    assert all(part.startswith(" ") for part in parts[1:])
    assert "".join([parts[0], *(p[1:] for p in parts[1:])]) == line


def test_calendar_structure():
    ics = build_calendar([make_match()], name="Football on TV", now=NOW)
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.endswith("END:VCALENDAR\r\n")
    assert ics.count("BEGIN:VEVENT") == 1
    assert ics.count("END:VEVENT") == 1
    assert "\r\n" in ics and "\n\n" not in ics
    # A subscription feed must not look like a meeting invitation.
    assert "METHOD:" not in ics


def test_event_fields():
    body = unfold(build_calendar([make_match()], now=NOW))
    assert "DTSTART:20260816T214000Z" in body
    assert "DTEND:20260816T230500Z" in body
    assert "SUMMARY:Match of the Day — 16/08/2026" in body
    assert "LOCATION:BBC One" in body
    assert "URL:https://www.bbc.co.uk/programmes/m00abcde" in body
    assert "Highlights\\; analysis\\, and goals." in body
    assert "TRANSP:TRANSPARENT" in body


def test_missing_stop_gets_an_hour_long_event():
    body = unfold(build_calendar([make_match(stop=None)], now=NOW))
    assert "DTSTART:20260816T214000Z" in body
    assert "DTEND:20260816T224000Z" in body


def test_alarm_is_optional():
    assert "BEGIN:VALARM" in build_calendar([make_match()], reminder_minutes=15, now=NOW)
    assert "TRIGGER:-PT30M" in build_calendar([make_match()], reminder_minutes=30, now=NOW)
    assert "BEGIN:VALARM" not in build_calendar([make_match()], reminder_minutes=0, now=NOW)


def test_event_prefix():
    body = unfold(build_calendar([make_match()], event_prefix="⚽ ", now=NOW))
    assert "SUMMARY:⚽ Match of the Day" in body


def test_uid_is_stable_and_unique():
    first = make_match()
    same = make_match(description="different synopsis")
    other = make_match(start=first.programme.start + timedelta(hours=1))

    assert first.uid == same.uid  # same broadcast, re-scraped
    assert first.uid != other.uid
    assert f"UID:{first.uid}@footballtv" in build_calendar([first], now=NOW)


def test_uid_differs_per_channel():
    assert make_match().uid != make_match(channel_id="bbctwo.uk").uid


def test_long_summary_is_folded_and_recoverable():
    long_subtitle = "Very long episode subtitle " * 6
    ics = build_calendar([make_match(subtitle=long_subtitle)], now=NOW)
    assert all(len(line.encode()) <= 75 for line in ics.split("\r\n"))
    assert long_subtitle.strip() in unfold(ics)


def test_empty_calendar_is_still_valid():
    ics = build_calendar([], now=NOW)
    assert "BEGIN:VEVENT" not in ics
    assert ics.startswith("BEGIN:VCALENDAR") and ics.endswith("END:VCALENDAR\r\n")
