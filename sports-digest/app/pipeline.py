"""Orchestrates one digest run: fetch sources -> build match summaries -> LLM -> Telegram."""
from __future__ import annotations

import logging

from .config import LeagueConfig, Settings, YamlConfig
from .llm.anthropic_backend import AnthropicBackend
from .llm.base import LLMBackend
from .llm.ollama_backend import OllamaBackend
from .notify.telegram import send_message
from .sources.base import NewsItem
from .sources.football_api import FootballDataClient
from .sources.rss import fetch_rss_items
from .sources.scrape import fetch_scrape_items

logger = logging.getLogger(__name__)


def build_llm_backend(settings: Settings) -> LLMBackend:
    if settings.llm_provider == "anthropic":
        return AnthropicBackend(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    return OllamaBackend(base_url=settings.ollama_base_url, model=settings.ollama_model)


def _collect_news(league: LeagueConfig, max_age_hours: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    for feed_url in league.rss_feeds:
        # One bad feed shouldn't stop the others.
        try:
            items.extend(fetch_rss_items(feed_url, max_age_hours, source_label=feed_url))
        except Exception:
            logger.exception("Unexpected error fetching RSS feed %s", feed_url)

    for target in league.scrape_targets:
        try:
            items.extend(fetch_scrape_items(target))
        except Exception:
            logger.exception("Unexpected error scraping target %s", target.name)

    return items


def _news_for_team(team_name: str, news_items: list[NewsItem]) -> list[str]:
    """Best-effort substring match of team name against headlines.

    Deliberately naive: full name-alias resolution (e.g. "Man United" vs
    "Manchester United") is out of scope for this initial version.
    """
    name_lower = team_name.lower()
    # Also try the last word (common short form, e.g. "Arsenal" from "Arsenal FC").
    short = name_lower.split()[-1] if name_lower.split() else name_lower
    matched = []
    for item in news_items:
        title_lower = item.title.lower()
        if name_lower in title_lower or short in title_lower:
            matched.append(item.title)
    return matched[:5]


def _form_summary(matches: list[dict], team_id: int) -> str:
    """Compact W/D/L string for a team's recent finished matches, most recent first."""
    results = []
    for m in matches:
        score = m.get("score", {}).get("fullTime", {})
        home_id = m.get("homeTeam", {}).get("id")
        home_goals, away_goals = score.get("home"), score.get("away")
        if home_goals is None or away_goals is None:
            continue
        if home_goals == away_goals:
            results.append("D")
        elif (home_id == team_id) == (home_goals > away_goals):
            results.append("W")
        else:
            results.append("L")
    return "".join(results)


def _standings_lookup(standings: list[dict]) -> dict[int, dict]:
    return {row["team"]["id"]: row for row in standings if row.get("team", {}).get("id") is not None}


def build_match_contexts(league: LeagueConfig, football: FootballDataClient, news_items: list[NewsItem]) -> list[dict]:
    fixtures = football.upcoming_matches(league.competition_code, lookahead_days=7)
    if not fixtures:
        return []

    standings = football.standings(league.competition_code)
    standings_by_team = _standings_lookup(standings)

    contexts: list[dict] = []
    for match in fixtures:
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        home_id, away_id = home.get("id"), away.get("id")
        home_name, away_name = home.get("name", "?"), away.get("name", "?")

        home_standing = standings_by_team.get(home_id, {})
        away_standing = standings_by_team.get(away_id, {})

        home_form = _form_summary(football.recent_form(home_id), home_id) if home_id else ""
        away_form = _form_summary(football.recent_form(away_id), away_id) if away_id else ""

        h2h = football.head_to_head(match.get("id")) if match.get("id") else []

        context = {
            "competition": league.name,
            "kickoff_utc": match.get("utcDate"),
            "home_team": home_name,
            "away_team": away_name,
            "home_position": home_standing.get("position"),
            "away_position": away_standing.get("position"),
            "home_points": home_standing.get("points"),
            "away_points": away_standing.get("points"),
            "home_recent_form": home_form,
            "away_recent_form": away_form,
            "head_to_head_count": len(h2h),
            "home_team_news": _news_for_team(home_name, news_items),
            "away_team_news": _news_for_team(away_name, news_items),
        }
        contexts.append(context)

    return contexts


def run_pipeline(settings: Settings, config: YamlConfig) -> dict:
    """Runs the full pipeline once. Returns a small result summary for logging/API responses."""
    football = FootballDataClient(settings.football_data_api_token)
    all_contexts: list[dict] = []

    try:
        for league in config.leagues:
            try:
                news_items = _collect_news(league, config.news_max_age_hours)
                league_contexts = build_match_contexts(league, football, news_items)
                all_contexts.extend(league_contexts)
            except Exception:
                # A failure in one league must not abort the whole run.
                logger.exception("Failed to process league %s", league.name)
    finally:
        football.close()

    if not all_contexts:
        logger.info("Pipeline run produced no match data - skipping digest/telegram send")
        return {"status": "skipped", "reason": "no data fetched", "matches": 0}

    llm = build_llm_backend(settings)
    try:
        digest_text = llm.summarize(all_contexts)
    except Exception:
        logger.exception("LLM summarization failed")
        return {"status": "error", "reason": "llm failure", "matches": len(all_contexts)}

    if not digest_text:
        logger.warning("LLM returned an empty digest - not sending to Telegram")
        return {"status": "skipped", "reason": "empty digest", "matches": len(all_contexts)}

    sent = send_message(settings.telegram_bot_token or "", settings.telegram_chat_id or "", digest_text)

    return {
        "status": "ok" if sent else "error",
        "matches": len(all_contexts),
        "digest_preview": digest_text[:200],
        "telegram_sent": sent,
    }
