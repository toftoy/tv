/* Ukulelegrep (GCEA) og barnesanger med akkorder. Fungerer i nettleser og Node. */
(function (root) {
  "use strict";

  // frets: bånd per streng i rekkefølgen G C E A (0 = åpen streng)
  // fingers: hvilken finger (1 = pekefinger … 4 = lillefinger), 0 = ingen
  var CHORDS = {
    "C":  { frets: [0, 0, 0, 3], fingers: [0, 0, 0, 3] },
    "Am": { frets: [2, 0, 0, 0], fingers: [2, 0, 0, 0] },
    "F":  { frets: [2, 0, 1, 0], fingers: [2, 0, 1, 0] },
    "G7": { frets: [0, 2, 1, 2], fingers: [0, 2, 1, 3] },
    "G":  { frets: [0, 2, 3, 2], fingers: [0, 1, 3, 2] },
    "C7": { frets: [0, 0, 0, 1], fingers: [0, 0, 0, 1] },
    "Dm": { frets: [2, 2, 1, 0], fingers: [2, 3, 1, 0] },
    "Em": { frets: [0, 4, 3, 2], fingers: [0, 3, 2, 1] },
    "D":  { frets: [2, 2, 2, 0], fingers: [1, 2, 3, 0] },
    "D7": { frets: [2, 2, 2, 3], fingers: [1, 1, 1, 2] },
    "A":  { frets: [2, 1, 0, 0], fingers: [2, 1, 0, 0] },
    "A7": { frets: [0, 1, 0, 0], fingers: [0, 1, 0, 0] },
    "E7": { frets: [1, 2, 0, 2], fingers: [1, 2, 0, 3] },
    "Bb": { frets: [3, 2, 1, 1], fingers: [3, 2, 1, 1] }
  };

  var CHORD_GROUPS = [
    { name: "Start her", chords: ["C", "Am", "F", "G7"] },
    { name: "Neste steg", chords: ["G", "C7", "Dm", "Em", "A7"] },
    { name: "Litt vanskeligere", chords: ["D", "D7", "A", "E7", "Bb"] }
  ];

  // Barnesanger. [Akkord] står foran stavelsen der grepet skiftes.
  // Akkordene er hentet fra sangboken.no og nortabs.net og transponert til C der det trengs.
  var SONGS = [
    {
      id: "fader-jakob", title: "Fader Jakob", note: "Bare ett grep – perfekt å starte med.",
      verses: [[
        "[C]Fader Jakob, Fader Jakob,",
        "sover du, sover du?",
        "Hører du ei klokken, hører du ei klokken:",
        "Ding – dang – dong, ding – dang – dong."
      ]]
    },
    {
      id: "hjulene-pa-bussen", title: "Hjulene på bussen", note: "To grep: C og G.",
      verses: [[
        "[C]Hjulene på bussen de går rundt og rundt,",
        "[G]rundt og rundt, [C]rundt og rundt.",
        "[C]Hjulene på bussen de går rundt og rundt,",
        "[G]gjennom hele [C]byen."
      ]]
    },
    {
      id: "ro-ro", title: "Ro, ro til fiskeskjær", note: "C, G7 og F.",
      verses: [[
        "[C]Ro, ro til [G7]fiskeskjær,",
        "[G7]hvor mange fisker [C]får vi der?",
        "[C]Én til far og [F]én til mor,",
        "[C]én til søster [G7]og til [C]bror."
      ], [
        "[C]Ro, ro til [G7]fiskeskjær,",
        "[G7]hvor mange fisker [C]får vi der?",
        "[C]Én til bestefar og [F]bestemor,",
        "[C]én til den [G7]lille [C]bror."
      ]]
    },
    {
      id: "bae-bae", title: "Bæ, bæ, lille lam", note: "C, G7, F, A og Dm.",
      verses: [[
        "[C]Bæ, bæ, lille lam, [G7]har du noe [C]ull?",
        "Ja, ja, kjære barn, [G7]jeg har kroppen [C]full.",
        "[F]Søndagsklær til [C]far",
        "[G7]og søndagsklær til [C]mor",
        "og [F]to par [C]strøm[A]per til [Dm]bitte[G7]lille[C]bror."
      ]]
    },
    {
      id: "hode-skulder", title: "Hode, skulder, kne og tå", note: "C, G, C7, F, Dm og G7.",
      verses: [[
        "[C]Hode, skulder, kne og tå, kne og tå.",
        "[C]Hode, skulder, kne og [G]tå, kne og tå.",
        "[C]Øyne, [C7]ører, [F]kinn å klappe [Dm]på.",
        "[G]Hode, [G7]skulder, kne og [C]tå, kne og tå."
      ]]
    },
    {
      id: "lille-petter", title: "Lille Petter Edderkopp", note: "C, Am, G, Em og F.",
      verses: [[
        "[C]Lille Petter [Am]edderkopp han [G]klatret på min [C]hatt.",
        "[C]Så begynte det å [Em]regne og [G]Petter ned han [C]datt.",
        "[C]Så kom [Em]solen og [F]skinte på min [C]hatt.",
        "[C]Da ble det liv i [Am]edderkopp som [G]klatret på min [C]hatt."
      ]]
    }
  ];

  /** "[C]Hei [G7]du" -> [{chord:"C", text:"Hei "}, {chord:"G7", text:"du"}] */
  function parseLine(line) {
    var parts = [], re = /\[([^\]]+)\]/g, last = 0, chord = null, m;
    while ((m = re.exec(line))) {
      if (m.index > last || chord !== null) parts.push({ chord: chord, text: line.slice(last, m.index) });
      chord = m[1];
      last = re.lastIndex;
    }
    parts.push({ chord: chord, text: line.slice(last) });
    return parts.filter(function (p) { return p.chord || p.text; });
  }

  /** Alle akkorder en sang bruker, i rekkefølgen de først dukker opp. */
  function songChords(song) {
    var seen = [];
    song.verses.forEach(function (v) {
      v.forEach(function (line) {
        parseLine(line).forEach(function (p) {
          if (p.chord && seen.indexOf(p.chord) === -1) seen.push(p.chord);
        });
      });
    });
    return seen;
  }

  var api = { CHORDS: CHORDS, CHORD_GROUPS: CHORD_GROUPS, SONGS: SONGS, parseLine: parseLine, songChords: songChords };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Chords = api;
})(this);
