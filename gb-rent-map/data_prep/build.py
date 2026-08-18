import re

ROOT = "/home/user/tmp/gb-rent-map"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_fragment():
    tpl = read(f"{ROOT}/src/app.template.html")
    leaflet_css = read(f"{ROOT}/data_prep/leaflet.css")
    leaflet_js = read(f"{ROOT}/data_prep/leaflet.js")
    geo_local = read(f"{ROOT}/data/geo_local.json")
    geo_region = read(f"{ROOT}/data/geo_region.json")
    geo_country = read(f"{ROOT}/data/geo_country.json")
    rent_data = read(f"{ROOT}/data/rent_data.json")
    app_js = read(f"{ROOT}/src/app.js")

    out = tpl
    out = out.replace("{{LEAFLET_CSS}}", leaflet_css)
    out = out.replace("{{LEAFLET_JS}}", leaflet_js)
    out = out.replace("{{GEO_LOCAL_JSON}}", geo_local)
    out = out.replace("{{GEO_REGION_JSON}}", geo_region)
    out = out.replace("{{GEO_COUNTRY_JSON}}", geo_country)
    out = out.replace("{{RENT_DATA_JSON}}", rent_data)
    out = out.replace("{{APP_JS}}", app_js)
    return out


def wrap_standalone(fragment):
    m = re.search(r"<title>.*?</title>", fragment, re.S)
    title_tag = m.group(0) if m else "<title>Rent Atlas</title>"
    rest = fragment[m.end():] if m else fragment
    return (
        "<!DOCTYPE html>\n"
        '<html lang="cs">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{title_tag}\n"
        '<meta name="description" content="Interaktivní vektorová mapa Velké Británie zobrazující ceny soukromého nájemního bydlení podle ONS (2015–2026).">\n'
        "</head>\n"
        "<body>\n"
        f"{rest}\n"
        "</body>\n"
        "</html>\n"
    )


if __name__ == "__main__":
    fragment = build_fragment()
    with open(f"{ROOT}/dist_artifact_fragment.html", "w", encoding="utf-8") as f:
        f.write(fragment)

    standalone = wrap_standalone(fragment)
    with open(f"{ROOT}/index.html", "w", encoding="utf-8") as f:
        f.write(standalone)

    import os
    print("fragment bytes:", os.path.getsize(f"{ROOT}/dist_artifact_fragment.html"))
    print("standalone bytes:", os.path.getsize(f"{ROOT}/index.html"))
