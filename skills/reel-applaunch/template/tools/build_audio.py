"""Builds the sample's two audio tracks, timed to SCENARIO.md:

  assets/music.wav — a bed synthesised here (no samples), one chord per request, a break before the reveal.
  assets/sfx.wav   — reel-sfx sounds (code-generated) plus recorded ones from the user's own pack
                     (assets/sfx-src/*.wav), each on its animation moment. A missing pack file falls back
                     to the nearest reel-sfx sound (STAND_IN).

Beat times mirror the beat clock in index.html (scenario v3).

Times below are on the authored 16 s clock (same numbers as index.html); the picture is delivered
SPEED× faster, so every time is divided by SPEED and the tempo rises with it.

Run with the reel-sfx venv:  ~/.reel-styles/venv/bin/python tools/build_audio.py
"""
import json
import wave
from pathlib import Path

import numpy as np

SR = 48000
SPEED = 1.0
AUTHORED = 16.0
DUR = AUTHORED / SPEED
N = int(SR * DUR)
ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = Path.home() / ".reel-styles" / "sfx"
USER = ROOT / "assets" / "sfx-src"
rng = np.random.default_rng(7)

# beat clock — same numbers as index.html (scenario v3)
ORB_IN, DIVE, DROP = 1.62, 2.4, 1.4
LAND = DIVE + DROP; Q_T = LAND + 0.75
Q_END = Q_T + 2.55 / 1.5         # typing plays 1.5× faster than the spoken take
PULL = Q_END + 0.45; LIFT = PULL + 1.0; ANS = LIFT + 0.7
GRID_IN = ANS + 1.75; TICK = GRID_IN + 0.9; TO_CO = TICK + 0.75; PRESS = TO_CO + 0.85; GROW = PRESS + 0.3
REVEAL = GROW + 0.8                   # the logo


def w(x):
    """Authored time → delivered time."""
    return x / SPEED


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v) / 8388608.0
    elif sw == 2:
        v = np.frombuffer(raw, dtype="<i2") / 32768.0
    else:
        v = np.frombuffer(raw, dtype="<i4") / 2147483648.0
    v = v.reshape(-1, ch)
    if ch == 1:
        v = np.repeat(v, 2, axis=1)
    assert sr == SR, f"{path} is {sr} Hz"
    return v


def db(g):
    return 10 ** (g / 20)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def onepole_lp(x, cutoff):
    """Time-varying one-pole low-pass; cutoff is an array (Hz) per sample."""
    a = np.exp(-2 * np.pi * np.asarray(cutoff) / SR)
    a = np.broadcast_to(a, x.shape[:1])
    y = np.zeros_like(x)
    prev = np.zeros(x.shape[1:])
    for i in range(len(x)):
        prev = (1 - a[i]) * x[i] + a[i] * prev
        y[i] = prev
    return y


def reverb(x, secs=2.2, mix=0.28):
    n = int(SR * secs)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t / (secs / 5.5))[:, None]
    ir[: int(0.012 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    out = np.zeros((len(x) + n - 1, 2))
    L = 1 << int(np.ceil(np.log2(len(x) + n)))
    for c in range(2):
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c], L) * np.fft.rfft(ir[:, c], L), L)[: len(x) + n - 1]
    return x * (1 - mix) + out[: len(x)] * mix * 2.2


# ---------------------------------------------------------------- music
t = np.arange(N) / SR
BEAT = 0.6 / SPEED  # 100 BPM authored → 120 BPM delivered
CHORDS = [(w(a), w(b), n, bs) for (a, b, n, bs) in [
    (0.0, DIVE, [53, 57, 60, 64], 41),                 # Fmaj7 — title, orb
    (DIVE, PULL, [57, 60, 64, 67], 45),                # Am7 — inside the bar, the spoken request
    (PULL, GRID_IN, [50, 53, 57, 60, 64], 38),         # Dm9 — the phone draws, the answer
    (GRID_IN, GROW, [58, 62, 65, 69], 34),             # Bbmaj7 — ingredients, checkout
    (REVEAL, AUTHORED, [53, 60, 64, 67, 69], 29),      # Fmaj9 — the reveal
]]


