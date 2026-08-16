"""TOML configuration loading (stdlib `tomllib`, no third-party deps)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .catalogue import ShowRule, builtin_rules

DEFAULT_SOURCES: list[dict] = [
    {
        "name": "uk",
        "type": "xmltv",
        "url": "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    },
    {
        "name": "us",
        "type": "xmltv",
        "url": "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
    },
    {
        "name": "us-sports",
        "type": "xmltv",
        "url": "https://epgshare01.online/epgshare01/epg_ripper_US_SPORTS1.xml.gz",
    },
    {
        "name": "cz",
        "type": "xmltv",
        "url": "https://epgshare01.online/epgshare01/epg_ripper_CZ1.xml.gz",
    },
]


@dataclass(slots=True)
class Config:
    sources: list[dict] = field(default_factory=lambda: [dict(s) for s in DEFAULT_SOURCES])
    shows: list[ShowRule] = field(default_factory=builtin_rules)

    days_ahead: int = 14
    days_back: int = 0
    timezone: str = "Europe/Prague"
    include_repeats: bool = False
    dedupe_window_hours: int = 6
    channel_allowlist: list[str] = field(default_factory=list)
    channel_blocklist: list[str] = field(default_factory=list)
    cache_hours: int = 6

    calendar_name: str = "Football on TV"
    calendar_description: str = "Football magazines and analysis shows from TV listings"
    reminder_minutes: int = 15
    event_prefix: str = ""
    output: str = "football.ics"

    google_calendar_id: str = "primary"

    @property
    def cache_seconds(self) -> int:
        return max(0, self.cache_hours) * 3600


def load_config(path: str | Path | None) -> Config:
    """Load a config file, falling back to the built-in defaults."""
    config = Config()
    if path is None:
        return config

    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    general = data.get("general", {})
    for key in (
        "days_ahead",
        "days_back",
        "timezone",
        "include_repeats",
        "dedupe_window_hours",
        "channel_allowlist",
        "channel_blocklist",
        "cache_hours",
    ):
        if key in general:
            setattr(config, key, general[key])

    calendar = data.get("calendar", {})
    for key, attr in (
        ("name", "calendar_name"),
        ("description", "calendar_description"),
        ("reminder_minutes", "reminder_minutes"),
        ("event_prefix", "event_prefix"),
        ("output", "output"),
    ):
        if key in calendar:
            setattr(config, attr, calendar[key])

    google = data.get("google", {})
    if "calendar_id" in google:
        config.google_calendar_id = google["calendar_id"]

    if sources := data.get("sources"):
        config.sources = [dict(source) for source in sources]

    config.shows = _load_shows(data)
    return config


def _load_shows(data: dict) -> list[ShowRule]:
    """Combine the built-in catalogue with user-defined `[[shows]]` entries."""
    shows_config = data.get("show_catalogue", {})
    use_builtin = shows_config.get("use_builtin", True)
    groups = shows_config.get("groups")

    rules: list[ShowRule] = list(builtin_rules(groups)) if use_builtin else []

    for entry in data.get("shows", []):
        if "name" not in entry or "pattern" not in entry:
            raise ValueError("each [[shows]] entry needs at least 'name' and 'pattern'")
        rules.append(
            ShowRule(
                name=entry["name"],
                pattern=entry["pattern"],
                group=entry.get("group", "custom"),
                channels=entry.get("channels", []),
                exclude=entry.get("exclude", ""),
                match_subtitle=entry.get("match_subtitle", False),
                min_minutes=entry.get("min_minutes", 0),
            )
        )

    # A later rule with the same name overrides the catalogue entry, which is
    # how a user tweaks one built-in show without disabling the whole group.
    by_name: dict[str, ShowRule] = {}
    for rule in rules:
        by_name[rule.name.lower()] = rule
    return list(by_name.values())
