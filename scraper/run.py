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
import bf_model  # noqa: E402
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


OSLO = __import__("zoneinfo").ZoneInfo("Europe/Oslo")
PRO = re.compile(r"hotel|hospitality|signage|skilt|infoskjerm|bedrift|business|b-line|\bHG\d\d|\bBE\d\dF|\bLH\d\d|DM66|PK640|UK660|BFL\d", re.I)


def oslo_date(iso):
    return parse_dt(iso).astimezone(OSLO).date().isoformat()


def lowest(series, days):
    """series: [[iso-dato, pris, butikk], ...] trinnvis (pris gjelder fra dato). Laveste i vinduet."""
    start = NOW - dt.timedelta(days=days)
    s = sorted(bf_model.clean(series), key=lambda x: x[0])
    before = [x for x in s if parse_dt(x[0]) < start]
    inside = [x for x in s if parse_dt(x[0]) >= start]
    vals = ([before[-1]] if before else []) + inside
    if not vals:
        return None
    m = min(vals, key=lambda x: x[1])
    return {"price": m[1], "shop": m[2], "date": oslo_date(m[0])}


def lowest_multi(serieses, days):
    """Laveste over flere trinnvise serier (marked + hver butikk), beregnet per serie."""
    lows = [x for x in (lowest(s, days) for s in serieses if s) if x]
    return min(lows, key=lambda x: x["price"]) if lows else None


def series_of(h, before=None):
    """Markedsserien og hver butikkserie som egne trinnvise serier [[dato, pris, butikk]]."""
    out = [list(h.get("market", []))]
    for shop, lst in h.get("shops", {}).items():
        out.append([[x[0], x[1], shop] for x in lst])
    if before:
        out = [[x for x in s if parse_dt(x[0]) < before] for s in out]
    return out


