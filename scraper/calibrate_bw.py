"""Kalibrer Black Month-modellen (bf_model v2) på fjorårets Black Month.

Bruk: python scraper/calibrate_bw.py scraper/bw_calibration_data.json.gz 2025   (lagret kalibreringsgrunnlag)
  eller: python scraper/calibrate_bw.py <katalog med historikk-json per produkt> [år]
  eller: python scraper/calibrate_bw.py data/history.json [år]   (bruker markedsserien i history.json)
Skriver scraper/bw_calibration.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bf_model  # noqa: E402

src = sys.argv[1]
year = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
series = {}
if src.endswith(".json.gz"):
    import gzip
    series = {k: [[d + "T00:00:00Z", p] for d, p in v] for k, v in json.loads(gzip.decompress(open(src, "rb").read())).items()}
elif os.path.isdir(src):
    for f in os.listdir(src):
        if f.endswith(".json"):
            series[f[:-5]] = [[x["date"], x["price"]] for x in json.load(open(os.path.join(src, f)))]
else:
    for pid, h in json.load(open(src, encoding="utf-8")).items():
        series[pid] = [[x[0], x[1]] for x in h.get("market", [])]
model = bf_model.fit(series, year)
out = os.path.join(os.path.dirname(__file__), "bw_calibration.json")
json.dump(model, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for c, g in model["cuts"].items():
    print(c, {k: (v["n"], v["q25"], v["q50"], v["q75"], v["p_lavere"]) for k, v in g.items()})
