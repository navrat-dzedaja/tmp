# vimm-wii-catalog.sh

Bash skript pro macOS, který prolistuje celou sekci Wii ve Vimm's Lair Vault,
vytvoří CSV se všemi hrami a na konci vypíše **součet velikostí všech .wbfs
souborů** — abys věděl, jak velký disk potřebuješ.

Napsáno pro to, co je na macOS předinstalované: `bash` 3.2, BSD `sed`/`awk`,
systémový `curl` a `perl`. Žádný Homebrew, žádné závislosti.

## Použití

```bash
chmod +x vimm-wii-catalog.sh

./vimm-wii-catalog.sh --self-test          # offline test parserů (5 s, nic nestahuje)
./vimm-wii-catalog.sh -s G --limit 5 -v    # rychlý test na pár hrách
./vimm-wii-catalog.sh                      # plný běh -> wii_games.csv
```

Plný běh je ~2500 her, jeden request za sekundu → počítej cca 45–60 minut.
Všechno se cachuje do `.vimm-cache/`, takže **přerušený běh můžeš prostě spustit
znovu a pokračuje tam, kde skončil**. Opakovaný běh nad plnou cache je otázka
sekund.

### Volby

| Volba | Význam |
|---|---|
| `-o FILE` | výstupní CSV (default `wii_games.csv`) |
| `-c DIR` | cache adresář (default `.vimm-cache`) |
| `-d SEC` | pauza mezi requesty (default `1.0`) |
| `-j N` | paralelní stahování detailů (default `1`; `3` je slušné maximum) |
| `-s "A B"` | jen vybrané sekce (`number` = `#`) |
| `--limit N` | zastav po N hrách (na testování) |
| `--keep-duplicates` | nespojovat regionální duplikáty, jeden řádek na region |
| `--region-priority LIST` | vlastní preference regionů, nejlepší první |
| `--format FMT` | formát, jehož velikost se má brát (default `wbfs`) |
| `--exclude-extras` | vynechat dema, prototypy, unlicensed, bonus, překlady |
| `--refresh` | ignorovat cache a stáhnout znovu |
| `--total-row` | přidat řádek `TOTAL` i do CSV |
| `-v` | podrobnější průběh |

## Výstup

CSV má hlavičku a sloupce:

```
name,region,version,year,publisher,players,serial,crc,rating,votes,
format,size_gb,size_source,verified,vault_id,url,duplicates_dropped
```

Všechna pole jsou v uvozovkách, takže názvy jako `Gesundheitscoach, Der`
neposunou sloupce. `duplicates_dropped` ukazuje, které regionální varianty se
zahodily — např. `Ghostbusters: The Video Game (USA) v1.1 #102`.
`size_source` říká, kterým pravidlem se velikost našla — viz sekci o velikostech
níž; hodnota `last-on-page-UNRELIABLE` znamená „tomuto číslu nevěř".

Na konci skript vypíše:

```
Games in CSV (after region dedup): 2437
CSV written to:                     wii_games.csv

TOTAL DOWNLOAD SIZE: 4812.63 GB  (4.70 TB)
Disk to buy (+10% headroom): 5.17 TB
```

Součet se počítá ze stejných dvoudesetinných hodnot, které jsou v CSV, takže
když si sloupec `size_gb` sečteš v Excelu, vyjde ti přesně stejné číslo.

## Jak funguje deduplikace

Hry, které existují pro víc regionů, se sloučí na jeden řádek. Vítěz se vybírá
podle pořadí: **Europe → World → evropské země (UK, DE, FR, ES, IT, …) →
Australia/NZ → USA → Japan → ostatní**. Při stejném regionu vyhraje vyšší verze,
pak větší soubor, pak nižší vault ID. Pořadí se dá přepsat přes
`--region-priority`.

Klíč pro porovnání je název normalizovaný na malá písmena bez interpunkce.
Pozor: dvě opravdu různé hry se shodným názvem by se tím slily do jedné —
u Wii katalogu to prakticky nenastává, ale `--keep-duplicates` ti ukáže vše.

## Ověření a ladění

`--self-test` postaví fixture HTML stránky, prohoní je celým řetězcem
(parse → dedup → CSV → součet) a zkontroluje 29 tvrzení: parsování názvu,
regionu, vydavatele, seriálu, hodnocení, převod MB→GB, že Evropa přebije USA
i Japonsko, CSV quoting i výsledný součet. Běží offline.

