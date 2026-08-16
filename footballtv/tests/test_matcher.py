from datetime import datetime, timedelta, timezone

import pytest

from footballtv.catalogue import ShowRule, builtin_rules
from footballtv.matcher import Matcher, discover
from footballtv.models import Programme

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def programme(title, *, channel="BBC One", hours=24, subtitle="", repeat=False, minutes=60, desc=""):
    start = NOW + timedelta(hours=hours)
    return Programme(
        channel_id=channel.lower().replace(" ", "") + ".uk",
        channel_name=channel,
        start=start,
        stop=start + timedelta(minutes=minutes),
        title=title,
        subtitle=subtitle,
        description=desc,
        is_repeat=repeat,
    )


def match_titles(programmes, rules=None, **kwargs):
    matcher = Matcher(rules or builtin_rules(), **kwargs)
    return [(m.show, m.programme.channel_name) for m in matcher.run(programmes, now=NOW)]


def test_motd_and_motd2_do_not_collide():
    result = match_titles([programme("Match of the Day 2"), programme("Match of the Day", hours=25)])
    assert sorted(show for show, _ in result) == ["Match of the Day", "Match of the Day 2"]


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Match of the Day", "Match of the Day"),
        ("MOTDx", "MOTDx"),
        ("Match of the Day: Top 10", "Match of the Day: Top 10"),
        ("Football Focus", "Football Focus"),
        ("Tiki-Taka", "Tiki-Taka"),
        ("Tiki Taka", "Tiki-Taka"),
        ("Soccer Saturday", "Soccer Saturday"),
        ("Gillette Soccer Saturday", "Soccer Saturday"),
        ("Monday Night Football", "Monday Night Football"),
        ("Morning Footy", "Morning Footy"),
        ("UEFA Champions League Today", "Champions League Today"),
        ("Kickin' It", "Kickin' It"),
        ("Premier League Goal Zone", "Premier League Goal Zone"),
        ("ESPN FC", "ESPN FC"),
        ("Netbusters", "Netbusters"),
        ("Football Tonight", "Football Tonight"),
    ],
)
def test_catalogue_matches_known_shows(title, expected):
    channel = "Oneplay Sport 1" if "Tiki" in title else "BBC One"
    assert match_titles([programme(title, channel=channel)]) == [(expected, channel)]


@pytest.mark.parametrize(
    "title",
    [
        "Arsenal v Chelsea",
        "Premier League: Liverpool v Everton",
        "The Football Ramble Podcast Hour",
        "Rugby Tonight",
        "News at Ten",
    ],
)
def test_catalogue_ignores_non_magazines(title):
    assert match_titles([programme(title)]) == []


def test_channel_glob_restricts_bbc_shows():
    # "Final Score" is BBC-scoped in the catalogue, so an unrelated channel
    # showing something by that name must not match.
    assert match_titles([programme("Final Score", channel="Random Channel 5")]) == []
    assert match_titles([programme("Final Score", channel="BBC One")]) == [
        ("Final Score", "BBC One")
    ]


def test_repeats_are_dropped_unless_requested():
    entries = [programme("Football Focus", repeat=True)]
    assert match_titles(entries) == []
    assert match_titles(entries, include_repeats=True) == [("Football Focus", "BBC One")]


def test_window_excludes_far_future_and_past():
    entries = [
        programme("Football Focus", hours=24 * 30),
        programme("Match of the Day", hours=-48),
        programme("MOTDx", hours=12),
    ]
    assert match_titles(entries, days_ahead=14) == [("MOTDx", "BBC One")]


def test_days_back_includes_recent_past():
    entries = [programme("Match of the Day", hours=-24)]
    assert match_titles(entries) == []
    assert match_titles(entries, days_back=2) == [("Match of the Day", "BBC One")]


def test_dedupe_collapses_simulcasts():
    entries = [
        programme("Match of the Day", channel="BBC One", subtitle="16/08/2026", hours=10),
        programme("Match of the Day", channel="BBC One HD", subtitle="16/08/2026", hours=10),
        programme("Match of the Day", channel="BBC One Wales", subtitle="16/08/2026", hours=11),
    ]
    assert match_titles(entries) == [("Match of the Day", "BBC One")]


def test_dedupe_keeps_a_genuinely_later_episode():
    entries = [
        programme("Match of the Day", subtitle="16/08/2026", hours=10),
        programme("Match of the Day", subtitle="23/08/2026", hours=10 + 24 * 7),
    ]
    assert len(match_titles(entries)) == 2


def test_dedupe_window_is_configurable():
    entries = [
        programme("Football Focus", subtitle="ep1", hours=10),
        programme("Football Focus", subtitle="ep1", channel="BBC Two", hours=18),
    ]
    assert len(match_titles(entries, dedupe_window_hours=6)) == 2
    assert len(match_titles(entries, dedupe_window_hours=12)) == 1


def test_channel_blocklist_and_allowlist():
    entries = [
        programme("Football Focus", channel="BBC One"),
        programme("Football Focus", channel="BBC One +1", hours=25),
    ]
    assert len(match_titles(entries, channel_blocklist=["*+1*"])) == 1
    assert match_titles(entries, channel_allowlist=["*two*"]) == []


def test_custom_rule_min_minutes_filters_stings():
    rules = [ShowRule("Preview", r"^preview\b", "custom", min_minutes=20)]
    entries = [programme("Preview Show", minutes=5), programme("Preview Show", minutes=30, hours=25)]
    assert len(match_titles(entries, rules=rules)) == 1


def test_custom_rule_can_match_subtitle():
    rules = [ShowRule("Studio", r"fotbal", "custom", match_subtitle=True)]
    entries = [programme("Studio", subtitle="Fotbal dnes")]
    assert match_titles(entries, rules=rules) == [("Studio", "BBC One")]
    assert match_titles(entries, rules=[ShowRule("Studio", r"fotbal", "custom")]) == []


def test_matcher_requires_rules():
    with pytest.raises(ValueError, match="no show rules"):
        Matcher([])


def test_invalid_regex_is_reported_with_the_show_name():
    with pytest.raises(ValueError, match="Broken"):
        Matcher([ShowRule("Broken", r"([unclosed", "custom")])


def test_discover_finds_unlisted_magazines():
    entries = [
        programme("Bundesliga Weekly", channel="Sky Sports", hours=h) for h in (10, 34, 58)
    ] + [
        programme("Arsenal v Chelsea", channel="Sky Sports"),
        programme("Match of the Day", channel="BBC One"),
        programme("Cooking Show", channel="BBC Two"),
    ]
    found = discover(entries, known=builtin_rules(["bbc"]), min_occurrences=2)
    assert [title for title, _, _ in found] == ["Bundesliga Weekly"]
    assert found[0][1] == 3


def test_discover_skips_shows_already_in_the_catalogue():
    entries = [programme("Football Focus", hours=h) for h in (10, 34)]
    assert discover(entries, known=builtin_rules()) == []
