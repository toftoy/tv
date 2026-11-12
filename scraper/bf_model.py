"""Sannsynlig Black Week-pris.

Kalibrering: for hver TV som fantes i fjor måles forholdet
    laveste pris i Black Month (1. nov – 2. des)  /  laveste pris i aug–okt samme år
fra Prisjakts markedslaveste-historikk. Forholdet grupperes etter modellens alder ved
Black Week (årets modell / fjorårets / eldre) og paneltype (OLED / LCD).

Prediksjon for i år: laveste pris aug–okt i år × kvartilene (25/50/75 %) for gruppen.
"""
import datetime as dt
import re
import statistics

UTC = dt.timezone.utc


def _p(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def window_min(series, start, end):
    """Laveste pris i kraft i [start, end] for en trinnvis serie [[dato, pris, butikk], ...]."""
    s = sorted((x for x in series if x[1] is not None), key=lambda x: x[0])
    before = [x for x in s if _p(x[0]) < start]
    inside = [x for x in s if start <= _p(x[0]) <= end]
    vals = ([before[-1]] if before else []) + inside
    return min(x[1] for x in vals) if vals else None


def covers(series, start, end):
    s = [x for x in series if x[1] is not None]
    return bool(s) and min(_p(x[0]) for x in s) <= start + dt.timedelta(days=14) and max(_p(x[0]) for x in s) >= start


def windows(year):
    return (dt.datetime(year, 8, 1, tzinfo=UTC), dt.datetime(year, 10, 31, 23, 59, tzinfo=UTC),
            dt.datetime(year, 11, 1, tzinfo=UTC), dt.datetime(year, 12, 2, 23, 59, tzinfo=UTC))


def model_year(p):
    m = re.search(r"(20\d\d)$", p.get("family_label") or "") or re.search(r"\((20\d\d)\)", p.get("name") or "")
    return int(m.group(1)) if m else None


def panel(p):
    s = ((p.get("panel") or "") + " " + p.get("name", "")).upper()
    return "OLED" if "OLED" in s and "QNED" not in s else "LCD"


def age_group(age):
    if age is None:
        return "ukjent"
    return "årets modell" if age <= 0 else "fjorårets modell" if age == 1 else "eldre modell"


def _q(vals):
    v = sorted(vals)
    if len(v) < 4:
        return None
    qs = statistics.quantiles(v, n=4)
    return {"q25": round(qs[0], 3), "q50": round(qs[1], 3), "q75": round(qs[2], 3), "n": len(v)}


def fit(history, products, year):
    """Kalibrer på fjorårets Black Week (year = i fjor)."""
    a0, a1, b0, b1 = windows(year)
    rows = []
    for p in products:
        h = history.get(str(p["id"]))
        if not h:
            continue
        ser = h["market"]
        if not covers(ser, a0, b1):
            continue
        ref, bw = window_min(ser, a0, a1), window_min(ser, b0, b1)
        if not ref or not bw:
            continue
        r = bw / ref
        if not (0.4 <= r <= 1.3):
            continue  # urimelig (feildata, utsalg av siste eksemplar e.l.)
        my = model_year(p)
        rows.append({"ratio": r, "age": age_group(year - my if my else None), "panel": panel(p)})
    groups = {}
    for age in {r["age"] for r in rows}:
        for pan in ("OLED", "LCD"):
            q = _q([r["ratio"] for r in rows if r["age"] == age and r["panel"] == pan])
            if q and q["n"] >= 8:
                groups[f"{age}|{pan}"] = q
        q = _q([r["ratio"] for r in rows if r["age"] == age])
        if q:
            groups[f"{age}|*"] = q
    groups["*|*"] = _q([r["ratio"] for r in rows]) or {"q25": 0.9, "q50": 0.95, "q75": 1.0, "n": 0}
    share = {
        "billigere": round(sum(r["ratio"] < 0.98 for r in rows) / max(1, len(rows)), 2),
        "omtrent_likt": round(sum(0.98 <= r["ratio"] <= 1.02 for r in rows) / max(1, len(rows)), 2),
        "dyrere": round(sum(r["ratio"] > 1.02 for r in rows) / max(1, len(rows)), 2),
    }
    return {"year": year, "n": len(rows), "groups": groups, "andel": share}


def predict(model, p, series, year):
    a0, a1, _, _ = windows(year)
    ref = window_min(series, a0, a1)
    if not ref:
        return None
    my = model_year(p)
    age = age_group(year - my if my else None)
    g = model["groups"].get(f"{age}|{panel(p)}") or model["groups"].get(f"{age}|*") or model["groups"]["*|*"]
    key = f"{age}|{panel(p)}" if f"{age}|{panel(p)}" in model["groups"] else (f"{age}|*" if f"{age}|*" in model["groups"] else "*|*")
    return {"low": round(ref * g["q25"] / 10) * 10, "mid": round(ref * g["q50"] / 10) * 10,
            "high": round(ref * g["q75"] / 10) * 10, "ref": ref, "group": key.replace("|*", "").replace("|", ", "),
            "n": g["n"]}
