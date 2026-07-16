# Blesk 🎬⚡

> Pracovní název. Lightweight, pekelně rychlý multiplatformní přehrávač filmů, seriálů a IPTV
> se systémem addonů instalovaných z repozitářů (jako Kodi), kompatibilní se Stremio addony.

## Principy

1. **Lightweight** — žádný Electron, žádný Chromium v balíčku. Jádro v Rustu, UI přes
   systémový webview (Tauri 2). Cílová velikost desktop binárky: jednotky MB.
2. **Pekelně rychlý** — start aplikace < 1 s, jádro bez alokací navíc, streaming parsing
   playlistů, SQLite cache metadat, lazy načítání obrázků.
3. **Multiplatformní** — jedno Rust jádro (`blesk-core`), tenké shelly:
   - Windows / macOS / Linux: Tauri 2 + libmpv
   - Android / iOS: Tauri 2 Mobile (Media3/ExoPlayer, AVPlayer)
   - Android TV / tvOS: nativní tenké shelly nad stejným jádrem (UniFFI) — fáze 3
4. **Addony z repozitářů** — přehrávač sám o sobě neobsahuje žádné zdroje obsahu.
   Zdroje (M3U, Xtream Codes, Stalker portál, scrapery, katalogy) se instalují jako
   addony z uživatelem přidaných repozitářů. Navíc **kompatibilita se Stremio addon
   protokolem** = existující ekosystém funguje hned.

Detailní návrh: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
Formát addonů a repozitářů: [docs/ADDON_SPEC.md](docs/ADDON_SPEC.md)

## Struktura

```
blesk/
├── crates/
│   └── blesk-core/     # jádro: protokoly, addon systém, modely (sans-IO, bez UI)
├── app/
│   ├── src-tauri/      # desktop/mobile shell (Tauri 2)
│   └── ui/             # frontend — vanilla TS/JS, žádný framework
└── docs/
    ├── ARCHITECTURE.md
    ├── ADDON_SPEC.md
    └── examples/       # ukázkový repozitář a addony
```

## Vývoj

```sh
# jádro (funguje kdekoliv, bez systémových závislostí)
cargo test

# desktop aplikace (vyžaduje prerekvizity Tauri 2: webkit2gtk na Linuxu atd.)
cd app/src-tauri && cargo tauri dev
```

## Stav

- [x] Návrh architektury a formátu addonů/repozitářů
- [x] `blesk-core`: parser M3U/M3U8 (atributy tvg-*, group-title, EXTGRP)
- [x] `blesk-core`: klient Xtream Codes API (kategorie, live/VOD/seriály, stream URL, XMLTV)
- [x] `blesk-core`: klient Stalker/Ministra portálu (handshake, kanály, žánry, create_link)
- [x] `blesk-core`: manifest addonu, index repozitáře, kontrola aktualizací
- [x] `blesk-core`: kompatibilní klient Stremio addon protokolu
- [x] Scaffold Tauri 2 shellu (načtení a prohlížení M3U playlistu)
- [ ] Přehrávání přes libmpv (desktop)
- [ ] Instalace addonů (zip + sha256) a správa repozitářů v UI
- [ ] XMLTV EPG parser + timeline
- [ ] SQLite cache, watch-history, oblíbené
- [ ] Sandboxované JS scraper addony (QuickJS)
- [ ] Mobilní shelly, TV shelly
