"""
Build a single GeoJSON of Great Britain local-authority-level polygons whose
`code` property matches the Area code used in the ONS Price Index of Private
Rents dataset, plus dissolved region- and country-level GeoJSONs.

Source boundaries: martinjc/UK-GeoJSON (LAD 2013 boundaries, ONS/OS licensed).
The ONS rent dataset uses *current* (2023+) local authority codes, so a
number of 2013-era districts have since merged into larger unitary
authorities, and Scotland is reported by 18 Broad Rental Market Areas (BRMA)
rather than the 32 council areas. Both are handled below by dissolving
(unioning) the old polygons into the new units.
"""
import json
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid


def _valid(geom):
    return make_valid(geom) if not geom.is_valid else geom

GEO_ROOT = "/workspace/martinjc/uk-geojson/json/administrative"
SIMPLIFY_TOLERANCE = 0.0015  # degrees, ~150m -- keeps LAD shapes recognisable but light
COORD_DECIMALS = 4  # ~11m precision

# England 2013-LAD -> current-LAD merges since the source boundaries were published
ENGLAND_MERGES = {
    ("E06000058", "Bournemouth, Christchurch and Poole"): ["E06000028", "E06000029", "E07000048"],
    ("E06000059", "Dorset"): ["E07000049", "E07000050", "E07000051", "E07000052", "E07000053"],
    ("E06000060", "Buckinghamshire"): ["E07000004", "E07000005", "E07000006", "E07000007"],
    ("E06000061", "North Northamptonshire"): ["E07000150", "E07000152", "E07000153", "E07000156"],
    ("E06000062", "West Northamptonshire"): ["E07000151", "E07000154", "E07000155"],
    ("E06000063", "Cumberland"): ["E07000026", "E07000028", "E07000029"],
    ("E06000064", "Westmorland and Furness"): ["E07000027", "E07000030", "E07000031"],
    ("E06000065", "North Yorkshire"): ["E07000163", "E07000164", "E07000165", "E07000166", "E07000167", "E07000168", "E07000169"],
    ("E06000066", "Somerset"): ["E07000187", "E07000188", "E07000189", "E07000190", "E07000191"],
    ("E07000244", "East Suffolk"): ["E07000205", "E07000206"],
    ("E07000245", "West Suffolk"): ["E07000201", "E07000204"],
}
# simple renumberings with no boundary change
ENGLAND_RENAMES = {
    "E08000016": ("E08000038", "Barnsley"),
    "E08000019": ("E08000039", "Sheffield"),
}
# 2013 codes that are consumed by a merge above and must not also appear standalone
ENGLAND_DROP_STANDALONE = {c for codes in ENGLAND_MERGES.values() for c in codes} | set(ENGLAND_RENAMES)

# Scotland: 32 council areas (S12) -> 18 Broad Rental Market Areas (S33), per
# Rent Service Scotland's published BRMA definitions.
SCOTLAND_BRMA = [
    ("S33000001", "Aberdeen and Shire", ["Aberdeen City", "Aberdeenshire"]),
    ("S33000002", "Argyll and Bute", ["Argyll and Bute"]),
    ("S33000003", "Ayrshires", ["East Ayrshire", "North Ayrshire", "South Ayrshire"]),
    ("S33000004", "Dumfries and Galloway", ["Dumfries and Galloway"]),
    ("S33000005", "Dundee and Angus", ["Dundee City", "Angus"]),
    ("S33000006", "East Dunbartonshire", ["East Dunbartonshire"]),
    ("S33000007", "Fife", ["Fife"]),
    ("S33000008", "Forth Valley", ["Falkirk", "Clackmannanshire", "Stirling"]),
    ("S33000009", "Greater Glasgow", ["Glasgow City", "East Renfrewshire"]),
    ("S33000010", "Highland and Islands", ["Highland", "Orkney Islands", "Shetland Islands", "Eilean Siar", "Moray"]),
    ("S33000011", "Lothian", ["City of Edinburgh", "Midlothian", "East Lothian"]),
    ("S33000012", "North Lanarkshire", ["North Lanarkshire"]),
    ("S33000013", "Perth and Kinross", ["Perth and Kinross"]),
    ("S33000014", "Renfrewshire/Inverclyde", ["Renfrewshire", "Inverclyde"]),
    ("S33000015", "Scottish Borders", ["Scottish Borders"]),
    ("S33000016", "South Lanarkshire", ["South Lanarkshire"]),
    ("S33000017", "West Dunbartonshire", ["West Dunbartonshire"]),
    ("S33000018", "West Lothian", ["West Lothian"]),
]


def load_features(nation):
    with open(f"{GEO_ROOT}/{nation}/lad.json") as f:
        d = json.load(f)
    out = {}
    for feat in d["features"]:
        p = feat["properties"]
        out[p["LAD13CD"]] = {"name": p["LAD13NM"], "geom": _valid(shape(feat["geometry"]))}
    return out


def _polygons_only(geom):
    """Drop stray points/lines that can appear in union results; keep only polygonal area."""
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        polys = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        return unary_union(polys)
    raise ValueError(f"unexpected geometry type: {geom.geom_type}")


def simplify_round(geom):
    geom = _polygons_only(_valid(geom))
    g = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
    gj = mapping(g)

    def rnd(coords):
        if isinstance(coords[0], (int, float)):
            return [round(c, COORD_DECIMALS) for c in coords]
        return [rnd(c) for c in coords]

    gj["coordinates"] = rnd(gj["coordinates"])
    return gj


