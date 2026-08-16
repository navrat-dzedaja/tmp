from datetime import datetime, timezone

import pytest

from footballtv import gcal
from footballtv.config import load_config
from footballtv.models import Match, Programme
from footballtv.sources import build_source
from footballtv.sources.bbc import BbcSource, _find_broadcasts
from footballtv.sources.xmltv import XmltvSource


def write_config(tmp_path, body):
    path = tmp_path / "config.toml"
    path.write_text(body)
    return path


def test_defaults_without_a_config_file():
    config = load_config(None)
    assert config.days_ahead == 14
    assert any("epg_ripper_UK1" in s["url"] for s in config.sources)
    assert any(rule.name == "Tiki-Taka" for rule in config.shows)
    assert any(rule.name == "Match of the Day" for rule in config.shows)


def test_missing_config_file_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.toml")


def test_general_and_calendar_sections(tmp_path):
    path = write_config(
        tmp_path,
        """
[general]
days_ahead = 3
timezone = "Europe/London"
channel_blocklist = ["*+1*"]

[calendar]
name = "Fotbal"
reminder_minutes = 45
output = "out/f.ics"

[google]
calendar_id = "abc@group.calendar.google.com"
""",
    )
    config = load_config(path)
    assert config.days_ahead == 3
    assert config.timezone == "Europe/London"
    assert config.channel_blocklist == ["*+1*"]
    assert config.calendar_name == "Fotbal"
    assert config.reminder_minutes == 45
    assert config.output == "out/f.ics"
    assert config.google_calendar_id == "abc@group.calendar.google.com"


def test_groups_limit_the_catalogue(tmp_path):
    path = write_config(tmp_path, '[show_catalogue]\ngroups = ["cz"]\n')
    names = {rule.name for rule in load_config(path).shows}
    assert "Tiki-Taka" in names
    assert "Match of the Day" not in names


def test_unknown_group_is_reported(tmp_path):
    path = write_config(tmp_path, '[show_catalogue]\ngroups = ["atlantis"]\n')
    with pytest.raises(ValueError, match="unknown show group"):
        load_config(path)


def test_custom_show_added_to_builtins(tmp_path):
    path = write_config(
        tmp_path,
        '[[shows]]\nname = "Chill Show"\npattern = "^chill"\ngroup = "custom"\n',
    )
    config = load_config(path)
    assert any(rule.name == "Chill Show" for rule in config.shows)
    assert any(rule.name == "Match of the Day" for rule in config.shows)


def test_custom_show_overrides_a_builtin(tmp_path):
    path = write_config(
        tmp_path,
        '[[shows]]\nname = "Tiki-Taka"\npattern = "^tiki"\nchannels = ["*oneplay*"]\n',
    )
    rules = {rule.name: rule for rule in load_config(path).shows}
    assert rules["Tiki-Taka"].channels == ["*oneplay*"]


def test_disabling_builtins_leaves_only_custom_shows(tmp_path):
    path = write_config(
        tmp_path,
        '[show_catalogue]\nuse_builtin = false\n\n[[shows]]\nname = "Only"\npattern = "^only"\n',
    )
    assert [rule.name for rule in load_config(path).shows] == ["Only"]


def test_incomplete_show_entry_is_rejected(tmp_path):
    path = write_config(tmp_path, '[[shows]]\nname = "No pattern"\n')
    with pytest.raises(ValueError, match="'name' and 'pattern'"):
        load_config(path)


def test_sources_replace_the_defaults(tmp_path):
    path = write_config(
        tmp_path, '[[sources]]\nname = "local"\ntype = "xmltv"\npath = "./guide.xml"\n'
    )
    assert load_config(path).sources == [{"name": "local", "type": "xmltv", "path": "./guide.xml"}]


def test_build_source_dispatch():
    assert isinstance(build_source({"type": "xmltv", "url": "http://x/y.xml"}), XmltvSource)
    assert isinstance(build_source({"type": "bbc"}), BbcSource)
    with pytest.raises(ValueError, match="unknown source type"):
        build_source({"type": "teletext"})
    with pytest.raises(ValueError, match="'url' or 'path'"):
        build_source({"type": "xmltv", "name": "empty"})


