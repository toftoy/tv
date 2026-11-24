// Kjør: node ukulele-tuner/pitch.test.js
const assert = require("assert");
const P = require("./pitch.js");

function pluck(freq, sr, n, noise = 0) {
  // Grunntone + overtoner (som en streng) med litt støy
  const buf = new Float32Array(n);
  const amps = [1, 0.6, 0.4, 0.25, 0.15];
  for (let i = 0; i < n; i++) {
    let v = 0;
    amps.forEach((a, h) => { v += a * Math.sin(2 * Math.PI * freq * (h + 1) * i / sr + h); });
    buf[i] = 0.2 * v + noise * (Math.random() * 2 - 1);
  }
  return buf;
}

let fails = 0;
for (const sr of [44100, 48000]) {
  for (const note of ["D3", "G3", "C4", "E4", "G4", "A4", "B4", "F#4"]) {
    for (const detune of [-30, 0, 12]) {
      const f = P.midiToFreq(P.noteToMidi(note)) * Math.pow(2, detune / 1200);
      const r = P.detectPitch(pluck(f, sr, 2048, 0.02), sr);
      const err = r ? P.centsOff(r.freq, f) : NaN;
      if (!(Math.abs(err) < 2)) { fails++; console.log("FEIL", sr, note, detune, r && r.freq, err); }
    }
  }
}
assert.strictEqual(P.detectPitch(new Float32Array(2048), 48000), null, "stillhet skal gi null");
assert.strictEqual(P.noteToMidi("A4"), 69);
assert.strictEqual(P.midiToName(67).name + P.midiToName(67).octave, "G4");
const ns = P.nearestString(265, ["G4", "C4", "E4", "A4"]);
assert.strictEqual(ns.index, 1);
assert.ok(ns.cents > 0, "265 Hz er over C4");
assert.strictEqual(fails, 0, fails + " deteksjonsfeil");
console.log("Alle tester OK");
