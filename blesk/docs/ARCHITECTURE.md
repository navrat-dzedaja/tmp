# Architektura

## Cíle

- Přehrávač typu Stremio: katalogy filmů/seriálů + živá TV (IPTV), zdroje řeší addony.
- Co nejmenší a nejrychlejší: žádný přibalený prohlížeč, žádný těžký runtime.
- Všechny platformy: desktop (Win/mac/Linux), mobil (Android/iOS), TV (Android TV/tvOS).
- Addony instalované z repozitářů jako v Kodi + kompatibilita se Stremio addony.

## Volba stacku

| Varianta | Proč ne / proč ano |
|---|---|
| Electron (cesta Stremia) | 150+ MB, pomalý start, RAM. Přesný opak zadání. |
| Flutter | Slušný, ale ~30 MB runtime, vlastní rendering, horší integrace libmpv na desktopu. |
| Fork Kodi | Obrovská C++ kódová báze, Python addony = pomalé a težké sandboxovat. |
| **Rust jádro + Tauri 2 shell** | Binárka v jednotkách MB (systémový webview), Rust výkon a bezpečnost, Tauri 2 pokrývá desktop i Android/iOS. Jádro je na shellu nezávislé → TV shelly mohou být nativní. |

Přehrávání videa **nikdy** neběží ve webview:

- Desktop: **libmpv** vykreslované do okna aplikace (render API), UI jen jako overlay.
  mpv zvládne vše: HLS, MPEG-TS, RTSP, DASH, všechny kodeky, hw akcelerace.
- Android / Android TV: **Media3/ExoPlayer** (nativní view pod webview overlay).
- iOS / tvOS: **AVPlayer**, volitelně mpv-kit pro exotické formáty.

## Vrstvy

```
┌─────────────────────────────────────────────────────┐
│  UI shelly (tenké)                                  │
│  Tauri 2 (desktop+mobil) · Compose TV · SwiftUI tvOS│
├─────────────────────────────────────────────────────┤
│  Playback: libmpv · Media3 · AVPlayer               │
├─────────────────────────────────────────────────────┤
│  blesk-core (Rust, sans-IO)                         │
│  • modely (MediaItem, StreamRef, EPG)               │
│  • protokoly zdrojů: M3U/M3U8, Xtream Codes,        │
│    Stalker/Ministra                                 │
│  • addon systém: manifesty, repozitáře, instalace,  │
│    aktualizace                                      │
│  • Stremio addon protokol (klient)                  │
│  • cache (SQLite), watch-history — plánováno        │
├─────────────────────────────────────────────────────┤
│  Transport trait — HTTP dodává shell                │
└─────────────────────────────────────────────────────┘
```

### Sans-IO jádro

`blesk-core` samo nedělá síťové požadavky. Klienti protokolů **sestavují požadavky**
(`http::Request`) a **parsují odpovědi**; skutečný přenos zajišťuje shell přes trait
`http::Transport`. Výhody:

- jádro se kompiluje bleskově a bez systémových závislostí, testuje se offline,
- shell může použít optimální HTTP stack pro danou platformu (reqwest, NSURLSession, OkHttp),
- deterministické, snadno cachovatelné.

Na mobilech/TV se jádro vystaví přes **UniFFI** (Kotlin/Swift bindingy) — proto žádné
UI ani IO závislosti uvnitř.

## Addon systém

Detailní formáty viz [ADDON_SPEC.md](ADDON_SPEC.md). Shrnutí:

- **Repozitář** = statický `repository.json` hostovaný kdekoliv (GitHub Pages, vlastní
  server). Uživatel přidá URL repozitáře, aplikace zobrazí nabídku addonů, hlídá
  aktualizace (semver). Žádný centrální server.
- **Addon** = `manifest.json` (případně zip balíček) jednoho z typů:
  1. `stremio-addon` — odkaz na Stremio-kompatibilní HTTP addon → okamžitý přístup
     k existujícímu ekosystému katalogů/streamů.
  2. `m3u-source` — M3U/M3U8 playlist + volitelné XMLTV EPG.
  3. `xtream-source` — Xtream Codes server; přihlašovací údaje zadá uživatel při instalaci.
  4. `stalker-source` — Stalker/Ministra portál; MAC/údaje zadá uživatel.
  5. `script` (plánováno) — JS scraper běžící v **QuickJS sandboxu** s úzkým API
     (fetch přes jádro, žádný filesystem, limity CPU/paměti). Kodi-like flexibilita
     bez Pythonu a bez plného přístupu k systému.

Vestavěné protokolové enginy (M3U, Xtream, Stalker) jsou součástí jádra — addon je
jen deklarativně konfiguruje. Díky tomu jsou tyto zdroje rychlé a bezpečné (žádný
cizí kód).

### Bezpečnost

- Balíčky addonů mají v indexu repozitáře `sha256`; ověřuje se před instalací.
- Skriptové addony běží v sandboxu bez přístupu k FS a s HTTP jen přes jádro
  (možnost per-addon network allowlistu).
- Přihlašovací údaje (Xtream, Stalker) se ukládají do systémové keychain, nikdy do
  manifestu.

### Právní poznámka

Aplikace je čistý přehrávač bez obsahu — jako Kodi/Stremio. Zdroje si instaluje a
odpovídá za ně uživatel.

## Datový tok (příklad: živá TV přes Stalker)

1. UI požádá jádro o kanály zdroje → jádro vrátí `Request` pro handshake.
2. Shell požadavek odešle (`Transport`), jádro odpověď zparsuje → token.
3. Totéž pro `get_all_channels` → `Vec<Channel>` → UI (virtualizovaný seznam).
4. Klik na kanál → `create_link` → skutečná stream URL → předá se libmpv/ExoPlayeru.
5. EPG a loga se dotahují lazy a cachují.

## Výkonová pravidla

- Start bez blokující sítě; poslední stav z SQLite cache, refresh na pozadí.
- Parsery streamové/jednoprůchodové (M3U s 50k kanály musí být instantní).
- Seznamy v UI virtualizované; obrázky přes disk-cache s downscalem.
- Žádné JS frameworky ve frontend­u shellu — vanilla TS, DOM, CSS.