def main():
    os.makedirs(DATA, exist_ok=True)
    history = load("history.json", {})      # pid -> {"market": [[dato,pris,butikk]], "shops": {butikk: [[dato,pris,før,medlem]]}}
    prev = {p["id"]: p for p in load("products.json", {"products": []})["products"]}
    sources = {}

    cache = os.environ.get("CACHE_DIR")
    if cache and os.path.exists(os.path.join(cache, "category.json")):
        cat = json.load(open(os.path.join(cache, "category.json"), encoding="utf-8"))
    else:
        cat = prisjakt.category("tv")
    flt = CFG["filter"]
    in_range = lambda r: r["size"] and flt["min_size"] <= r["size"] <= flt["max_size"]  # noqa: E731
    cand = [r for r in cat if in_range(r) and r["stock"] == "in_stock" and r["offers"] >= flt["min_offers"]]
    # Ta alltid med produkter vi har fulgt før (innenfor størrelsesområdet)
    ids = {r["id"] for r in cand}
    cand += [r for r in cat if r["id"] in prev and r["id"] not in ids and in_range(r)]
    print(f"Kategori: {len(cat)} produkter, {len(cand)} kandidater", flush=True)

    products, fails, consecutive = [], 0, 0
    sec = set(CFG.get("secondary_shops", []))
    for i, r in enumerate(cand):
        try:
            if cache:
                cp = os.path.join(cache, f"{r['id']}.html")
                if not os.path.exists(cp):
                    continue
                prisjakt.fetch = lambda _path, _p=cp: open(_p, encoding="utf-8").read()
            d = prisjakt.product(r["id"])
            consecutive = 0
        except Exception as e:
            print("FEIL", r["id"], e, flush=True)
            fails += 1
            consecutive += 1
            if consecutive >= 25:
                print("Avbryter: 25 feil på rad – Prisjakt blokkerer trolig. Lagrer ingenting.", flush=True)
                sys.exit(1)
            continue
        if i % 50 == 0:
            print(f"  {i}/{len(cand)}", flush=True)
        if not d["shops"] and r["id"] not in prev:
            continue
        if d["shops"] and set(d["shops"]) <= sec:
            continue  # bare hos «sekundære» butikker (f.eks. Multicom)
        if PRO.search(r["name"]):
            continue  # hotell-/bedrifts-/skiltskjermer
        h = history.setdefault(str(r["id"]), {"market": [], "shops": {}})
        seen = {x[0] for x in h["market"]}
        for x in d["history"]:
            if x["date"] not in seen:
                h["market"].append([x["date"], x["price"], x["shop"]])
        if not h.get("long"):  # to års historikk fra Prisjakts API, én gang per produkt
            lc = os.environ.get("LONG_CACHE")
            try:
                if lc:
                    lf = os.path.join(lc, f"{r['id']}.json")
                    long = json.load(open(lf)) if os.path.exists(lf) else None
                else:
                    long = prisjakt.price_history(r["id"])
                if long is not None:
                    seen = {x[0] for x in h["market"]}
                    h["market"] += [[x["date"], x["price"], x["shop"]] for x in long if x["date"] not in seen]
                    h["long"] = TODAY
            except Exception as e:
                print("Historikk-API feilet", r["id"], e, flush=True)
        h["market"].sort(key=lambda x: x[0])
        extra = [o.get("title") or "" for o in d["shops"].values()] + [o.get("sku") or "" for o in d["shops"].values()]
        fkey, flabel, fsrc = families.family(r["brand"], r["name"], r["size"], extra)
        products.append({
            "id": r["id"], "name": r["name"], "brand": r["brand"], "size": r["size"],
            "panel": r["panel"], "hz": r["hz"], "res": r["res"], "img": r["img"], "vesa": d.get("vesa"), "specs": d.get("specs") or {},
            "rating": r["rating"], "expert": r["expert"],
            "family": fkey, "family_label": flabel, "family_src": fsrc,
            "shops": d["shops"], "market_now": d["market_now"],
            "url": f"https://www.prisjakt.no/product.php?p={r['id']}",
        })
    sources["Prisjakt"] = {"ok": len(products), "feil": fails}

    # Vern mot delvis innhenting: ikke overskriv gode data med en halv kjøring
    prev_pj = sum(1 for k in prev if isinstance(k, int))
    if prev_pj and len(products) < 0.6 * prev_pj and not cache:
        print(f"Avbryter: bare {len(products)} Prisjakt-produkter mot {prev_pj} sist. Lagrer ingenting.", flush=True)
        sys.exit(1)

    if CFG.get("shops", {}).get("enabled", True) and not os.environ.get("SKIP_SHOPS"):
        sources.update(merge_shops(products, history))

    # Egen historikk per butikk: skrives én gang, fra endelig tilstand (utsolgt = None)
    stamp = NOW.isoformat(timespec="seconds")
    for p in products:
        h = history.setdefault(str(p["id"]), {"market": [], "shops": {}})
        h["seen"] = TODAY
        for shop, o in p["shops"].items():
            lst = h["shops"].setdefault(shop, [])
            price = None if o.get("stock") == "OutOfStock" else o["price"]
            if not lst or lst[-1][1] != price:
                lst.append([stamp, price, o.get("before"), o.get("member")])
        for shop, lst in h["shops"].items():
            if shop not in p["shops"] and lst and lst[-1][1] is not None:
                lst.append([stamp, None, None, False])  # ikke lenger i salg
    # Laveste priser *før i dag*, per serie
    today0 = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    for p in products:
        h = history[str(p["id"])]
        ss = series_of(h, before=today0)
        for key, days in (("low30", 30), ("low60", 60), ("low90", 90), ("low365", 365)):
            p[key] = lowest_multi(ss, days)
        allpts = [x[0] for s in series_of(h) for x in s if x[1] is not None]
        first = min(allpts, default=None)
        p["history_since"] = oslo_date(first) if first else None
        p["history_days"] = (NOW - parse_dt(first)).days if first else 0
        live = {s: o for s, o in p["shops"].items() if o.get("stock") != "OutOfStock"}
        b = min(live.items(), key=lambda kv: kv[1]["price"]) if live else None
        p["best"] = {"shop": b[0], "price": b[1]["price"]} if b else None
        if not p.get("panel"):  # butikkprodukter: utled paneltype fra navnet
            n = p["name"].upper()
            p["panel"] = ("OLED" if "OLED" in n and "QNED" not in n else "Mini-LED" if re.search(r"MINI.?LED", n)
                          else "QLED" if re.search(r"QLED|QNED|NANO", n) else "LED")

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
            p["vesa"], p["vesa_note"] = m["vesa"], f"undersøkt ({m.get('confidence') or '?'} sikkerhet): {m.get('source', '')}"
            p["vesa_conf"] = m.get("confidence")
    fam_vesa = {}
    for p in products:
        if p.get("vesa"):
            fam_vesa.setdefault(p["family"], p["vesa"])
    for p in products:
        if not p.get("vesa") and p["family"] in fam_vesa:
            p["vesa"], p["vesa_note"] = fam_vesa[p["family"]], "fra annen variant av samme TV"
    # Del egenskaper innen familien (varianter av samme TV), og Hz fra butikktitler
    fam_specs, fam_hz = {}, {}
    for p in products:
        fs = fam_specs.setdefault(p["family"], {})
        for k, v in (p.get("specs") or {}).items():
            fs.setdefault(k, v)
        hz = fam_hz.setdefault(p["family"], set())
        if p.get("hz"):
            hz.add(p["hz"])
        for o in p["shops"].values():
            hz.update(re.findall(r"\d{2,3}\s*Hz", o.get("title") or ""))
    for p in products:
        p["specs"] = {**fam_specs.get(p["family"], {}), **(p.get("specs") or {})}
        p["family_hz"] = sorted(fam_hz.get(p["family"], []))
    for p in products:
        p["quality"], p["quality_basis"] = quality.score(p, CFG.get("quality_profile"))
        p["stand"] = stand_fit(p)
    # Sannsynlig Black Month-pris (bf_model v2), kalibrert på fjorårets Black Month
    cal = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bw_calibration.json")
    model = json.load(open(cal, encoding="utf-8")) if os.path.exists(cal) else bf_model.fit(
        {k: v.get("market", []) for k, v in history.items()}, NOW.year - 1)
    for p in products:
        h = history.get(str(p["id"]), {})
        ser = list(h.get("market", [])) + [[x[0], x[1]] for l in h.get("shops", {}).values() for x in l]
        p["bw"] = bf_model.predict(model, ser, NOW, (p.get("best") or {}).get("price"))
    print(f"Black Month-modell: kalibrert på {model.get('n')} TV-er fra {model.get('year')}", flush=True)
    save("quality_tiers.json", {"tiers": [{"pattern": pt, "score": sc, "label": lb} for pt, sc, lb in quality.TIERS],
                                "adjust": quality.ADJUST})
    # Rydd historikk: behold produkter som er med nå eller sett siste 30 dager
    keep = {str(p["id"]) for p in products}
    cutoff = (NOW - dt.timedelta(days=30)).date().isoformat()
    for k in list(history):
        if k not in keep and history[k].get("seen", "0000") < cutoff:
            del history[k]
    save("history.json", history)
    save("products.json", {"updated": NOW.isoformat(timespec="seconds"), "sources": sources,
                           "bw_active": any(p.get("bw") for p in products), "products": products})
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
    """Kobler Power/Elkjøp sine egne produktsider til Prisjakt-produktene. Returnerer kildestatus."""
    sc = CFG.get("shops", {})
    cache = os.environ.get("SHOPS_CACHE")
    if cache and os.path.exists(cache):
        items, status = json.load(open(cache, encoding="utf-8")), {}
    else:
        items, status = shopsrc.collect({"min_size": sc.get("min_size", CFG["filter"]["min_size"]),
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
    added = matched = skipped = 0
    watch = CFG.get("watch", [])
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
        old_id = f"{shop[0]}{it['sku']}"
        if p:
            matched += 1
            o = p["shops"].get(shop)
            if o:
                o["stock"], o["url"] = it["stock"], it["url"]
                if o["price"] != it["price"] and it["stock"] != "OutOfStock":
                    o["price"] = it["price"]  # butikkens egen side er ferskest
            else:
                p["shops"][shop] = entry
            # Tidligere «kun i butikk»-produkt som nå finnes på Prisjakt: flytt historikken
            if str(p["id"]) != old_id and old_id in history:
                h = history.setdefault(str(p["id"]), {"market": [], "shops": {}})
                for sh, lst in history.pop(old_id).get("shops", {}).items():
                    h["shops"][sh] = sorted(lst + h["shops"].get(sh, []), key=lambda x: x[0])
        else:
            if PRO.search(it["name"]):
                continue
            brand = it.get("brand") or it["name"].split()[0]
            name = it["name"] + (f" - {it['mpn']}" if it.get("mpn") else "")
            fkey, flabel, fsrc = families.family(brand, name, it["size"], [it.get("mpn") or ""])
            p = {"id": old_id, "name": name, "brand": brand, "size": it["size"],
                 "panel": None, "hz": None, "res": None, "img": None, "vesa": None, "img_url": it.get("img"),
                 "rating": None, "expert": None, "family": fkey, "family_label": flabel, "family_src": fsrc,
                 "shops": {shop: entry}, "market_now": None, "url": it["url"], "store_only": True}
            # Utsolgte butikkprodukter tas bare med hvis de er på overvåkingslisten eller fulgt før
            if it["stock"] == "OutOfStock" and old_id not in history and not any(
                    matches(dict(p, family_label=flabel), w) for w in watch):
                skipped += 1
                continue
            added += 1
            products.append(p)
            codes.append((p, {mpn} if len(mpn) >= 7 else set()))
            by_sku[(shop, it["sku"])] = p
    print(f"Butikksider: {len(items)} lest, {matched} koblet til Prisjakt, {added} nye, {skipped} utsolgte hoppet over",
          flush=True)
    return status


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
    old_state = load("alert_state.json", {})
    state = dict(old_state)
    rules = CFG.get("watch", [])
    lines = []
    for p in products:
        for shop, o in p["shops"].items():
            k = f"{p['id']}|{shop}"
            price = o["price"]
            if o.get("stock") == "OutOfStock":
                continue
            last = state.get(k)
            if last is not None and price > last * 1.02:
                state.pop(k)  # prisen har steget igjen: nytt varsel neste gang den faller
                last = None
            po = ((prev.get(p["id"]) or {}).get("shops") or {}).get(shop) or {}
            back = po.get("stock") == "OutOfStock"
            if last is not None and price >= last and not back:
                continue  # allerede varslet om denne prisen eller lavere
            for w in rules:
                if not matches(p, w):
                    continue
                why = ["tilbake på lager"] if back else []
                if "max_price" in w and price <= w["max_price"]:
                    why.append(f"under din grense {w['max_price']:,} kr".replace(",", " "))
                bw = p.get("bw")
                if w.get("on_bw", True) and bw and price <= bw["mid"]:
                    why.append(f"i forventet Black Week-nivå ({bw['low']:,}–{bw['high']:,} kr)".replace(",", " "))
                l60 = p["low60"]["price"] if p.get("low60") else None
                if w.get("on_low60", True) and l60 and price <= l60 and p.get("history_days", 0) >= 60:
                    why.append(f"laveste pris siste 60 d (var {l60:,.0f} kr)".replace(",", " "))
                if why:
                    state[k] = price
                    lines.append((p, shop, o, why))
                    break
    if first_run:
        save("alert_state.json", state, indent=1)
        print(f"Første kjøring: {len(lines)} treff registrert uten varsel (se dashboardet)")
        return
    if not lines:
        save("alert_state.json", state, indent=1)
        print("Ingen nye varsler")
        return
    body = ["Nye prisvarsler fra TV-prisvakta:\n"]
    for p, shop, o, why in sorted(lines, key=lambda x: x[2]["price"]):
        before = f" (førpris {o['before']:,} kr)".replace(",", " ") if o.get("before") else ""
        mem = " – medlemspris" if o.get("member") else ""
        l90 = p["low90"]["price"] if p.get("low90") else None
        body.append(f"- **{p['family_label']}** – {shop}: **{o['price']:,} kr**{before}{mem}".replace(",", " ")
                    + f"  \n  {'; '.join(why)}. Laveste 90 d: {fmt_kr(l90)}. [{p['name']}]({o.get('url') or p['url']})")
    site = CFG.get("site_url")
    if site:
        body.append(f"\nDashboard: {site}")
    text = "\n".join(body)
    print(text)
    try:
        create_issue(f"Prisvarsel {TODAY}: {len(lines)} TV-er", text)
        save("alert_state.json", state, indent=1)
    except Exception as e:
        # Varselet ble ikke levert: behold gammel tilstand så det prøves igjen neste kjøring
        print("Klarte ikke opprette varsel:", e, flush=True)
        save("alert_state.json", old_state, indent=1)


def fmt_kr(v):
    return f"{v:,.0f} kr".replace(",", " ") if v is not None else "ukjent"


def gh(method, path, data=None):
    token, repo = os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"]
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}{path}", method=method,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def create_issue(title, body):
    if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GITHUB_REPOSITORY"):
        print("(Ikke i GitHub Actions – oppretter ikke issue)")
        return
    owner = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    new = gh("POST", "/issues", {"title": title, "body": body + f"\n\n@{owner}", "labels": ["prisvarsel"]})
    print("Opprettet issue:", new.get("html_url"))
    try:  # lukk eldre prisvarsler så listen holder seg ryddig
        for old in gh("GET", "/issues?labels=prisvarsel&state=open&per_page=50"):
            if old["number"] != new["number"]:
                gh("PATCH", f"/issues/{old['number']}", {"state": "closed", "state_reason": "completed"})
    except Exception as e:
        print("Klarte ikke lukke gamle varsler:", e, flush=True)


if __name__ == "__main__":
    main()
