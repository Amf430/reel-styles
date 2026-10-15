// Paper diorama in 2.5D: every visible thing is a flat "leaf" placed in 3D under one perspective stage.
// A keyframed camera (look-at x/y, dolly z, tilt rx/ry, focus depth fz) flies through the world;
// each leaf blurs by its distance from the focus depth (depth of field). Filters live on leaves only —
// a filter, opacity or overflow on #cam would flatten the whole world.
//
//   const tl = gsap.timeline();  dioInit(document.getElementById("cam"), tl, paletteFrom(CONTENT.palette));
//   leaf(...) / popLeaf(...) / sticker(...) / dressAt(...) / key(...)
//   window.__timelines.main = dioMaster(gsap.timeline({ paused: true }), DURATION)

const DIO = { P: 1600, leaves: [], keys: [], cam: { t: 0 }, camK: { k: 1 }, seed: 7 };
const PAL = {};
const rnd = () => ((DIO.seed = (DIO.seed * 16807) % 2147483647) / 2147483647);   // seeded: every render identical

// the set's colours, derived from the four brand colours in content.js (primary, accent, light, ink)
function mixHex(a, b, t) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}
function paletteFrom(c) {
  const w = "#ffffff";
  return { primary: c.primary, accent: c.accent, light: c.light, ink: c.ink,
    paper: mixHex(c.accent, w, 0.97), edge: mixHex(c.accent, w, 0.72), bg: mixHex(c.accent, w, 0.94),
    hill1: mixHex(c.accent, w, 0.86), hill2: mixHex(c.accent, w, 0.74), hill3: mixHex(c.accent, w, 0.6),
    far1: mixHex(c.accent, w, 0.93), far2: mixHex(c.accent, w, 0.88), far3: mixHex(c.accent, w, 0.83) };
}

function dioInit(camEl, tl, palette) {
  DIO.camEl = camEl; DIO.tl = tl;
  Object.assign(PAL, palette);
  for (const [k, v] of Object.entries(palette)) document.documentElement.style.setProperty(`--${k}`, v);
}

// ── leaves: one flat element at a 3D spot; GSAP tweens its state object, render() writes it ──
// state: x y z (world px), rx ry rz (deg), s (scale), o (opacity), b (extra blur), dy (offset),
//        sharp (never defocus), k (defocus strength), win [t0, t1] (exists only then), reach (half depth of big floors)
function leaf(html, st, cls = "", style = "") {
  const el = document.createElement("div");
  el.className = "L " + cls; el.innerHTML = html; el.style.cssText = style;
  DIO.camEl.appendChild(el);
  const s = Object.assign({ x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0, s: 1, o: 1, b: 0, dy: 0 }, st);
  DIO.leaves.push({ el, s });
  return s;
}
const leafEl = (s) => DIO.leaves.find((l) => l.s === s).el;
// leaves made since index `from` exist only between t0 and t1, so far scenes never show through near ones
const scene = (from, t0, t1) => DIO.leaves.slice(from).forEach(({ s }) => { s.win = s.win || [t0, t1]; });
const mark = () => DIO.leaves.length;