# --- BBC source -------------------------------------------------------------


def test_bbc_broadcasts_are_found_however_they_are_nested():
    payload = {"schedule": {"day": {"broadcasts": [{"start": "2026-08-16T22:40:00+01:00"}]}}}
    assert _find_broadcasts(payload) == [{"start": "2026-08-16T22:40:00+01:00"}]
    assert _find_broadcasts({"nothing": "here"}) == []


def test_bbc_parses_a_broadcast():
    source = BbcSource(services={"p00fzl6p": "BBC One"})
    payload = {
        "schedule": {
            "day": {
                "broadcasts": [
                    {
                        "start": "2026-08-16T22:40:00+01:00",
                        "end": "2026-08-17T00:05:00+01:00",
                        "is_repeat": False,
                        "programme": {
                            "pid": "m00abcde",
                            "display_titles": {"title": "Match of the Day", "subtitle": "16/08/2026"},
                            "short_synopsis": "Premier League highlights.",
                        },
                    },
                    {"start": None, "programme": {}},
                ]
            }
        }
    }
    programmes = list(source._parse(payload, "p00fzl6p", "BBC One"))
    assert len(programmes) == 1
    assert programmes[0].title == "Match of the Day"
    assert programmes[0].subtitle == "16/08/2026"
    assert programmes[0].url == "https://www.bbc.co.uk/programmes/m00abcde"
    assert programmes[0].start.astimezone(timezone.utc).hour == 21


# --- Google Calendar --------------------------------------------------------


def make_match(**overrides):
    defaults = dict(
        channel_id="bbcone.uk",
        channel_name="BBC One",
        start=datetime(2026, 8, 16, 21, 40, tzinfo=timezone.utc),
        stop=datetime(2026, 8, 16, 23, 5, tzinfo=timezone.utc),
        title="Match of the Day",
        subtitle="16/08/2026",
        source="uk",
    )
    defaults.update(overrides)
    return Match(programme=Programme(**defaults), show="Match of the Day", group="bbc")


def test_google_event_id_is_valid():
    event_id = gcal._event_id(make_match())
    # Google requires base32hex (a-v and 0-9), 5-1024 characters.
    assert 5 <= len(event_id) <= 1024
    assert set(event_id) <= set("abcdefghijklmnopqrstuv0123456789")


def test_google_event_body():
    body = gcal._event_body(make_match(), 15, "⚽ ")
    assert body["summary"] == "⚽ Match of the Day — 16/08/2026"
    assert body["start"] == {"dateTime": "2026-08-16T21:40:00Z", "timeZone": "UTC"}
    assert body["end"] == {"dateTime": "2026-08-16T23:05:00Z", "timeZone": "UTC"}
    assert body["extendedProperties"]["private"]["footballtv"] == "1"
    assert body["reminders"]["overrides"] == [{"method": "popup", "minutes": 15}]


def test_google_needs_update_detects_real_changes():
    desired = gcal._event_body(make_match(), 15, "")
    assert gcal._needs_update(desired, desired) is False
    # Same instant, different offset notation — not a change.
    shifted = dict(desired, start={"dateTime": "2026-08-16T23:40:00+02:00", "timeZone": "UTC"})
    assert gcal._needs_update(shifted, desired) is False
    assert gcal._needs_update(dict(desired, summary="Something else"), desired) is True
    assert gcal._needs_update({}, desired) is True


def test_google_dry_run_does_not_authenticate(monkeypatch):
    def explode():
        raise AssertionError("dry run must not touch the network")

    monkeypatch.setattr(gcal, "_access_token", explode)
    result = gcal.sync(
        [make_match()],
        time_min=datetime(2026, 8, 1, tzinfo=timezone.utc),
        time_max=datetime(2026, 9, 1, tzinfo=timezone.utc),
        dry_run=True,
    )
    assert result.created == 1