def build_lad_level():
    eng = load_features("eng")
    wal = load_features("wal")
    sco = load_features("sco")

    features = []

    # England: pass through untouched codes, then merges + renames
    for code, rec in eng.items():
        if code in ENGLAND_DROP_STANDALONE:
            continue
        features.append((code, rec["name"], rec["geom"]))

    for (new_code, new_name), old_codes in ENGLAND_MERGES.items():
        geoms = [eng[c]["geom"] for c in old_codes]
        features.append((new_code, new_name, unary_union(geoms)))

    for old_code, (new_code, new_name) in ENGLAND_RENAMES.items():
        features.append((new_code, new_name, eng[old_code]["geom"]))

    # Wales: 1:1, no changes needed
    for code, rec in wal.items():
        features.append((code, rec["name"], rec["geom"]))

    # Scotland: dissolve 32 council areas into 18 BRMAs
    by_name = {rec["name"]: rec["geom"] for rec in sco.values()}
    for code, name, members in SCOTLAND_BRMA:
        geoms = [by_name[m] for m in members]
        features.append((code, name, unary_union(geoms)))

    used_sco_names = {m for _, _, members in SCOTLAND_BRMA for m in members}
    all_sco_names = set(by_name)
    assert used_sco_names == all_sco_names, f"Scotland name mismatch: {used_sco_names ^ all_sco_names}"

    codes = [c for c, _, _ in features]
    assert len(codes) == len(set(codes)), "duplicate codes in LAD-level output"

    print(f"LAD-level features: {len(features)}")
    return features


def dissolve_by(features, key_fn):
    """features: list of (code, name, geom, region). Group + union geometries."""
    groups = {}
    for code, name, geom, region in features:
        k = key_fn(code, name, region)
        if k is None:
            continue
        groups.setdefault(k, []).append(geom)
    return {k: unary_union(v) for k, v in groups.items()}


def to_feature_collection(items):
    """items: iterable of (code, name, geom)"""
    feats = []
    for code, name, geom in items:
        feats.append({
            "type": "Feature",
            "properties": {"code": code, "name": name},
            "geometry": simplify_round(geom),
        })
    return {"type": "FeatureCollection", "features": feats}


def build_higher_levels(lad_features):
    """Dissolve LAD-level geoms into English regions + 3 countries, using the
    dataset's own region/country groupings (see prepare_data.py).

    Takes the *raw* (unsimplified, pre-rounding) LAD/BRMA geometries so that
    shared borough/district edges still coincide exactly before they are
    unioned -- dissolving already-simplified-and-rounded polygons leaves
    hairline sliver gaps along old internal boundaries."""
    import openpyxl
    XLSX = "/tmp/claude-0/-home-user-tmp/a52f200a-156f-5ac6-9345-7fea3b75f823/scratchpad/ons/rents.xlsx"
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["Table 1"]
    rows = ws.iter_rows(values_only=True)
    next(rows); next(rows); next(rows)
    code_to_region = {}
    for row in rows:
        code, region = row[1], row[3]
        if code[:3] in ("E06", "E07", "E08", "E09", "W06", "S33"):
            code_to_region[code] = region

    geoms_by_code = {code: geom for code, _, geom in lad_features}

    region_names = {
        "North East": "E12000001", "North West": "E12000002",
        "Yorkshire and The Humber": "E12000003", "East Midlands": "E12000004",
        "West Midlands": "E12000005", "East of England": "E12000006",
        "London": "E12000007", "South East": "E12000008", "South West": "E12000009",
    }
    region_groups = {}
    for code, geom in geoms_by_code.items():
        if code in ("E06000053", "E09000001"):
            region = "London" if code == "E09000001" else "South West"
        else:
            region = code_to_region.get(code)
        if code[:3] == "W06" or code[:3] == "S33":
            continue
        region_groups.setdefault(region, []).append(geom)

    region_items = []
    for region_name, rcode in region_names.items():
        region_items.append((rcode, region_name, unary_union(region_groups[region_name])))
    region_fc = to_feature_collection(region_items)

    wales_geom = unary_union([g for c, g in geoms_by_code.items() if c[:3] == "W06"])
    scotland_geom = unary_union([g for c, g in geoms_by_code.items() if c[:3] == "S33"])
    region_fc["features"].append({
        "type": "Feature", "properties": {"code": "W92000004", "name": "Wales"},
        "geometry": simplify_round(wales_geom),
    })
    region_fc["features"].append({
        "type": "Feature", "properties": {"code": "S92000003", "name": "Scotland"},
        "geometry": simplify_round(scotland_geom),
    })
    with open("/home/user/tmp/gb-rent-map/data/geo_region.json", "w") as f:
        json.dump(region_fc, f, separators=(",", ":"))
    print("geo_region.json bytes:", len(json.dumps(region_fc, separators=(",", ":"))), "features:", len(region_fc["features"]))

    england_geom = unary_union(list(region_groups.values() and [g for gs in region_groups.values() for g in gs]))
    country_items = [
        ("E92000001", "England", england_geom),
        ("W92000004", "Wales", wales_geom),
        ("S92000003", "Scotland", scotland_geom),
    ]
    country_fc = to_feature_collection(country_items)
    with open("/home/user/tmp/gb-rent-map/data/geo_country.json", "w") as f:
        json.dump(country_fc, f, separators=(",", ":"))
    print("geo_country.json bytes:", len(json.dumps(country_fc, separators=(",", ":"))), "features:", len(country_fc["features"]))


if __name__ == "__main__":
    lad_features = build_lad_level()

    lad_fc = to_feature_collection(lad_features)
    with open("/home/user/tmp/gb-rent-map/data/geo_local.json", "w") as f:
        json.dump(lad_fc, f, separators=(",", ":"))
    print("geo_local.json bytes:", len(json.dumps(lad_fc, separators=(',', ':'))))

    build_higher_levels(lad_features)
