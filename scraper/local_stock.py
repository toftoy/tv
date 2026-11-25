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


POWER_API = "https://www.power.no/api/v2/products/{}/stores?postalCode={}"


def power(skus, stores, postal="5003", delay=0.7):
    """Power: én forespørsel per produkt (samme som «Se tilgjengelighet i butikk» på produktsiden).
    storeAvailability: 2 = på lager, 1 = ikke på lager, 4/5 = kan bestilles til butikk.
    Returnerer ({varenr: [{"store", "n", "demo"}]}, antall feil)."""
    out, errs = {}, 0
    for sku in skus:
        try:
            data = _json(POWER_API.format(sku, postal), {"User-Agent": UA["User-Agent"], "Accept": "application/json"})
        except Exception:
            errs += 1
            if errs >= 10 and errs > len(out):
                raise RuntimeError(f"Power butikklager: {errs} feil")
            continue
        finally:
            time.sleep(delay)
        lst = [{"store": stores[str(s["storeId"])], "n": "", "demo": int(s.get("storeDisplayStock") or 0)}
               for s in data if str(s.get("storeId")) in stores and s.get("storeAvailability") == 2]
        if lst:
            out[str(sku)] = lst
    return out, errs
