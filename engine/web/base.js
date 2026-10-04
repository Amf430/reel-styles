// Reel runtime shared by every style scene.
// A scene calls `const R = await Reel.init()` and then `R.define({ ready, renderAt })`.
// renderAt(t) must be a pure function of t (seconds on the source video's timeline):
// no CSS animations, transitions or timers, so any frame renders on its own.

// ------------------------------------------------------------------ math
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, k) => a + (b - a) * k;
export const ease = {
  linear: (k) => k,
  outCubic: (k) => 1 - Math.pow(1 - k, 3),
  inCubic: (k) => k * k * k,
  inOutCubic: (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
  outExpo: (k) => (k >= 1 ? 1 : 1 - Math.pow(2, -10 * k)),
  inExpo: (k) => (k <= 0 ? 0 : Math.pow(2, 10 * k - 10)),
  outBack: (k) => { const c = 1.70158; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); },
  outQuint: (k) => 1 - Math.pow(1 - k, 5),
};
/** Progress 0..1 of a tween that starts at t0 and lasts dur, shaped by an easing. */
export const tw = (t, t0, dur, fn = ease.outExpo) => fn(clamp((t - t0) / Math.max(dur, 1e-6)));
/** Deterministic pseudo-random in [0,1) from any number of numeric seeds. */
export function rand(...s) {
  let h = 2166136261;
  for (const v of s) { h ^= Math.floor(v * 1000003); h = Math.imul(h, 16777619); }
  h ^= h >>> 13; h = Math.imul(h, 0x5bd1e995); h ^= h >>> 15;
  return (h >>> 0) / 4294967296;
}
/** Smooth value noise in [-1,1] (for flicker, drift). */
export function noise1(x, seed = 0) {
  const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
  return lerp(rand(i, seed) * 2 - 1, rand(i + 1, seed) * 2 - 1, u);
}
/** Read/write a dotted path like "theme.glow" on an object. */
export const getPath = (o, p) => p.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
export function setPath(o, p, v) {
  const ks = p.split("."); let a = o;
  ks.slice(0, -1).forEach((k) => { a[k] = a[k] ?? {}; a = a[k]; });
  a[ks.at(-1)] = v;
}

/**
 * Text with emphasis markup → HTML, one <span class="w"> per word (for word-by-word motion).
 * `*word*` or `*several words*` marks the emphasised part (class "hl"). HTML is escaped.
 */
export function richWords(str) {
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const out = [];
  let hl = false;
  for (const tok of String(str ?? "").split(/(\*)/)) {
    if (tok === "*") { hl = !hl; continue; }
    for (const w of tok.split(/\s+/).filter(Boolean)) out.push({ text: w, hl });
  }
  return { words: out, html: out.map((w, i) => `<span class="w${w.hl ? " hl" : ""}" data-i="${i}">${esc(w.text)}</span>`).join(" ") };
}

// ------------------------------------------------------------------ runtime
// Modes: "render" (render.py, the viewport is the frame) and "embed" (inside the editor's iframe,
// the iframe is the frame). Opening a scene on its own sends you to the editor.
const qs = new URLSearchParams(location.search);
const JOB = qs.get("j") ?? "0";

