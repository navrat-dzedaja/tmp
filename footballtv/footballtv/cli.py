"""Command line interface."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import __version__
from .config import Config, load_config
from .ics import build_calendar
from .matcher import Matcher, discover
from .models import Match, Programme
from .sources import build_source

log = logging.getLogger("footballtv")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    try:
        config = load_config(args.config)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2

    _apply_overrides(config, args)

    try:
        return args.handler(args, config)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # surfaced as a clean message, traceback with -v
        log.debug("failed", exc_info=True)
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="footballtv",
        description="Find football magazine shows in TV listings and put them in your calendar.",
    )
    parser.add_argument("--version", action="version", version=f"footballtv {__version__}")
    parser.add_argument("-c", "--config", help="path to config.toml")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--days", type=int, help="days ahead to scan (default 14)")
    parser.add_argument("--days-back", type=int, help="days in the past to include")
    parser.add_argument("--timezone", help="timezone for displayed times, e.g. Europe/Prague")
    parser.add_argument("--source", action="append", help="only use these source names")
    parser.add_argument(
        "--no-cache", action="store_true", help="always re-download the EPG feeds"
    )
    parser.add_argument(
        "--include-repeats", action="store_true", help="keep programmes marked as repeats"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="print the matched shows")
    listing.add_argument("--show", help="filter to one show (substring, case-insensitive)")
    listing.add_argument("--group", help="filter to one catalogue group")
    listing.set_defaults(handler=cmd_list)

    ics = sub.add_parser("ics", help="write an .ics calendar file")
    ics.add_argument("-o", "--output", help="output path (default football.ics)")
    ics.set_defaults(handler=cmd_ics)

    google = sub.add_parser("sync-google", help="sync into a Google Calendar")
    google.add_argument("--calendar-id", help="target calendar id (default primary)")
    google.add_argument("--dry-run", action="store_true", help="report without writing")
    google.add_argument(
        "--no-prune",
        action="store_true",
        help="keep previously synced events that no longer match",
    )
    google.set_defaults(handler=cmd_sync_google)

    serve = sub.add_parser("serve", help="serve the .ics over HTTP for calendar subscriptions")
    serve.add_argument("--port", type=int, default=8777)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--refresh-minutes", type=int, default=360)
    serve.set_defaults(handler=cmd_serve)

    disc = sub.add_parser("discover", help="find football shows not in the catalogue yet")
    disc.add_argument("--min-count", type=int, default=2, help="minimum airings to report")
    disc.set_defaults(handler=cmd_discover)

    channels = sub.add_parser("channels", help="list channels in the configured sources")
    channels.add_argument("--grep", help="filter by substring, e.g. sky or oneplay")
    channels.set_defaults(handler=cmd_channels)

    shows = sub.add_parser("shows", help="list the configured show rules")
    shows.set_defaults(handler=cmd_shows)

    return parser


def _apply_overrides(config: Config, args: argparse.Namespace) -> None:
    if args.days is not None:
        config.days_ahead = args.days
    if args.days_back is not None:
        config.days_back = args.days_back
    if args.timezone:
        config.timezone = args.timezone
    if args.include_repeats:
        config.include_repeats = True
    if args.no_cache:
        config.cache_hours = 0
    if args.source:
        wanted = {name.lower() for name in args.source}
        config.sources = [s for s in config.sources if s.get("name", "").lower() in wanted]
        if not config.sources:
            raise SystemExit(f"error: no configured source matches {sorted(wanted)}")
    if getattr(args, "output", None):
        config.output = args.output
    if getattr(args, "calendar_id", None):
        config.google_calendar_id = args.calendar_id


# --- shared plumbing --------------------------------------------------------


def _load_programmes(config: Config) -> Iterator[Programme]:
    """Stream programmes from every configured source, tolerating failures."""
    for spec in config.sources:
        spec = {"max_age": config.cache_seconds, **spec}
        try:
            source = build_source(spec)
        except ValueError as exc:
            log.error("skipping source: %s", exc)
            continue
        log.info("loading source %s", source.name)
        count = 0
        try:
            for programme in source.load():
                count += 1
                yield programme
        except Exception as exc:  # one dead feed must not kill the run
            log.error("source %s failed after %d programmes: %s", source.name, count, exc)
            continue
        log.info("source %s: %d programmes", source.name, count)


def _collect(config: Config) -> list[Match]:
    matcher = Matcher(
        config.shows,
        days_ahead=config.days_ahead,
        days_back=config.days_back,
        include_repeats=config.include_repeats,
        dedupe_window_hours=config.dedupe_window_hours,
        channel_allowlist=config.channel_allowlist,
        channel_blocklist=config.channel_blocklist,
    )
    matches = matcher.run(_load_programmes(config))
    log.info(
        "scanned %d programmes, matched %d, kept %d after dedupe",
        matcher.stats["scanned"],
        matcher.stats["matched"],
        matcher.stats["kept"],
    )
    return matches


def _zone(config: Config) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(config.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("unknown timezone %r, falling back to UTC", config.timezone)
        return timezone.utc


# --- commands ---------------------------------------------------------------


def cmd_list(args: argparse.Namespace, config: Config) -> int:
    matches = _collect(config)
    if args.show:
        needle = args.show.lower()
        matches = [m for m in matches if needle in m.show.lower()]
    if args.group:
        matches = [m for m in matches if m.group.lower() == args.group.lower()]

    if not matches:
        print("No matching programmes found.")
        print("Try 'footballtv channels --grep sky' and 'footballtv discover' to tune the config.")
        return 0

    zone = _zone(config)
    current_day = None
    for match in matches:
        local = match.programme.start.astimezone(zone)
        day = local.date()
        if day != current_day:
            current_day = day
            print(f"\n{local:%a %d %b %Y}")
        channel = match.programme.channel_name or match.programme.channel_id
        title = match.show
        if match.programme.subtitle:
            title = f"{title} — {match.programme.subtitle}"
        print(f"  {local:%H:%M}  {title[:58]:<58} {channel[:28]}")

    print(f"\n{len(matches)} programmes ({config.timezone})")
    return 0


def cmd_ics(args: argparse.Namespace, config: Config) -> int:
    matches = _collect(config)
    calendar = build_calendar(
        matches,
        name=config.calendar_name,
        description=config.calendar_description,
        reminder_minutes=config.reminder_minutes,
        event_prefix=config.event_prefix,
    )
    output = Path(config.output).expanduser()
    if output.parent != Path(""):
        output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(calendar, encoding="utf-8", newline="")
    print(f"Wrote {len(matches)} events to {output}")
    return 0


def cmd_sync_google(args: argparse.Namespace, config: Config) -> int:
    from . import gcal

    matches = _collect(config)
    matcher_window = Matcher(
        config.shows, days_ahead=config.days_ahead, days_back=config.days_back
    ).window()
    result = gcal.sync(
        matches,
        calendar_id=config.google_calendar_id,
        time_min=matcher_window[0],
        time_max=matcher_window[1],
        reminder_minutes=config.reminder_minutes,
        event_prefix=config.event_prefix,
        prune=not args.no_prune,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(f"[dry run] would create {result.created} events")
    else:
        print(f"Synced to {config.google_calendar_id}: {result}")
    return 0


def cmd_serve(args: argparse.Namespace, config: Config) -> int:
    from .serve import serve

    serve(config, host=args.host, port=args.port, refresh_minutes=args.refresh_minutes)
    return 0


def cmd_discover(args: argparse.Namespace, config: Config) -> int:
    found = discover(_load_programmes(config), known=config.shows, min_occurrences=args.min_count)
    if not found:
        print("Nothing new found. Every football-looking recurring show is already matched.")
        return 0

    print("Recurring football shows that are NOT in your config yet:\n")
    print(f"{'airings':>7}  {'title':<52} example channel")
    for title, count, channel in found:
        print(f"{count:>7}  {title[:52]:<52} {channel[:30]}")
    print("\nAdd one to config.toml with:\n")
    print('[[shows]]\nname = "Some Show"\npattern = "^some show\\\\b"')
    return 0


def cmd_channels(args: argparse.Namespace, config: Config) -> int:
    needle = (args.grep or "").lower()
    rows: list[tuple[str, str, str]] = []
    for spec in config.sources:
        spec = {"max_age": config.cache_seconds, **spec}
        try:
            source = build_source(spec)
        except ValueError as exc:
            log.error("skipping source: %s", exc)
            continue
        try:
            for _ in source.load():
                pass  # channels are populated as the document streams past
        except Exception as exc:
            log.error("source %s failed: %s", source.name, exc)
        for channel in source.channels.values():
            haystack = " ".join(channel.aliases()).lower()
            if not needle or needle in haystack:
                rows.append((source.name, channel.id, channel.display))

    if not rows:
        print("No channels matched.")
        return 0
    for source_name, channel_id, display in sorted(rows):
        print(f"{source_name:<10} {channel_id:<44} {display}")
    print(f"\n{len(rows)} channels")
    return 0


def cmd_shows(args: argparse.Namespace, config: Config) -> int:
    by_group: dict[str, list[str]] = {}
    for rule in config.shows:
        by_group.setdefault(rule.group, []).append(rule.name)
    for group in sorted(by_group):
        print(f"\n[{group}]")
        for name in sorted(by_group[group]):
            print(f"  {name}")
    print(f"\n{len(config.shows)} show rules in {len(by_group)} groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
