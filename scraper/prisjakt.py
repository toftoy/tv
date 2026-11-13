"""Henter og tolker offentlige sider fra Prisjakt.no (kategori- og produktsider).

Bruker kun sider som er tillatt i prisjakt.no/robots.txt, med pause mellom kall.
"""
import json
import re
import time
import urllib.request

BASE = "https://www.prisjakt.no"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36 tv-prisvakt (privat bruk)")
SHOPS = {324: "Elkjøp", 30366: "Power", 9782: "Komplett", 10626: "NetOnNet", 10982: "Multicom", 29990: "Samsung"}
DELAY = 1.0
_last = 0.0


def fetch(path, tries=3):
    global _last
    for i in range(tries):
        wait = DELAY - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            req = urllib.request.Request(BASE + path, headers={"User-Agent": UA, "Accept-Language": "nb-NO,nb;q=0.9"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # nettverksfeil: prøv igjen med økende pause
            err = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"Klarte ikke hente {path}: {err}")


# ---------- window.__REACT_QUERY_STATE__ (kategorisider) ----------
_ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def _unescape_js(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c != "\\":
            out.append(c); i += 1; continue
        e = s[i + 1]
        if e == "x":
            out.append(chr(int(s[i + 2:i + 4], 16))); i += 4
        elif e == "u":
            out.append(chr(int(s[i + 2:i + 6], 16))); i += 6
        elif e in _ESC:
            out.append(_ESC[e]); i += 2
        else:
            out.append(e); i += 2
    return "".join(out)


def js_state(html, key):
    p = "window.%s = JSON.parse('" % key
    i = html.find(p)
    if i < 0:
        return None
    i += len(p); j = i
    while True:
        j = html.find("')", j)
        bs, t = 0, j - 1
        while html[t] == "\\":
            bs += 1; t -= 1
        if bs % 2 == 0:
            break
        j += 1
    s = _unescape_js(html[i:j]).encode("utf-16", "surrogatepass").decode("utf-16")
    return json.loads(s)


# ---------- Next.js flight-data (produktsider) ----------
def flight(html):
    out = []
    for m in re.finditer(r"self\.__next_f\.push\((\[.*?\])\)</script>", html, re.S):
        try:
            a = json.loads(m.group(1))
            if len(a) > 1 and isinstance(a[1], str):
                out.append(a[1])
        except Exception:
            pass
    return "".join(out)


def find_obj(txt, key):
    res, dec, i = [], json.JSONDecoder(), 0
    while True:
        i = txt.find('"%s":' % key, i)
        if i < 0:
            return res
        j = i + len(key) + 3
        try:
            o, _ = dec.raw_decode(txt, j)
            res.append(o)
        except Exception:
            pass
        i = j


# ---------- Kategorien ----------
def category(slug="tv"):
    """Returnerer alle produkter i kategorien (alle sider)."""
    rows, offset, pages = {}, 0, None
    while True:
        html = fetch(f"/c/{slug}" + (f"?offset={offset}" if offset else ""))
        d = js_state(html, "__REACT_QUERY_STATE__")
        slices = d["queries"][0]["state"]["data"]["productCollection"]["slices"]
        n = 0
        for s in slices:
            if s["__typename"] == "HeaderBlockSlice":
                pages = s["pagination"]["pages"]
            if s["__typename"] != "ProductsSlice":
                continue
            for p in s["products"]:
                n += 1
                props = {x["id"]: x for x in p["properties"]["nodes"]}
                rows[p["id"]] = dict(
                    id=p["id"], name=p["name"], brand=p["brand"]["name"],
                    stock=p["stockStatus"],
                    size=(props.get("89") or {}).get("number"),
                    panel=(props.get("113496") or {}).get("pretty"),
                    hz=(props.get("106741") or {}).get("pretty"),
                    res=(props.get("2") or {}).get("pretty"),
                    price=p["priceSummary"].get("regular"),
                    offers=p["priceSummary"].get("count") or 0,
                    img=(p.get("media") or {}).get("first"),
                    rating=(p.get("userReviewSummary") or {}).get("rating"),
                    expert=p.get("isExpertTopRated"),
                )
        offset += 44
        if n == 0 or (pages and offset >= pages * 44):
            return list(rows.values())


# ---------- Produktside ----------
def price_history(pid, time_range="TWO_YEARS"):
    """Prisjakts prishistorikk (laveste i markedet over tid) via nettsidens eget API."""
    global _last
    wait = DELAY - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    body = json.dumps({"productId": int(pid), "timeRange": time_range, "shopIds": [], "variantIds": []}).encode()
    req = urllib.request.Request(BASE + "/api/price-history", data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    return [dict(date=x["date"], price=x["price"] / 100, shop=x["shopName"], member=x.get("isMembershipPrice", False))
            for x in (d.get("priceHistory") or {}).get("historyItems", [])]


SPEC_KEYS = ("Oppdateringsfrekvens", "HDR-format", "Bakbelysningsteknologi", "Type synkronisering",
             "HDMI-standarder", "Antall HDMI-innganger", "Operativsystem", "Integrerte høyttalere")


def specs(html):
    """Utvalgte tekniske egenskaper fra produktsidens spesifikasjonstabell."""
    out = {}
    for m in re.finditer(r'>([^<>]{3,60})</p><p class="text-body-small text-text-tertiary[^>]*>([^<]{1,120})<', html):
        k, v = m.group(1).strip(), m.group(2).strip()
        if k in SPEC_KEYS and k not in out:
            out[k] = v.replace("&quot;", '"')
    return out


def vesa(html):
    m = re.search(r"VESA-feste \(størrelse\)</p>.*?>([^<]{3,40})</", html, re.S)
    if not m:
        return None
    d = re.findall(r"\d{2,4}", m.group(1))
    return f"{d[0]}x{d[1]}" if len(d) >= 2 else None


def product(pid):
    html = fetch(f"/product.php?p={pid}")
    t = flight(html)
    ph = find_obj(t, "priceHistory")
    ph = ph[0] if ph and isinstance(ph[0], dict) else {}
    history = [
        dict(date=x["date"], price=x["price"] / 100, shop=x["shopName"], member=x.get("isMembershipPrice", False))
        for x in ph.get("historyItems", [])
    ]
    offers = find_obj(t, "offerRows")
    offers = offers[0] if offers and isinstance(offers[0], list) else []
    shops, market_now = {}, None
    for r in offers:
        if not isinstance(r, dict) or r.get("condition") not in (None, "New"):
            continue
        p = (r.get("price") or {}).get("amount")
        if p is None:
            continue
        market_now = p if market_now is None else min(market_now, p)
        name = SHOPS.get(r.get("shopId"))
        if not name:
            continue
        op = r.get("originalPrice")
        op = op.get("amount") if isinstance(op, dict) else None
        if name not in shops or p < shops[name]["price"]:
            shops[name] = dict(price=p, before=op if op and op > p else None,
                               member=r.get("priceType") == "MemberPrice",
                               title=r.get("name"), sku=r.get("shopOfferId"),
                               stock=r.get("stockStatus"))
    return dict(history=history, shops=shops, market_now=market_now, vesa=vesa(html), specs=specs(html))
