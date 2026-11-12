"""Engangskalibrering av Black Week-modellen på fjorårets Black Week.

Bruk: python scraper/calibrate_bw.py <produkter.json> <katalog med historikk-json per produkt>
Skriver scraper/bw_calibration.json, som run.py bruker i stedet for å kalibrere på nytt hver dag.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bf_model  # noqa: E402

prods = json.load(open(sys.argv[1], encoding="utf-8"))
hist = {}
for p in prods:
    f = os.path.join(sys.argv[2], f"{p['id']}.json")
    if os.path.exists(f):
        hist[str(p["id"])] = {"market": [[x["date"], x["price"], x["shop"]] for x in json.load(open(f))]}
year = int(sys.argv[3]) if len(sys.argv) > 3 else 2025
model = bf_model.fit(hist, prods, year)
out = os.path.join(os.path.dirname(__file__), "bw_calibration.json")
json.dump(model, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(model, ensure_ascii=False, indent=1))
