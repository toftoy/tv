# Ukulele

Stemmer, grep og barnesanger for ukulele.

## Stemmer

Et stemmeapparat for ukulele som kjører i nettleseren og bruker mikrofonen på telefonen.
Det hører hvilken tone som spilles, viser avviket i cent på en viser og sier om strengen må
strammes (for lav) eller slakkes (for høy).

Stemninger: standard GCEA (høy G), lav G, D-stemning (ADF#B), baryton (DGBE),
slack key (GCEG) og B-stemning (F#BD#G#).

## Grep og sanger

Fanen **Grep** viser 14 vanlige grep for GCEA-stemning med fingersetting. Fanen **Sanger** har
barnesanger med akkordene over teksten (akkordene er hentet fra sangboken.no og nortabs.net). Grep og sanger ligger i `chords.js`; nye sanger
legges til med `[Akkord]` foran stavelsen der grepet skiftes. Trykk på et grep for å høre det.

## Adresse

https://toftoy.github.io/tv/ukulele/ – publiseres automatisk av workflowen «Oppdater TV-priser» når `site/**` endres på `main`.

## Filer

- `index.html` – appen (grensesnitt, mikrofon, referansetone)
- `pitch.js` – tonehøydedeteksjon (YIN-algoritmen) og notehjelpere
- `chords.js` – grep og sanger
- `chords.test.js` – tester: `node site/ukulele/chords.test.js`
- `pitch.test.js` – tester: `node site/ukulele/pitch.test.js`