def env(start, end, att=0.5, rel=0.6):
    a = (t - start) / att
    r = (end + rel - t) / rel
    return np.clip(np.minimum(a, r), 0, 1) * (t >= start)


def saw(f, phase=0.0, harmonics=9):
    y = np.zeros(N)
    for h in range(1, harmonics + 1):
        y += np.sin(2 * np.pi * f * h * t + phase * h) / h
    return y


pad = np.zeros((N, 2))
for (s0, e0, notes, bass) in CHORDS:
    ev = env(s0, e0, att=0.45 if s0 > 0 else 0.05, rel=0.6 if e0 < DUR - 0.1 else 0.3)
    for k, m in enumerate(notes):
        for d, pan in ((-7, 0.25), (0, 0.5), (7, 0.75)):
            v = saw(midi(m) * 2 ** (d / 1200), phase=k + d)
            pad[:, 0] += v * ev * (1 - pan) * 0.05
            pad[:, 1] += v * ev * pan * 0.05
    pad += (np.sin(2 * np.pi * midi(bass + 12) * t) * env(s0, e0, 0.3, 0.5) * 0.12)[:, None]
cut = np.interp(t, [0, w(Q_T), w(GRID_IN), w(GROW - 0.4), w(GROW + 0.1), w(REVEAL), DUR], [700, 1100, 2600, 2900, 500, 3600, 2400])
pad = onepole_lp(pad, cut)

arp = np.zeros((N, 2))
pattern = [0, 1, 2, 3, 2, 1, 3, 2]
for i, st in enumerate(np.arange(w(Q_T), w(GROW - 0.2), BEAT / 2)):
    chord = next(c for c in CHORDS if c[0] <= st < c[1] + 0.01)
    f = midi(chord[2][pattern[i % len(pattern)] % len(chord[2])] + 12)
    a = int(st * SR); n = int(0.6 * SR); tt = np.arange(n) / SR
    tone = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt / 0.16)
    g = np.interp(st, [w(Q_T), w(ANS), w(GROW)], [0.06, 0.09, 0.11])
    b = min(N, a + n); pan = 0.35 if i % 2 else 0.65
    arp[a:b, 0] += tone[: b - a] * g * (1 - pan)
    arp[a:b, 1] += tone[: b - a] * g * pan
dl = int(BEAT * 0.75 * SR)
for rep, g in ((1, 0.38), (2, 0.16)):
    sh = dl * rep
    arp[sh:, 0] += arp[:-sh, 1 if rep % 2 else 0] * g
    arp[sh:, 1] += arp[:-sh, 0 if rep % 2 else 1] * g

drums = np.zeros((N, 2))


def place(sig, at, gain):
    a = int(at * SR); b = min(N, a + len(sig))
    if a < N:
        drums[a:b] += sig[: b - a, None] * gain


kt = np.arange(int(0.4 * SR)) / SR
kick = np.sin(2 * np.pi * np.cumsum(45 + 75 * np.exp(-kt / 0.035)) / SR) * np.exp(-kt / 0.13)
hn = int(0.06 * SR)
hat = np.diff(rng.standard_normal(hn + 1)) * np.exp(-np.arange(hn) / SR / 0.012)
cn = int(0.25 * SR)
clap = np.convolve(rng.standard_normal(cn) * np.exp(-np.arange(cn) / SR / 0.05), np.ones(6) / 6, mode="same")
for b_ in np.arange(w(PULL), w(GROW - 0.2), BEAT):
    place(kick, b_, 0.55)
for b_ in np.arange(w(ANS) + BEAT / 2, w(GROW - 0.2), BEAT):
    place(hat, b_, 0.05)
for b_ in np.arange(w(GRID_IN) + BEAT, w(GROW - 0.2), BEAT * 2):
    place(clap, b_, 0.12)
bt = np.arange(int(1.6 * SR)) / SR
place(np.sin(2 * np.pi * np.cumsum(38 + 40 * np.exp(-bt / 0.08)) / SR) * np.exp(-bt / 0.55), w(REVEAL), 0.6)

