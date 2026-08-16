# Tivi Web

TiviMate-style webový IPTV přehrávač pro **m3u playlisty** a **XMLTV EPG**.
Běží v Dockeru na localhostu, ovládá se z prohlížeče a nahrazuje kostrbaté VLC.

![port 8098](https://img.shields.io/badge/port-8098-3ea6ff)

## Spuštění

```bash
cd iptv-player
docker compose up -d --build
```

Otevři **http://localhost:8098**. Předvyplněný je playlist a EPG z BCU Media,
takže hned po startu naskočí seznam kanálů.

Bez Dockeru: `npm install && npm start`.

## Co to umí

**Seznam kanálů**
- Logo, číslo kanálu, právě běžící pořad a proužek postupu — jako v TiviMate
- Skupiny z `group-title` jako klikací štítky, oblíbené kanály (uloží se do prohlížeče)
- Okamžité vyhledávání kanálu
- Seznam je virtualizovaný — plynulý i u playlistů s tisíci kanály

**Hledání pořadu napříč stanicemi**

Nemusíš vědět, na které stanici co běží. Napiš do vyhledávacího pole třeba
`arsenal` a pod kanály se vypíše sekce **V programu** — všechny pořady, které
ten výraz mají v názvu nebo popisu, napříč všemi kanály:

```
V PROGRAMU · 3
ŽIVĚ    Arsenal FC - Manchester City      Nova Sport 1 Czech HD
Dnes    Studio fotbal: Arsenal            ČT Sport
18:40
Zítra   Sestřihy Premier League           Nova Sport 2 Czech HD
20:40
```

Řadí se podle času, ukazuje se jen to, co **právě běží nebo teprve bude** —
skončené pořady se nevypisují. Kliknutím se otevře detail s popisem a
tlačítkem pro přepnutí na daný kanál.

Totéž funguje i v TV průvodci (`G`), kde je na výsledky víc místa.

**EPG**
- TV průvodce s časovou osou, blok pro každý pořad, červená linka „teď"
- Vyhledávání pořadu napříč celým EPG (viz výše), včetně dnů dopředu
- Detail pořadu s popisem a přepnutím na kanál
- Volba dne (včera až +6 dní)

**Přehrávání**
- HLS přes hls.js, adaptivní kvalita, na Safari nativně
- Přehrát / pozastavit, zastavit, a tlačítko **ŽIVĚ** pro skok na živou hranu —
  když se pauzou nebo zaseknutím opozdíš, tlačítko zčervená a jedním klepnutím
  tě vrátí do přímého přenosu
- Hlasitost, ztlumení, obraz v obraze, celá obrazovka
- Info lišta s kanálem, pořadem, průběhem a „Pak:" následujícím pořadem

**Ovládání klávesnicí**

| Klávesa | Akce |
|---|---|
| `/` | vyhledávání |
| `G` | TV průvodce |
| `↑` `↓` | pohyb v seznamu, `Enter` přehrát |
| `PgUp` `PgDn` | skok po 10 kanálech |
| `mezerník` | přehrát / pozastavit |
| `S` | zastavit |
| `L` | skok na živé vysílání |
| `F` | celá obrazovka |
| `M` | ztlumit |
| `P` | obraz v obraze |
| `I` | info lišta |
| `Esc` | zavřít / skrýt seznam |

**Na telefonu**

Video nahoře v poměru 16:9 (žádné černé pruhy navíc), seznam pod ním.
Klepnutí na obraz vyvolá info lištu, dvojklik přepne na celou obrazovku.
Dlouhé názvy pořadů se zalamují do dvou řádků místo oříznutí.
TV průvodce má na telefonu hustší časovou osu, takže je vidět zhruba
hodina a půl programu místo tři čtvrtě hodiny.

## Konfigurace přes .env

Zkopíruj `.env.example` jako `.env` — `docker compose` ho načte sám:

```bash
cp .env.example .env
# uprav, pak:
docker compose up -d
```

```env
PLAYLIST_1_NAME=BCU Media
PLAYLIST_1_URL=https://bcumedia.su/playlist/hls/ucbaaspl8i.m3u
PLAYLIST_1_GROUPS=Sport*, Czech*, !18+

EPG_1_URL=https://epg.bcumedia.pro/epg.xml
FAVORITES_NAME=Moje oblíbené
```

**Výběr skupin** dělá `PLAYLIST_<n>_GROUPS`. Když ho vynecháš, zobrazí se
všechny. Jinak platí:

| Zápis | Význam |
|---|---|
| `Sport` | přesně tato skupina (nezáleží na velikosti písmen) |
| `Nova*` | vše, co začíná na „Nova" |
| `!18+` | tuhle skupinu vyloučit |

Uvedené se kombinuje — `Sport*, Czech*, !18+` znamená „sportovní a české
skupiny, ale nic z 18+". Názvy skupin uvidíš jako štítky nad seznamem kanálů.

`FAVORITES_NAME` pojmenuje kategorii oblíbených; bez něj se jmenuje
„Oblíbené". Jde nastavit i v GUI.

`.env` je v `.gitignore`, protože playlist URL bývá osobní.

## Vystavení na vlastní doménu (Cloudflare Tunnel)

Compose obsahuje službu `cloudflared`, která přehrávač vystrčí na
`https://tv.toobab.net` — **bez otevírání portů na routeru**, protože tunel se
připojuje ven.

1. [Cloudflare Zero Trust](https://one.dash.cloudflare.com) → **Networks → Tunnels
   → Create a tunnel** → typ *Cloudflared*, pojmenuj třeba `tivi`.
2. Zkopíruj token z instalačního příkazu (dlouhý řetězec za `--token`).
3. V tunelu **Public Hostname → Add**:
   - Subdomain `tv`, Domain `toobab.net`
   - Service **HTTP**, URL `tivi-web:8098`

   DNS záznam vytvoří Cloudflare sám. `tivi-web` je název služby v compose,
   takže se cloudflared dostane k přehrávači po interní síti Dockeru.
4. Do `.env`:

   ```env
   COMPOSE_PROFILES=tunnel
   CLOUDFLARE_TUNNEL_TOKEN=token_z_dashboardu
   ```

5. `docker compose up -d`

Bez `COMPOSE_PROFILES=tunnel` se cloudflared nespustí, takže běžné lokální
použití zůstává beze změny.

### Než to pustíš do světa

Přehrávač **nemá vlastní přihlašování**. Na veřejné doméně by se k tvému IPTV
předplatnému dostal kdokoli, kdo adresu uhodne. Zamkni to v Cloudflare:
**Access → Applications → Add an application → Self-hosted**, doména
`tv.toobab.net`, a jako pravidlo dej svůj e-mail (jednorázový kód do mailu).
Ve free tarifu to jde pro 50 uživatelů.

Server zároveň **odmítá stahovat z adres ve tvé lokální síti** — jinak by
`/stream?url=…` po vystavení fungoval jako otevřená proxy do domácí sítě
(router, NAS, cloud metadata). Kontroluje se i každé přesměrování, aby veřejná
adresa nemohla přesměrovat na privátní. Když máš playlist na privátní adrese,
povol `ALLOW_PRIVATE_UPSTREAM=true` — ale pak raději bez veřejného tunelu.

## Vlastní playlisty a EPG z GUI

Ozubené kolečko vpravo nahoře. Jeden zdroj na řádek, ve stejném tvaru:

```
Moje IPTV | http://neco/playlist.m3u | Sport*, !18+
http://jine/playlist.m3u
```

Více playlistů se sloučí do jednoho seznamu, více EPG zdrojů taky.
Jakmile v GUI něco uložíš, má přednost před `.env`; tlačítkem
**Načíst z .env** se vrátíš zpět k souboru.
EPG se páruje na kanály přes `tvg-id`, a když ten chybí, podle názvu kanálu
(ignoruje se `HD`/`4K` a podobné přípony). Podporuje i gzipované `.xml.gz`.

## Jak to funguje

Node.js server dělá tři věci:

- `/api/playlist?url=…` — stáhne a rozparsuje m3u na JSON (cache 5 min)
- `/api/epg?url=…` — rozparsuje XMLTV, ořízne na okno −12 h až +48 h a vrátí
  jen to podstatné, takže se do prohlížeče nesype několikasetmegový XML (cache 30 min)
- `/stream?url=…` — proxy pro streamy; přepisuje URL v HLS manifestech, takže
  prohlížeč nenarazí na CORS, a posílá `User-Agent`, který poskytovatelé čekají

Proxy jde v nastavení vypnout, pokud tvůj poskytovatel CORS řeší sám.

Frontend je čisté ES moduly bez build kroku — žádný bundler, žádný `node_modules`
v prohlížeči, načte se okamžitě.

## Konfigurace

| Proměnná | Výchozí | Popis |
|---|---|---|
| `PORT` | `8098` | port serveru |
| `UPSTREAM_UA` | `VLC/3.0.20 LibVLC/3.0.20` | User-Agent posílaný poskytovateli |

## Poznámky

- Playlist ani EPG se nikam neukládají na disk, jen do paměti procesu.
- Oblíbené, poslední kanál a nastavení jsou v `localStorage` prohlížeče.
- Když se stream nerozjede, zkus v nastavení přepnout proxy — někteří
  poskytovatelé vyžadují přímé spojení, jiní naopak bez proxy neprojdou přes CORS.
