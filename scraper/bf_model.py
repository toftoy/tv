"""Sannsynlig Black Week-/Black Month-pris (modell v2).

Målet er laveste markedspris i Black Month (1. nov – 2. des).

Referanse (D): laveste kjente markedspris fram til i dag, over hele historikken (inntil to år,
fra Prisjakts API) – inkludert det som allerede har skjedd i november.
Grupper:
  * «ny bunn i nov»: laveste pris i november så langt er TV-ens laveste noensinne
  * «stort fall»: D er mer enn 15 % under laveste pris aug–okt
Kalibrering: forholdet (laveste pris i Black Month) / D for alle TV-er med historikk fra fjorårets
Black Month, beregnet for flere skjæringsdatoer (31. okt, 7., 13., 20. og 27. nov), slik at
modellen bruker samme informasjon som vi har på dagens dato.

Backtest på Black Week 2025 (272 TV-er, 5-delt kryssvalidering): median avvik 2,0 %
(mot 6,6 % for v1 som bare brukte laveste pris aug–okt).
"""
import datetime as dt
import statistics

UTC = dt.timezone.utc
CUTS = [(10, 31), (11, 7), (11, 13), (11, 20), (11, 27)]


def _p(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if isinstance(s, str) else s


def clean(raw):
    """Fjerner feilpriser: punkter under 40 % av medianprisen i serien (f.eks. 949 kr for en 43" TV)."""
    vals = [x[1] for x in raw if x[1] is not None]
    if len(vals) < 3:
        return [x for x in raw if x[1] is not None]
    med = statistics.median(vals)
    return [x for x in raw if x[1] is not None and x[1] >= 0.4 * med]


def _series(raw):
    return sorted((_p(x[0]), x[1]) for x in clean(raw))


def _at(s, t):
    b = [p for d, p in s if d <= t]
    return b[-1] if b else None


def _wmin(s, a, b):
    v = [p for d, p in s if a <= d <= b]
    x = _at(s, a)
    if x is not None:
        v.append(x)
    return min(v) if v else None


def features(s, year, cut):
    """Egenskaper kjent på skjæringsdatoen `cut` (datetime)."""
    if not s:
        return None
    nov1 = dt.datetime(year, 11, 1, tzinfo=UTC)
    A = _wmin(s, dt.datetime(year, 8, 1, tzinfo=UTC), min(cut, dt.datetime(year, 10, 31, 23, 59, tzinfo=UTC)))
    D = _wmin(s, s[0][0], cut)
    Dn = _wmin(s, nov1, cut) if cut >= nov1 else None
    if not D:
        return None
    nov = "ny bunn i nov" if Dn and Dn <= D * 1.001 else "ikke ny bunn"
    drop = "stort fall" if A and D < A * 0.85 else "lite fall"
    return {"A": A, "D": D, "Dn": Dn, "group": f"{nov}, {drop}"}


def cut_key(now):
    y = now.year
    for m, d in reversed(CUTS):
        if now >= dt.datetime(y, m, d, tzinfo=UTC):
            return f"{m:02d}-{d:02d}"
    return f"{CUTS[0][0]:02d}-{CUTS[0][1]:02d}"


def fit(series_by_id, year):
    """series_by_id: {id: [[dato, pris, ...], ...]}. Kalibrerer på Black Month i `year`."""
    end = dt.datetime(year, 12, 2, 23, 59, tzinfo=UTC)
    nov1 = dt.datetime(year, 11, 1, tzinfo=UTC)
    out = {"year": year, "cuts": {}}
    for m, d in CUTS:
        cut = dt.datetime(year, m, d, 23, 59, tzinfo=UTC)
        rows = []
        for raw in series_by_id.values():
            s = _series(raw)
            if not s or s[0][0] > dt.datetime(year, 10, 1, tzinfo=UTC) or s[-1][0] < dt.datetime(year, 8, 1, tzinfo=UTC):
                continue
            f = features(s, year, cut)
            tgt = _wmin(s, nov1, end)
            if not f or not tgt:
                continue
            r = tgt / f["D"]
            if 0.3 < r < 1.5:
                rows.append((f["group"], r))
        groups = {}
        for g in sorted({g for g, _ in rows}) + ["*"]:
            rs = sorted(r for gg, r in rows if g == "*" or gg == g)
            if len(rs) < 8:
                continue
            q = statistics.quantiles(rs, n=4)
            groups[g] = {"q25": round(q[0], 3), "q50": round(q[1], 3), "q75": round(q[2], 3), "n": len(rs),
                         "p_lavere": round(sum(x < 0.98 for x in rs) / len(rs), 2),
                         "dist": [round(x, 3) for x in statistics.quantiles(rs, n=20)]}
        out["cuts"][f"{m:02d}-{d:02d}"] = groups
    out["n"] = max((g.get("*", {}).get("n", 0) for g in out["cuts"].values()), default=0)
    return out


def _p_below(dist, x):
    """Andel av fjorårets TV-er der forholdet var under x (fra 5 %-kvantiler)."""
    return round(sum(v < x for v in dist) / (len(dist) + 1), 2)


def predict(model, raw_series, now, best=None):
    """Sannsynlig laveste markedspris i årets Black Month, gitt historikken fram til `now`."""
    year = now.year
    if now > dt.datetime(year, 12, 2, 23, 59, tzinfo=UTC) or now < dt.datetime(year, 9, 1, tzinfo=UTC):
        return None
    s = _series(raw_series)
    f = features(s, year, now)
    if not f:
        return None
    groups = model["cuts"].get(cut_key(now)) or {}
    g = groups.get(f["group"]) or groups.get("*")
    if not g:
        return None
    D = f["D"]
    return {"low": round(D * g["q25"] / 10) * 10, "mid": round(D * g["q50"] / 10) * 10,
            "high": round(D * g["q75"] / 10) * 10, "ref": D, "group": f["group"], "n": g["n"],
            "p_lavere": g["p_lavere"], "cut": cut_key(now),
            # sjanse for at laveste markedspris i Black Month blir minst 2 % under dagens beste butikkpris
            "p_billigere": _p_below(g.get("dist", []), best * 0.98 / D) if best and g.get("dist") else None}
