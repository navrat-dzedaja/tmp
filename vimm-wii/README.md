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

**Jak dlouho to bude trvat** si nemusíš odhadovat — skript to řekne sám po
prolistování výpisů, ještě než začne stahovat detaily:

```
133 list entries -> 80 distinct titles (53 regional duplicates skipped)
1874 detail pages to fetch
```

To druhé číslo je počet requestů, a od verze s `--gentle` si skript hned spočítá
i dobu běhu. Na plný katalog používej `--gentle` (viz sekci o rate limitingu) —
při výchozí 1 s Vimm limiter sepne po dvou desítkách requestů.
Všechno se cachuje do `.vimm-cache/`, takže **přerušený běh můžeš prostě spustit
znovu a pokračuje tam, kde skončil**. Opakovaný běh nad plnou cache je otázka
sekund.

### Volby

| Volba | Význam |
|---|---|
| `-o FILE` | výstupní CSV (default `wii_games.csv`) |
| `-c DIR` | cache adresář (default `.vimm-cache`) |
| `-d SEC` | pauza mezi requesty (default `1.0`, s jitterem 0–25 %) |
| `--gentle` | 60 s mezi requesty, jeden job — nastavení pro plný běh bez 429 |
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
release_name,format,size_gb,size_source,verified,vault_id,url,duplicates_dropped
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

Hry, které existují pro víc regionů, se sloučí na jeden řádek, a to **ještě před
stahováním detailů** — výpis už obsahuje název, region i verzi, takže se stahuje
jen vítěz každého titulu. Měřeno na sekci G: 133 záznamů výpisu → 80 titulů, tedy o ~40 % méně stahování.
Kdyby stránka vítěze nešla stáhnout (404, vzdání se po retry), vezme se druhá
nejlepší regionální varianta, aby se titul neztratil úplně (max 3 kola). Vítěz se vybírá
podle pořadí **Europe → USA → Japan → cokoli dalšího**. Při stejném regionu
vyhraje vyšší verze, pak nižší vault ID. (Velikost jako tiebreak odpadla — ta je
až v detailu, který se u prohraných variant vůbec nestahuje.)

**Nic se nezahazuje.** Ta preference jen určuje, která varianta titulu se stáhne.
Hra, která existuje jen pro USA, Japonsko, Německo nebo Koreu, vyhraje ve své
kategorii a v CSV bude — jen s tím svým regionem. Ve sloupci
`duplicates_dropped` vidíš, co konkrétně prohrálo.

Jedna věc k rozvážení: Wii je regionově zamčená. Při striktním EU → USA → JP
dostaneš u titulu, který vyšel v Německu a v USA, tu **americkou** (NTSC) verzi —
a ta se ti na evropské konzoli bez homebrew nespustí, kdežto ta německá (PAL)
ano. Když chceš nejdřív všechno PAL a teprve pak USA:

```bash
./vimm-wii-catalog.sh --region-priority "Europe,United Kingdom,Germany,France,Spain,Italy,Netherlands,Scandinavia,Australia,USA,Japan"
```

Klíč pro porovnání je název normalizovaný na malá písmena bez interpunkce.
Pozor: dvě opravdu různé hry se shodným názvem by se tím slily do jedné —
u Wii katalogu to prakticky nenastává, ale `--keep-duplicates` ti ukáže vše.

## Ověření a ladění

`--self-test` postaví fixture HTML stránky, prohoní je celým řetězcem
(parse → dedup → CSV → součet) a zkontroluje 48 tvrzení: parsování názvu,
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
  `/js/vault.min.js`. Nedá se vzít z HTML — ale je v JS payloadu jako base64
  `GoodTitle`, odkud ho skript dekóduje.

## Velikosti

Velikost server posílá na dvou místech. Zobrazená je v
`<td id="dl_size">2.39 GB</td>` uvnitř `<tr id="dl-row">`, ale **přesná** je v JS
payloadu stránky: `let media=[{"ID":9018,…,"Zipped":"2509593",…}]`, kde `Zipped`
je velikost v KB a zobrazené „2.39 GB" je jen její zaokrouhlení. Skript bere
`Zipped` — na tisících řádcích by se ze zaokrouhlených hodnot součet rozjel.
Ze stejného objektu se dekóduje i `GoodTitle` (base64) do sloupce `release_name`.

