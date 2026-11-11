# TV-prisvakt

Følger TV-priser hos **Elkjøp, Power, Komplett, NetOnNet, Multicom og Samsung** (32–58") via offentlige produktsider på Prisjakt.no,
og viser laveste pris siste 30/60/90/365 dager – slik at «Black Week-tilbud» med oppblåste førpriser avsløres.

- **Dashboard:** https://toftoy.github.io/tv/
- **Oppdatering:** GitHub Actions kjører `scraper/run.py` kl. 06:17 og 16:17 hver dag (eller manuelt: *Actions → Oppdater TV-priser → Run workflow*).
- **Varsler:** Når en TV på overvåkingslisten når laveste pris siste 60 dager eller din maksgrense, opprettes en issue med etiketten `prisvarsel`. GitHub sender deg e-post om den automatisk.

## Overvåkingsliste – `config.json`

```json
{"contains": "OLED B6", "sizes": [55], "max_price": 9000, "on_low60": true}
```

| felt | betydning |
|---|---|
| `contains` | tekst som finnes i modell-/familienavnet (f.eks. `OLED C5`, `TCL C7`, `S90`) |
| `family` | alternativt eksakt familienøkkel, f.eks. `LG OLED C5 55" 2025` |
| `id` | alternativt Prisjakt-produkt-ID |
| `sizes` | tommer som skal overvåkes |
| `max_price` | varsle når prisen er ≤ dette |
| `on_low60` | varsle når prisen er ≤ laveste markedspris siste 60 dager (standard `true`) |

Du får bare varsel én gang per butikk og pris – nytt varsel kommer først hvis prisen faller ytterligere.

## Data
- `data/products.json` – siste priser per produkt, med familie (gruppering av butikkvarianter av samme TV).
- `data/history.json` – Prisjakts serie for laveste markedspris (sammenslått over tid) + egen prishistorikk per butikk fra 11.11.2026.
- `scraper/families.py` – regler for å slå sammen modellkoder (LG C54/C55/C56, Samsung TQ/QE, TCL C69K = MQLED75K osv.).

## Begrensninger
- «Laveste pris» er laveste hos *noen* butikk på Prisjakt (også små nettbutikker/markedsplasser). Historikk per butikk bygges opp fra start-datoen.
- Prisjakts produktsider viser ca. 3 måneders historikk; 365-dagerstallet blir komplett etter hvert som data samles.