Po běhu najdeš v `.vimm-cache/work/size-source.tsv` pro každou hru
`velikost, id, název, kterým regexem se velikost našla` — rychlá kontrola, že
se velikosti tahají odkud mají. Hodnoty `last-on-page` jsou ty, kterým se
vyplatí věnovat pozornost.

Když se něco rozbije, skript to řekne konkrétně: rozliší „nešla stáhnout ani
jedna stránka" (síť/blokace) od „stránky mám, ale nic se nenaparsovalo"
(změnilo se HTML) a v prvním případě vypíše i původní chybu z curlu.

## Jak Vimm brání scrapování (a jak to skript řeší)

Tohle je zjištěné z reálné odpovědi serveru, ne z dokumentace:

- **Každý řádek výpisu začíná skrytým past-odkazem**:
  `<a href="/vault/999999" style="display:none">9</a>`. Naivní regex na
  `/vault/(\d+)` sebere tuhle nulu a ne hru. Skript proto prochází všechny
  odkazy v prvním sloupci, zahazuje `display:none` a ID 999999.
- **Skutečný odkaz má mezeru za `href=`**: `<a href= "/vault/17478">`. Přesný
  vzor `href="/vault/N"` nenajde vůbec nic.
- **Stránka hry nemá `<h1>`/`<h2>` s názvem** — jediné nadpisy patří menu konzolí,
  takže naivní parser pojmenuje každou hru „Nintendo". Název se bere z `og:title`.
- **Název romsetu** (`id="data-good-title"`) server posílá prázdný, doplňuje ho
  `/js/vault.min.js`. Bez JS engine se nedá získat, proto ten sloupec v CSV není.

## Velikosti — čti prosím

Velikost u tlačítka Download **taky vykresluje JavaScript**. Server posílá jen
`<tr id="dl-row">` s formulářem, který POSTuje `mediaId` na `dl3.vimm.net`.
Skript zkouší velikost najít v tomto pořadí a do sloupce `size_source` zapíše,
co zabralo:

| size_source | význam |
|---|---|
| `dl-row` | z download boxu (server-side) — spolehlivé |
| `js-format-size`, `js-size-string`, `js-size-bytes` | z JS dat stránky — spolehlivé |
| `format-label` | text u `.wbfs` — pravděpodobně dobré |
| `last-on-page-UNRELIABLE` | poslední velikost kdekoli na stránce — **nevěř** |
| `none` (size_gb 0.00) | velikost se nenašla vůbec |

Po běhu se koukni na rozdělení hodnot:

```bash
cut -f4 .vimm-cache/work/size-source.tsv | sort | uniq -c | sort -rn
```

Když převažují `none` nebo `UNRELIABLE`, znamená to, že Vimm velikost servíruje
jinak, než skript čeká, a **součet bude podstřelený**. V takovém případě pusť
`./probe.sh https://vimm.net/vault/17493` a podívej se, v jakém `<script>` bloku
velikost je — přidat další vzor je pak otázka jednoho řádku v `PARSE_DETAIL_PL`
(sekce `--- size ---`).

## Další známá omezení

- Jednotky se převádějí binárně (1 GB = 1024 MB).
- Hry na víc discích se berou jako jeden záznam s velikostí, kterou stránka udává.
- Filtr `version=new` znamená, že se u každé hry bere jen nejnovější revize.
- Výchozí URL je filtrovaný výpis, protože vrací víc záznamů: pro sekci G
  126 her, kdežto plain `/vault/Wii/G` jen 48. `--plain` přepne na druhou formu.

## GitHub Actions

`.github/workflows/wii-catalog.yml` umí skript pustit na macOS runneru
(stejná platforma, na jakou je psaný, a s neomezeným přístupem k síti).
Push do vývojové branche udělá malý smoke run, „Run workflow" bere parametry
`sections` (`all` = vše), `limit`, `delay`, `jobs`. CSV, `size-source.tsv`
a ukázkové HTML se ukládají jako artifacts a součet se vypíše do job summary.

Pozn.: aby šel workflow spustit ručně tlačítkem, musí ten soubor být na výchozí
branchi (`main`) — dokud je jen na feature branchi, spouští se pushem.

## Buď slušný

Default je jeden sekvenční request za sekundu s realistickým User-Agentem
a cache, aby se nic nestahovalo dvakrát. Nezvyšuj `-j` do desítek — Vimm je
malý web zdarma a rate-limit (HTTP 429) skript sice zvládne, ale je lepší ho
nevyvolávat.
