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

**EPG**
- TV průvodce s časovou osou, blok pro každý pořad, červená linka „teď"
- Vyhledávání pořadu napříč celým EPG (v názvu i popisu), včetně dnů dopředu
- Detail pořadu s popisem a přepnutím na kanál
- Volba dne (včera až +6 dní)

**Přehrávání**
- HLS přes hls.js, adaptivní kvalita, na Safari nativně
- Hlasitost, ztlumení, obraz v obraze, celá obrazovka
- Info lišta s kanálem, pořadem, průběhem a „Pak:" následujícím pořadem

**Ovládání klávesnicí**

| Klávesa | Akce |
|---|---|
| `/` | vyhledávání |
| `G` | TV průvodce |
| `↑` `↓` | pohyb v seznamu, `Enter` přehrát |
| `PgUp` `PgDn` | skok po 10 kanálech |
| `F` | celá obrazovka |
| `M` | ztlumit |
| `P` | obraz v obraze |
| `I` | info lišta |
| `Esc` | zavřít / skrýt seznam |

Rozhraní je responzivní — na mobilu je video nahoře a seznam pod ním.

## Vlastní playlisty a EPG

Ozubené kolečko vpravo nahoře. Zadává se jeden zdroj na řádek, volitelně
s vlastním názvem:

```
Moje IPTV | http://neco/playlist.m3u
http://jine/playlist.m3u
```

Více playlistů se sloučí do jednoho seznamu, více EPG zdrojů taky.
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
