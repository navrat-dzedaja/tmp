# Pěšky bez silnic

Mapa souvislých přírodních celků v Evropě (les, přirozené trávníky, vřesoviště, skály, mokřady,
volitelně louky a pastviny), které nepřetínají pole, zástavba, velké řeky ani silnice.

Pipeline (spouštět z pracovní složky se složkami `dl/`, `code/`, `site/`):

1. `dl_clc.sh` – stáhne CORINE Land Cover 2018 (EEA MapServer, 100 m, EPSG:3035) po dlaždicích 4096 px.
2. `clc_convert.py i j` – převede barvy legendy na třídy a agreguje na mřížku 200 m (počty přírodních subpixelů).
3. `ovt_meta.py`, `ovt_roads.py` – vyberou z Overture Maps (OSM) silnice motorway–tertiary a železnice pro Evropu.
4. `roads_raster.py` – rasterizace silnic na 200 m (all_touched), tunely a mosty vynechány.
5. `ctx.py` – rastr států (GISCO), hranice a města (Natural Earth).
6. `analyze.py v1|v2|v3` – 4-souvislé celky, výběr hlavních celků, nejdelší trasy (dvojí Dijkstra v `sweep.c`, váhy 5/7 bez řezání rohů), trasy ze Šumavy.
7. `tiles.py`, `finalize.py` – pyramida dlaždic (RGB = pořadí celku pro 3 varianty, šedotón = typ krajiny + bity silnic) a `data.json`.
8. `page.html` – stránka (Leaflet 1.9.4, CRS.Simple); CSS Leafletu se vkládá místo `/*LEAFLETCSS*/`.

Data: CORINE Land Cover 2018 © EEA/Copernicus · © přispěvatelé OpenStreetMap (ODbL) přes Overture Maps · © EuroGeographics (GISCO) · Natural Earth.
