"""Henter Elkjøp-butikklager for Bergensområdet og lagrer data/local_elkjop.json.
Kjøres utenfor GitHub Actions (Elkjøp blokkerer GitHubs servere). run.py bruker filen som reserve."""
import datetime as dt
import json
import os

import local_stock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))["local_stores"]["Elkjøp"]
stock = local_stock.elkjop(cfg)
out = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "stock": stock}
json.dump(out, open(os.path.join(ROOT, "data", "local_elkjop.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(len(stock), "TV-er på lager i Elkjøp-butikker")
