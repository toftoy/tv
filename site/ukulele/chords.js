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

  // Tradisjonelle barnesanger. [Akkord] står foran stavelsen der den skiftes.
  var SONGS = [
    {
      id: "fader-jakob", title: "Fader Jakob", note: "Bare ett grep – perfekt å starte med.",
      verses: [[
        "[C]Fader Jakob, fader Jakob,",
        "sover du? Sover du?",
        "Hører du ei klokka? Hører du ei klokka?",
        "Ding, dang, dong. Ding, dang, dong."
      ]]
    },
    {
      id: "hjulene-pa-bussen", title: "Hjulene på bussen", note: "To grep: C og G7.",
      verses: [[
        "[C]Hjulene på bussen går rundt og rundt,",
        "[G7]rundt og rundt, [C]rundt og rundt.",
        "Hjulene på bussen går rundt og rundt",
        "[G7]hele dagen [C]lang."
      ], [
        "[C]Vindusviskerne går svisj, svisj, svisj,",
        "[G7]svisj, svisj, svisj, [C]svisj, svisj, svisj.",
        "Vindusviskerne går svisj, svisj, svisj",
        "[G7]hele dagen [C]lang."
      ], [
        "[C]Hornet på bussen sier tut, tut, tut,",
        "[G7]tut, tut, tut, [C]tut, tut, tut.",
        "Hornet på bussen sier tut, tut, tut",
        "[G7]hele dagen [C]lang."
      ]]
    },
    {
      id: "hode-skulder", title: "Hode, skulder, kne og tå", note: "C, F og G7.",
      verses: [[
        "[C]Hode, skulder, kne og [G7]tå, kne og [C]tå,",
        "hode, skulder, kne og [G7]tå, kne og [C]tå,",
        "øyne, ører, [F]kinn å klappe [C]på,",
        "hode, skulder, [G7]kne og tå, kne og [C]tå."
      ]]
    },
    {
      id: "ro-ro", title: "Ro, ro til fiskeskjær", note: "C og G7. Bytt ut «deg» med navnet til barnet.",
      verses: [[
        "[C]Ro, ro til fiskeskjær,",
        "[G7]mange fisker får vi [C]der.",
        "Én til far og én til mor,",
        "[G7]én til søster, én til [C]bror,",
        "én til den som fisken dro,",
        "[G7]og det var vesle [C]deg!"
      ]]
    },
    {
      id: "bae-bae", title: "Bæ, bæ, lille lam", note: "C, F og G7.",
      verses: [[
        "[C]Bæ, bæ, lille lam, [F]har du [C]noe ull?",
        "[F]Ja, ja, kjære [C]barn, [G7]jeg har kroppen [C]full.",
        "Søndagsklær til [G7]far og [C]søndagsklær til [G7]mor,",
        "[C]og til lille [F]søster, [C]og til [G7]lille [C]bror."
      ]]
    },
    {
      id: "lille-petter", title: "Lille Petter Edderkopp", note: "C, F og G7.",
      verses: [[
        "[C]Lille Petter Edderkopp han [G7]klatret opp på [C]taket.",
        "Så kom [F]regnet og [C]skylte Petter [G7]ned. [C]",
        "Så kom [F]sola og [C]tørket opp alt [G7]regnet, [C]",
        "og lille Petter Edderkopp han [G7]klatret opp i[C]gjen."
      ]]
    },
    {
      id: "se-min-kjole", title: "Se min kjole", note: "C, F og G7.",
      verses: [[
        "[C]Se min kjole, den er [G7]grønn som gresset,",
        "alt hva jeg eier, det er [C]grønt som den.",
        "Det er fordi jeg [F]elsker alt det [C]grønne,",
        "og fordi en [G7]jeger er min [C]venn."
      ], [
        "[C]Se min kjole, den er [G7]blå som havet,",
        "alt hva jeg eier, det er [C]blått som den.",
        "Det er fordi jeg [F]elsker alt det [C]blå,",
        "og fordi en [G7]sjømann er min [C]venn."
      ], [
        "[C]Se min kjole, den er [G7]svart som kullet,",
        "alt hva jeg eier, det er [C]svart som den.",
        "Det er fordi jeg [F]elsker alt det [C]svarte,",
        "og fordi en [G7]feier er min [C]venn."
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
