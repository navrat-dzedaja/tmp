# sports-digest

A lightweight scheduled service that pulls upcoming football matches and news
from configurable sources, builds a compact factual summary per interesting
match, asks an LLM to write a short digest, and posts it to a Telegram chat.

## Features

- Pluggable sources: RSS feeds, generic CSS-selector web scraping, and the
  [football-data.org](https://www.football-data.org/) REST API (fixtures,
  standings, recent form, head-to-head).
- Sources and leagues are defined in `config.yaml` - no hardcoded teams.
- Runs on a cron schedule (APScheduler) and exposes a FastAPI app for
  health checks, manual triggering, and inspecting the loaded config.
- LLM backend is swappable: Anthropic Claude API or a local Ollama model.

## Setup

### 1. Get credentials

- **football-data.org API token**: sign up at
  https://www.football-data.org/client/register, the free tier is enough for
  a handful of top leagues. You get a token immediately by email.
- **Telegram bot token**: message [@BotFather](https://t.me/BotFather) on
  Telegram, run `/newbot`, follow the prompts, and copy the token it gives you.
- **Telegram chat ID**: message your new bot once (anything), then visit
  `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser - the
  JSON response contains `message.chat.id`. For a group chat, add the bot to
  the group first and send a message there instead.
- **Anthropic API key** (if using `LLM_PROVIDER=anthropic`): create one at
  https://console.anthropic.com/settings/keys.

### 2. Configure

```bash
cp .env.example .env
cp config.example.yaml config.yaml
```

Edit `.env` with your tokens and `config.yaml` with the leagues, RSS feeds,
and (optionally) scrape targets you want. `config.yaml` never contains
secrets - only structural configuration (competition codes, feed URLs,
CSS selectors, schedule).

Competition codes come from football-data.org, e.g. `PL` (Premier League),
`BL1` (Bundesliga), `PD` (La Liga), `SA` (Serie A), `FL1` (Ligue 1),
`CL` (Champions League).

### 3. Run

With Docker (recommended):

```bash
docker compose up --build
```

The API is then available at `http://localhost:8000`.

To also run a local Ollama instance in the same compose stack, set
`LLM_PROVIDER=ollama` in `.env` and start with the `ollama` profile:

```bash
docker compose --profile ollama up --build
```

Without Docker, using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run uvicorn app.main:app --reload
```

### 4. Test

```bash
curl http://localhost:8000/health

# Trigger the pipeline immediately (fetches sources, calls the LLM, sends to Telegram)
curl -X POST http://localhost:8000/run-now

# Inspect the loaded config (secrets are redacted)
curl http://localhost:8000/config
```

`POST /run-now` runs synchronously and returns a small JSON summary
(`status`, number of matches found, a digest preview, whether Telegram
sending succeeded). Check the container logs for full detail.

## Configuration reference

Environment variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `anthropic` or `ollama` |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Used when `LLM_PROVIDER=anthropic` |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Used when `LLM_PROVIDER=ollama` |
| `FOOTBALL_DATA_API_TOKEN` | football-data.org API token |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram Bot API credentials |
| `CONFIG_PATH` | Path to the YAML config, default `config.yaml` |
| `DIGEST_CRON` | Overrides `digest_cron` from `config.yaml` if set |

`config.yaml` fields: `timezone`, `digest_cron` (5-field cron expression),
`fixture_lookahead_days`, `news_max_age_hours`, and a `leagues` list, each
with `name`, `competition_code`, `rss_feeds`, and optional `scrape_targets`
(each with `url`, `item_selector`, `title_selector`, `link_selector`,
`link_attr`, `base_url`).

## Exposing it externally (optional)

The FastAPI app only needs to be reachable by you (for `/run-now` and
`/config`) - it doesn't need to be public. If you want to trigger it from
outside your home network without opening a port, a
[cloudflared](https://github.com/cloudflare/cloudflared) tunnel pointed at
`http://localhost:8000` works well and is free for a single hostname; this
is entirely optional and not required for the scheduled digest to run.

## Known limitations / TODOs

- **Team-name matching between news headlines and API team names is naive
  substring matching** (full name and last word only) - it will miss
  aliases like "Man United" for "Manchester United FC". Good enough for an
  initial version; a proper alias table or fuzzy matching would improve
  recall.
- "Interesting match" selection is implicit - all upcoming fixtures in the
  lookahead window are sent to the LLM with whatever context is available,
  and the LLM is instructed to skip anything not noteworthy rather than the
  pipeline pre-filtering matches itself.
- No persistence/dedup: if you trigger `/run-now` twice, you'll get two
  Telegram messages. Nothing tracks "already sent" state.
- The football-data.org free tier has a low rate limit (10 requests/minute)
  and limited historical head-to-head depth; large league lists may need
  request pacing if you hit 429s.
- Scraping selectors are brittle by nature - expect to update
  `config.yaml` when a target site changes its markup.
