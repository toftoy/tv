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


ELON_API = "https://www.elon.no/integration/localstores/instocklocation"


def elon(skus, stores, chunk=60):
    """Elon: samme oppslag som «Er varen på lager?» på elon.no, mange varenr per kall, ett kall per butikk.
    stores: {GLN: navn}. Returnerer {varenr: [{"store", "n", "demo"}]}."""
    out = {}
    skus = sorted({str(s) for s in skus if s})
    for gln, name in stores.items():
        for i in range(0, len(skus), chunk):
            body = urllib.parse.urlencode({"gln": gln, "sku": ",".join(skus[i:i + chunk])}).encode()
            req = urllib.request.Request(ELON_API, data=body, headers={
                "User-Agent": UA["User-Agent"], "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
            with urllib.request.urlopen(req, timeout=40) as r:
                j = json.load(r)
            if not j.get("success"):
                raise RuntimeError("Elon: svar uten success")
            for sku, qty in (j.get("data") or {}).items():
                try:
                    n = int(float(qty))
                except (TypeError, ValueError):
                    continue
                if n > 0:
                    out.setdefault(sku, []).append({"store": name, "n": str(n), "demo": 0})
            time.sleep(1)
    return out


def hifiklubben(skus, stores, delay=1.0):
    """Hi-Fi Klubben: produktsiden har butikklageret innebygd (samme som «Se alle butikker» på siden).
    På lager i butikken = beskrivelsen «N stk på lager». /x/<varenr>/ fungerer uansett navnedel.
    stores: {butikk-id: navn}. Returnerer {varenr: [{"store", "n", "demo"}]}."""
    import re
    out, errs = {}, 0
    for sku in sorted({str(s) for s in skus if s}):
        try:
            req = urllib.request.Request(f"https://www.hifiklubben.no/x/{sku.lower()}/",
                                         headers={"User-Agent": UA["User-Agent"]})
            with urllib.request.urlopen(req, timeout=40) as r:
                html = r.read().decode("utf-8", "replace").replace('\\"', '"').replace("\\\\", "\\")
        except Exception:
            errs += 1
            if errs >= 8 and errs > len(out):
                raise RuntimeError(f"Hi-Fi Klubben: {errs} feil")
            continue
        finally:
            time.sleep(delay)
        found = []
        for sid, name in stores.items():
            i = html.find('{"store":{"id":"%s"' % sid)
            if i < 0:
                continue
            try:
                o, _ = json.JSONDecoder().raw_decode(html[i:])
            except ValueError:
                continue
            for p in o.get("products") or []:
                if str(p.get("skuCode", "")).upper() != sku.upper():
                    continue
                m = re.search(r"(\d+)\s*stk på lager", p.get("description") or "")
                if m and int(m.group(1)) > 0:
                    found.append({"store": name, "n": m.group(1), "demo": 1 if p.get("isDemoProduct") else 0})
        if found:
            out[sku] = found
    return out
