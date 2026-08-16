import gzip
from datetime import datetime, timedelta, timezone

import pytest

from footballtv.sources.xmltv import XmltvSource, parse_xmltv_time

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="BBCOne.uk">
    <display-name>BBC One</display-name>
    <display-name lang="en">BBC One HD</display-name>
  </channel>
  <channel id="OneplaySport.cz">
    <display-name>Oneplay Sport</display-name>
  </channel>
  <programme start="20260816224000 +0100" stop="20260817000500 +0100" channel="BBCOne.uk">
    <title lang="cs">Fotbal dne</title>
    <title lang="en">Match of the Day</title>
    <sub-title>16/08/2026</sub-title>
    <desc lang="en">Highlights of the Premier League.</desc>
    <category>Sports</category>
    <url>https://www.bbc.co.uk/programmes/m00abcde</url>
  </programme>
  <programme start="20260817101500 +0100" stop="20260817111500 +0100" channel="BBCOne.uk">
    <title>Match of the Day 2</title>
    <previously-shown />
  </programme>
  <programme start="20260818200000 +0200" channel="OneplaySport.cz">
    <title>Tiki-Taka</title>
  </programme>
  <programme start="garbage" channel="BBCOne.uk"><title>Broken</title></programme>
  <programme start="20260818210000 +0200"><title>No channel</title></programme>
</tv>
"""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("20260816224000 +0100", datetime(2026, 8, 16, 21, 40, tzinfo=timezone.utc)),
        ("20260816224000 -0500", datetime(2026, 8, 17, 3, 40, tzinfo=timezone.utc)),
        ("20260816224000", datetime(2026, 8, 16, 22, 40, tzinfo=timezone.utc)),
        ("202608162240 +0100", datetime(2026, 8, 16, 21, 40, tzinfo=timezone.utc)),
        ("20260816224000 +01:00", datetime(2026, 8, 16, 21, 40, tzinfo=timezone.utc)),
    ],
)
def test_parse_xmltv_time(raw, expected):
    parsed = parse_xmltv_time(raw)
    assert parsed is not None
    assert parsed.astimezone(timezone.utc) == expected


@pytest.mark.parametrize("raw", ["", "not a time", "2026", "99999999999999 +0100"])
def test_parse_xmltv_time_rejects_junk(raw):
    assert parse_xmltv_time(raw) is None


def _write_sample(tmp_path, compress=False):
    path = tmp_path / ("sample.xml.gz" if compress else "sample.xml")
    data = SAMPLE.encode()
    path.write_bytes(gzip.compress(data) if compress else data)
    return path


@pytest.mark.parametrize("compress", [False, True])
def test_load_parses_programmes(tmp_path, compress):
    source = XmltvSource("test", path=str(_write_sample(tmp_path, compress)))
    programmes = list(source.load())

    # The two malformed entries are skipped, not fatal.
    assert [p.title for p in programmes] == ["Match of the Day", "Match of the Day 2", "Tiki-Taka"]

    motd = programmes[0]
    assert motd.channel_name == "BBC One"
    assert motd.subtitle == "16/08/2026"
    assert motd.description == "Highlights of the Premier League."
    assert motd.categories == ["Sports"]
    assert motd.url == "https://www.bbc.co.uk/programmes/m00abcde"
    assert motd.is_repeat is False
    assert motd.start == datetime(2026, 8, 16, 21, 40, tzinfo=timezone.utc)
    assert motd.duration_minutes == 85

    assert programmes[1].is_repeat is True


def test_english_title_preferred(tmp_path):
    source = XmltvSource("test", path=str(_write_sample(tmp_path)))
    assert list(source.load())[0].title == "Match of the Day"


def test_missing_stop_falls_back_to_an_hour(tmp_path):
    source = XmltvSource("test", path=str(_write_sample(tmp_path)))
    tiki = list(source.load())[2]
    assert tiki.stop is None
    assert tiki.end - tiki.start == timedelta(hours=1)


def test_channels_are_collected(tmp_path):
    source = XmltvSource("test", path=str(_write_sample(tmp_path)))
    list(source.load())
    assert set(source.channels) == {"BBCOne.uk", "OneplaySport.cz"}
    assert source.channels["BBCOne.uk"].aliases() == ["BBCOne.uk", "BBC One", "BBC One HD"]


def test_channel_filter(tmp_path):
    source = XmltvSource("test", path=str(_write_sample(tmp_path)), channel_filter=["oneplay"])
    assert [p.title for p in source.load()] == ["Tiki-Taka"]
