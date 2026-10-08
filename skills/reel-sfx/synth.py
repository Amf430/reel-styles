#!/usr/bin/env python3
"""reel-sfx — our own sound effects, made entirely from code (oscillators, noise, filters). No samples.

  synth.py                          make every sound → ~/.reel-styles/sfx  (+ index.json, audition.html)
  synth.py --only pop,ding          just these ids
  synth.py --out DIR                somewhere else
  synth.py --list                   print the catalogue

Deterministic: the same recipe gives the same file on every machine (each sound has its own seed).
Output: 48 kHz, 24-bit, stereo WAV. Ids with variants also get <id>_2.wav, <id>_3.wav.
"""
import argparse
import json
import os
import sys
import wave
import zlib

HERE = os.path.dirname(os.path.realpath(__file__))
try:
    import numpy as np
except ImportError:  # use the engine's private venv (~/.reel-styles/venv) instead of system Python
    sys.path.insert(0, os.path.join(HERE, "..", "..", "engine"))
    import mlenv
    py = mlenv.ensure(["numpy"])
    os.execv(py, [py, os.path.realpath(__file__)] + sys.argv[1:])

SR = 48000
OUT = os.path.expanduser(os.path.join(os.environ.get("REEL_HOME", "~/.reel-styles"), "sfx"))


# ---------------------------------------------------------------- building blocks
def N(d):
    return int(round(d * SR))


def T(d):
    return np.arange(N(d)) / SR


def osc(freq, d, shape="sine"):
    f = np.full(N(d), float(freq)) if np.ndim(freq) == 0 else np.asarray(freq, float)
    ph = 2 * np.pi * np.cumsum(f) / SR
    if shape == "sine":
        return np.sin(ph)
    if shape == "tri":
        return 2 / np.pi * np.arcsin(np.sin(ph))
    if shape == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1.0) - 1
    return np.tanh(5 * np.sin(ph))  # soft square


def glide(d, pts):
    """Frequency curve through (sec, hz) points, interpolated on a log scale."""
    x, y = zip(*pts)
    return np.exp(np.interp(T(d), x, np.log(y)))


def ramp(d, pts):
    x, y = zip(*pts)
    return np.interp(T(d), x, y)


def decay(d, tau, attack=0.0005):
    t = T(d)
    e = np.exp(-np.maximum(t - attack, 0) / tau)
    return np.where(t < attack, t / max(attack, 1e-9), e)


def bell(d, peak, k_in=2.0, k_out=1.5):
    """0 → 1 at `peak` sec → 0 at the end."""
    t = T(d)
    return np.where(t < peak, (t / peak) ** k_in, np.clip((d - t) / (d - peak), 0, 1) ** k_out)


def biquad(x, kind, f, q=0.707):
    n = len(x)
    f = np.clip(np.full(n, float(f)) if np.ndim(f) == 0 else np.asarray(f, float), 15, SR * 0.45)
    w = 2 * np.pi * f / SR
    cs, al = np.cos(w), np.sin(w) / (2 * q)
    if kind == "lp":
        b0 = (1 - cs) / 2; b1 = 1 - cs; b2 = b0
    elif kind == "hp":
        b0 = (1 + cs) / 2; b1 = -(1 + cs); b2 = b0
    else:  # band-pass, 0 dB peak
        b0 = al; b1 = np.zeros(n); b2 = -al
    a0 = 1 + al
    B0, B1, B2 = (b0 / a0).tolist(), (b1 / a0).tolist(), (b2 / a0).tolist()
    A1, A2 = (-2 * cs / a0).tolist(), ((1 - al) / a0).tolist()
    xs, y = x.tolist(), [0.0] * n
    x1 = x2 = y1 = y2 = 0.0
    for i in range(n):
        xi = xs[i]
        yi = B0[i] * xi + B1[i] * x1 + B2[i] * x2 - A1[i] * y1 - A2[i] * y2
        x2, x1, y2, y1 = x1, xi, y1, yi
        y[i] = yi
    return np.asarray(y)


def kick(d, f0, f1, tau_pitch, tau_amp):
    t = T(d)
    return osc(f1 + (f0 - f1) * np.exp(-t / tau_pitch), d) * decay(d, tau_amp, 0.001)


def fm_bell(f, d, ratio=3.5, index=2.5, tau=0.5, idx_tau=0.15):
    t = T(d)
    mod = index * np.exp(-t / idx_tau) * np.sin(2 * np.pi * f * ratio * t)
    return np.sin(2 * np.pi * f * t + mod) * decay(d, tau, 0.001)


def marimba(f, d=0.7):
    return (osc(f, d) * decay(d, 0.25, 0.001) + 0.4 * osc(4 * f, d) * decay(d, 0.03, 0.001)
            + 0.15 * osc(10 * f, d) * decay(d, 0.008, 0.0005))


def st(x, pan=0.0):
    """Mono → stereo, equal-power pan (scalar or per-sample, −1..1)."""
    p = (np.asarray(pan, float) + 1) * np.pi / 4
    return np.stack([x * np.cos(p), x * np.sin(p)], 1)


def at(x, t0):
    return np.concatenate([np.zeros((N(t0),) + x.shape[1:]), x])


def mix(*xs):
    xs = [st(x) if x.ndim == 1 else x for x in xs]
    out = np.zeros((max(len(x) for x in xs), 2))
    for x in xs:
        out[:len(x)] += x
    return out


