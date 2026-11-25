"""Lagerstatus i fysiske butikker i et område (Bergensområdet).

Elkjøp: samme søkeindeks (Algolia) som elkjop.no bruker for «på lager i butikk».
Én nøkkel hentes fra elkjop.no, deretter noen få søkekall for TV-er som er på lager i
minst én av butikkene i config.json -> local_stores. Godkjent av eieren for privat bruk.
"""
import json
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tv-prisvakt (privat bruk)",
      "Referer": "https://www.elkjop.no/", "Origin": "https://www.elkjop.no"}
ALG = "https://z0fl7r8ubh-dsn.algolia.net/1/indexes/commerce_b2c_OCNOELK"


def _json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def elkjop(stores):
    """stores: {butikk-id: navn}. Returnerer {varenr: [{"store", "n", "demo"}]} for TV-er på lager."""
    key = None
    for i in range(3):
        try:
            key = _json("https://www.elkjop.no/api/algolia/signed-api-key", UA)["apiKey"]
            break
        except Exception:
            if i == 2:
                raise
            time.sleep(10 * (i + 1))
    h = {**UA, "X-Algolia-Application-Id": "Z0FL7R8UBH", "X-Algolia-API-Key": key}
    filt = "productTaxonomy.id:PT351 AND (" + " OR ".join(f"storesWithStock:{s}" for s in stores) + ")"
    out, page = {}, 0
    while True:
        q = urllib.parse.urlencode({"filters": filt, "hitsPerPage": 100, "page": page, "query": "",
                                    "attributesToRetrieve": "articleNumber,departmentStock",
                                    "attributesToHighlight": ""})
        j = _json(f"{ALG}?{q}", h)
        for hit in j["hits"]:
            ds = hit.get("departmentStock") or {}
            lst = []
            for sid, name in stores.items():
                d = ds.get(sid) or {}
                if d.get("inStock"):
                    lst.append({"store": name, "n": str(d.get("display") or ""),
                                "demo": int(d.get("onDisplayAmount") or 0)})
            if lst:
                out[str(hit["articleNumber"])] = lst
        page += 1
        if page >= j.get("nbPages", 0) or page > 20:
            break
        time.sleep(0.5)
    return out
