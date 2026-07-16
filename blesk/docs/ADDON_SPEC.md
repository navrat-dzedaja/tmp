# Specifikace addonů a repozitářů (v0.1)

## Repozitář

Repozitář je statický JSON soubor (`repository.json`) dostupný přes HTTPS — stačí
GitHub Pages, gist nebo libovolný web. Uživatel v aplikaci přidá jeho URL.

```json
{
  "id": "cz.example.repo",
  "name": "Ukázkový repozitář",
  "description": "Demo repozitář s veřejnými zdroji",
  "addons": [
    {
      "id": "org.iptv-org.playlist",
      "name": "iptv-org — veřejné kanály",
      "version": "1.0.0",
      "description": "Veřejně dostupné IPTV kanály z projektu iptv-org",
      "download": "https://example.com/addons/iptv-org-playlist/manifest.json",
      "sha256": null
    }
  ]
}
```

- `id` — reverse-DNS, unikátní.
- `version` — [semver](https://semver.org). Aplikace hlídá aktualizace porovnáním
  s nainstalovanou verzí.
- `download` — URL buď přímo na `manifest.json`, nebo na zip balíček obsahující
  `manifest.json` (a u typu `script` i kód). U zipu je `sha256` povinné.

## Manifest addonu

Společná pole:

| Pole | Povinné | Popis |
|---|---|---|
| `id` | ano | reverse-DNS id, musí odpovídat záznamu v repozitáři |
| `name` | ano | zobrazované jméno |
| `version` | ano | semver |
| `type` | ano | typ addonu, viz níže |
| `description`, `author`, `icon` | ne | metadata |
| `core` | ne | semver požadavek na verzi jádra, např. `">=0.1"` |

### `type: "stremio-addon"` — Stremio-kompatibilní addon

```json
{
  "id": "com.example.catalog",
  "name": "Ukázkový katalog",
  "version": "1.2.0",
  "type": "stremio-addon",
  "url": "https://addon.example.com/manifest.json"
}
```

Jádro mluví Stremio addon protokolem (`/manifest.json`, `/catalog/{type}/{id}.json`,
`/meta/{type}/{id}.json`, `/stream/{type}/{id}.json`) → existující Stremio addony
fungují beze změn.

### `type: "m3u-source"` — M3U/M3U8 playlist

```json
{
  "id": "org.iptv-org.playlist",
  "name": "iptv-org — veřejné kanály",
  "version": "1.0.0",
  "type": "m3u-source",
  "url": "https://iptv-org.github.io/iptv/index.m3u",
  "epg_url": "https://iptv-org.github.io/epg/guides/cz.xml"
}
```

Podporované atributy `#EXTINF`: `tvg-id`, `tvg-name`, `tvg-logo`, `group-title`
(+ `#EXTGRP`). EPG ve formátu XMLTV.

### `type: "xtream-source"` — Xtream Codes

```json
{
  "id": "com.example.xtream",
  "name": "Můj Xtream poskytovatel",
  "version": "1.0.0",
  "type": "xtream-source",
  "server": "http://portal.example.com:8080"
}
```

`server` je volitelné (předvyplnění). Uživatelské jméno a heslo zadá uživatel při
instalaci; ukládají se do systémové keychain, nikdy do manifestu.

### `type: "stalker-source"` — Stalker / Ministra portál

```json
{
  "id": "com.example.stalker",
  "name": "Můj Stalker portál",
  "version": "1.0.0",
  "type": "stalker-source",
  "portal": "http://portal.example.com/stalker_portal/server/load.php"
}
```

MAC adresu (a případné přihlášení) zadá uživatel při instalaci.

### `type: "script"` — sandboxovaný scraper (plánováno)

```json
{
  "id": "com.example.scraper",
  "name": "Ukázkový scraper",
  "version": "0.3.1",
  "type": "script",
  "entry": "main.js"
}
```

JS modul běžící v QuickJS sandboxu. K dispozici má jen úzké API jádra
(`blesk.fetch`, `blesk.addCatalog`, `blesk.addStreams`), bez přístupu k souborům
a s limity CPU/paměti. Distribuuje se výhradně jako zip s povinným `sha256`.

## Životní cyklus

1. **Instalace** — stažení `download`, ověření `sha256` (u zipu), validace manifestu
   (`id` shoda, `core` požadavek), případný dotaz na přihlašovací údaje.
2. **Aktualizace** — periodické stažení `repository.json`, porovnání semver verzí
   (`RepositoryIndex::updates_for` v jádru).
3. **Odinstalace** — smazání balíčku + credentials z keychain.

Ukázky: [examples/](examples/)