// ── camera ──
function key(t, x, y, z, rx, ry, fz, ease = "none") { DIO.keys.push({ t, x, y, z, rx, ry, fz, ease: gsap.parseEase(ease) }); }
function camAt(t) {
  const K = DIO.keys;
  let i = 0; while (i < K.length - 2 && K[i + 1].t <= t) i++;
  const a = K[i], b = K[i + 1];
  const e = b.ease(Math.min(1, Math.max(0, (t - a.t) / (b.t - a.t || 1))));
  const m = (k) => a[k] + (b[k] - a[k]) * e;
  return { x: m("x"), y: m("y"), z: m("z"), rx: m("rx"), ry: m("ry"), fz: m("fz") };
}
function render() {
  const P = DIO.P, c = camAt(DIO.cam.t), k = DIO.camK.k;
  DIO.camEl.style.transform = `rotateX(${c.rx}deg) rotateY(${c.ry}deg) scale3d(${k}, ${k}, ${k}) translate3d(${-c.x}px, ${-c.y}px, ${c.z}px)`;
  const focus = (c.fz + c.z) * k;
  for (const { el, s } of DIO.leaves) {
    const depth = (s.z + c.z) * k;
    if ((s.win && (DIO.cam.t < s.win[0] || DIO.cam.t > s.win[1])) || depth - (s.reach || 0) > P - 60 || s.o <= 0.001) { el.style.visibility = "hidden"; continue; }
    el.style.visibility = "visible";
    const blur = (s.sharp ? 0 : Math.min(14, Math.abs(depth - focus) * 0.016 * (s.k ?? 1))) + s.b;
    el.style.transform = `translate3d(${s.x}px, ${s.y + s.dy}px, ${s.z}px) rotateX(${s.rx}deg) rotateY(${s.ry}deg) rotateZ(${s.rz}deg) scale(${s.s}) translate(-50%, -50%)`;
    el.style.filter = blur > 0.3 ? `blur(${blur.toFixed(2)}px)` : "none";
    const lens = depth > P - 400 ? Math.max(0, (P - 60 - depth) / 340) : 1;   // fade before a leaf hits the lens
    el.style.opacity = s.o * (s.f ?? 1) * lens;
  }
}
// content tweens first, then the camera draws the frame — reversed, the camera renders stale leaves
function dioMaster(master, duration) {
  master.add(DIO.tl, 0);
  master.fromTo(DIO.cam, { t: 0 }, { t: duration, duration, ease: "none", onUpdate: render }, 0);
  return master;
}

// ── movement ──
// a card drops in tilted and lands flat
function cardIn(s, at, d = 0.9, ry = 0, rx = 0) {
  DIO.tl.fromTo(s, { ry: ry - 14, rx: rx + 9, dy: 50, o: 0 }, { ry, rx, dy: 0, o: 1, duration: d, ease: "back.out(1.4)" }, at);
}
// a paper piece that stands up from the floor like a pop-up page (anchor its bottom: transform-origin 50% 100%)
function popLeaf(html, st, style = "transform-origin:50% 100%") {
  const s = leaf(`<div class="pop" style="${style}">${html}</div>`, Object.assign({ sharp: 1 }, st), "", "transform-style:preserve-3d");
  return { s, el: leafEl(s).querySelector(".pop") };
}
function popUp(p, at, d = 1.0) {
  DIO.tl.fromTo(p.el, { rotationX: 86 }, { rotationX: 0, duration: d, ease: "back.out(1.6)" }, at);
  DIO.tl.fromTo(p.el, { opacity: 0 }, { opacity: 1, duration: 0.12, ease: "none" }, at);
}
function popDown(p, at, d = 0.7) { DIO.tl.to(p.el, { rotationX: 88, duration: d, ease: "power2.in" }, at); }
const fadeOut = (list, at) => list.forEach((s, i) => DIO.tl.to(s, { o: 0, b: 8, duration: 0.4, ease: "power2.in" }, at + i * 0.04));

// a figure: one cut-out PNG/SVG (a sticker with a thin paper edge) standing on the floor at (x, footY, z).
// It stands up like a pop-up page, then lives until `end`: a slow sway and a breath. Loops are finite so every frame seeks.
function sticker(src, h, x, footY, z, at, end, w = h * 0.45) {
  const p = popLeaf(`<div class="fig" style="width:${w}px;height:${h}px"><div class="sway">${src.startsWith("<") ? src : `<img src="${src}">`}</div></div>`,
    { x, y: footY - h / 2, z });
  const sway = p.el.querySelector(".sway");
  popUp(p, at, 1.15);
  DIO.tl.fromTo(p.el, { scaleY: 1 }, { scaleY: 1.04, duration: 0.14, ease: "sine.out", yoyo: true, repeat: 1 }, at + 0.62);
  const t0 = at + 1, n = Math.max(1, Math.floor((end - t0) / 2.4));
  DIO.tl.fromTo(sway, { rotation: -1.1 }, { rotation: 1.1, duration: 1.2, ease: "sine.inOut", yoyo: true, repeat: n * 2 - 1 }, t0);
  DIO.tl.fromTo(sway, { scaleY: 1 }, { scaleY: 1.012, duration: 0.85, ease: "sine.inOut", yoyo: true, repeat: Math.max(0, Math.floor((end - t0) / 0.85)) }, t0);
  return p;
}