class ReelRuntime {
  async init() {
    this.mode = qs.has("render") ? "render" : qs.has("embed") ? "embed" : null;
    if (!this.mode) { location.replace("/player"); await new Promise(() => {}); }
    this.job = await (await fetch(`/job.json?j=${JOB}`)).json();
    this.P = this.job.params || {};
    this.T = this.P.theme || {};
    this.start = this.job.start ?? 0;
    this.end = this.job.end ?? 5;
    this.fps = this.job.fps ?? 30;
    this.source = null; // frame under the layer: HTMLImageElement in render, the editor's <video> in embed
    this.items = [];
    this.stage = document.getElementById("stage") || Object.assign(document.body.appendChild(document.createElement("div")), { id: "stage" });
    const css = document.createElement("style");
    css.textContent = ".xf-wrap{position:absolute;inset:0;pointer-events:none;transform-origin:0 0}.xf-wrap>*{pointer-events:auto}";
    document.head.appendChild(css);
    this._layout();
    addEventListener("resize", () => this._layout());
    // Google fonts: wait for the stylesheet AND the font files, or the first frames render in Tajawal.
    this._fonts = (this.P.google_fonts || []).map((f) => new Promise((res) => {
      const l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(f)}:wght@400;700&display=block`;
      l.onload = () => Promise.all([document.fonts.load(`400 40px "${f}"`, "ابجد"), document.fonts.load(`700 40px "${f}"`, "ابجد")]).then(res, res);
      l.onerror = () => { console.warn("font failed:", f); res(); };
      document.head.appendChild(l);
    }));
    window.__reel = this;
    return this;
  }

  _layout() {
    this.W = innerWidth; this.H = innerHeight;
    this.u = Math.min(this.W, this.H) / 1080; // 1u = 1px on a 1080p short side
    this.portrait = this.H > this.W;
    document.documentElement.style.setProperty("--u", this.u + "px");
    document.documentElement.classList.toggle("portrait", this.portrait);
    this._needsLayout = true;
  }

  /** An element's box relative to the frame, after transforms. */
  rect(el) {
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, width: r.width, height: r.height };
  }

  /** Resolve a job-relative or absolute local path to a served URL. */
  asset(p) {
    if (!p) return p;
    if (/^(https?:|data:|\/r\/|\/f\/)/.test(p)) return p;
    const abs = p.startsWith("/") ? p : `${this.job._dir}/${p}`;
    return "/f" + encodeURI(abs);
  }

  define(scene) {
    this.scene = scene;
    this.ready = (async () => {
      await Promise.all(this._fonts || []);
      await document.fonts.ready;
      if (scene.ready) await scene.ready(this);
      await document.fonts.ready;
    })();
    return this.ready;
  }

  /** One frame: the scene, then the user's per-item transforms. Same path in render and editor. */
  async renderFrame(t) {
    // The editor resizes iframes; don't wait for the async resize event to catch up.
    if (innerWidth !== this.W || innerHeight !== this.H) this._layout();
    await this.scene.renderAt(t, this);
    this.applyItems();
    this.applyBehind();
  }

  /**
   * "behind": the job's whole layer is hidden wherever the cut-out subject (job.behind.layer, from
   * key.py/segment.py) is opaque — text passes behind people/buildings. this.matte is that frame
   * (an <img> in render, the subject's preview <video> in the editor).
   */
  applyBehind() {
    if (!this.job.behind) return;
    const m = this.matte;
    if (!m || (m.readyState !== undefined && m.readyState < 2)) { this.stage.style.webkitMaskImage = ""; return; }
    const c = (this._matteCv ??= document.createElement("canvas"));
    const k = this.mode === "render" ? 0.5 : 1;
    c.width = Math.max(2, Math.round(this.W * k)); c.height = Math.max(2, Math.round(this.H * k));
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.filter = `blur(${(this.job.behind.feather ?? 1) * k}px)`;
    ctx.drawImage(m, 0, 0, c.width, c.height);
    Object.assign(this.stage.style, {
      webkitMaskImage: `linear-gradient(#000, #000), url(${c.toDataURL()})`,
      webkitMaskSize: "100% 100%", webkitMaskRepeat: "no-repeat", webkitMaskComposite: "xor", maskComposite: "exclude",
    });
  }

  /** Called by render.py for every frame. */
  async frame(t, frameUrl, matteUrl) {
    const load = async (u) => { const img = new Image(); img.src = u; await img.decode(); return img; };
    if (frameUrl) this.source = await load(frameUrl);
    if (matteUrl) this.matte = await load(matteUrl);
    await this.renderFrame(t);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  }

  meta() { return this.scene.meta ? this.scene.meta(this) : {}; }

  // ---------------------------------------------------------------- items
  // A scene registers each movable piece once per build:
  //   R.item({ id, label, els: [shadow, card], in: "cards.0.in", out: "cards.0.out", xf: "cards.0.xf" })
  // `in`/`out` are param paths (seconds) the editor's timeline drags; `xf` is where the piece's
  // transform lives: { x, y (fractions of the frame), rot (deg), scale, opacity }. The els are
  // moved into one wrapper that carries the transform, so the scene's own animation stays intact.
  clearItems() { this.items = []; }

  item(spec) {
    const els = spec.els.filter(Boolean);
    let wrap = els[0].parentElement?.classList.contains("xf-wrap") ? els[0].parentElement : null;
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "xf-wrap";
      els[0].before(wrap);
      for (const e of els) wrap.appendChild(e);
    }
    const it = { ...spec, els, wrap, main: els.at(-1) };
    for (const e of els) e.__reelItem = it;
    this.items.push(it);
    return it;
  }

