/* Tonehøydedeteksjon (YIN) og notehjelpere. Fungerer både i nettleser og Node. */
(function (root) {
  "use strict";

  var NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

  /**
   * Finn grunnfrekvensen i et lydutsnitt med YIN-algoritmen.
   * Returnerer {freq, clarity, rms} eller null når det ikke er noen tydelig tone.
   */
  function detectPitch(buf, sampleRate, opts) {
    opts = opts || {};
    var minF = opts.minFreq || 80;
    var maxF = opts.maxFreq || 1200;
    var threshold = opts.threshold || 0.12;
    var minRms = opts.minRms == null ? 0.008 : opts.minRms;

    var N = buf.length;
    var rms = 0;
    for (var i = 0; i < N; i++) rms += buf[i] * buf[i];
    rms = Math.sqrt(rms / N);
    if (rms < minRms) return null;

    var maxTau = Math.min(Math.floor(sampleRate / minF), Math.floor(N / 2));
    var minTau = Math.max(2, Math.floor(sampleRate / maxF));
    var W = N - maxTau;

    // Differansefunksjon
    var d = new Float32Array(maxTau + 2);
    for (var tau = 1; tau <= maxTau + 1 && tau < N - W + 1; tau++) {
      var sum = 0;
      for (var j = 0; j < W; j++) {
        var diff = buf[j] - buf[j + tau];
        sum += diff * diff;
      }
      d[tau] = sum;
    }

    // Kumulativ normalisert differanse
    var cmnd = new Float32Array(maxTau + 2);
    cmnd[0] = 1;
    var running = 0;
    for (tau = 1; tau <= maxTau + 1; tau++) {
      running += d[tau];
      cmnd[tau] = running === 0 ? 1 : (d[tau] * tau) / running;
    }

    var best = -1;
    for (tau = minTau; tau <= maxTau; tau++) {
      if (cmnd[tau] < threshold) {
        while (tau + 1 <= maxTau && cmnd[tau + 1] < cmnd[tau]) tau++;
        best = tau;
        break;
      }
    }
    if (best === -1) {
      // Ingen under terskel: bruk globalt minimum hvis det er rimelig tydelig
      var minVal = Infinity;
      for (tau = minTau; tau <= maxTau; tau++) {
        if (cmnd[tau] < minVal) { minVal = cmnd[tau]; best = tau; }
      }
      if (minVal > 0.3) return null;
    }

    // Parabolsk interpolasjon for presisjon under ett sampel
    var t = best;
    var betterTau = t;
    if (t > 1 && t < maxTau + 1) {
      var s0 = cmnd[t - 1], s1 = cmnd[t], s2 = cmnd[t + 1];
      var denom = s0 + s2 - 2 * s1;
      if (denom !== 0) betterTau = t + (s0 - s2) / (2 * denom);
    }

    return { freq: sampleRate / betterTau, clarity: 1 - cmnd[t], rms: rms };
  }

  function freqToMidi(f) { return 69 + 12 * Math.log2(f / 440); }
  function midiToFreq(m) { return 440 * Math.pow(2, (m - 69) / 12); }
  function centsOff(f, target) { return 1200 * Math.log2(f / target); }

  /** "G4" -> MIDI-nummer */
  function noteToMidi(name) {
    var m = /^([A-G])(#|b)?(-?\d)$/.exec(name);
    if (!m) throw new Error("Ugyldig note: " + name);
    var idx = NOTE_NAMES.indexOf(m[1]);
    if (m[2] === "#") idx += 1;
    if (m[2] === "b") idx -= 1;
    return (parseInt(m[3], 10) + 1) * 12 + idx;
  }

  function midiToName(m) {
    var r = Math.round(m);
    return { name: NOTE_NAMES[((r % 12) + 12) % 12], octave: Math.floor(r / 12) - 1 };
  }

  /** Velg strengen i stemningen som ligger nærmest frekvensen (i cent). */
  function nearestString(freq, strings) {
    var bestIdx = 0, bestCents = Infinity;
    for (var i = 0; i < strings.length; i++) {
      var c = centsOff(freq, midiToFreq(noteToMidi(strings[i])));
      if (Math.abs(c) < Math.abs(bestCents)) { bestCents = c; bestIdx = i; }
    }
    return { index: bestIdx, cents: bestCents };
  }

  var api = {
    detectPitch: detectPitch, freqToMidi: freqToMidi, midiToFreq: midiToFreq,
    centsOff: centsOff, noteToMidi: noteToMidi, midiToName: midiToName,
    nearestString: nearestString
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Pitch = api;
})(this);
