"""Built-in catalogue of football magazine / analysis shows.

Rules are grouped by broadcaster so they can be enabled or disabled wholesale
from the config (`groups = ["bbc", "sky", "cz"]`). Every regex is matched
case-insensitively against the programme title (and, when `match_subtitle` is
set, against "Title: Subtitle").

`channels` is a list of case-insensitive glob patterns tested against the
channel id and every display name the source advertises. It is a filter, not a
requirement: an empty list means "any channel", which is what you want for
syndicated shows that turn up on a different channel in every country.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ShowRule:
    name: str
    pattern: str
    group: str = "custom"
    channels: list[str] = field(default_factory=list)
    exclude: str = ""
    match_subtitle: bool = False
    min_minutes: int = 0

    @property
    def rule_id(self) -> str:
        return f"{self.group}/{self.name}"


# --- BBC -------------------------------------------------------------------
BBC = [
    ShowRule(
        "Match of the Day",
        r"^match of the day(?!\s*(?:2|kickabout|top\s*10|:?\s*top\s*10))",
        "bbc",
        channels=["*bbc*"],
    ),
    ShowRule("Match of the Day 2", r"^match of the day\s*2\b", "bbc", channels=["*bbc*"]),
    ShowRule("MOTDx", r"^motdx\b|^match of the day:?\s*motdx", "bbc", channels=["*bbc*"]),
    ShowRule("Football Focus", r"^football focus\b", "bbc", channels=["*bbc*"]),
    ShowRule("Final Score", r"^final score\b", "bbc", channels=["*bbc*"]),
    ShowRule(
        "The Women's Football Show",
        r"women'?s football show",
        "bbc",
        channels=["*bbc*"],
    ),
    ShowRule("Match of the Day: Top 10", r"^match of the day:?\s*top\s*10", "bbc"),
    ShowRule("Scotland's Football Show", r"scotland'?s football show", "bbc"),
]

# --- Sky Sports (UK) -------------------------------------------------------
SKY = [
    ShowRule("Soccer Saturday", r"^(?:gillette\s+)?soccer saturday\b", "sky"),
    ShowRule("Monday Night Football", r"^monday night football\b", "sky"),
    ShowRule("The Football Show", r"^the football show\b", "sky"),
    ShowRule("Sunday Supplement", r"^sunday supplement\b", "sky"),
    ShowRule("Saturday Social", r"^(?:sky sports )?saturday social\b", "sky"),
    ShowRule("Sky Sports Football Gold", r"^football gold\b", "sky"),
    ShowRule("The Overlap", r"^the overlap\b", "sky"),
]

# --- TNT Sports (UK, ex BT Sport) -----------------------------------------
TNT = [
    ShowRule("Football Tonight", r"^football tonight\b", "tnt"),
    ShowRule("Early Kick Off", r"^early kick[\s-]?off\b", "tnt"),
    ShowRule("Champions League Goals Show", r"champions league goals show", "tnt"),
    ShowRule("Serie A: Full Impact", r"^serie a:?\s*full impact", "tnt"),
    ShowRule("Ligue 1 Show", r"^ligue 1 show\b", "tnt"),
    ShowRule("Bundesliga Show", r"^bundesliga (?:show|weekly)\b", "tnt"),
]

# --- CBS Sports / Golazo (US) ---------------------------------------------
CBS = [
    ShowRule("Morning Footy", r"^morning foot(?:y|ie)\b", "cbs"),
    ShowRule("Champions League Today", r"^(?:uefa\s+)?champions league today\b", "cbs"),
    ShowRule("Scoreline", r"^scoreline\b", "cbs"),
    ShowRule("Kickin' It", r"^kickin'?\s*it\b", "cbs"),
    ShowRule("Attacking Third", r"^attacking third\b", "cbs"),
    ShowRule("Golazo Matchday", r"^(?:que\s+)?golazo\b", "cbs"),
    ShowRule("Call It What You Want", r"^call it what you want\b", "cbs"),
]

# --- NBC / USA Network (Premier League US) --------------------------------
NBC = [
    ShowRule("Premier League Goal Zone", r"premier league goal\s?zone", "nbc"),
    ShowRule("Premier League Live", r"^premier league live\b", "nbc"),
    ShowRule("Premier League Mornings Live", r"^premier league mornings\b", "nbc"),
    ShowRule("The 2 Robbies", r"^the (?:2|two) robbies\b", "nbc"),
]

# --- ESPN / Fox (US) -------------------------------------------------------
ESPN_FOX = [
    ShowRule("ESPN FC", r"^espn\s?fc\b", "espn"),
    ShowRule("Futbol Americas", r"^f[uú]tbol americas\b", "espn"),
    ShowRule("Fox Soccer Tonight", r"^fox (?:soccer|football) (?:tonight|now)\b", "fox"),
    ShowRule("World Cup Tonight", r"world cup (?:tonight|now|today)\b", "fox"),
    ShowRule("Fox Soccer Extra", r"^fox soccer extra\b", "fox"),
]

# --- Premier League Productions world feed (carried almost everywhere) -----
PLP = [
    ShowRule("Premier League World", r"^premier league world\b", "plp"),
    ShowRule("Premier League Preview", r"^premier league preview\b", "plp"),
    ShowRule("Premier League Review", r"^premier league review\b", "plp"),
    ShowRule("Premier League Match Pack", r"^premier league match\s?pack\b", "plp"),
    ShowRule("Netbusters", r"^netbusters\b", "plp"),
    ShowRule("Premier League Stories", r"^premier league stories\b", "plp"),
]

# --- Czech / Slovak --------------------------------------------------------
CZ = [
    ShowRule("Tiki-Taka", r"^tiki[\s-]?taka\b", "cz"),
    ShowRule("Studio fotbal", r"^studio fotbal\b", "cz"),
    ShowRule("Fotbalový magazín", r"fotbalov[yý] magaz[ií]n", "cz"),
    ShowRule("Liga naruby", r"^liga naruby\b", "cz"),
    ShowRule("Gólové momenty", r"^g[oó]lov[eé] momenty\b", "cz"),
]

GROUPS: dict[str, list[ShowRule]] = {
    "bbc": BBC,
    "sky": SKY,
    "tnt": TNT,
    "cbs": CBS,
    "nbc": NBC,
    "espn": [rule for rule in ESPN_FOX if rule.group == "espn"],
    "fox": [rule for rule in ESPN_FOX if rule.group == "fox"],
    "plp": PLP,
    "cz": CZ,
}

DEFAULT_GROUPS = list(GROUPS)


def builtin_rules(groups: list[str] | None = None) -> list[ShowRule]:
    """Return the catalogue rules for the named groups (all groups by default)."""
    selected = groups if groups is not None else DEFAULT_GROUPS
    rules: list[ShowRule] = []
    for group in selected:
        key = group.lower()
        if key not in GROUPS:
            known = ", ".join(sorted(GROUPS))
            raise ValueError(f"unknown show group {group!r}; known groups: {known}")
        rules.extend(GROUPS[key])
    return rules


# Keywords used by `footballtv discover` to surface magazine-style shows that
# are not in the catalogue yet. Deliberately broad — discovery is a research
# aid, not a matcher.
DISCOVERY_KEYWORDS = [
    "football",
    "soccer",
    "fotbal",
    "futbol",
    "fútbol",
    "premier league",
    "champions league",
    "europa league",
    "la liga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "eredivisie",
    "efl",
    "mls",
]

DISCOVERY_FORMAT_HINTS = [
    "magazine",
    "magazín",
    "show",
    "review",
    "preview",
    "highlights",
    "round-up",
    "roundup",
    "weekly",
    "tonight",
    "today",
    "daily",
    "talk",
    "debate",
    "analysis",
    "studio",
    "extra",
    "focus",
    "verdict",
    "matchday",
    "goals",
]