  xfOf(it) { return (it.xf && getPath(this.P, it.xf)) || {}; }

  /** The item's transform as a matrix in frame px (pivot = centre of its main element's layout box). */
  xfMatrix(it) {
    const xf = this.xfOf(it), m = it.main;
    const ox = m.offsetLeft + m.offsetWidth / 2, oy = m.offsetTop + m.offsetHeight / 2;
    return new DOMMatrix()
      .translate(ox + (xf.x || 0) * this.W, oy + (xf.y || 0) * this.H)
      .rotate(xf.rot || 0)
      .scale(xf.scale ?? 1)
      .translate(-ox, -oy);
  }

  applyItems() {
    for (const it of this.items) {
      const xf = this.xfOf(it);
      const ident = !xf.x && !xf.y && !xf.rot && (xf.scale ?? 1) === 1;
      it.wrap.style.transform = ident ? "" : this.xfMatrix(it).toString();
      it.wrap.style.opacity = xf.opacity ?? "";
    }
  }

  /** Item under a frame point (editor picking), topmost first. */
  itemAt(x, y) {
    for (const el of document.elementsFromPoint(x, y)) {
      let e = el;
      while (e && !e.__reelItem) e = e.parentElement;
      if (e) return e.__reelItem;
    }
    return null;
  }

  /** Shrink an element's font-size until it fits maxW px (keeps one line). */
  fit(el, maxW, minScale = 0.4) {
    const base = parseFloat(el.style.fontSize) || parseFloat(getComputedStyle(el).fontSize);
    el.style.fontSize = base + "px";
    let s = 1;
    while (el.scrollWidth > maxW && s > minScale) { s -= 0.03; el.style.fontSize = base * s + "px"; }
    return s;
  }

  /**
   * Fill `canvas` (a child of `el`, offset by -pad) with the frame behind `el`, through a CSS filter.
   * Accounts for the item transform, so a moved/rotated/scaled glass card still blurs what is
   * really behind it. `zoom` > 1 magnifies around el's centre. Returns el's box without the item
   * transform (size the canvas from it).
   */
  drawSourceFor(el, canvas, filter = "none", pad = 0, zoom = 1) {
    let it = null;
    for (let e = el; e && !it; e = e.parentElement) it = e.__reelItem; // el may sit inside an item
    const wrap = it?.wrap;
    let r0;
    if (wrap && wrap.style.transform) {
      const s = wrap.style.transform; wrap.style.transform = ""; r0 = this.rect(el); wrap.style.transform = s;
    } else r0 = this.rect(el);
    const dpr = Math.min(2, devicePixelRatio || 1);
    const cw = Math.max(1, Math.round((r0.width + pad * 2) * dpr));
    const ch = Math.max(1, Math.round((r0.height + pad * 2) * dpr));
    if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    const src = this.source;
    if (!src || (src.readyState !== undefined && src.readyState < 2)) return r0;
    ctx.filter = filter;
    ctx.setTransform(dpr, 0, 0, dpr, (pad - r0.left) * dpr, (pad - r0.top) * dpr);
    if (it) { const inv = this.xfMatrix(it).inverse(); ctx.transform(inv.a, inv.b, inv.c, inv.d, inv.e, inv.f); }
    if (zoom !== 1) {
      // Magnify what's behind around el's centre (refraction / lens look).
      const cx = r0.left + r0.width / 2, cy = r0.top + r0.height / 2;
      ctx.translate(cx, cy); ctx.scale(zoom, zoom); ctx.translate(-cx, -cy);
    }
    ctx.drawImage(src, 0, 0, this.W, this.H);
    return r0;
  }
}

export const Reel = new ReelRuntime();
