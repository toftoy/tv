"""Direkte kilde fra butikkene (Power, Elkjøp) via deres offentlige sitemaps og
schema.org-data (JSON-LD) på produktsidene.

Fanger opp TV-er som Prisjakt mangler (f.eks. utsolgte modeller), og gir lagerstatus.
Bare sitemap- og produktsider brukes; søk/kategori-API-er som er stengt i robots.txt
brukes ikke. Pause mellom kall.
"""
import gzip
import json
import re
import time
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36 tv-prisvakt (privat bruk)")
DELAY = 1.0
_last = 0.0

SHOPS = {
    "Power": {
        "index": "https://www.power.no/services/sitemap.xml",
        "child": r"/services/sitemap/products-\d+\.xml",
        "tv": r"/tv-og-lyd/tv/",
    },
    "Elkjøp": {
        "index": "https://www.elkjop.no/sitemaps/OCNOELK.pdp.index.sitemap.xml",
        "child": r"/sitemaps/OCNOELK\.pdp-\d+\.xml",
        "tv": r"/tv-og-tilbehor/tv/",
    },
}

AVAIL = {"InStock": "InStock", "OutOfStock": "OutOfStock", "BackOrder": "BackOrder",
         "PreOrder": "PreOrder", "SoldOut": "OutOfStock", "Discontinued": "OutOfStock",
         "LimitedAvailability": "InStock", "InStoreOnly": "InStoreOnly", "OnlineOnly": "InStock"}


def get(url, tries=3):
    global _last
    err = None
    for i in range(tries):
        wait = DELAY - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip",
                                                       "Accept-Language": "nb-NO,nb;q=0.9"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or b[:2] == b"\x1f\x8b":
                    b = gzip.decompress(b)
                return b.decode("utf-8", "replace")
        except Exception as e:
            err = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def tv_urls(shop, min_size, max_size, min_year):
    cfg = SHOPS[shop]
    idx = get(cfg["index"])
    urls = []
    for child in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", idx):
        if not re.search(cfg["child"], child):
            continue
        sm = get(child)
        urls += [u for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm) if re.search(cfg["tv"], u)]
    out = []
    for u in dict.fromkeys(urls):
        slug = u.rstrip("/").split("/")[-2 if shop == "Power" or u.rstrip("/").split("/")[-1].isdigit() else -1]
        m = re.search(r"(?:^|-)(\d{2,3})(?:-|$)", slug)
        if not m or not (min_size <= int(m.group(1)) <= max_size):
            continue
        y = re.search(r"(20\d\d)", slug)
        if y and int(y.group(1)) < min_year:
            continue
        out.append((u, int(m.group(1))))
    return out


def product(url):
    h = get(url)
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S):
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue
        nodes = d.get("@graph", [d]) if isinstance(d, dict) else d
        for n in nodes:
            if isinstance(n, dict) and n.get("@type") == "Product" and n.get("offers"):
                offers = n["offers"] if isinstance(n["offers"], list) else [n["offers"]]
                best = None
                for o in offers:
                    ect = o.get("eligibleCustomerType") or {}
                    ect = ect.get("@id", "") if isinstance(ect, dict) else str(ect)
                    if ect.rstrip("/").endswith("Business") or re.search(r"bedrift|b2b|business", (o.get("name") or "").lower()):
                        continue  # bedriftspris (uten mva)
                    try:
                        p = float(o.get("price"))
                    except (TypeError, ValueError):
                        continue
                    if best is None or p < best[0]:
                        best = (p, o)
                if not best:
                    continue
                av = (best[1].get("availability") or "").rsplit("/", 1)[-1]
                img = n.get("image")
                img = img[0] if isinstance(img, list) and img else img
                return {
                    "name": n.get("name"), "mpn": n.get("mpn"), "sku": str(n.get("sku") or ""),
                    "gtin": n.get("gtin13") or n.get("gtin"),
                    "brand": (n.get("brand") or {}).get("name") if isinstance(n.get("brand"), dict) else n.get("brand"),
                    "price": round(best[0]), "stock": AVAIL.get(av, av or "Unknown"),
                    "member": "medlem" in (best[1].get("name") or "").lower() or "member" in (best[1].get("name") or "").lower(),
                    "img": img, "url": url,
                }
    return None


def collect(cfg):
    """Returnerer liste med produkter fra alle butikkene i SHOPS."""
    res = []
    for shop in SHOPS:
        try:
            urls = tv_urls(shop, cfg["min_size"], cfg["max_size"], cfg.get("min_year", 2024))
        except Exception as e:
            print(f"{shop}: klarte ikke lese sitemap: {e}", flush=True)
            continue
        print(f"{shop}: {len(urls)} TV-sider", flush=True)
        for u, size in urls:
            try:
                p = product(u)
            except Exception as e:
                print("FEIL", u, e, flush=True)
                continue
            if p:
                p["shop"], p["size"] = shop, size
                res.append(p)
    return res
