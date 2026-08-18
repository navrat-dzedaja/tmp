# Rent Atlas — GB

Interaktivní vektorová mapa Velké Británie zobrazující ceny soukromého
nájemního bydlení, postavená na datové sadě ONS **Price Index of Private
Rents, UK: monthly price statistics** (vydání červenec 2026, období leden
2015 – červen 2026).

## Spuštění

`index.html` je samostatný soubor (žádný build krok, žádný server, žádné
externí API) — obsahuje vloženou knihovnu Leaflet i všechna data. Stačí ho
otevřít v prohlížeči, nebo pro plnou funkčnost service-workerů/local-storage
ho servírovat lokálně:

```
python3 -m http.server 8000
# http://localhost:8000/index.html
```

## Funkce

- **3 geografické úrovně** – místní obvody/BRMA (334), regiony (11),
  země (3), přepínatelné v panelu nástrojů.
- **Zoom, pan** a vyhledávání oblasti podle názvu s automatickým přiblížením.
- **Časová osa** 2015–2026 (posuvník + přehrávání vývoje v čase).
- 4 ukazatele: průměrné nájemné, index nájmů, meziroční a měsíční změna
  (sekvenční, resp. divergentní barevná škála).
- 5 kategorií velikosti bytu (vše, 1–4 a více ložnic).
- Detailní panel s minigrafem vývoje indexu po kliknutí na oblast.
- Světlý/tmavý režim podle nastavení prohlížeče.

## Data a hranice — poznámky k přesnosti

- **Zdroj dat:** ONS, *Price Index of Private Rents, UK: monthly price
  statistics*, tabulka „Table 1“.
- **Severní Irsko** není v datové sadě součástí Velké Británie, a proto zde
  není zobrazeno.
- **Skotsko** je v datech agregováno do 18 oblastí *Broad Rental Market Area*
  (BRMA), nikoli 32 radničních obvodů (council areas). Mapové hranice BRMA
  byly pro tento projekt dopočítány sloučením hranic council areas podle
  veřejně publikovaného přiřazení Rent Service Scotland — viz
  `data_prep/prepare_geo.py` (`SCOTLAND_BRMA`). Pokud budete potřebovat
  ověřit přesné složení jednotlivých BRMA, porovnejte s aktuálním publikovaným
  seznamem Rent Service Scotland / ONS.
- **Anglie a Wales:** místní obvody odpovídají aktuálním (2023+) kódům ONS.
  Zdrojové hranice (`martinjc/UK-GeoJSON`) jsou z roku 2013, proto byly
  obvody, které od té doby sloučily (Cumberland, Westmorland and Furness,
  Severní Yorkshire, Somerset, Buckinghamshire, Dorset, Bournemouth
  Christchurch and Poole, North/West Northamptonshire, East/West Suffolk),
  pro tuto mapu sloučeny odpovídajícím způsobem — viz `ENGLAND_MERGES`
  v `data_prep/prepare_geo.py`.
- Ostrovy Scilly (E06000053) a City of London (E09000001) v datové sadě ONS
  nemají samostatné hodnoty (příliš malý vzorek) — na mapě jsou zobrazeny
  jako „data nejsou k dispozici“, aby v mapě nevznikaly díry.
- Hranice: [`martinjc/UK-GeoJSON`](https://github.com/martinjc/UK-GeoJSON)
  (ONS/OS Open Data licence).

## Struktura repozitáře

```
index.html            – finální samostatná aplikace (commitovaný výstup)
src/app.template.html – HTML/CSS šablona (s {{PLACEHOLDER}} bloky)
src/app.js            – veškerá aplikační logika (vanilla JS, žádné závislosti)
data/                 – vygenerovaná geodata a časové řady (JSON)
data_prep/            – Python skripty použité k vygenerování data/ a index.html
  prepare_geo.py       – staví GeoJSON hranice (dissolve/rename, viz výše)
  prepare_data.py      – extrahuje časové řady z ONS Excelu do data/rent_data.json
  build.py              – poskládá index.html ze šablony + dat + Leafletu
```

Skripty v `data_prep/` odkazují na cesty ze session, ve které vznikly
(stažený ONS Excel a naklonovaný `UK-GeoJSON`), takže je nelze bez úpravy
znovu spustit v jiném prostředí — jsou ponechány jako dokumentace postupu,
ne jako spustitelný pipeline.
