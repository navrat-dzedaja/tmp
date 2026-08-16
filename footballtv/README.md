# footballtv ⚽

Najde fotbalové magazíny a analytické pořady v TV programech (EPG) a automaticky
je nasype do kalendáře — Proton Calendar, Google Calendar, Apple Calendar na
macOS/iOS i libovolný kalendář na Androidu.

Hledá věci jako **Match of the Day** (BBC), **Tiki-Taka** (Oneplay Sport),
**Soccer Saturday** a **Monday Night Football** (Sky Sports), **Morning Footy**
a **Champions League Today** (CBS Golazo), **ESPN FC**, **Fox Soccer Tonight**,
**Premier League Goal Zone** (NBC/USA) a další — celkem 48 pořadů v 9 skupinách.

Bez závislostí: čistá Python 3.11+ standardní knihovna, žádné `pip install`.

---

## Rychlý start

```bash
cd footballtv
cp config.example.toml config.toml     # volitelné, funguje i bez toho

python -m footballtv list               # co poběží příští 2 týdny
python -m footballtv ics -o football.ics   # vyrobí kalendář
```

Import `football.ics` do Proton Calendar / Google Calendar / Kalendář na macOS
a hotovo. Pro **automatickou** aktualizaci pokračuj sekcí
[Napojení na kalendář](#napojení-na-kalendář).

---

## Odkud bere data

Zdrojem je **XMLTV** — společný formát TV programů, kterým mluví epgshare01,
epg.pw, [iptv-org/epg](https://github.com/iptv-org/epg), WebGrab+Plus,
Tvheadend i Jellyfin. Ve výchozím stavu se stahují čtyři veřejné feedy:

| Zdroj | Pokrývá |
|---|---|
| `epg_ripper_UK1.xml.gz` | BBC One/Two/Three/Four, Sky Sports, TNT Sports, ITV |
| `epg_ripper_US1.xml.gz` | CBS, NBC, USA Network, FOX |
| `epg_ripper_US_SPORTS1.xml.gz` | CBS Sports Network, FS1, ESPN, Golazo |
| `epg_ripper_CZ1.xml.gz` | Oneplay Sport 1–4, ČT Sport, Nova Sport |

Nepotřebné zdroje smaž z configu — jsou to velké soubory (UK feed má přes
100 MB rozbalený). Stažené soubory se cachují (výchozí 6 hodin).

Přidat jde cokoliv dalšího:

```toml
[[sources]]
name = "lokalni"
type = "xmltv"
path = "./guide.xml"        # soubor z jakéhokoli grabberu, i .gz
```

```toml
[[sources]]
name = "bbc"
type = "bbc"                # vlastní JSON rozvrh BBC — lepší popisky epizod
```

Když je potřeba kanál, který ve veřejných feedech není, vygeneruj si vlastní
XMLTV grabberem iptv-org (má přes 100 zdrojů včetně `sky.com`,
`tvpassport.com`, `m.tv.sms.cz`) a připoj ho jako `path`.

---

## Příkazy

```bash
python -m footballtv list                  # výpis pořadů po dnech
python -m footballtv list --show "match of the day"
python -m footballtv list --group cz       # jen české pořady

python -m footballtv ics -o football.ics   # .ics soubor
python -m footballtv serve --port 8777     # servíruje .ics přes HTTP
python -m footballtv sync-google           # zápis přímo do Google Calendar

python -m footballtv discover              # najde magazíny, které ještě nemáš
python -m footballtv channels --grep sky   # vypíše ID kanálů ve feedech
python -m footballtv shows                 # vypíše nakonfigurovaná pravidla
```

Globální přepínače: `--days 30`, `--days-back 7`, `--timezone Europe/Prague`,
`--source cz` (jen vybraný zdroj), `--no-cache`, `--include-repeats`, `-v`.

### `discover` — jak si rozšířit katalog

Katalog nikdy nebude úplný. `discover` projde EPG, vyhodí pořady, které už
matchuješ, a ukáže opakující se relace, které vypadají jako fotbalový magazín
(zmiňují fotbal **a** mají v názvu formátové slovo jako *show*, *review*,
*tonight*, *magazín*). Živé zápasy typu „Arsenal v Chelsea“ filtruje pryč.

```
airings  title                                    example channel
      3  La Liga Weekly Show                      Sky Sports Football
      2  Bundesliga Highlights Show               ESPN
```

Co se hodí, se přidá do `config.toml`:

```toml
[[shows]]
name = "La Liga Weekly"
pattern = "^la liga weekly\\b"
channels = ["*sky sports*"]
```

---

## Napojení na kalendář

### Proton Calendar (doporučeno)

Proton neumí CalDAV ani nemá zapisovací API, ale umí **odebírat kalendář z
URL**. Potřebuješ tedy veřejně dostupný `.ics`, který se sám obnovuje — na to
je v repozitáři workflow `.github/workflows/calendar.yml`:

1. V repozitáři zapni **Settings → Pages → Source: GitHub Actions**.
2. Spusť workflow *Update football calendar* (běží pak sám 2× denně).
3. V Proton Calendar: **Other calendars → Add calendar from URL** a vlož
   `https://<uzivatel>.github.io/<repo>/football.ics`.

Proton si feed tahá zhruba jednou za 16 hodin, takže dvakrát denně generovaný
soubor je bohatě dost. Odebíraný kalendář je read-only — události se needitují
v Protonu, ale mění se samy, jak se mění TV program.

Bez GitHubu funguje stejně dobře jakýkoli veřejný hosting — `football.ics`
stačí nahrát kamkoli, kde je dosažitelný přes HTTPS.

### Google Calendar

Dvě možnosti. **Odběr z URL** je stejný postup jako u Protonu
(*Other calendars → From URL*). **Přímý zápis** přes API dá okamžitou
aktualizaci a plnou kontrolu:

```bash
# jednorázově: v Google Cloud Console vyrob OAuth klienta typu "Desktop app"
# a ulož stažený JSON do ~/.config/footballtv/google_client.json
python -m footballtv sync-google --dry-run          # nejdřív nasucho
python -m footballtv sync-google --calendar-id primary
```

Sync je **idempotentní**: každá událost má odvozené ID a privátní příznak
`footballtv=1`. Opakované spuštění tedy nic needuplikuje, změněné časy opraví a
zrušené pořady smaže (`--no-prune` to vypne). Cizích událostí se nikdy nedotkne.

Pro běh v CI přenes `refresh_token` do proměnných `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET` a `GOOGLE_REFRESH_TOKEN`.

### macOS / iOS

Kalendář → Soubor → Nový odběr kalendáře → vlož URL. Nebo lokálně:

```bash
python -m footballtv serve --port 8777
# → http://127.0.0.1:8777/football.ics
```

### Android

Odběr z URL nativní kalendář neumí; nejjednodušší je nechat synchronizaci na
Google Calendar (viz výše) a v telefonu jen zapnout zobrazení toho kalendáře.
Alternativa je aplikace typu ICSx⁵, která odběr z URL zvládne.

---

## Konfigurace

Kompletní okomentovaný vzor je v [`config.example.toml`](config.example.toml).
Nejdůležitější kousky:

```toml
[general]
days_ahead = 14
timezone = "Europe/Prague"
dedupe_window_hours = 6            # sloučí stejný díl na SD/HD/+1 kanálech
channel_blocklist = ["*+1*"]

[calendar]
name = "Fotbal v TV"
event_prefix = "⚽ "
reminder_minutes = 15              # 0 = bez upozornění

[show_catalogue]
groups = ["bbc", "sky", "cz"]      # jen tyto skupiny
```

Skupiny katalogu: `bbc`, `sky`, `tnt`, `cbs`, `nbc`, `espn`, `fox`, `plp`
(Premier League Productions), `cz`.

Vlastní pravidlo přebije stejnojmenné vestavěné, takže jde doladit jeden pořad
bez vypnutí celé skupiny:

```toml
[[shows]]
name = "Tiki-Taka"
pattern = "^tiki[\\s-]?taka\\b"
channels = ["*oneplay*", "*o2 tv sport*"]   # case-insensitive globy
exclude = "upoutávka"                        # co v názvu naopak nesmí být
match_subtitle = true                        # testovat i podtitul
min_minutes = 20                             # ignorovat krátké znělky
```

---

## Jak to uvnitř funguje

```
XMLTV / BBC JSON  →  Programme  →  Matcher  →  Match  →  ICS / Google Calendar
   (streamované)      (norm.)      (regex +     (dedup)
                                   kanály)
```

Několik věcí, které stojí za zmínku:

- **Streamované parsování.** XMLTV se čte přes `iterparse` a elementy se hned
  uvolňují, takže i stomegový feed jede v konstantní paměti.
- **Deduplikace.** Národní feedy uvádějí pořad zvlášť na SD, HD a +1 kanálu a
  zdroje se navíc překrývají. Bez toho by v kalendáři byly čtyři *Match of the
  Day* místo jednoho. Klíčem je podtitul epizody, a když chybí, tak den.
- **Stabilní UID.** `sha1(kanál|čas|název)` — stejné vysílání dostane při každém
  běhu stejné UID, takže reimport ani resync nic needuplikuje.
- **Odolnost.** Když jeden feed spadne, použije se starší cache a běh
  pokračuje ostatními zdroji. Rozbité položky v EPG se přeskakují, ne že by
  shodily celý běh.

## Testy

```bash
pip install pytest
python -m pytest -q      # 80 testů
```

Pokryté je parsování XMLTV (včetně poškozených dat a časových zón), katalog
pořadů, deduplikace, filtry kanálů, discovery heuristika, načítání configu,
generování ICS (escapování, skládání řádků na 75 oktetů, UTF-8) a sestavení
události pro Google Calendar. Výstupní `.ics` byl navíc ověřen proti knihovně
`icalendar`.

## Licence

MIT
