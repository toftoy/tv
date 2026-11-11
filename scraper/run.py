"""Daglig kjøring: henter TV-priser fra Prisjakt, oppdaterer data/ og lager prisvarsler.

Bruk:  python scraper/run.py            (henter fra nett)
       CACHE_DIR=sti python scraper/run.py   (bruker lagrede produktsider <id>.html, for testing)
"""
import datetime as dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import families  # noqa: E402
import prisjakt  # noqa: E402
import quality  # noqa: E402
import re  # noqa: E402
import shops as shopsrc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))


def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def save(name, obj, indent=None):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))


def parse_dt(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def lowest(series, days):
    """series: [[iso-dato, pris, butikk], ...] trinnvis (pris gjelder fra dato). Laveste i vinduet."""
    start = NOW - dt.timedelta(days=days)
    s = sorted(series, key=lambda x: x[0])
    before = [x for x in s if parse_dt(x[0]) < start]
    inside = [x for x in s if parse_dt(x[0]) >= start]
    vals = ([before[-1]] if before else []) + inside
    if not vals:
        return None
    m = min(vals, key=lambda x: x[1])
    return {"price": m[1], "shop": m[2], "date": m[0][:10]}


def main():
    os.makedirs(DATA, exist_ok=True)
    history = load("history.json", {})      # pid -> {"market": [[dato,pris,butikk]], "shops": {butikk: [[dato,pris,før,medlem]]}}
    prev = {p["id"]: p for p in load("products.json", {"products": []})["products"]}

    cache = os.environ.get("CACHE_DIR")
    if cache and os.path.exists(os.path.join(cache, "category.json")):
        cat = json.load(open(os.path.join(cache, "category.json"), encoding="utf-8"))
    else:
        cat = prisjakt.category("tv")
    f = CFG["filter"]
    cand = [r for r in cat if r["size"] and f["min_size"] <= r["size"] <= f["max_size"]
            and r["stock"] == "in_stock" and r["offers"] >= f["min_offers"]]
    # Ta alltid med produkter som tidligere har vært hos Elkjøp/Power/Komplett
    ids = {r["id"] for r in cand}
    cand += [r for r in cat if r["id"] in prev and r["id"] not in ids]
    print(f"Kategori: {len(cat)} produkter, {len(cand)} kandidater", flush=True)

    products = []
    for i, r in enumerate(cand):
        try:
            if cache:
                p = os.path.join(cache, f"{r['id']}.html")
                if not os.path.exists(p):
                    continue
                prisjakt.fetch = lambda _path, _p=p: open(_p, encoding="utf-8").read()
            d = prisjakt.product(r["id"])
        except Exception as e:
            print("FEIL", r["id"], e, flush=True)
            continue
        if i % 50 == 0:
            print(f"  {i}/{len(cand)}", flush=True)
        if not d["shops"] and r["id"] not in prev:
            continue
        pid = str(r["id"])
        h = history.setdefault(pid, {"market": [], "shops": {}})
        # Slå sammen Prisjakts markedslaveste-serie (bygger historikk utover 3 mnd over tid)
        seen = {x[0] for x in h["market"]}
        for x in d["history"]:
            if x["date"] not in seen:
                h["market"].append([x["date"], x["price"], x["shop"]])
        h["market"].sort(key=lambda x: x[0])
        # Egen historikk per butikk: lagre når prisen endres
        for shop, o in d["shops"].items():
            lst = h["shops"].setdefault(shop, [])
            if not lst or lst[-1][1] != o["price"]:
                lst.append([NOW.isoformat(timespec="seconds"), o["price"], o["before"], o["member"]])
        for shop in list(h["shops"]):
            if shop not in d["shops"] and h["shops"][shop] and h["shops"][shop][-1][1] is not None:
                h["shops"][shop].append([NOW.isoformat(timespec="seconds"), None, None, False])  # ikke lenger i salg

        extra = [o.get("title") or "" for o in d["shops"].values()] + [o.get("sku") or "" for o in d["shops"].values()]
        fkey, flabel, fsrc = families.family(r["brand"], r["name"], r["size"], extra)
        # Kombinert serie for laveste-beregning: markedsserie + egne butikkpunkter
        series = [x for x in h["market"]] + [
            [x[0], x[1], s] for s, lst in h["shops"].items() for x in lst if x[1] is not None]
        # Laveste pris *før i dag*, slik at dagens tilbud sammenlignes med historikken
        today0 = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
        series = [x for x in series if parse_dt(x[0]) < today0]
        best = min(d["shops"].items(), key=lambda kv: kv[1]["price"]) if d["shops"] else None
        earliest = min((x[0] for x in series), default=None)
        products.append({
            "id": r["id"], "name": r["name"], "brand": r["brand"], "size": r["size"],
            "panel": r["panel"], "hz": r["hz"], "res": r["res"], "img": r["img"], "vesa": d.get("vesa"),
            "rating": r["rating"], "expert": r["expert"],
            "family": fkey, "family_label": flabel, "family_src": fsrc,
            "shops": d["shops"], "market_now": d["market_now"],
            "best": {"shop": best[0], "price": best[1]["price"]} if best else None,
            "low30": lowest(series, 30), "low60": lowest(series, 60),
            "low90": lowest(series, 92), "low365": lowest(series, 365),
            "history_since": earliest[:10] if earliest else None,
            "url": f"https://www.prisjakt.no/product.php?p={r['id']}",
        })

    if CFG.get("shops", {}).get("enabled", True) and not os.environ.get("SKIP_SHOPS"):
        merge_shops(products, history)
    # VESA: forkast urimelige verdier, arv fra andre varianter av samme TV
    for p in products:
        v = p.get("vesa")
        if v and (p.get("size") or 99) <= 50 and max(int(x) for x in v.split("x")) > 400:
            p["vesa"], p["vesa_note"] = None, f"Prisjakt oppgir {v}, trolig feil"
    # Manuelt undersøkte VESA-mål (vesa.json): overstyrer manglende/feil verdier
    vp = os.path.join(ROOT, "vesa.json")
    manual = json.load(open(vp, encoding="utf-8")) if os.path.exists(vp) else []
    by_fam = {m["family"].upper(): m for m in manual if m.get("vesa")}
    by_code = {_norm(m["code"]): m for m in manual if m.get("vesa") and len(_norm(m.get("code"))) >= 6}
    for p in products:
        m = by_fam.get(p["family"])
        if not m:
            codes = [_norm(p["name"].rsplit(" - ", 1)[-1])] + [_norm(o.get("title")) for o in p["shops"].values()]
            m = next((by_code[c] for c in by_code if any(x.startswith(c) or (len(x) >= 6 and c.startswith(x)) for x in codes if x)), None)
        if m and (not p.get("vesa") or p.get("vesa_note")):
            p["vesa"], p["vesa_note"] = m["vesa"], f"undersøkt: {m.get('source', '')}"
    fam_vesa = {}
    for p in products:
        if p.get("vesa"):
            fam_vesa.setdefault(p["family"], p["vesa"])
    for p in products:
        if not p.get("vesa") and p["family"] in fam_vesa:
            p["vesa"], p["vesa_note"] = fam_vesa[p["family"]], "fra annen variant av samme TV"
    for p in products:
        p["quality"], p["quality_basis"] = quality.score(p)
        p["stand"] = stand_fit(p)
    save("quality_tiers.json", {"tiers": [{"pattern": pt, "score": sc, "label": lb} for pt, sc, lb in quality.TIERS],
                                "adjust": quality.ADJUST})
    save("history.json", history)
    save("products.json", {"updated": NOW.isoformat(timespec="seconds"), "products": products})
    print(f"Lagret {len(products)} produkter", flush=True)
    alerts(products, prev)


def stand_fit(p):
    """Passer TV-en på TV-stativet i config.json? 'ja', 'nei' eller None (ukjent)."""
    st = CFG.get("stand")
    if not st:
        return None
    size = p.get("size") or 0
    if size and not (st.get("min_size", 0) <= round(size) <= st.get("max_size", 999)):
        return "nei"
    v = p.get("vesa")
    if not v:
        return None
    w, h = (int(x) for x in v.split("x"))
    return "ja" if w in st["vesa_dims"] and h in st["vesa_dims"] else "nei"


# ---------------- Butikkenes egne sider (Power, Elkjøp) ----------------
def _norm(c):
    return re.sub(r"[^A-Z0-9]", "", (c or "").upper())


def merge_shops(products, history):
    sc = CFG.get("shops", {})
    cache = os.environ.get("SHOPS_CACHE")
    if cache and os.path.exists(cache):
        items = json.load(open(cache, encoding="utf-8"))
    else:
        items = shopsrc.collect({"min_size": sc.get("min_size", CFG["filter"]["min_size"]),
                                 "max_size": sc.get("max_size", CFG["filter"]["max_size"]),
                                 "min_year": sc.get("min_year", 2024)})
    by_sku, codes = {}, []
    for p in products:
        for shop, o in p["shops"].items():
            if o.get("sku"):
                by_sku[(shop, str(o["sku"]))] = p
        toks = set()
        if " - " in p["name"]:
            toks.add(_norm(p["name"].rsplit(" - ", 1)[-1]))
        for o in p["shops"].values():
            toks.update(_norm(t) for t in re.findall(r"\b[A-Z]{0,4}\d{2}[A-Z0-9]{3,}\b", o.get("title") or ""))
        codes.append((p, {t for t in toks if len(t) >= 7}))
    added = matched = 0
    stamp = NOW.isoformat(timespec="seconds")
    today0 = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    for it in items:
        shop, mpn = it["shop"], _norm(it.get("mpn"))
        p = by_sku.get((shop, it["sku"]))
        if not p and mpn:
            for cand, toks in codes:
                if any(mpn.startswith(t) or t.startswith(mpn) for t in toks):
                    p = cand
                    break
        entry = {"price": it["price"], "before": None, "member": it["member"], "title": it["name"],
                 "sku": it["sku"], "stock": it["stock"], "url": it["url"], "source": "butikk"}
        if p:
            matched += 1
            o = p["shops"].get(shop)
            if o:
                o["stock"], o["url"] = it["stock"], it["url"]
                if o["price"] != it["price"] and it["stock"] != "OutOfStock":
                    o["price"] = it["price"]  # butikkens egen side er ferskest
            else:
                p["shops"][shop] = entry
        else:
            added += 1
            brand = it.get("brand") or it["name"].split()[0]
            name = it["name"] + (f" - {it['mpn']}" if it.get("mpn") else "")
            fkey, flabel, fsrc = families.family(brand, name, it["size"], [it.get("mpn") or ""])
            p = {"id": f"{shop[0]}{it['sku']}", "name": name, "brand": brand, "size": it["size"],
                 "panel": None, "hz": None, "res": None, "img": None, "vesa": None, "img_url": it.get("img"),
                 "rating": None, "expert": None, "family": fkey, "family_label": flabel, "family_src": fsrc,
                 "shops": {shop: entry}, "market_now": None, "low30": None, "low60": None, "low90": None,
                 "low365": None, "history_since": None, "url": it["url"], "store_only": True}
            products.append(p)
            codes.append((p, {mpn} if len(mpn) >= 7 else set()))
            by_sku[(shop, it["sku"])] = p
        # historikk per butikk
        h = history.setdefault(str(p["id"]), {"market": [], "shops": {}})
        lst = h["shops"].setdefault(shop, [])
        price = p["shops"][shop]["price"] if it["stock"] != "OutOfStock" else None
        if not lst or lst[-1][1] != price:
            lst.append([stamp, price, None, it["member"]])
        if p.get("store_only"):
            series = [[x[0], x[1], s] for s, l in h["shops"].items() for x in l
                      if x[1] is not None and parse_dt(x[0]) < today0]
            p["low30"], p["low60"] = lowest(series, 30), lowest(series, 60)
            p["low90"], p["low365"] = lowest(series, 92), lowest(series, 365)
    for p in products:
        live = {s: o for s, o in p["shops"].items() if o.get("stock") != "OutOfStock"}
        b = min(live.items(), key=lambda kv: kv[1]["price"]) if live else None
        p["best"] = {"shop": b[0], "price": b[1]["price"]} if b else None
    print(f"Butikksider: {len(items)} lest, {matched} koblet til Prisjakt, {added} nye", flush=True)


# ---------------- Varsling ----------------
def matches(p, w):
    if "id" in w and str(w["id"]) != str(p["id"]):
        return False
    if "family" in w and w["family"].upper() != p["family"]:
        return False
    if "contains" in w and w["contains"].lower() not in (p["name"] + " " + p["family_label"]).lower():
        return False
    if "sizes" in w and int(round(p["size"])) not in w["sizes"]:
        return False
    return True


def alerts(products, prev):
    first_run = not os.path.exists(os.path.join(DATA, "alert_state.json"))
    state = load("alert_state.json", {})
    rules = CFG.get("watch", [])
    lines = []
    for p in products:
        for shop, o in p["shops"].items():
            k = f"{p['id']}|{shop}"
            price = o["price"]
            if o.get("stock") == "OutOfStock":
                continue
            po = ((prev.get(p["id"]) or {}).get("shops") or {}).get(shop) or {}
            back = po.get("stock") == "OutOfStock"
            last = state.get(k)
            if last is not None and price >= last and not back:
                continue  # allerede varslet om denne prisen eller lavere
            for w in rules:
                if not matches(p, w):
                    continue
                why = ["tilbake på lager"] if back else []
                if "max_price" in w and price <= w["max_price"]:
                    why.append(f"under din grense {w['max_price']:,} kr".replace(",", " "))
                l60 = p["low60"]["price"] if p["low60"] else None
                if w.get("on_low60", True) and l60 and price <= l60:
                    why.append(f"laveste pris siste 60 d (var {l60:,.0f} kr)".replace(",", " "))
                if why:
                    state[k] = price
                    lines.append((p, shop, o, why))
                    break
    save("alert_state.json", state, indent=1)
    if first_run:
        print(f"Første kjøring: {len(lines)} treff registrert uten varsel (se dashboardet)")
        return
    if not lines:
        print("Ingen nye varsler")
        return
    body = ["Nye prisvarsler fra TV-prisvakta:\n"]
    for p, shop, o, why in sorted(lines, key=lambda x: x[2]["price"]):
        before = f" (førpris {o['before']:,} kr)".replace(",", " ") if o.get("before") else ""
        mem = " – medlemspris" if o.get("member") else ""
        l90 = p["low90"]["price"] if p["low90"] else None
        body.append(f"- **{p['family_label']}** – {shop}: **{o['price']:,} kr**{before}{mem}".replace(",", " ")
                    + f"  \n  {'; '.join(why)}. Laveste 90 d: {fmt_kr(l90)}. [{p['name']}]({o.get('url') or p['url']})")
    site = CFG.get("site_url")
    if site:
        body.append(f"\nDashboard: {site}")
    text = "\n".join(body)
    print(text)
    title = f"Prisvarsel {TODAY}: {len(lines)} TV-er"
    create_issue(title, text)


def fmt_kr(v):
    return f"{v:,.0f} kr".replace(",", " ") if v is not None else "ukjent"


def create_issue(title, body):
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("(Ikke i GitHub Actions – oppretter ikke issue)")
        return
    owner = repo.split("/")[0]
    data = json.dumps({"title": title, "body": body + f"\n\n@{owner}", "labels": ["prisvarsel"]}).encode()
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues", data=data, method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        print("Opprettet issue:", json.load(r).get("html_url"))


if __name__ == "__main__":
    main()
