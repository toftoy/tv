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
            "panel": r["panel"], "hz": r["hz"], "res": r["res"], "img": r["img"],
            "rating": r["rating"], "expert": r["expert"],
            "family": fkey, "family_label": flabel, "family_src": fsrc,
            "shops": d["shops"], "market_now": d["market_now"],
            "best": {"shop": best[0], "price": best[1]["price"]} if best else None,
            "low30": lowest(series, 30), "low60": lowest(series, 60),
            "low90": lowest(series, 92), "low365": lowest(series, 365),
            "history_since": earliest[:10] if earliest else None,
            "url": f"https://www.prisjakt.no/product.php?p={r['id']}",
        })

    save("history.json", history)
    save("products.json", {"updated": NOW.isoformat(timespec="seconds"), "products": products})
    print(f"Lagret {len(products)} produkter", flush=True)
    alerts(products, prev)


# ---------------- Varsling ----------------
def matches(p, w):
    if "id" in w and int(w["id"]) != p["id"]:
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
            last = state.get(k)
            if last is not None and price >= last:
                continue  # allerede varslet om denne prisen eller lavere
            for w in rules:
                if not matches(p, w):
                    continue
                why = []
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
                    + f"  \n  {'; '.join(why)}. Laveste 90 d: {l90:,.0f} kr. [{p['name']}]({p['url']})".replace(",", " "))
    site = CFG.get("site_url")
    if site:
        body.append(f"\nDashboard: {site}")
    text = "\n".join(body)
    print(text)
    title = f"Prisvarsel {TODAY}: {len(lines)} TV-er"
    create_issue(title, text)


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