def reverb(x, size=1.2, wet=0.25, tone=6000, seed=7):
    """Convolution with a synthetic decaying-noise room (different noise per channel = width)."""
    x = (st(x) if x.ndim == 1 else x).copy()
    k = min(N(0.01), len(x) // 4)
    x[-k:] *= np.linspace(1, 0, k)[:, None]  # a dry tail cut mid-decay would click
    rng = np.random.default_rng(seed)
    L = N(size * 1.4)
    env = np.exp(-6.9 * np.arange(L) / SR / size)
    n = 1 << int(np.ceil(np.log2(len(x) + L)))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    tilt = 1 / (1 + (freqs / tone) ** 2)
    out = np.zeros((len(x) + L, 2))
    for c in range(2):
        ir = rng.standard_normal(L) * env
        ir[:N(0.012)] = 0  # pre-delay
        ir /= np.sqrt(np.sum(ir ** 2))
        wetc = np.fft.irfft(np.fft.rfft(x[:, c], n) * np.fft.rfft(ir, n) * tilt, n)[:len(x) + L]
        out[:, c] = wetc * wet
    out[:len(x)] += x
    return out


def noise(rng, d):
    return rng.standard_normal(N(d)) * 0.5


def finish(x, peak_db):
    x = st(x) if x.ndim == 1 else x
    mag = np.abs(x).max(1)
    loud = np.nonzero(mag > mag.max() * 10 ** (-72 / 20))[0]
    x = x[:loud[-1] + 1] if len(loud) else x
    k = min(N(0.006), len(x) // 4)
    x[-k:] *= np.linspace(1, 0, k)[:, None]
    x[:N(0.0004)] *= np.linspace(0, 1, N(0.0004))[:, None]
    return x / (np.abs(x).max() + 1e-12) * 10 ** (peak_db / 20)


# ---------------------------------------------------------------- catalogue
SOUNDS = []
CATS = {"whoosh": ("هواء وسحبات", "Whooshes"), "ui": ("واجهة وضغطات", "UI & clicks"),
        "notify": ("تنبيهات ونغمات", "Notifications"), "impact": ("ضربات", "Impacts"),
        "element": ("عناصر الحركة", "Motion elements"), "drama": ("دراما وتوتر", "Drama & tension"),
        "reaction": ("ردود فعل", "Reactions")}
PEAK = {"whoosh": -3, "ui": -5, "notify": -4, "impact": -1, "element": -5, "drama": -1.5, "reaction": -4}


def sound(id, cat, ar, en, use, tags=(), variants=1):
    def reg(fn):
        SOUNDS.append(dict(id=id, cat=cat, ar=ar, en=en, use=use, tags=list(tags), variants=variants, fn=fn))
        return fn
    return reg


# ---- whooshes
def _whoosh(rng, d, peak, path, q, pan=(-0.5, 0.5), air=0.15, room=0.15):
    n = noise(rng, d)
    e = bell(d, peak)
    body = biquad(n, "bp", glide(d, path), q) * e
    hiss = biquad(n, "bp", glide(d, path) * 2.5, 0.8) * e * air
    return reverb(st(body + hiss, ramp(d, [(0, pan[0]), (d, pan[1])])), 0.6, room)


@sound("whoosh_soft", "whoosh", "هواء ناعم", "Soft whoosh", "دخول نص أو كرت", ("text", "slide"), 3)
def _(rng, v):
    p = 0.42 + 0.05 * v
    return _whoosh(rng, 0.75, p, [(0, 350), (p, 2000 * (1 + 0.1 * v)), (0.75, 600)], 1.6)


@sound("whoosh_fast", "whoosh", "هواء سريع", "Fast whoosh", "سحبة سريعة، دخول قوي", ("swipe",), 3)
def _(rng, v):
    return _whoosh(rng, 0.38, 0.24, [(0, 800), (0.24, 3800 - 300 * v), (0.38, 1800)], 1.6, (-0.6, 0.6), 0.15, 0.1)


@sound("whoosh_deep", "whoosh", "هواء عميق", "Deep whoosh", "انتقال بين مشاهد", ("transition",))
def _(rng, v):
    d = 1.1
    w = _whoosh(rng, d, 0.55, [(0, 160), (0.55, 900), (d, 220)], 0.9, room=0.25)
    sub = osc(glide(d, [(0, 70), (d, 45)]), d) * bell(d, 0.55) * 0.35
    return mix(w, st(sub))


@sound("whip", "whoosh", "سحبة كرباج", "Whip", "انتقال whip / swipe سريع", ("transition", "swipe"), 2)
def _(rng, v):
    d = 0.3
    n = noise(rng, d)
    body = biquad(n, "bp", glide(d, [(0, 1200), (0.21, 6000 - 1200 * v), (d, 4000)]), 1.0) * bell(d, 0.21, 3, 0.5)
    snap = biquad(noise(rng, 0.01), "hp", 3000) * decay(0.01, 0.0015)
    return reverb(mix(st(body, ramp(d, [(0, -0.7), (d, 0.7)])), at(st(snap * 0.6), 0.21)), 0.4, 0.1)


@sound("whoosh_in", "whoosh", "سحب للداخل", "Suck-in whoosh", "قبل ظهور عنوان مباشرة (ينتهي بقطع)", ("riser", "reverse"))
def _(rng, v):
    d = 0.9
    t = T(d)
    e = (t / d) ** 3 * np.clip((d - t) / 0.02, 0, 1)
    body = biquad(noise(rng, d), "bp", glide(d, [(0, 300), (d, 3500)]), 1.0) * e
    return st(body)


@sound("swipe_ui", "whoosh", "سحبة واجهة", "UI swipe", "كرت/إشعار يدخل من الجنب", ("ui", "slide"))
def _(rng, v):
    return _whoosh(rng, 0.22, 0.12, [(0, 1200), (0.12, 3000), (0.22, 2000)], 1.0, (-0.3, 0.3), 0.1, 0.05)


# ---- UI
@sound("click", "ui", "كلك", "Click", "ضغطة زر أو مؤشر", ("cursor", "button"), 3)
def _(rng, v):
    s = [1, 0.9, 1.12][v]
    d = 0.05
    return st(biquad(noise(rng, d), "bp", 3500 * s, 1.5) * decay(d, 0.0015) * 1.6 + osc(2200 * s, d) * decay(d, 0.004) * 0.5)


@sound("click_soft", "ui", "كلك ناعم", "Soft click", "اختيار، تبديل هادئ", ("button",))
def _(rng, v):
    d = 0.06
    return st(biquad(noise(rng, d), "lp", 1800) * decay(d, 0.003) * 1.5 + osc(900, d) * decay(d, 0.008) * 0.6)


@sound("tap", "ui", "نقرة", "Tap", "نقرة خشبية لعنصر صغير", ("element",), 3)
def _(rng, v):
    s = [1, 0.85, 1.2][v]
    d = 0.12
    body = osc(glide(d, [(0, 1100 * s), (0.03, 700 * s), (d, 650 * s)]), d) * decay(d, 0.018, 0.0008)
    snap = biquad(noise(rng, d), "hp", 2000) * decay(d, 0.002) * 0.4
    return reverb(st(body + snap), 0.25, 0.1)


@sound("pop", "ui", "بوب", "Pop", "كبسولة/أيقونة/كلمة تطلع", ("pill", "icon", "word"), 3)
def _(rng, v):
    s = [1, 0.85, 1.22][v]
    d = 0.14
    t = T(d)
    f = 300 * s * (1 + 3 * (1 - np.exp(-t / 0.01)))
    body = osc(f, d) * decay(d, 0.03, 0.001)
    click = biquad(noise(rng, d), "bp", 2500, 1) * decay(d, 0.0015) * 0.3
    return st(body + click)


@sound("pop_low", "ui", "بوب غليظ", "Low pop", "عنصر كبير يطلع", ("card",))
def _(rng, v):
    d = 0.18
    t = T(d)
    return st(osc(160 * (1 + 2.5 * (1 - np.exp(-t / 0.012))), d) * decay(d, 0.045, 0.001))


@sound("bubble", "ui", "فقاعة", "Bubble", "فقاعة محادثة / عنصر ناعم", ("chat", "soft"), 2)
def _(rng, v):
    d = 0.22
    f = glide(d, [(0, 350 + 80 * v), (0.12, 1400 + 200 * v), (d, 1500)])
    return st(osc(f, d) * decay(d, 0.05, 0.004))


def _toggle(rng, up):
    d = 0.16
    a = biquad(noise(rng, 0.02), "bp", 3000, 1.5) * decay(0.02, 0.0012)
    b = biquad(noise(rng, 0.02), "bp", 4200, 1.5) * decay(0.02, 0.0012)
    tone = osc(glide(0.1, [(0, 880), (0.1, 1320)] if up else [(0, 1320), (0.1, 880)]), 0.1) * decay(0.1, 0.03) * 0.3
    first, second = (a, b) if up else (b, a)
    return mix(st(first), at(st(second), 0.05), at(st(tone), 0.04), st(np.zeros(N(d))))


@sound("toggle_on", "ui", "تشغيل", "Toggle on", "سويتش يشتغل، ✓ تنضاف", ("switch",))
def _(rng, v):
    return _toggle(rng, True)


@sound("toggle_off", "ui", "إطفاء", "Toggle off", "سويتش يطفي، عنصر ينشال", ("switch",))
def _(rng, v):
    return _toggle(rng, False)


def _key(rng, s=1.0, space=False):
    d = 0.08
    thock = osc((120 if space else 180) * s, d) * decay(d, 0.014 if space else 0.01, 0.0008) * (0.9 if space else 0.6)
    down = biquad(noise(rng, d), "bp", 2600 * s, 1.2) * decay(d, 0.004) * 1.3
    up = np.zeros(N(d))
    up[N(0.028):N(0.048)] = biquad(noise(rng, 0.02), "bp", 3500 * s, 1.5) * decay(0.02, 0.002) * 0.4
    return thock + down + up


@sound("key", "ui", "زر كيبورد", "Key press", "حرف واحد", ("typing",), 3)
def _(rng, v):
    return st(_key(rng, [1, 0.93, 1.08][v]))


@sound("typing", "ui", "كتابة كيبورد", "Typing", "نص ينكتب حرف حرف / شريط بحث", ("typing", "search"))
def _(rng, v):
    out, t = [], 0.04
    while t < 2.0:
        sp = rng.random() < 0.1
        k = _key(rng, rng.uniform(0.9, 1.1), sp) * rng.uniform(0.6, 1.0)
        out.append(at(st(k, rng.uniform(-0.15, 0.15)), t))
        t += rng.uniform(0.06, 0.15) + (0.2 if rng.random() < 0.06 else 0)
    return reverb(mix(*out), 0.3, 0.06)


@sound("scroll_tick", "ui", "تكة تمرير", "Scroll tick", "قائمة تتمرر، تكات صغيرة", ("list",))
def _(rng, v):
    d = 0.025
    return st(biquad(noise(rng, d), "hp", 5000) * decay(d, 0.0008) * 1.5 + osc(4000, d) * decay(d, 0.002) * 0.3)


# ---- notifications
@sound("ding", "notify", "دينگ", "Ding", "معلومة مهمة، رقم يوصل", ("bell",))
def _(rng, v):
    d = 1.6
    return reverb(st(fm_bell(1568, d, 3.5, 2.0, 0.55) + 0.2 * osc(3136, d) * decay(d, 0.2)), 1.0, 0.2)


def _chime(notes, gap=0.09):
    d = 0.9
    return reverb(mix(*[at(st(fm_bell(f, d, 2.0, 1.5, 0.35), (i - 1) * 0.25), i * gap) for i, f in enumerate(notes)]), 1.1, 0.25)


@sound("chime_up", "notify", "نغمة صاعدة", "Chime up", "شي إيجابي يظهر", ("positive",))
def _(rng, v):
    return _chime([1047, 1319, 1568])


@sound("chime_down", "notify", "نغمة نازلة", "Chime down", "عنصر يختفي، نهاية", ("close",))
def _(rng, v):
    return _chime([1568, 1319, 1047])


@sound("notify", "notify", "إشعار", "Notification", "إشعار ينزل من فوق", ("ios", "banner"))
def _(rng, v):
    return reverb(mix(st(marimba(784)), at(st(marimba(1175)), 0.11)), 0.5, 0.15)


@sound("message_in", "notify", "رسالة واصلة", "Message in", "فقاعة محادثة من الطرف الثاني", ("chat",))
def _(rng, v):
    d = 0.12
    a = osc(glide(d, [(0, 700), (d, 640)]), d) * decay(d, 0.04, 0.003)
    b = osc(glide(d, [(0, 1050), (d, 990)]), d) * decay(d, 0.05, 0.003)
    return reverb(mix(st(a), at(st(b), 0.09)), 0.4, 0.1)


@sound("message_out", "notify", "رسالة مرسلة", "Message sent", "فقاعة محادثة منك", ("chat",))
def _(rng, v):
    d = 0.2
    sw = biquad(noise(rng, d), "bp", glide(d, [(0, 1500), (d, 4000)]), 1) * bell(d, 0.14) * 0.6
    t = T(0.1)
    p = osc(500 * (1 + 2 * (1 - np.exp(-t / 0.008))), 0.1) * decay(0.1, 0.025, 0.001)
    return mix(st(sw, 0.2), at(st(p), 0.13))


@sound("success", "notify", "نجاح", "Success", "تم ✓، إنجاز", ("done",))
def _(rng, v):
    notes = [523, 659, 784, 1047]
    return reverb(mix(*[at(st(marimba(f) * 0.8, (i - 1.5) * 0.2), i * 0.07) for i, f in enumerate(notes)]), 0.8, 0.2)


@sound("error", "notify", "خطأ", "Error", "✗، شي غلط", ("wrong",))
def _(rng, v):
    a = osc(330, 0.12, "square") * bell(0.12, 0.005, 1, 0.3)
    b = osc(247, 0.22, "square") * bell(0.22, 0.005, 1, 0.6)
    return st(biquad(np.concatenate([a, np.zeros(N(0.03)), b]), "lp", 2000) * 0.8)


@sound("alert", "notify", "تنبيه", "Alert", "انتبه! تحذير", ("warning",))
def _(rng, v):
    beep = (osc(1000, 0.07) + 0.3 * osc(1000, 0.07, "tri")) * bell(0.07, 0.004, 1, 0.2)
    return mix(*[at(st(beep), i * 0.13) for i in range(3)])


# ---- impacts
@sound("hit_deep", "impact", "ضربة عميقة", "Deep hit", "رقم ضخم، لحظة مهمة", ("boom", "hook"))
def _(rng, v):
    d = 3.0
    x = (kick(d, 110, 38, 0.05, 0.7) + biquad(noise(rng, d), "lp", 2500) * decay(d, 0.02) * 0.8
         + biquad(noise(rng, d), "lp", 150) * decay(d, 0.6, 0.01) * 1.2)
    return reverb(st(np.tanh(1.8 * x)), 1.8, 0.25, 3000)


@sound("hit_punch", "impact", "ضربة قصيرة", "Punch hit", "كلمة/عنوان ينضرب", ("slam", "text"), 2)
def _(rng, v):
    d = 0.5
    x = kick(d, 180 - 30 * v, 55, 0.02, 0.15) + biquad(noise(rng, d), "bp", 1800 + 600 * v, 0.8) * decay(d, 0.012) * 0.9
    return reverb(st(np.tanh(2 * x)), 0.4, 0.1)


@sound("slam", "impact", "صدمة عنوان", "Title slam", "Hook ضخم ينزل على الشاشة", ("hook", "title"))
def _(rng, v):
    d = 1.2
    x = (kick(d, 180, 55, 0.02, 0.15) + kick(d, 90, 40, 0.04, 0.4) * 0.8
         + biquad(noise(rng, d), "bp", 1600, 0.7) * decay(d, 0.015) * 0.8 + fm_bell(220, d, 1.41, 4, 0.15) * 0.15)
    return reverb(st(np.tanh(1.6 * x)), 1.2, 0.2, 4000)


@sound("thud", "impact", "خبطة", "Thud", "شي يطيح/ينحط", ("drop",))
def _(rng, v):
    d = 0.35
    return st(kick(d, 120, 60, 0.02, 0.08) * 0.9 + biquad(noise(rng, d), "lp", 600) * decay(d, 0.02) * 1.2)


@sound("boom", "impact", "بوم سينمائي", "Cinematic boom", "افتتاحية، كشف كبير", ("cinematic", "trailer"))
def _(rng, v):
    d = 4.0
    x = (kick(d, 80, 28, 0.12, 1.5) + biquad(noise(rng, d), "lp", 250) * decay(d, 1.2, 0.01) * 1.6
         + biquad(noise(rng, d), "bp", 1500) * decay(d, 0.05) * 0.4)
    return reverb(st(np.tanh(1.5 * x)), 3.0, 0.35, 2500)


@sound("braam", "impact", "برااام", "Braam", "لحظة درامية ثقيلة", ("cinematic", "trailer"))
def _(rng, v):
    d = 3.0
    x = sum(osc(f, d, "saw") for f in (55, 55 * 1.006, 110 * 0.996, 82.4, 41.2))
    x = biquad(x, "lp", glide(d, [(0, 200), (0.25, 1800), (d, 300)]), 1.2) * bell(d, 0.08, 1, 1.2)
    return reverb(st(np.tanh(1.2 * x)), 2.5, 0.3, 3000)


# ---- motion elements
@sound("tick", "element", "تكة", "Tick", "رقم يتغير، ثانية تمر", ("counter",))
def _(rng, v):
    d = 0.025
    return st(biquad(noise(rng, d), "hp", 4000) * decay(d, 0.0007) * 1.5 + osc(3200, d) * decay(d, 0.002) * 0.4)


@sound("count_up", "element", "عدّاد يعد", "Count up", "رقم يعدّ لين يوصل", ("counter", "number"))
def _(rng, v):
    out, t, i = [], 0.0, 0
    while t < 1.5:
        f = 2000 + 2000 * t / 1.5
        tk = osc(f, 0.02) * decay(0.02, 0.0025) * 0.5 + biquad(noise(rng, 0.02), "hp", 5000) * decay(0.02, 0.0006)
        out.append(at(st(tk), t))
        t += 0.11 - 0.075 * min(t / 1.2, 1)
        i += 1
    return mix(*out)


@sound("count_end", "element", "نهاية العد", "Count land", "الرقم يوصل النهاية", ("counter",))
def _(rng, v):
    return reverb(mix(st(marimba(1568)), st(biquad(noise(rng, 0.03), "bp", 3000, 1.2) * decay(0.03, 0.002))), 0.7, 0.2)


@sound("sparkle", "element", "لمعة نجوم", "Sparkle", "شي يلمع، عنصر سحري", ("shine", "magic"))
def _(rng, v):
    d = 1.0
    parts = [at(st(osc(rng.uniform(3500, 9000), 0.3) * decay(0.3, 0.08, 0.001) * rng.uniform(0.2, 0.5),
                   rng.uniform(-0.8, 0.8)), rng.uniform(0, 0.6)) for _ in range(18)]
    parts.append(st(biquad(noise(rng, d), "hp", 7000) * bell(d, 0.3) * 0.08))
    return reverb(mix(*parts), 0.8, 0.3, 9000)


@sound("shine", "element", "لمعة عابرة", "Shine sweep", "لمعة تمر على نص/كرت", ("shine", "glass"))
def _(rng, v):
    d = 0.9
    t = T(d)
    tone = osc(glide(d, [(0, 2000), (d, 6000)]), d) * (0.6 + 0.4 * np.sin(2 * np.pi * 30 * t)) * bell(d, 0.4) * 0.3
    air = biquad(noise(rng, d), "hp", 6000) * bell(d, 0.4) * 0.3
    return reverb(st(tone + air, ramp(d, [(0, -0.4), (d, 0.4)])), 0.7, 0.25, 9000)


@sound("glitch", "element", "قلتش", "Glitch", "نص يتقطع، تشويش رقمي", ("glitch", "digital"), 2)
def _(rng, v):
    out, t = [], 0.0
    while t < 0.55:
        seg = rng.uniform(0.015, 0.06)
        kind = rng.integers(4)
        if kind == 0:
            x = osc(rng.uniform(200, 2000), seg, "square") * 0.5
        elif kind == 1:
            hold = int(rng.integers(8, 40))
            x = np.repeat(noise(rng, seg)[::hold], hold)[:N(seg)]
        elif kind == 2:
            x = osc(rng.uniform(60, 180), seg, "saw") * 0.7
        else:
            x = np.zeros(N(seg))
        out.append(at(st(x, rng.uniform(-0.7, 0.7)), t))
        t += seg
    return mix(*out)


def _buzz(d):
    x = osc(120, d, "saw") * 0.6 + osc(240, d) * 0.3 + osc(60, d) * 0.4
    return biquad(x, "lp", 2500)


@sound("neon_on", "element", "نيون يشتغل", "Neon flicker on", "عنوان نيون يولّع", ("neon",))
def _(rng, v):
    d = 1.2
    gate, t = np.zeros(N(d)), 0.0
    clicks = []
    while t < 0.45:
        on, off = rng.uniform(0.015, 0.06), rng.uniform(0.02, 0.08)
        gate[N(t):N(t + on)] = rng.uniform(0.5, 1)
        clicks.append(at(st(biquad(noise(rng, 0.004), "hp", 3000) * 0.5), t))
        t += on + off
    gate[N(t):] = 1
    gate = biquad(gate, "lp", 400) * ramp(d, [(0, 1), (0.8, 1), (d, 0)])
    zap = biquad(noise(rng, 0.06), "bp", 4000, 1) * decay(0.06, 0.015)
    return mix(st(_buzz(d) * gate * 0.7), st(zap * 0.6), *clicks)


@sound("neon_hum", "element", "طنين نيون", "Neon hum", "خلفية خفيفة تحت النيون (تتكرر)", ("neon", "loop"))
def _(rng, v):
    d = 3.0
    jitter = 0.85 + 0.15 * biquad(rng.standard_normal(N(d)), "lp", 8) * 8
    x = _buzz(d) * jitter * ramp(d, [(0, 0), (0.2, 1), (d - 0.2, 1), (d, 0)])
    return st(x) * 0.25


def _stroke(rng, d, fpath=None, circle=False):
    n = noise(rng, d)
    grain = np.abs(biquad(rng.standard_normal(N(d)), "lp", 180))
    grain = 0.4 + grain / (grain.max() + 1e-9)
    t = T(d)
    f = 3000 + 1200 * np.sin(2 * np.pi * 1.2 * t) if circle else (fpath if fpath is not None else 3800)
    speed = 0.6 + 0.4 * np.abs(np.cos(2 * np.pi * 1.2 * t)) if circle else 1
    env = ramp(d, [(0, 0), (0.03, 1), (d - 0.08, 0.9), (d, 0)])
    tip = biquad(n, "bp", f, 0.7) * grain * speed * env
    rub = biquad(n, "lp", 900) * env * 0.3
    return tip + rub


@sound("draw_line", "element", "رسم خط", "Marker line", "خط تحت / سهم ينرسم", ("marker", "draw"), 3)
def _(rng, v):
    return st(_stroke(rng, [0.55, 0.45, 0.7][v], 3800 - 400 * v))


@sound("draw_circle", "element", "رسم دائرة", "Marker circle", "دائرة تنرسم حول شي", ("marker", "draw"))
def _(rng, v):
    return st(_stroke(rng, 0.9, circle=True))


@sound("scribble", "element", "شخبطة", "Scribble", "شطب / شخبطة", ("marker",))
def _(rng, v):
    out, t = [], 0.0
    for i in range(7):
        d = rng.uniform(0.08, 0.18)
        out.append(at(st(_stroke(rng, d, rng.uniform(3000, 4500)) * rng.uniform(0.7, 1), 0.15 * (-1) ** i), t))
        t += d + 0.015
    return mix(*out)


@sound("paper", "element", "ورق", "Paper slide", "ورقة/قصاصة تدخل (كولاج)", ("collage", "paper"), 2)
def _(rng, v):
    d = 0.5
    body = biquad(biquad(noise(rng, d), "lp", 3500), "bp", 1500 + 300 * v, 0.5) * bell(d, 0.15, 1.5, 1)
    crackle = np.zeros(N(d))
    idx = rng.integers(0, N(d), 40)
    crackle[idx] = rng.uniform(-1, 1, 40)
    crackle = biquad(crackle, "hp", 3000) * bell(d, 0.15, 1, 1) * 2
    return st(body * 1.5 + crackle)


@sound("stamp", "element", "ختم", "Stamp", "ختم/لاصق ينحط", ("collage",))
def _(rng, v):
    d = 0.4
    x = kick(d, 140, 70, 0.015, 0.05) + biquad(noise(rng, d), "lp", 1500) * decay(d, 0.015) * 1.2
    return reverb(st(x), 0.3, 0.1)


@sound("shutter", "element", "كاميرا", "Camera shutter", "صورة تنلقط / تطلع", ("photo",))
def _(rng, v):
    def clk(f):
        return biquad(noise(rng, 0.04), "hp", 2000) * decay(0.04, 0.003) * 1.2 + osc(f, 0.04) * decay(0.04, 0.01) * 0.4
    return reverb(mix(st(clk(600)), at(st(clk(450) * 0.8), 0.09)), 0.25, 0.08)


def _zoom(rng, inward):
    d = 0.7
    t = T(d)
    e = (t / d) ** 1.5 * np.clip((d - t) / 0.03, 0, 1) if inward else ((d - t) / d) ** 1.5 * np.clip(t / 0.01, 0, 1)
    path = [(0, 400), (d, 3000)] if inward else [(0, 3000), (d, 400)]
    body = biquad(noise(rng, d), "bp", glide(d, path), 1.2) * e
    tone = osc(glide(d, [(p[0], p[1] * 0.3) for p in path]), d) * e * 0.15
    return reverb(st(body + tone), 0.4, 0.1)


@sound("zoom_in", "element", "زوم للداخل", "Zoom in", "punch-in / تقريب", ("camera", "zoom"))
def _(rng, v):
    return _zoom(rng, True)


@sound("zoom_out", "element", "زوم للخارج", "Zoom out", "تبعيد الكاميرا", ("camera", "zoom"))
def _(rng, v):
    return _zoom(rng, False)


@sound("coin", "element", "عملة", "Coin", "سعر، نقاط، خصم", ("price", "money"))
def _(rng, v):
    a = osc(988, 0.07, "square") * 0.5
    b = osc(1319, 0.45, "square") * decay(0.45, 0.12) * 0.5
    return st(biquad(np.concatenate([a, b]), "lp", 6000))


@sound("cash", "element", "كاش", "Cash", "سعر / بيع / ربح", ("price", "money"))
def _(rng, v):
    d = 1.0
    x = mix(st(biquad(noise(rng, 0.02), "hp", 3000) * decay(0.02, 0.002) * 0.6),
            at(st(fm_bell(2637, d, 1.5, 3, 0.5) * 0.6, -0.2), 0.02), at(st(fm_bell(3136, d, 1.5, 3, 0.45) * 0.5, 0.2), 0.05),
            at(st(kick(0.2, 120, 60, 0.02, 0.05) * 0.5), 0.06))
    return reverb(x, 0.6, 0.15)


@sound("pin_drop", "element", "دبوس خريطة", "Map pin", "دبوس ينزل على الخريطة", ("map", "pin"))
def _(rng, v):
    d = 0.8
    ping = lambda a: st(fm_bell(3520, d, 2.76, 1, 0.3) * a)
    return reverb(mix(ping(1), at(ping(0.4), 0.12), at(ping(0.15), 0.2)), 0.6, 0.2)


# ---- drama
def _riser(rng, d):
    t = T(d)
    f = 150 * 8 ** ((t / d) ** 1.2)
    x = sum(osc(f * k, d, "saw") for k in (1, 1.007, 0.994)) / 3
    x = biquad(x, "lp", glide(d, [(0, 400), (d, 6000)])) * (t / d) ** 2
    hiss = biquad(noise(rng, d), "bp", glide(d, [(0, 1000), (d, 6000)]), 0.7) * (t / d) ** 3 * 0.6
    cut = np.clip((d - t) / 0.01, 0, 1)
    return reverb(st(np.tanh(1.3 * (x + hiss)) * cut), 0.8, 0.15)


@sound("riser", "drama", "رايزر", "Riser", "يبني توتر قبل كشف/قطع (2.5ث)", ("build", "transition"))
def _(rng, v):
    return _riser(rng, 2.5)


@sound("riser_long", "drama", "رايزر طويل", "Long riser", "بناء طويل قبل لحظة كبيرة (5ث)", ("build",))
def _(rng, v):
    return _riser(rng, 5.0)


@sound("downlifter", "drama", "نزول", "Downlifter", "بعد ضربة، رجوع للهدوء", ("transition",))
def _(rng, v):
    d = 1.8
    x = osc(glide(d, [(0, 600), (d, 60)]), d) * decay(d, 0.6, 0.005) * 0.6
    x += biquad(noise(rng, d), "lp", glide(d, [(0, 6000), (d, 200)])) * decay(d, 0.5, 0.005)
    return reverb(st(x), 1.2, 0.25)


@sound("drone_dark", "drama", "درون غامق", "Dark drone", "خلفية توتر/غموض (تتكرر)", ("suspense", "loop"))
def _(rng, v):
    d = 5.0
    t = T(d)
    x = sum(osc(f, d, "saw") for f in (41.2, 41.2 * 1.004, 61.7, 82.4 * 0.998))
    x = biquad(x, "lp", 280 + 120 * np.sin(2 * np.pi * 0.2 * t), 1.5) * ramp(d, [(0, 0), (1, 1), (d - 1.5, 1), (d, 0)])
    return reverb(st(x), 3.0, 0.3, 2000)


@sound("stinger", "drama", "ستنگر", "Stinger", "صدمة/مفاجأة درامية", ("shock", "reveal"))
def _(rng, v):
    d = 2.5
    hit = kick(d, 110, 38, 0.05, 0.5) + biquad(noise(rng, d), "lp", 2500) * decay(d, 0.02) * 0.8
    cluster = sum(fm_bell(f, d, 1.0, 3, 1.2, 0.3) for f in (311, 330, 466)) * 0.25
    return reverb(st(np.tanh(1.5 * hit) + cluster), 2.5, 0.35, 3500)


@sound("reverse_swell", "drama", "سحبة عكسية", "Reverse swell", "يتصاعد وينقطع على القطع", ("transition", "reverse"))
def _(rng, v):
    d = 1.0
    hit = biquad(noise(rng, d), "bp", 1200, 0.6) * decay(d, 0.3, 0.001) + fm_bell(880, d, 2, 2, 0.5) * 0.5
    tail = reverb(st(hit), 1.2, 0.9)
    return tail[::-1].copy()


@sound("tension_tick", "drama", "تكتكة توتر", "Tension tick", "عد تنازلي / انتظار (تتكرر)", ("clock", "loop"))
def _(rng, v):
    parts = []
    for i in range(4):
        tk = biquad(noise(rng, 0.03), "bp", 2500 if i % 2 else 2000, 2) * decay(0.03, 0.002) * 1.5
        parts.append(at(st(tk), i * 0.5))
        parts.append(at(st(kick(0.3, 70, 50, 0.02, 0.12) * 0.5), i * 0.5))
    return reverb(mix(*parts), 0.6, 0.15)


# ---- reactions
@sound("correct", "reaction", "صح", "Correct", "إجابة صح ✓", ("quiz", "yes"))
def _(rng, v):
    return reverb(mix(st(marimba(880)), at(st(marimba(1319)), 0.09)), 0.6, 0.15)


@sound("wrong", "reaction", "غلط", "Wrong buzzer", "إجابة غلط ✗", ("quiz", "no"))
def _(rng, v):
    a = osc(196, 0.15, "saw") * bell(0.15, 0.005, 1, 0.3)
    b = osc(147, 0.32, "saw") * bell(0.32, 0.005, 1, 0.8)
    return st(biquad(np.concatenate([a, np.zeros(N(0.04)), b]), "lp", 1200))


@sound("boing", "reaction", "بوينگ", "Boing", "كوميدي، شي ينط", ("comedy", "bounce"))
def _(rng, v):
    d = 0.7
    t = T(d)
    f = glide(d, [(0, 180), (d, 260)]) * (1 + 0.25 * np.exp(-t / 0.2) * np.sin(2 * np.pi * 11 * t))
    return st((osc(f, d) * 0.7 + osc(f, d, "tri") * 0.3) * decay(d, 0.25, 0.002))


@sound("scratch", "reaction", "سكراتش", "Record scratch", "وقفة مفاجئة «استنى!»", ("stop", "comedy"))
def _(rng, v):
    d = 0.45
    t = T(d)
    f = 250 + 900 * np.abs(np.sin(2 * np.pi * 3.5 * t))
    x = osc(f, d, "saw") * 0.4 + biquad(noise(rng, d), "bp", f * 2, 1.5) * 0.9
    return st(biquad(x, "lp", 4000) * bell(d, 0.02, 1, 0.6))


# ---------------------------------------------------------------- output
def seed_of(id, v):
    return zlib.crc32(f"{id}:{v}".encode())


def write_wav(path, x):
    y = (np.clip(x, -1, 1) * 8388607).astype("<i4")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(y.view(np.uint8).reshape(-1, 4)[:, :3].tobytes())


AUDITION = """<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>reel-sfx</title><style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1c1a;--mut:#6b6862;--line:#e3e0da;--acc:#b8432f}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1e1d1b;--ink:#f0eee9;--mut:#9a968e;--line:#2e2c29;--acc:#e0765f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"SF Arabic","Geeza Pro",sans-serif;padding:24px 16px 60px}
h1{font-size:22px;margin:0 0 4px}p.s{color:var(--mut);margin:0 0 20px}h2{font-size:15px;color:var(--mut);margin:26px 0 8px;font-weight:600}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px}
button{all:unset;cursor:pointer;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;display:flex;flex-direction:column;gap:2px}
button:hover{border-color:var(--acc)}button.on{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc)}
b{font-weight:600}small{color:var(--mut);font-size:12.5px}code{font:12px ui-monospace,Menlo,monospace;color:var(--acc);direction:ltr;text-align:right}
</style><h1>reel-sfx</h1><p class="s">__COUNT__ صوت متولّد بالكود · اضغط للتشغيل</p><div id="r"></div><script>
const D=__DATA__;const r=document.getElementById('r');let cur=null,btn=null;
for(const [c,[ar]] of Object.entries(D.categories)){const items=D.sounds.filter(s=>s.category===c);if(!items.length)continue;
const h=document.createElement('h2');h.textContent=ar;r.append(h);const g=document.createElement('div');g.className='g';r.append(g);
for(const s of items)for(const f of s.files){const b=document.createElement('button');
b.innerHTML=`<b>${s.name.ar}${s.files.length>1?' · '+(s.files.indexOf(f)+1):''}</b><small>${s.use}</small><code>${f}</code>`;
b.onclick=()=>{if(cur){cur.pause();btn.classList.remove('on')}cur=new Audio(f);btn=b;b.classList.add('on');cur.play();cur.onended=()=>b.classList.remove('on')};g.append(b)}}
</script></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--only", help="comma-separated ids")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for s in SOUNDS:
            print(f"{s['cat']:9} {s['id']:15} ×{s['variants']}  {s['ar']} — {s['use']}")
        return
    only = set(a.only.split(",")) if a.only else None
    os.makedirs(a.out, exist_ok=True)
    idx_path = os.path.join(a.out, "index.json")
    index = {}
    if only and os.path.exists(idx_path):
        index = {s["id"]: s for s in json.load(open(idx_path))["sounds"]}
    for s in SOUNDS:
        if only and s["id"] not in only:
            continue
        files, durs = [], []
        for v in range(s["variants"]):
            x = finish(s["fn"](np.random.default_rng(seed_of(s["id"], v)), v), PEAK[s["cat"]])
            name = s["id"] + (f"_{v + 1}" if v else "") + ".wav"
            write_wav(os.path.join(a.out, name), x)
            files.append(name)
            durs.append(round(len(x) / SR, 3))
        index[s["id"]] = {"id": s["id"], "category": s["cat"], "name": {"ar": s["ar"], "en": s["en"]}, "use": s["use"],
                          "tags": s["tags"], "files": files, "duration": max(durs)}
        print(f"ok  {s['id']:15} {len(files)} file(s)  {max(durs):.2f}s", flush=True)
    order = [s["id"] for s in SOUNDS]
    data = {"version": 1, "generator": "reel-sfx/synth.py", "sample_rate": SR, "categories": CATS,
            "sounds": sorted(index.values(), key=lambda s: order.index(s["id"]) if s["id"] in order else 1e9)}
    json.dump(data, open(idx_path, "w"), ensure_ascii=False, indent=1)
    page = AUDITION.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace(
        "__COUNT__", str(sum(len(s["files"]) for s in data["sounds"])))
    open(os.path.join(a.out, "audition.html"), "w").write(page)
    print(f"\n{a.out}  ·  open audition.html to listen")


if __name__ == "__main__":
    main()