// ── words on the voice: each word slides in from the reading side, out of blur, and settles ──
const words = (t, style = "") => t.split(" ").map((w) => `<span class="w" style="${style}">${w}</span>`).join(" ");
const TITLE = (main, accent = "") => `<div class="title">${words(main)}${accent ? " " + words(accent, "color:var(--accent)") : ""}</div>`;
const SUB = (t) => `<div class="sub">${words(t)}</div>`;
function sayWords(s, times) {
  DIO.tl.set(s, { o: 1, b: 0, s: 1 }, times[0] - 0.01);
  leafEl(s).querySelectorAll(".w").forEach((w, i) => {
    const at = times[i] ?? times[times.length - 1] + 0.18 * (i - times.length + 1);
    DIO.tl.fromTo(w, { opacity: 0, x: 34, scale: 0.9, filter: "blur(14px)" }, { opacity: 1, x: 0, scale: 1, filter: "blur(0px)", duration: 0.55, ease: "expo.out" }, at - 0.08);
  });
}

// ── the set: every stop is framed by the same paper pieces — dense at the bottom and the sides, calm at the top centre ──
function HILLS(w, h, pal) {
  const layer = (base, amp, ph, valley, fill) => {
    const pts = [];
    for (let x = 0; x <= w; x += 300) {
      const v = Math.exp(-(((x - w / 2) / 700) ** 2));                  // a valley in the middle where a road can run
      pts.push([x, (base + amp * (0.65 * Math.sin(x / 520 + ph) + 0.35 * Math.sin(x / 230 + ph * 2))) * (1 - v) + valley * v]);
    }
    const d = pts.reduce((d, p, i, a) => {
      if (!i) return `M${p[0]} ${p[1]}`;
      const p0 = a[i - 2] || a[i - 1], p1 = a[i - 1], p3 = a[i + 1] || p;
      return d + ` C${p1[0] + (p[0] - p0[0]) / 6} ${p1[1] + (p[1] - p0[1]) / 6} ${p[0] - (p3[0] - p1[0]) / 6} ${p[1] - (p3[1] - p1[1]) / 6} ${p[0]} ${p[1]}`;
    }, "");
    return `<path d="${d}V${h}H0z" fill="${fill}" stroke="#fff" stroke-width="8"/>`;
  };
  return `<svg viewBox="0 0 ${w} ${h}" style="width:${w}px;height:${h}px;display:block">
    ${layer(h * 0.3, h * 0.16, 0.4, h * 0.74, pal[0])}${layer(h * 0.5, h * 0.12, 2.1, h * 0.84, pal[1])}${layer(h * 0.68, h * 0.08, 4.0, h * 0.92, pal[2])}</svg>`;
}
const CLOUD = (w) => `<svg viewBox="0 0 300 130" style="width:${w}px;height:${w * 130 / 300}px;display:block;overflow:visible">
  <g fill="var(--paper)"><circle cx="80" cy="82" r="44"/><circle cx="145" cy="58" r="56"/><circle cx="215" cy="80" r="42"/><rect x="40" y="82" width="220" height="44" rx="22"/></g>
  <rect x="44" y="108" width="212" height="18" rx="9" fill="var(--edge)"/></svg>`;
