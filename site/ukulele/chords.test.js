// Kjør: node site/ukulele/chords.test.js
const assert = require("assert");
const C = require("./chords.js");

assert.deepStrictEqual(C.parseLine("[C]Hei [G7]du"), [{ chord: "C", text: "Hei " }, { chord: "G7", text: "du" }]);
assert.deepStrictEqual(C.parseLine("uten grep"), [{ chord: null, text: "uten grep" }]);
assert.deepStrictEqual(C.parseLine("start [F]midt i"), [{ chord: null, text: "start " }, { chord: "F", text: "midt i" }]);
assert.deepStrictEqual(C.parseLine("slutt [C]"), [{ chord: null, text: "slutt " }, { chord: "C", text: "" }]);
assert.deepStrictEqual(C.parseLine("klatret opp i[C]gjen."), [{ chord: null, text: "klatret opp i" }, { chord: "C", text: "gjen." }]);

for (const s of C.SONGS) {
  for (const ch of C.songChords(s)) assert.ok(C.CHORDS[ch], `${s.title} bruker ukjent grep ${ch}`);
}
for (const g of C.CHORD_GROUPS) for (const ch of g.chords) assert.ok(C.CHORDS[ch], ch);
for (const [name, c] of Object.entries(C.CHORDS)) {
  assert.strictEqual(c.frets.length, 4, name);
  c.frets.forEach((f, i) => assert.strictEqual(f === 0, c.fingers[i] === 0, `${name}: finger og bånd stemmer ikke`));
  assert.ok(Math.max(...c.frets) <= 4, name);
}
assert.deepStrictEqual(C.songChords(C.SONGS.find(s => s.id === "bae-bae")), ["C", "G7", "F", "A", "Dm"]);
console.log("Alle tester OK");
