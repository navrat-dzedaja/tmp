"""
Extract the ONS Price Index of Private Rents (Table 1) into a compact JSON
structure keyed by area code, ready to embed in the map page.

Only "All property types", "1 bed", "2 bed", "3 bed" and "4 or more bed" are
kept (dwelling-type breakdown -- detached/semi/terraced/flat -- is dropped)
to keep the embedded payload small; monthly/annual % change is computed
client-side from the index series rather than stored twice.
"""
import json
import openpyxl

XLSX = "/tmp/claude-0/-home-user-tmp/a52f200a-156f-5ac6-9345-7fea3b75f823/scratchpad/ons/rents.xlsx"

# (output key, column index of Index, column index of Rental price)
CATEGORIES = [
    ("all", 4, 7),
    ("bed1", 8, 11),
    ("bed2", 12, 15),
    ("bed3", 16, 19),
    ("bed4", 20, 23),
]

LOCAL_PREFIXES = ("E06", "E07", "E08", "E09", "W06", "S33")
REGION_CODES = {f"E1200000{i}" for i in range(1, 10)} | {"W92000004", "S92000003"}
COUNTRY_CODES = {"E92000001", "W92000004", "S92000003"}


def clean(v):
    if isinstance(v, (int, float)):
        return v
    return None  # "[x]" not applicable, "[z]" not applicable, blanks


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["Table 1"]
    rows = ws.iter_rows(values_only=True)
    next(rows); next(rows); next(rows)  # skip title/blank/header

    months = []
    areas = {}  # code -> {"name":..., "series": {cat: {"index":[...], "price":[...]}}}

    for row in rows:
        t, code, name = row[0], row[1], row[2]
        if code is None:
            continue
        region = row[3]
        if code not in areas:
            areas[code] = {
                "name": name,
                "region": region if isinstance(region, str) and region != "[z]" else None,
                "series": {cat: {"index": [], "price": []} for cat, _, _ in CATEGORIES},
            }
        rec = areas[code]
        for cat, idx_col, price_col in CATEGORIES:
            rec["series"][cat]["index"].append(clean(row[idx_col]))
            rec["series"][cat]["price"].append(clean(row[price_col]))

    # months: derive from any one area's row count == len(months); rebuild from first pass
    wb2 = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws2 = wb2["Table 1"]
    rows2 = ws2.iter_rows(values_only=True)
    next(rows2); next(rows2); next(rows2)
    seen_for_uk = False
    for row in rows2:
        if row[1] == "K02000001":
            months.append(row[0].strftime("%Y-%m"))
    print("months:", len(months), months[0], "..", months[-1])

    # round for size: index to 1dp, price already integer
    for rec in areas.values():
        for cat_series in rec["series"].values():
            cat_series["index"] = [round(v, 1) if v is not None else None for v in cat_series["index"]]

    def subset(codes_filter):
        out = {}
        for code, rec in areas.items():
            if codes_filter(code):
                out[code] = rec
        return out

    local = subset(lambda c: c.startswith(LOCAL_PREFIXES))
    region = subset(lambda c: c in REGION_CODES)
    country = subset(lambda c: c in COUNTRY_CODES)
    uk_gb = subset(lambda c: c in ("K02000001", "K03000001"))

    payload = {
        "months": months,
        "categories": {
            "all": "Vše",
            "bed1": "1 ložnice",
            "bed2": "2 ložnice",
            "bed3": "3 ložnice",
            "bed4": "4+ ložnice",
        },
        "levels": {
            "local": local,
            "region": region,
            "country": country,
        },
        "national": uk_gb,
    }

    out_path = "/home/user/tmp/gb-rent-map/data/rent_data.json"
    with open(out_path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    sz = len(json.dumps(payload, separators=(",", ":")))
    print("rent_data.json bytes:", sz, f"({sz/1_000_000:.2f} MB)")
    print("local areas:", len(local), "region areas:", len(region), "country areas:", len(country))


if __name__ == "__main__":
    main()