Pořadí zdrojů a co skript zapíše do `size_source`:

| size_source | význam |
|---|---|
| `js-zipped` | přesné KB z JS payloadu pro vybrané `mediaId` — **tohle chceš** |
| `dl-row` | zobrazený text z download boxu — dobré, jen zaokrouhlené |
| `js-format-size`, `js-size-string`, `js-size-bytes` | jiné podoby JS dat |
| `format-label` | text u `.wbfs` — pravděpodobně dobré |
| `last-on-page-UNRELIABLE` | poslední velikost kdekoli na stránce — **nevěř** |
| `none` (size_gb 0.00) | velikost se nenašla vůbec |

Pozor na to poslední: neomezené hledání velikosti na stránce chytne řádek
„Cart size" a vrátí nesmysl (0,0002 GB). Proto je hledání scopované.

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
Na plný katalog to ale nepoužívej — viz sekci o rate limitingu výš; workflow je
tady na ověřování parserů proti živému webu, ne na produkci dat.

Pozn.: aby šel workflow spustit ručně tlačítkem, musí ten soubor být na výchozí
branchi (`main`) — dokud je jen na feature branchi, spouští se pushem.

## Rate limiting: kde tohle pouštět

Ověřeno tvrdě: plný běh na GitHub Actions (macOS runner, `-j 2`, 1 s pauza)
**nedoběhl** — po 6 hodinách ho zabil timeout a poslední hodiny strávil v HTTP 429
backoffu. Konec logu vypadal takhle:

```
warning: 429 for https://vimm.net/vault/17497 -- rate limited, waiting 30s
warning: 429 for https://vimm.net/vault/17499 -- rate limited, waiting 40s
```

Vimm datacentrovým IP adresám (a GitHub Actions je přesně to) limituje agresivně.
Skript se choval správně — pauzoval a zkoušel to znovu — ale na tomhle se plný
katalog dotáhnout nedá.

**Pouštěj to z vlastního stroje**, z běžné domácí linky. Skript je na to psaný:
cache v `.vimm-cache/` znamená, že běh můžeš kdykoli přerušit `Ctrl-C` a druhý
den pustit znovu — pokračuje tam, kde skončil, takže se to dá rozložit na víc
sezení. Když narazíš na 429 i doma, zvyš pauzu (`-d 2` nebo `-d 3`); je to
paradoxně rychlejší než sbírat backoffy.

Doporučený plný běh na Macu:

```bash
caffeinate -is ./vimm-wii-catalog.sh --gentle 2>&1 | tee run.log
```

`--gentle` je 60 s mezi requesty a jeden job. Na ~1700 titulů to je **cca 32
hodin** — přesnou dobu ti skript vypíše hned, jak zjistí počet stránek:

```
1712 detail pages to fetch -- about 32.1 hours at 60s apart
```

Pauza se navíc sama zvyšuje: každé 429 zdvihne minimum pro celý zbytek běhu
(1 s → 31 → 62 → 124, strop 600 s) a ten limit se sdílí i mezi paralelní workery.
Cílem je narazit na limiter maximálně jednou, ne ho objevovat u každé stránky.

`caffeinate -is` zabrání uspání stroje uprostřed běhu, `tee` uloží log, ať se
dá po dokončení zkontrolovat, jestli se objevily 429:

```bash
grep -c 'rate limited' run.log      # 0 = limiter vůbec nezasáhl
cut -f4 .vimm-cache/work/size-source.tsv | sort | uniq -c | sort -rn
```

## Buď slušný

Default je jeden sekvenční request za sekundu s realistickým User-Agentem
a cache, aby se nic nestahovalo dvakrát. Nezvyšuj `-j` do desítek — Vimm je
malý web zdarma a rate-limit (HTTP 429) skript sice zvládne, ale je lepší ho
nevyvolávat.
