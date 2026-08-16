"""Idempotent Google Calendar sync using the REST API directly.

No google-api-python-client dependency: the whole integration is three
endpoints and stdlib `urllib` handles them, which keeps the tool a single
`pip install`-free script.

Every event this tool writes is tagged with the private extended property
`footballtv=1`, so a sync only ever touches its own events and never disturbs
anything else in the calendar.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Iterable

from .models import Match

log = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/calendar.events"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/calendar/v3"
TAG_KEY = "footballtv"

CONFIG_DIR = Path(
    os.environ.get("FOOTBALLTV_CONFIG_DIR")
    or Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "footballtv"
)
TOKEN_FILE = CONFIG_DIR / "google_token.json"
CLIENT_FILE = CONFIG_DIR / "google_client.json"


class GoogleAuthError(RuntimeError):
    pass


@dataclass(slots=True)
class SyncResult:
    created: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0

    def __str__(self) -> str:
        return (
            f"created {self.created}, updated {self.updated}, "
            f"deleted {self.deleted}, unchanged {self.unchanged}"
        )


# --- OAuth ------------------------------------------------------------------


def _client_credentials() -> tuple[str, str]:
    """Read the OAuth client from the environment or the config directory."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if client_id and client_secret:
        return client_id, client_secret

    if CLIENT_FILE.exists():
        data = json.loads(CLIENT_FILE.read_text())
        block = data.get("installed") or data.get("web") or data
        if block.get("client_id") and block.get("client_secret"):
            return block["client_id"], block["client_secret"]

    raise GoogleAuthError(
        "No Google OAuth client found. Create a Desktop OAuth client in the Google "
        f"Cloud Console, then save it to {CLIENT_FILE} or set GOOGLE_CLIENT_ID and "
        "GOOGLE_CLIENT_SECRET."
    )


