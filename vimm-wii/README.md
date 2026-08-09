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
release_name,format,size_gb,verified,vault_id,url,duplicates_dropped
```

Všechna pole jsou v uvozovkách, takže názvy jako `Gesundheitscoach, Der` nebo
`Foo (Europe) (En,Fr,De)` neposunou sloupce. `duplicates_dropped` ukazuje, které
regionální varianty se zahodily — např. `Ghostbusters: The Video Game (USA) v1.1 #102`.

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

## Známá omezení

- **Parsery nebyly vyzkoušené proti živému vimm.net.** Prostředí, kde skript
  vznikl, má vimm.net zablokovaný na egress proxy, takže struktura HTML je
  odvozená ze snímků stránek a z URL formátů, ne z reálné odpovědi serveru.
  Logika je psaná tolerantně (víc fallbacků pro velikost i region) a otestovaná
  na fixturách, ale **první běh si prosím pusť s `-s G --limit 5 -v` a mrkni na
  výstup.** Kdyby sloupce nesedly, upravovat se budou jen dva perl bloky
  `PARSE_LIST_PL` a `PARSE_DETAIL_PL`.
- Velikost se bere z toho, co stránka zobrazuje u tlačítka Download; pro Wii je
  default `.wbfs`. Skript zkouší v tomto pořadí: velikost u `.wbfs` → velikost
  za tlačítkem Download → před tlačítkem → poslední velikost na stránce.
- Jednotky se převádějí binárně (1 GB = 1024 MB).
- Hry na víc discích se berou jako jeden záznam s velikostí, kterou stránka udává.
- Filtr `version=new` znamená, že se u každé hry bere jen nejnovější revize.

## Buď slušný

Default je jeden sekvenční request za sekundu s realistickým User-Agentem
a cache, aby se nic nestahovalo dvakrát. Nezvyšuj `-j` do desítek — Vimm je
malý web zdarma a rate-limit (HTTP 429) skript sice zvládne, ale je lepší ho
nevyvolávat.
