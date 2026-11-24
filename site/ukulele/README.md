# Ukulele-stemmer

Et stemmeapparat for ukulele som kjører i nettleseren og bruker mikrofonen på telefonen.
Det hører hvilken tone som spilles, viser avviket i cent på en viser og sier om strengen må
strammes (for lav) eller slakkes (for høy).

Stemninger: standard GCEA (høy G), lav G, D-stemning (ADF#B), baryton (DGBE),
slack key (GCEG) og B-stemning (F#BD#G#).

## Adresse

https://toftoy.github.io/tv/ukulele/ – publiseres automatisk av workflowen «Oppdater TV-priser» når `site/**` endres på `main`.

## Filer

- `index.html` – appen (grensesnitt, mikrofon, referansetone)
- `pitch.js` – tonehøydedeteksjon (YIN-algoritmen) og notehjelpere
- `pitch.test.js` – tester: `node site/ukulele/pitch.test.js`