def _post_form(url: str, fields: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise GoogleAuthError(f"token request failed ({exc.code}): {detail}") from exc


class _CallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None
    state: str = ""

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ok = params.get("state", [""])[0] == type(self).state and "code" in params
        if ok:
            type(self).code = params["code"][0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        message = (
            "<h2>footballtv is connected.</h2><p>You can close this tab.</p>"
            if ok
            else "<h2>Authorisation failed.</h2><p>Please run the command again.</p>"
        )
        self.wfile.write(message.encode())

    def log_message(self, *args: object) -> None:
        """Silence the default stderr access log."""


def _interactive_login() -> dict:
    client_id, client_secret = _client_credentials()
    state = secrets.token_urlsafe(16)
    _CallbackHandler.state = state
    _CallbackHandler.code = None

    server = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    print("Open this URL to authorise footballtv:\n", url, "\n", flush=True)
    try:
        webbrowser.open(url)
    except Exception:  # pragma: no cover - headless machines
        pass

    server.handle_request()
    server.server_close()
    if not _CallbackHandler.code:
        raise GoogleAuthError("authorisation was not completed")

    tokens = _post_form(
        TOKEN_URL,
        {
            "code": _CallbackHandler.code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if "refresh_token" not in tokens:
        raise GoogleAuthError("Google did not return a refresh token; revoke access and retry")
    return tokens


def _access_token() -> str:
    """Return a usable access token, refreshing or authorising as needed."""
    client_id, client_secret = _client_credentials()

    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
    if not refresh_token and TOKEN_FILE.exists():
        refresh_token = json.loads(TOKEN_FILE.read_text()).get("refresh_token", "")

    if not refresh_token:
        tokens = _interactive_login()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(json.dumps({"refresh_token": tokens["refresh_token"]}, indent=2))
        TOKEN_FILE.chmod(0o600)
        return tokens["access_token"]

    tokens = _post_form(
        TOKEN_URL,
        {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        },
    )
    return tokens["access_token"]


# --- API --------------------------------------------------------------------


def _api(method: str, path: str, token: str, *, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    return json.loads(payload) if payload else {}


def _event_id(match: Match) -> str:
    """Google event ids must be base32hex; a sha1 hex digest already is."""
    return f"ftv{match.uid}"


def _rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_body(match: Match, reminder_minutes: int, event_prefix: str) -> dict:
    programme = match.programme
    summary = f"{event_prefix}{match.show}" if event_prefix else match.show
    if programme.subtitle and programme.subtitle.lower() not in match.show.lower():
        summary = f"{summary} — {programme.subtitle}"

    description = "\n".join(
        part
        for part in (
            programme.description,
            f"Channel: {programme.channel_name or programme.channel_id}",
            f"Original title: {programme.title}" if programme.title != match.show else "",
            programme.url,
            f"Source: {programme.source}",
        )
        if part
    )

    body: dict = {
        "id": _event_id(match),
        "summary": summary,
        "description": description,
        "location": programme.channel_name or programme.channel_id,
        "start": {"dateTime": _rfc3339(programme.start), "timeZone": "UTC"},
        "end": {"dateTime": _rfc3339(programme.end), "timeZone": "UTC"},
        "transparency": "transparent",
        "extendedProperties": {"private": {TAG_KEY: "1", "show": match.show}},
    }
    if reminder_minutes > 0:
        body["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes}],
        }
    else:
        body["reminders"] = {"useDefault": False, "overrides": []}
    return body


def _existing_events(token: str, calendar_id: str, time_min: datetime, time_max: datetime) -> dict:
    """All events previously written by this tool inside the window."""
    events: dict[str, dict] = {}
    page_token = ""
    quoted = urllib.parse.quote(calendar_id, safe="")
    while True:
        query = urllib.parse.urlencode(
            {
                "privateExtendedProperty": f"{TAG_KEY}=1",
                "timeMin": _rfc3339(time_min),
                "timeMax": _rfc3339(time_max),
                "singleEvents": "true",
                "maxResults": "2500",
                "showDeleted": "false",
                **({"pageToken": page_token} if page_token else {}),
            }
        )
        payload = _api("GET", f"/calendars/{quoted}/events?{query}", token)
        for event in payload.get("items", []):
            if event.get("id"):
                events[event["id"]] = event
        page_token = payload.get("nextPageToken", "")
        if not page_token:
            return events


def _needs_update(existing: dict, desired: dict) -> bool:
    if existing.get("summary") != desired["summary"]:
        return True
    if (existing.get("description") or "") != (desired["description"] or ""):
        return True
    for edge in ("start", "end"):
        current = (existing.get(edge) or {}).get("dateTime", "")
        if not current:
            return True
        if _normalise(current) != _normalise(desired[edge]["dateTime"]):
            return True
    return False


def _normalise(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return value


def sync(
    matches: Iterable[Match],
    *,
    calendar_id: str = "primary",
    time_min: datetime,
    time_max: datetime,
    reminder_minutes: int = 15,
    event_prefix: str = "",
    prune: bool = True,
    dry_run: bool = False,
) -> SyncResult:
    """Make the calendar match `matches` exactly, within the given window."""
    desired = {
        _event_id(match): _event_body(match, reminder_minutes, event_prefix) for match in matches
    }
    result = SyncResult()

    if dry_run:
        result.created = len(desired)
        return result

    token = _access_token()
    quoted = urllib.parse.quote(calendar_id, safe="")
    existing = _existing_events(token, calendar_id, time_min, time_max)

    for event_id, body in desired.items():
        current = existing.get(event_id)
        if current is None:
            try:
                _api("POST", f"/calendars/{quoted}/events", token, body=body)
                result.created += 1
            except urllib.error.HTTPError as exc:
                if exc.code != 409:  # already exists (possibly outside the window)
                    raise
                _api("PUT", f"/calendars/{quoted}/events/{event_id}", token, body=body)
                result.updated += 1
        elif _needs_update(current, body):
            _api("PUT", f"/calendars/{quoted}/events/{event_id}", token, body=body)
            result.updated += 1
        else:
            result.unchanged += 1

    if prune:
        for event_id in existing.keys() - desired.keys():
            try:
                _api("DELETE", f"/calendars/{quoted}/events/{event_id}", token)
                result.deleted += 1
            except urllib.error.HTTPError as exc:
                if exc.code not in (404, 410):
                    raise

    return result