music = reverb(pad + arp, 2.4, 0.3) + drums
music *= np.interp(t, [0, 0.05, DUR - 0.8, DUR], [0, 1, 1, 0])[:, None]
music = np.tanh(music * 1.4) / np.tanh(1.4)
music *= db(-3) / np.max(np.abs(music))
write_wav(ROOT / "assets" / "music.wav", music)

# ---------------------------------------------------------------- sfx
idx = {s["id"]: s for s in json.load(open(SFX_DIR / "index.json"))["sounds"]}
EVENTS = [  # (authored time, sound id or @user file, variant / trim start, gain dB, length or None)
    (0.2, "@typing", 0.0, -16, 0.8),           # title types
    (1.25, "whoosh_soft", 0, -17, None),        # title deletes
    (ORB_IN, "sparkle", 0, -11, None),          # the orb
    (ORB_IN + 0.08, "shine", 0, -16, None),
    (DIVE, "@swoosh_main", 0.0, -12, None),     # the orb drops toward the bar, the camera follows
    (DIVE + 0.2, "whoosh_in", 0, -16, None),
    (LAND - 0.25, "swipe_ui", 0, -14, None),    # the bar grows out of it
    (LAND, "@pop", 0.58, -15, 0.3),
    (Q_T - 0.25, "chime_up", 0, -13, None),     # listening
    (PULL, "@swoosh_deep", 0.0, -10, None),     # pull back
    (PULL + 0.05, "draw_line", 0, -18, None),   # the phone draws itself
    (PULL + 0.95, "swipe_ui", 1, -17, None),
    (LIFT, "whoosh_soft", 2, -16, None),        # the words rise into the bubble
    (LIFT + 0.55, "message_out", 0, -12, None),
    (ANS, "message_in", 0, -12, None),
]
EVENTS += [(ANS + 1.0 + i * 0.08, "@pop", 0.58, -17 - (i % 2) * 2, 0.3) for i in range(6)]   # the ingredients
EVENTS += [(GRID_IN, "whoosh_in", 0, -15, None)]
EVENTS += [(TICK + i * 0.1, "@tap", 0.0, -10, None) for i in range(6)]                      # picked 1→6
EVENTS += [(TO_CO - 0.15, "swipe_ui", 1, -17, None), (PRESS, "@tap", 0.0, -6, None), (PRESS + 0.15, "@coin", 0.0, -9, None)]
EVENTS += [(GROW, "@swoosh_main", 0.0, -11, None)]                                           # the button floods the frame
EVENTS += [(REVEAL, "reverse_swell", 0, -12, "end"), (REVEAL, "hit_deep", 0, -11, None), (REVEAL - 0.02, "@flare", 0.0, -5, None)]

STAND_IN = {"typing": "typing", "swoosh_main": "whoosh_fast", "swoosh_deep": "whoosh_deep", "pop": "pop",
            "tap": "tap", "coin": "coin", "flare": "shine"}

sfx = np.zeros((N + SR * 4, 2))
for (at, sid, var, g, ln) in EVENTS:
    if sid.startswith("@") and (USER / f"{sid[1:]}.wav").exists():
        x = read_wav(USER / f"{sid[1:]}.wav")[int(var * SR):].copy()
    elif sid.startswith("@"):          # no sound pack in assets/sfx-src: the nearest reel-sfx sound
        files = idx[STAND_IN[sid[1:]]]["files"]
        x = read_wav(SFX_DIR / files[0])
    else:
        files = idx[sid]["files"]
        x = read_wav(SFX_DIR / files[var % len(files)])
    start = w(at)
    if ln == "end":                    # the swell finishes exactly on the reveal
        start = w(at) - len(x) / SR
    elif ln:
        L = ln / SPEED if sid == "@typing" else ln
        x = x[: int(L * SR)]
        x *= np.interp(np.arange(len(x)) / SR, [0, max(0, L - 0.1), L], [1, 1, 0])[:, None]
    a = int(start * SR)
    sfx[a : a + len(x)] += x * db(g)
sfx = sfx[:N]
sfx *= db(-1.5) / np.max(np.abs(sfx))
write_wav(ROOT / "assets" / "sfx.wav", sfx)
print("built", round(DUR, 2), "s")
