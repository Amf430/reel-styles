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

// ------------------------------------------------------------------ runtime
const qs = new URLSearchParams(location.search);

class ReelRuntime {
  async init() {
    this.job = await (await fetch("/job.json")).json();
    this.P = this.job.params || {};
    this.T = this.P.theme || {};
    this.mode = qs.has("render") ? "render" : "player";
    this.start = this.job.start ?? 0;
    this.end = this.job.end ?? 5;
    this.fps = this.job.fps ?? 30;
    this.source = null; // current video frame (HTMLImageElement in render, HTMLVideoElement in player)
    this.stage = document.getElementById("stage") || Object.assign(document.body.appendChild(document.createElement("div")), { id: "stage" });
    this._layout();
    addEventListener("resize", () => this._layout());
    for (const f of this.P.google_fonts || []) {
      const l = document.createElement("link");
      l.rel = "stylesheet";
      l.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(f)}:wght@300;400;500;700;800;900&display=block`;
      document.head.appendChild(l);
    }
    window.__reel = this;
    return this;
  }

  _layout() {
    // Render: the viewport is the frame. Player: the frame is letterboxed to the video's aspect.
    let w = innerWidth, h = innerHeight, x = 0, y = 0;
    if (this.mode === "player") {
      const [fw, fh] = this.job.size || [16, 9];
      const k = Math.min(innerWidth / fw, innerHeight / fh);
      w = Math.round(fw * k); h = Math.round(fh * k);
      x = Math.round((innerWidth - w) / 2); y = Math.round((innerHeight - h) / 2);
      Object.assign(this.stage.style, { left: x + "px", top: y + "px", width: w + "px", height: h + "px", right: "auto", bottom: "auto" });
      for (const id of ["pv-video", "pv-bg"]) {
        const e = document.getElementById(id);
        if (e) Object.assign(e.style, { left: x + "px", top: y + "px", width: w + "px", height: h + "px" });
      }
    }
    this.W = w; this.H = h; this.ox = x; this.oy = y;
    this.u = Math.min(w, h) / 1080; // 1u = 1px on a 1080p short side
    this.portrait = h > w;
    document.documentElement.style.setProperty("--u", this.u + "px");
    document.documentElement.classList.toggle("portrait", this.portrait);
    this._needsLayout = true;
    if (this.mode === "player" && Player.R) Player.draw();
  }

  /** An element's box relative to the frame (stage), after transforms. */
  rect(el) {
    const r = el.getBoundingClientRect();
    return { left: r.left - this.ox, top: r.top - this.oy, width: r.width, height: r.height };
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
      await document.fonts.ready;
      if (scene.ready) await scene.ready(this);
      await document.fonts.ready;
    })();
    if (this.mode === "player") this.ready.then(() => Player.mount(this));
    return this.ready;
  }

  /** Called by the renderer for every frame. */
  async frame(t, frameUrl) {
    if (frameUrl) {
      const img = new Image();
      img.src = frameUrl;
      await img.decode();
      this.source = img;
    }
    await this.scene.renderAt(t, this);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  }

  meta() { return this.scene.meta ? this.scene.meta(this) : {}; }

  /** Shrink an element's font-size until it fits maxW px (keeps one line). */
  fit(el, maxW, minScale = 0.4) {
    const base = parseFloat(el.style.fontSize) || parseFloat(getComputedStyle(el).fontSize);
    el.style.fontSize = base + "px";
    let s = 1;
    while (el.scrollWidth > maxW && s > minScale) { s -= 0.03; el.style.fontSize = base * s + "px"; }
    return s;
  }

  /**
   * Draw the current source frame into a canvas that sits at rect (frame px, see rect()), with
   * a CSS filter (blur/brightness/saturate). Used for glass. `pad` px bleed avoids dark blur edges.
   */
  drawSource(canvas, rect, filter = "none", pad = 0) {
    const dpr = Math.min(2, devicePixelRatio || 1);
    const cw = Math.max(1, Math.round((rect.width + pad * 2) * dpr));
    const ch = Math.max(1, Math.round((rect.height + pad * 2) * dpr));
    if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    const src = this.source;
    if (!src || (src.readyState !== undefined && src.readyState < 2)) return false;
    ctx.filter = filter;
    ctx.setTransform(dpr, 0, 0, dpr, (-rect.left + pad) * dpr, (-rect.top + pad) * dpr);
    ctx.drawImage(src, 0, 0, this.W, this.H);
    return true;
  }
}

export const Reel = new ReelRuntime();

// ------------------------------------------------------------------ live player
// Same frames as the export. Keys: space play/pause · ←/→ ±1s (shift ±5s) · , . one frame
// l loop · b before/after · w wipe · h hide UI · ?t=12 start time · ?panel=0 hide sliders.
const Player = {
  mount(R) {
    this.R = R;
    this.t = parseFloat(qs.get("t") ?? R.start);
    this.playing = false; this.loop = true; this.before = false; this.wipe = false; this.wipeX = 0.5;
    const css = document.createElement("style");
    css.textContent = `
      body{background:#111}
      #pv-video{position:absolute;opacity:0;pointer-events:none} #pv-bg{position:absolute;z-index:0} #stage{z-index:1}
      #pv-ui{position:fixed;left:0;right:0;bottom:0;z-index:99;font:12px/1.4 ui-monospace,Menlo,monospace;color:#eee;direction:ltr;
        background:linear-gradient(transparent,rgba(0,0,0,.75));padding:28px 14px 10px;display:flex;gap:10px;align-items:center}
      #pv-ui input[type=range]{flex:1}
      #pv-ui button,#pv-panel button{background:#222;color:#eee;border:1px solid #444;border-radius:6px;padding:4px 9px;font:inherit;cursor:pointer}
      #pv-panel{position:fixed;top:10px;left:10px;z-index:99;width:270px;max-height:calc(100vh - 90px);overflow:auto;direction:ltr;
        background:rgba(15,15,18,.86);backdrop-filter:blur(8px);border:1px solid #333;border-radius:10px;padding:10px 12px;font:12px/1.4 ui-monospace,Menlo,monospace;color:#ddd}
      #pv-panel label{display:block;margin:7px 0 2px;color:#aaa}
      #pv-panel input[type=range]{width:100%} #pv-panel .row{display:flex;gap:6px;align-items:center}
      #pv-panel output{min-width:44px;text-align:right;color:#fff}
      #pv-wipe{position:fixed;top:0;bottom:0;width:2px;background:#fff;z-index:98;pointer-events:none;display:none}
      .pv-hidden #pv-ui,.pv-hidden #pv-panel{display:none}`;
    document.head.appendChild(css);

    if (R.job.video) {
      const v = (this.video = document.createElement("video"));
      v.id = "pv-video"; v.src = R.asset(R.job.video); v.muted = qs.get("mute") === "1"; v.playsInline = true; v.preload = "auto";
      document.body.prepend(v);
      this.bg = document.createElement("canvas");
      this.bg.id = "pv-bg";
      v.after(this.bg);
      R.source = v;
      R._layout();
      v.addEventListener("seeked", () => this.draw());
      v.addEventListener("loadeddata", () => this.seek(this.t));
    }
    if (R.job.subject && R.job._output === "opaque") this.mountSubject();
    this.ui();
    if (qs.get("panel") !== "0") this.panel();
    addEventListener("keydown", (e) => this.key(e));
    addEventListener("mousemove", (e) => { if (this.wipe) { this.wipeX = e.clientX / innerWidth; this.applyView(); } });
    this.seek(this.t);
    const tick = () => {
      if (this.playing) {
        if (this.video) this.t = this.video.currentTime;
        else this.t += (performance.now() - (this._last || performance.now())) / 1000;
        if (this.t >= R.end) { if (this.loop) this.seek(R.start, true); else this.pause(); }
        this.draw();
      }
      this._last = performance.now();
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  },
  // Background styles: show the keyed presenter on top, where the render will put them.
  async mountSubject() {
    const R = this.R, stem = R.job.subject.layer.replace(/\.[^.]+$/, "");
    this.subInfo = await (await fetch(R.asset(stem + ".json"))).json();
    const sv = (this.subVideo = document.createElement("video"));
    sv.src = R.asset(stem + "_preview.webm"); sv.muted = true; sv.playsInline = true; sv.preload = "auto";
    sv.style.display = "none";
    this.subCanvas = document.createElement("canvas");
    this.subCanvas.id = "pv-subj";
    Object.assign(this.subCanvas.style, { position: "absolute", zIndex: 2, pointerEvents: "none" });
    document.body.append(sv, this.subCanvas);
    sv.addEventListener("seeked", () => this.drawSubject());
    sv.addEventListener("error", () => console.warn("no subject preview (.webm) — re-run key.py"));
  },
  async drawSubject() {
    const R = this.R, sv = this.subVideo, cv = this.subCanvas;
    if (!sv || sv.readyState < 2) return;
    const rect = R.meta().subject_rect || (this._rect ??= await (await fetch("/subject_rect")).json());
    if (!rect) return;
    Object.assign(cv.style, { left: R.ox + "px", top: R.oy + "px", width: R.W + "px", height: R.H + "px" });
    const dpr = Math.min(2, devicePixelRatio || 1);
    cv.width = R.W * dpr; cv.height = R.H * dpr;
    const [x, y, w, h] = rect, ctx = cv.getContext("2d");
    ctx.drawImage(sv, x * cv.width, y * cv.height, w * cv.width, h * cv.height);
    cv.style.visibility = this.before ? "hidden" : "visible";
  },
  syncSubject() {
    const sv = this.subVideo;
    if (!sv || !this.subInfo) return;
    const st = this.t - (this.subInfo.start || 0);
    if (this.playing) {
      if (sv.paused) { sv.currentTime = st; sv.play(); }
      else if (Math.abs(sv.currentTime - st) > 0.08) sv.currentTime = st;
      this.drawSubject();
    } else { sv.pause(); if (Math.abs(sv.currentTime - st) > 0.001) sv.currentTime = st; else this.drawSubject(); }
  },
  ui() {
    const R = this.R, el = (this.bar = document.createElement("div"));
    el.id = "pv-ui";
    el.innerHTML = `<button id=pv-play>▶</button><span id=pv-time></span>
      <input id=pv-scrub type=range min=${R.start} max=${R.end} step=${1 / R.fps} value=${this.t}>
      <button id=pv-loop>loop</button><button id=pv-before>after</button><button id=pv-wipeb>wipe</button>`;
    document.body.appendChild(el);
    this.wipeLine = Object.assign(document.body.appendChild(document.createElement("div")), { id: "pv-wipe" });
    el.querySelector("#pv-play").onclick = () => this.toggle();
    el.querySelector("#pv-scrub").oninput = (e) => this.seek(parseFloat(e.target.value));
    el.querySelector("#pv-loop").onclick = () => { this.loop = !this.loop; this.status(); };
    el.querySelector("#pv-before").onclick = () => { this.before = !this.before; this.applyView(); };
    el.querySelector("#pv-wipeb").onclick = () => { this.wipe = !this.wipe; this.applyView(); };
    this.status();
  },
  panel() {
    const R = this.R, specs = R.job._tune || [];
    const p = (this.panelEl = document.createElement("div"));
    p.id = "pv-panel";
    p.innerHTML = `<b>${R.job.style}</b> <span style="color:#888">${R.job.theme || ""}</span>`;
    for (const s of specs) {
      const val = getPath(R.P, s.path);
      const wrap = document.createElement("div");
      wrap.innerHTML = `<label>${s.label || s.path}</label><div class=row></div>`;
      const row = wrap.querySelector(".row");
      const input = document.createElement("input");
      if (s.type === "color") { input.type = "color"; input.value = val || "#ffffff"; }
      else if (s.type === "bool") { input.type = "checkbox"; input.checked = !!val; }
      else if (s.type === "text") { input.type = "text"; input.value = val ?? ""; input.style.width = "100%"; }
      else { input.type = "range"; input.min = s.min ?? 0; input.max = s.max ?? 1; input.step = s.step ?? 0.01; input.value = val ?? 0; }
      const out = document.createElement("output");
      out.textContent = s.type === "range" || !s.type ? (+input.value).toString() : "";
      input.oninput = () => {
        const v = input.type === "checkbox" ? input.checked : input.type === "range" ? parseFloat(input.value) : input.value;
        setPath(R.P, s.path, v); R.T = R.P.theme || {};
        if (input.type === "range") out.textContent = v;
        if (R.scene.onParams) R.scene.onParams(R);
        this.draw();
      };
      row.append(input, out);
      p.appendChild(wrap);
    }
    const btns = document.createElement("div");
    btns.style.marginTop = "10px"; btns.className = "row";
    btns.innerHTML = `<button id=pv-save>save to job</button><button id=pv-copy>copy JSON</button>`;
    p.appendChild(btns);
    btns.querySelector("#pv-copy").onclick = () => navigator.clipboard.writeText(JSON.stringify(R.P, null, 2));
    btns.querySelector("#pv-save").onclick = async (e) => {
      const r = await fetch("/save", { method: "POST", body: JSON.stringify(R.P) });
      e.target.textContent = r.ok ? "saved ✓" : "save failed";
      setTimeout(() => (e.target.textContent = "save to job"), 1500);
    };
    document.body.appendChild(p);
  },
  applyView() {
    const st = this.R.stage;
    st.style.visibility = this.before ? "hidden" : "visible";
    if (this.before) st.style.clipPath = "none";
    st.style.clipPath = this.wipe ? `inset(0 0 0 ${this.wipeX * 100}%)` : "none";
    this.wipeLine.style.display = this.wipe ? "block" : "none";
    this.wipeLine.style.left = this.wipeX * 100 + "%";
    this.bar.querySelector("#pv-before").textContent = this.before ? "before" : "after";
    this.R.scene.onView?.(this.R, { before: this.before, wipe: this.wipe, wipeX: this.wipeX });
  },
  async draw() {
    if (this._drawing) { this._again = true; return; }
    this._drawing = true;
    try {
      if (this.bg && this.video.readyState >= 2) {
        const R = this.R, dpr = Math.min(2, devicePixelRatio || 1);
        this.bg.width = R.W * dpr; this.bg.height = R.H * dpr;
        this.bg.getContext("2d").drawImage(this.video, 0, 0, this.bg.width, this.bg.height);
      }
      await this.R.scene.renderAt(this.t, this.R);
      this.syncSubject();
    } catch (e) { console.error(e); }
    this._drawing = false;
    this.status();
    if (this._again) { this._again = false; this.draw(); }
  },
  seek(t, keepPlaying = false) {
    const R = this.R;
    this.t = clamp(t, R.start, R.end);
    if (this.video) { this.video.currentTime = this.t; if (!keepPlaying && this.playing) this.video.play(); }
    this.draw();
  },
  toggle() { this.playing ? this.pause() : this.play(); },
  play() { this.playing = true; this._last = performance.now(); this.video?.play(); this.status(); },
  pause() { this.playing = false; this.video?.pause(); if (this.video) this.t = this.video.currentTime; this.draw(); },
  status() {
    const b = this.bar; if (!b) return;
    b.querySelector("#pv-play").textContent = this.playing ? "❚❚" : "▶";
    b.querySelector("#pv-time").textContent = `${this.t.toFixed(2)}s · f${Math.round((this.t - this.R.start) * this.R.fps)}`;
    b.querySelector("#pv-scrub").value = this.t;
    b.querySelector("#pv-loop").style.opacity = this.loop ? 1 : 0.45;
  },
  key(e) {
    if (e.target.tagName === "INPUT" && e.target.type === "text") return;
    const f = 1 / this.R.fps;
    const map = {
      " ": () => this.toggle(),
      ArrowLeft: () => this.seek(this.t - (e.shiftKey ? 5 : 1)),
      ArrowRight: () => this.seek(this.t + (e.shiftKey ? 5 : 1)),
      ",": () => { this.pause(); this.seek(this.t - f); },
      ".": () => { this.pause(); this.seek(this.t + f); },
      l: () => { this.loop = !this.loop; this.status(); },
      b: () => { this.before = !this.before; this.applyView(); },
      w: () => { this.wipe = !this.wipe; this.applyView(); },
      h: () => document.body.classList.toggle("pv-hidden"),
    };
    if (map[e.key]) { e.preventDefault(); map[e.key](); }
  },
};