const BUSH = (h, a, b) => `<svg viewBox="0 0 200 120" style="width:${h * 200 / 120}px;height:${h}px;display:block;overflow:visible">
  <ellipse cx="100" cy="116" rx="92" ry="8" fill="rgba(16,40,40,.14)"/>
  <circle cx="62" cy="74" r="42" fill="${a}"/><circle cx="138" cy="78" r="38" fill="${a}"/><circle cx="100" cy="56" r="50" fill="${b}"/>
  <path d="M100 6a50 50 0 0 0-50 50h100A50 50 0 0 0 100 6z" fill="rgba(255,255,255,.16)"/></svg>`;
const bushColors = () => [[PAL.accent, PAL.primary], [PAL.light, PAL.accent], [PAL.primary, PAL.accent], [PAL.light, PAL.edge]];
function ground(x, z, fy) {
  return leaf(`<svg viewBox="0 0 7000 3600" style="width:7000px;height:3600px;display:block"><defs><radialGradient id="g${x}_${z}_${fy}">
    <stop offset="0" stop-color="${PAL.accent}" stop-opacity=".1"/><stop offset=".7" stop-color="${PAL.accent}" stop-opacity=".05"/><stop offset="1" stop-color="${PAL.accent}" stop-opacity="0"/></radialGradient></defs>
    <ellipse cx="3500" cy="1800" rx="3500" ry="1800" fill="url(#g${x}_${z}_${fy})"/></svg>`, { x, y: fy + 2, z, rx: 90, sharp: 1, reach: 1800 });
}
// a stop's set rises at `rise`: floor, two rows of hills, three clouds, bushes, two out-of-focus bushes in front.
// Returns [floor, ...pieces] so a stop can fold it away (popDown on hills, fadeOut on the rest) once the camera leaves.
function dressAt(x, z, fy, rise, { floor = true, front = true, clear = 420 } = {}) {   // clear: half-width kept free of bushes for the stop's content
  const tl = DIO.tl, BC = bushColors(), set = floor ? [ground(x, z, fy)] : [];
  const hills = popLeaf(HILLS(9000, 560, [PAL.hill1, PAL.hill2, PAL.hill3]), { x, y: fy - 280, z: z - 380, sharp: 0, k: 0.3 });
  popUp(hills, rise, 1.1); set.push(hills);
  const far = popLeaf(HILLS(13000, 950, [PAL.far1, PAL.far2, PAL.far3]), { x, y: fy - 475, z: z - 1150, sharp: 0, k: 0.25 });
  popUp(far, rise + 0.1, 1.2); set.push(far);
  [[-1, 1080, -850, 420], [1, 1060, -890, 360], [1, 1560, -760, 240]].forEach(([side, dx, dy, w], i) => {
    const c = leaf(CLOUD(w), { x: x + side * dx, y: fy + dy, z: z - 300 - i * 80, k: 0.4 });
    tl.fromTo(c, { o: 0, dy: -90 }, { o: 1, dy: 0, duration: 1.2, ease: "power3.out" }, rise + 0.2 + i * 0.12);
    set.push(c);
  });
  if (front) [[-1, 930, 260], [1, 960, 230]].forEach(([side, dx, h], i) => {
    const [a, b] = BC[(i + 1) % 4];
    set.push(leaf(BUSH(h, a, b), { x: x + side * dx, y: fy - h / 2, z: z + 650 }));
  });
  for (let i = 0; floor && i < 12; i++) {
    const side = i % 2 ? 1 : -1, off = clear + rnd() * 900, h = 60 + rnd() * 70, [a, b] = BC[i % 4];
    set.push(leaf(BUSH(h, a, b), { x: x + side * off, y: fy - h / 2, z: z + 120 + rnd() * 420 }));
  }
  return set;
}

// a label is a sign planted in the ground: the same chip, the same post, everywhere
function sign(text, ic, col, x, fy, z, post = 150) {
  const H = 116 + post;
  return popLeaf(`<div style="display:flex;flex-direction:column;align-items:center;height:${H}px">
    <div class="chip" style="position:relative;z-index:1"><i style="background:${col}">${icon(ic)}</i>${text}</div>
    <div class="post"></div></div>`, { x, y: fy - H / 2, z });
}
