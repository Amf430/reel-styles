// Reel editor: the whole video, every job layered on it (one iframe per job, each running its style
// scene in "embed" mode), a timeline to move/trim pieces, and per-piece transforms
// (position · rotation · scale · opacity). Frames come from the same renderFrame() the export uses.
import { getPath, setPath, clamp } from "/r/engine/web/base.js";

const $ = (s) => document.querySelector(s);
const qs = new URLSearchParams(location.search);
const LABEL_W = 150;

const S = {
  proj: null, jobs: [], video: null, bg: null, box: { x: 0, y: 0, w: 0, h: 0 },
  t: 0, playing: false, before: false, wipe: false, wipeX: 0.5,
  zoom: 60, sel: null, selJob: 0, undo: [], redo: [], dirty: new Set(),
  peaks: null, cuts: [], drawing: false, again: false,
};

// ------------------------------------------------------------------ boot
window.__editor = S; // for debugging from the console
const proj = (S.proj = await (await fetch("/project.json")).json());
const fps = proj.fps;
const frame = (t) => Math.round(t * fps) / fps;

const video = (S.video = document.createElement("video"));
video.src = "/f" + encodeURI(proj.video); video.preload = "auto"; video.playsInline = true;
video.style.display = "none";
document.body.appendChild(video);
const box = $("#box");
S.bg = document.createElement("canvas");
box.appendChild(S.bg);

for (const info of proj.jobs) {
  const f = document.createElement("iframe");
  f.src = `/scene?j=${info.i}&embed=1`;
  box.appendChild(f);
  const job = { info, iframe: f, R: null };
  S.jobs.push(job);
  if (info.output === "opaque" && info.subject) {
    job.subCanvas = document.createElement("canvas");
    box.appendChild(job.subCanvas);
  }
}
const gzLayer = document.createElement("div");
gzLayer.id = "gz-layer";
gzLayer.innerHTML = `<div id="gz"><div class="h rot"></div><div class="h scl"></div></div>`;
box.appendChild(gzLayer);

await Promise.all(S.jobs.map((j) => new Promise((res) => {
  const wait = () => {
    const R = j.iframe.contentWindow?.__reel;
    if (R && R.ready) R.ready.then(() => { j.R = R; res(); }); else setTimeout(wait, 50);
  };
  j.iframe.addEventListener("load", wait); wait();
})));
for (const j of S.jobs) if (j.subCanvas) await mountSubject(j);
for (const j of S.jobs) if (j.info.behind) await mountMatte(j);
await new Promise((r) => (video.readyState >= 2 ? r() : video.addEventListener("loadeddata", r, { once: true })));


// ------------------------------------------------------------------ layout + drawing
function layout() {
  const v = $("#view").getBoundingClientRect(), [fw, fh] = proj.size;
  const k = Math.min((v.width - 24) / fw, (v.height - 24) / fh);
  const w = Math.round(fw * k), h = Math.round(fh * k);
  S.box = { x: Math.round((v.width - w) / 2), y: Math.round((v.height - h) / 2), w, h };
  Object.assign(box.style, { left: S.box.x + "px", top: S.box.y + "px", width: w + "px", height: h + "px" });
  const dpr = Math.min(2, devicePixelRatio || 1);
  S.bg.width = w * dpr; S.bg.height = h * dpr;
  for (const j of S.jobs) if (j.subCanvas) { j.subCanvas.width = w * dpr; j.subCanvas.height = h * dpr; }
  setTimeout(draw, 30); // iframes get their resize event first
}

async function draw() {
  if (S.drawing) { S.again = true; return; }
  S.drawing = true;
  try {
    const ctx = S.bg.getContext("2d");
    if (video.readyState >= 2) ctx.drawImage(video, 0, 0, S.bg.width, S.bg.height);
    syncMattes();
    for (const j of S.jobs) {
      j.R.source = video;
      await j.R.renderFrame(S.t);
      drawSubject(j);
    }
    applyView();
    updateGizmo();
    updateClock();
  } catch (e) { console.error(e); }
  S.drawing = false;
  if (S.again) { S.again = false; draw(); }
}

function tick() {
  if (S.playing) {
    S.t = video.currentTime;
    if (S.t >= proj.duration - 0.01) pause();
    draw();
  }
  requestAnimationFrame(tick);
}

function seek(t) {
  S.t = clamp(frame(t), 0, proj.duration);
  video.currentTime = S.t;
  video.addEventListener("seeked", draw, { once: true });
  updateClock();
}
function play() { S.playing = true; video.play(); syncSubjects(true); $("#b-play").textContent = "❚❚"; }
function pause() { S.playing = false; video.pause(); S.t = frame(video.currentTime); syncSubjects(false); $("#b-play").textContent = "▶"; seek(S.t); }

function applyView() {
  const layers = S.jobs.flatMap((j) => [j.iframe, j.subCanvas].filter(Boolean));
  for (const el of layers) {
    el.style.visibility = S.before ? "hidden" : "visible";
    el.style.clipPath = S.wipe && !S.before ? `inset(0 0 0 ${S.wipeX * 100}%)` : "none";
  }
  $("#b-before").textContent = S.before ? "before" : "after";
  $("#b-before").classList.toggle("on", S.before);
  $("#b-wipe").classList.toggle("on", S.wipe);
}

// ------------------------------------------------------------------ keyed presenter (background styles)
async function mountSubject(j) {
  const stem = j.info.subject.layer.replace(/\.[^.]+$/, "");
  const asset = (p) => j.R.asset(p);
  j.subInfo = await (await fetch(asset(stem + ".json"))).json();
  const sv = (j.subVideo = document.createElement("video"));
  sv.src = asset(stem + "_preview.webm"); sv.muted = true; sv.playsInline = true; sv.preload = "auto"; sv.style.display = "none";
  document.body.appendChild(sv);
  sv.addEventListener("seeked", () => drawSubject(j));
  j.subRect = await (await fetch(`/subject_rect?j=${j.info.i}`)).json();
}
function drawSubject(j) {
  if (!j.subCanvas || !j.subVideo) return;
  const st = S.t - (j.subInfo.start || 0), sv = j.subVideo;
  if (!S.playing && Math.abs(sv.currentTime - st) > 0.001) { sv.currentTime = Math.max(0, st); return; }
  if (S.playing && Math.abs(sv.currentTime - st) > 0.08) sv.currentTime = Math.max(0, st);
  const c = j.subCanvas, ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  const inRange = S.t >= j.info.start && S.t <= j.info.end;
  const rect = j.R.meta().subject_rect || j.subRect;
  if (!rect || !inRange || sv.readyState < 2) return;
  const [x, y, w, h] = rect;
  ctx.drawImage(sv, x * c.width, y * c.height, w * c.width, h * c.height);
}
// "behind" jobs: the cut-out subject's preview video is the matte that hides the layer.
async function mountMatte(j) {
  const stem = j.info.behind.layer.replace(/\.[^.]+$/, "");
  j.matteInfo = await (await fetch(j.R.asset(stem + ".json"))).json();
  const mv = (j.matteVideo = document.createElement("video"));
  mv.src = j.R.asset(stem + "_preview.webm"); mv.muted = true; mv.playsInline = true; mv.preload = "auto"; mv.style.display = "none";
  document.body.appendChild(mv);
  j.R.matte = mv;
  mv.addEventListener("seeked", () => { if (!S.playing) draw(); });
}
function syncMattes() {
  for (const j of S.jobs) {
    const mv = j.matteVideo; if (!mv) continue;
    const st = Math.max(0, S.t - (j.matteInfo.start || 0));
    if (S.playing) { if (mv.paused) { mv.currentTime = st; mv.play(); } else if (Math.abs(mv.currentTime - st) > 0.08) mv.currentTime = st; }
    else { if (!mv.paused) mv.pause(); if (Math.abs(mv.currentTime - st) > 0.001) mv.currentTime = st; }
  }
}
function syncSubjects(on) { for (const j of S.jobs) if (j.subVideo) { if (on) { j.subVideo.currentTime = Math.max(0, S.t - (j.subInfo.start || 0)); j.subVideo.play(); } else j.subVideo.pause(); } }

// ------------------------------------------------------------------ items
function itemsOf(j) { return j.R.items; }
function itemTimes(j, it) {
  const tin = it.in ? getPath(j.R.P, it.in) : null, tout = it.out ? getPath(j.R.P, it.out) : null;
  return { tin: tin ?? j.info.start, tout: tout ?? j.info.end, timed: !!(it.in || it.out) };
}
function findItem(sel) { const j = S.jobs[sel?.j]; return j && j.R.items.find((x) => x.id === sel.id) ? { j, it: j.R.items.find((x) => x.id === sel.id) } : null; }
function select(jIndex, id) {
  S.sel = id == null ? null : { j: jIndex, id };
  if (jIndex != null) S.selJob = jIndex;
  for (const b of document.querySelectorAll(".bar[data-id]")) b.classList.toggle("sel", S.sel && +b.dataset.j === S.sel.j && b.dataset.id === S.sel.id);
  renderSide(); updateGizmo();
}
function getXf(j, it) { return { x: 0, y: 0, rot: 0, scale: 1, opacity: 1, ...(getPath(j.R.P, it.xf) || {}) }; }
function setXf(j, it, xf) {
  const clean = {};
  if (xf.x) clean.x = +xf.x.toFixed(5); if (xf.y) clean.y = +xf.y.toFixed(5);
  if (xf.rot) clean.rot = +xf.rot.toFixed(2); if (xf.scale !== 1) clean.scale = +xf.scale.toFixed(4);
  if (xf.opacity !== 1) clean.opacity = +xf.opacity.toFixed(3);
  setPath(j.R.P, it.xf, clean);
  markDirty(j);
}

// ------------------------------------------------------------------ gizmo (move / rotate / scale on the video)
const gz = $("#gz");
function untransformedRect(j, it) {
  const w = it.wrap, s = w.style.transform; w.style.transform = "";
  const r = it.main.getBoundingClientRect(); w.style.transform = s;
  return r;
}
function itemVisible(j, it) {
  const { tin, tout } = itemTimes(j, it);
  return S.t >= tin && S.t <= tout && it.main.offsetParent !== null && getComputedStyle(it.main).display !== "none";
}
function updateGizmo() {
  const f = findItem(S.sel);
  if (!f || !f.it.xf || !itemVisible(f.j, f.it) || S.before) { gz.style.display = "none"; return; }
  const r = untransformedRect(f.j, f.it), M = f.j.R.xfMatrix(f.it);
  Object.assign(gz.style, { display: "block", width: r.width + "px", height: r.height + "px",
    transform: M.multiply(new DOMMatrix().translate(r.left, r.top)).toString() });
  const sc = getXf(f.j, f.it).scale || 1;
  for (const h of gz.querySelectorAll(".h")) h.style.transform = `scale(${1 / sc})`;
}

let drag = null;
gzLayer.addEventListener("pointerdown", (e) => {
  const b = box.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top;
  if (S.wipe && e.altKey) return;
  let f = findItem(S.sel), mode = "move";
  if (e.target.classList.contains("rot")) mode = "rot";
  else if (e.target.classList.contains("scl")) mode = "scale";
  else {
    // Pick: topmost job first.
    let hit = null;
    for (let i = S.jobs.length - 1; i >= 0 && !hit; i--) {
      const it = S.jobs[i].R.itemAt(x, y);
      if (it && it.xf && itemVisible(S.jobs[i], it)) hit = { j: S.jobs[i], it, i };
    }
    if (!hit) { select(null, null); return; }
    if (!f || hit.it !== f.it) select(hit.i, hit.it.id);
    f = { j: hit.j, it: hit.it };
  }
  if (!f) return;
  const r = untransformedRect(f.j, f.it), M = f.j.R.xfMatrix(f.it);
  const c = M.transformPoint(new DOMPoint(r.left + r.width / 2, r.top + r.height / 2));
  drag = { mode, f, x0: x, y0: y, xf0: getXf(f.j, f.it), c, a0: Math.atan2(y - c.y, x - c.x), d0: Math.hypot(x - c.x, y - c.y) };
  gzLayer.setPointerCapture(e.pointerId);
  e.preventDefault();
});
gzLayer.addEventListener("pointermove", (e) => {
  const b = box.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top;
  if (S.wipe) { S.wipeX = clamp(x / b.width); applyView(); }
  if (!drag) return;
  const { f, xf0, mode } = drag, xf = { ...xf0 };
  if (mode === "move") {
    let dx = x - drag.x0, dy = y - drag.y0;
    if (e.shiftKey) (Math.abs(dx) > Math.abs(dy) ? (dy = 0) : (dx = 0));
    xf.x = xf0.x + dx / S.box.w; xf.y = xf0.y + dy / S.box.h;
  } else if (mode === "rot") {
    let rot = xf0.rot + ((Math.atan2(y - drag.c.y, x - drag.c.x) - drag.a0) * 180) / Math.PI;
    if (e.shiftKey) rot = Math.round(rot / 15) * 15;
    xf.rot = rot;
  } else {
    xf.scale = Math.max(0.05, xf0.scale * (Math.hypot(x - drag.c.x, y - drag.c.y) / Math.max(1, drag.d0)));
  }
  setXf(f.j, f.it, xf);
  draw(); renderInspectorValues();
});
gzLayer.addEventListener("pointerup", () => { if (drag) { drag = null; pushUndo(); } });
gzLayer.addEventListener("dblclick", () => { const f = findItem(S.sel); if (f) { setXf(f.j, f.it, { x: 0, y: 0, rot: 0, scale: 1, opacity: 1 }); pushUndo(); draw(); renderSide(); } });

// ------------------------------------------------------------------ timeline
const inner = $("#tl-inner");
function tx(t) { return LABEL_W + t * S.zoom; }
function buildTimeline() {
  const W = proj.duration * S.zoom;
  const rows = [];
  rows.push(`<div class="row" id="ruler"><div class="lab">${proj.size[0]}×${proj.size[1]} · ${fps}fps</div><div class="track" style="width:${W}px"><canvas id="ruler-cv"></canvas></div></div>`);
  rows.push(`<div class="row tall"><div class="lab">video</div><div class="track" id="thumbs" style="width:${W}px;background:url(/thumbs.jpg) 0 0/100% 100%"></div></div>`);
  if (proj.has_audio) rows.push(`<div class="row"><div class="lab">audio</div><div class="track" style="width:${W}px"><canvas id="wave-cv"></canvas></div></div>`);
  S.jobs.forEach((j, ji) => {
    const name = `${j.info.style.replace("reel-", "")} · ${j.info.name}`;
    rows.push(`<div class="row job"><div class="lab" title="${j.info.file}">${name}</div><div class="track" style="width:${W}px">
      <div class="bar jobbar" data-job="${ji}" style="left:${j.info.start * S.zoom}px;width:${(j.info.end - j.info.start) * S.zoom}px">render range
      <div class="h l"></div><div class="h r"></div></div></div></div>`);
    for (const it of itemsOf(j)) {
      const { tin, tout, timed } = itemTimes(j, it);
      const sel = S.sel && S.sel.j === ji && S.sel.id === it.id;
      rows.push(`<div class="row"><div class="lab" title="${it.label}">${it.label}</div><div class="track" style="width:${W}px">
        <div class="bar ${timed ? "" : "static"} ${sel ? "sel" : ""}" data-j="${ji}" data-id="${it.id}" style="left:${tin * S.zoom}px;width:${Math.max(4, (tout - tin) * S.zoom)}px">${it.label}
        ${timed ? `<div class="h l"></div><div class="h r"></div>` : ""}</div></div></div>`);
    }
  });
  inner.innerHTML = rows.join("") + `<div id="playhead"></div><div id="snapline"></div>` +
    S.cuts.map((c) => `<div class="cut" style="left:${tx(c)}px"></div>`).join("");
  inner.style.width = LABEL_W + W + "px";
  drawRuler(); drawWave(); updateClock();
}
function drawRuler() {
  const cv = $("#ruler-cv"); if (!cv) return;
  const W = Math.min(32000, proj.duration * S.zoom), H = 25, dpr = devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px";
  const c = cv.getContext("2d"); c.scale(dpr, dpr); c.fillStyle = "#8a8d94"; c.strokeStyle = "#3a3d44"; c.font = "10px ui-monospace, Menlo";
  const step = [0.1, 0.5, 1, 2, 5, 10, 30, 60].find((s) => s * S.zoom >= 60) || 60;
  for (let t = 0; t <= proj.duration; t += step / 5) {
    const x = Math.round(t * S.zoom) + 0.5, major = Math.abs(t / step - Math.round(t / step)) < 1e-6;
    c.beginPath(); c.moveTo(x, major ? 10 : 18); c.lineTo(x, H); c.stroke();
    if (major) c.fillText(fmt(t, step < 1), x + 3, 10);
  }
}
function drawWave() {
  const cv = $("#wave-cv"); if (!cv || !S.peaks) return;
  const W = Math.min(32000, proj.duration * S.zoom), H = 25, dpr = devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px";
  const c = cv.getContext("2d"); c.scale(dpr, dpr); c.fillStyle = "#4a7a6a";
  const { per_sec, peaks } = S.peaks;
  for (let x = 0; x < W; x++) {
    const a = Math.floor((x / S.zoom) * per_sec), b = Math.max(a + 1, Math.floor(((x + 1) / S.zoom) * per_sec));
    let m = 0; for (let i = a; i < b && i < peaks.length; i++) m = Math.max(m, peaks[i]);
    const h = Math.max(1, m * (H - 2)); c.fillRect(x, (H - h) / 2, 1, h);
  }
}
async function loadTimelineHelpers() {
  try { if (proj.has_audio) { S.peaks = await (await fetch("/peaks.json")).json(); drawWave(); } } catch (e) { console.warn(e); }
  try { S.cuts = await (await fetch("/cuts.json")).json(); buildTimeline(); } catch (e) { console.warn(e); }
}
function updateClock() {
  $("#time").textContent = `${fmt(S.t, true)}  f${Math.round(S.t * fps)}`;
  const ph = $("#playhead"); if (ph) ph.style.left = tx(S.t) + "px";
}
function fmt(t, frac) { const m = Math.floor(t / 60), s = t - m * 60; return `${m}:${s.toFixed(frac ? 2 : 0).padStart(frac ? 5 : 2, "0")}`; }

// Scrub on the ruler.
inner.addEventListener("pointerdown", (e) => {
  if (!e.target.closest("#ruler") && !e.target.closest("#thumbs")) return;
  const scrub = (ev) => { const r = inner.getBoundingClientRect(); if (S.playing) pause(); seek((ev.clientX - r.left - LABEL_W) / S.zoom); };
  scrub(e);
  const up = () => { removeEventListener("pointermove", scrub); removeEventListener("pointerup", up); };
  addEventListener("pointermove", scrub); addEventListener("pointerup", up);
});

// Drag bars: body = move, edges = trim. Snaps to frames, playhead, cuts, other pieces (Shift = free).
function snapTargets(except) {
  const ts = [S.t, ...S.cuts];
  S.jobs.forEach((j) => { ts.push(j.info.start, j.info.end); for (const it of itemsOf(j)) if (it !== except) { const { tin, tout } = itemTimes(j, it); ts.push(tin, tout); } });
  return ts;
}
function snap(v, targets, free) {
  if (free) return { v: frame(v), at: null };
  let best = null;
  for (const t of targets) if (Math.abs(t - v) * S.zoom < 8 && (best == null || Math.abs(t - v) < Math.abs(best - v))) best = t;
  return best == null ? { v: frame(v), at: null } : { v: best, at: best };
}
inner.addEventListener("pointerdown", (e) => {
  const bar = e.target.closest(".bar"); if (!bar) return;
  const handle = e.target.classList.contains("h") ? (e.target.classList.contains("l") ? "l" : "r") : null;
  const x0 = e.clientX;
  if (bar.dataset.job != null) { // render range of a job
    const j = S.jobs[+bar.dataset.job], s0 = j.info.start, e0 = j.info.end;
    select(null, null); S.selJob = +bar.dataset.job; renderSide();
    const move = (ev) => {
      const dt = (ev.clientX - x0) / S.zoom, tg = snapTargets(null);
      if (handle !== "r") j.info.start = clamp(snap(s0 + dt, tg, ev.shiftKey).v, 0, (handle ? e0 : proj.duration) - 0.1);
      if (handle !== "l") j.info.end = clamp(snap(e0 + dt, tg, ev.shiftKey).v, j.info.start + 0.1, proj.duration);
      if (!handle) j.info.end = j.info.start + (e0 - s0);
      j.R.start = j.info.start; j.R.end = j.info.end;
      markDirty(j); buildTimeline();
    };
    const up = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); pushUndo(); draw(); };
    addEventListener("pointermove", move); addEventListener("pointerup", up);
    return;
  }
  const ji = +bar.dataset.j, j = S.jobs[ji], it = j.R.items.find((x) => x.id === bar.dataset.id);
  select(ji, it.id);
  if (bar.classList.contains("static")) return;
  const { tin: in0, tout: out0 } = itemTimes(j, it), tg = snapTargets(it), line = $("#snapline");
  const move = (ev) => {
    const dt = (ev.clientX - x0) / S.zoom;
    let tin = in0, tout = out0, at = null;
    if (handle === "l") { const s = snap(in0 + dt, tg, ev.shiftKey); tin = Math.min(s.v, out0 - 1 / fps); at = s.at; }
    else if (handle === "r") { const s = snap(out0 + dt, tg, ev.shiftKey); tout = Math.max(s.v, in0 + 1 / fps); at = s.at; }
    else {
      const a = snap(in0 + dt, tg, ev.shiftKey), b = snap(out0 + dt, tg, ev.shiftKey);
      const useB = b.at != null && (a.at == null || Math.abs(b.v - (out0 + dt)) < Math.abs(a.v - (in0 + dt)));
      const shift = useB ? b.v - out0 : a.v - in0;
      tin = in0 + shift; tout = out0 + shift; at = useB ? b.at : a.at;
      if (tin < 0) { tout -= tin; tin = 0; }
    }
    if (it.in) setPath(j.R.P, it.in, +tin.toFixed(3));
    if (it.out) setPath(j.R.P, it.out, +tout.toFixed(3));
    bar.style.left = tin * S.zoom + "px"; bar.style.width = (tout - tin) * S.zoom + "px";
    line.style.display = at != null ? "block" : "none"; if (at != null) line.style.left = tx(at) + "px";
    markDirty(j); draw(); renderInspectorValues();
  };
  const up = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); line.style.display = "none"; pushUndo(); };
  addEventListener("pointermove", move); addEventListener("pointerup", up);
});
$("#tl-scroll").addEventListener("wheel", (e) => {
  if (!(e.ctrlKey || e.metaKey)) return;
  e.preventDefault();
  setZoom(S.zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX);
}, { passive: false });
function setZoom(z, anchorX) {
  const sc = $("#tl-scroll"), r = sc.getBoundingClientRect();
  const ax = anchorX ?? r.left + r.width / 2, tAt = (sc.scrollLeft + ax - r.left - LABEL_W) / S.zoom;
  S.zoom = clamp(z, 5, Math.min(600, 30000 / proj.duration));
  $("#zoom").value = S.zoom;
  buildTimeline();
  sc.scrollLeft = tAt * S.zoom + LABEL_W - (ax - r.left);
}
$("#zoom").addEventListener("input", (e) => setZoom(+e.target.value));
S.zoom = clamp(($("#tl-scroll").clientWidth - LABEL_W - 20) / proj.duration, 5, 400);
$("#zoom").value = S.zoom;

// Timeline height.
$("#tl-resize").addEventListener("pointerdown", (e) => {
  const y0 = e.clientY, h0 = $("#tl").offsetHeight;
  const mv = (ev) => { document.documentElement.style.setProperty("--tl-h", clamp(h0 - (ev.clientY - y0), 120, innerHeight - 200) + "px"); layout(); };
  const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
  addEventListener("pointermove", mv); addEventListener("pointerup", up);
});

// ------------------------------------------------------------------ inspector
function field(label, key, val, { min, max, step, type = "range", unit = "" } = {}) {
  if (type === "color") return `<div class="field wide"><label>${label}</label><input type="color" data-k="${key}" value="${val}"></div>`;
  if (type === "bool") return `<div class="field wide"><label>${label}</label><input type="checkbox" data-k="${key}" ${val ? "checked" : ""}></div>`;
  if (type === "text") return `<div class="field wide"><label>${label}</label><input type="text" data-k="${key}" value="${String(val ?? "").replace(/"/g, "&quot;")}"></div>`;
  return `<div class="field"><label title="${label}">${label}</label><input type="range" data-k="${key}" min="${min}" max="${max}" step="${step}" value="${val}">
    <input type="number" data-k="${key}" step="${step}" value="${+(+val).toFixed(4)}">${unit}</div>`;
}
function renderSide() {
  const side = $("#side"), f = findItem(S.sel), j = S.jobs[S.selJob];
  let h = "";
  if (f) {
    const xf = getXf(f.j, f.it), { tin, tout, timed } = itemTimes(f.j, f.it);
    h += `<h2>${f.it.label}</h2><div class="muted">${f.j.info.style} · ${f.j.info.name}</div>`;
    if (timed) h += `<h3>time</h3>` + field("in (s)", "t.in", tin, { min: 0, max: proj.duration, step: 1 / fps }) + field("out (s)", "t.out", tout, { min: 0, max: proj.duration, step: 1 / fps });
    if (f.it.xf) {
      h += `<h3>transform <button id="xf-reset" style="float:right;padding:1px 8px">reset</button></h3>`;
      h += field("position x %", "xf.x", xf.x * 100, { min: -100, max: 100, step: 0.1 });
      h += field("position y %", "xf.y", xf.y * 100, { min: -100, max: 100, step: 0.1 });
      h += field("rotation °", "xf.rot", xf.rot, { min: -180, max: 180, step: 0.5 });
      h += field("scale %", "xf.scale", xf.scale * 100, { min: 5, max: 400, step: 1 });
      h += field("opacity %", "xf.opacity", xf.opacity * 100, { min: 0, max: 100, step: 1 });
    }
  } else {
    h += `<h2>${proj.video.split("/").pop()}</h2><div class="muted">${fmt(proj.duration, true)} · ${proj.size.join("×")}</div>`;
    h += `<h3>jobs</h3><div class="joblist">` + S.jobs.map((x, i) => `<div data-job="${i}" class="${i === S.selJob ? "sel" : ""}">${x.info.style} · ${x.info.name}</div>`).join("") + `</div>`;
  }
  if (j) {
    h += `<h3>style — ${j.info.style}${j.R.job.theme ? " · " + j.R.job.theme : ""}</h3>`;
    for (const s of j.R.job._tune || []) h += field(s.label || s.path, "p." + s.path, getPath(j.R.P, s.path) ?? (s.type === "color" ? "#ffffff" : 0), s);
  }
  h += `<h3>keys</h3><div id="help"><kbd>space</kbd> play · <kbd>←</kbd><kbd>→</kbd> 1s (<kbd>shift</kbd> 5s) · <kbd>,</kbd><kbd>.</kbd> frame<br>
    <kbd>i</kbd>/<kbd>o</kbd> set in/out of the selected piece at the playhead<br><kbd>alt</kbd>+<kbd>←</kbd><kbd>→</kbd> nudge it a frame (<kbd>shift</kbd> 10)<br>
    drag on video = move · top handle = rotate · corner = scale · <kbd>shift</kbd> constrain · double-click = reset<br>
    <kbd>b</kbd> before/after · <kbd>w</kbd> wipe · <kbd>h</kbd> hide panels · <kbd>⌘Z</kbd> undo · <kbd>⌘S</kbd> save · <kbd>ctrl</kbd>+wheel zoom</div>`;
  side.innerHTML = h;
  side.querySelectorAll("[data-job]").forEach((d) => (d.onclick = () => { S.selJob = +d.dataset.job; renderSide(); }));
  side.querySelector("#xf-reset")?.addEventListener("click", () => { const f2 = findItem(S.sel); setXf(f2.j, f2.it, { x: 0, y: 0, rot: 0, scale: 1, opacity: 1 }); pushUndo(); draw(); renderSide(); });
  side.querySelectorAll("input[data-k]").forEach((inp) => {
    inp.addEventListener("input", () => onField(inp));
    inp.addEventListener("change", () => pushUndo());
  });
}
function onField(inp) {
  const k = inp.dataset.k, raw = inp.type === "checkbox" ? inp.checked : inp.type === "range" || inp.type === "number" ? parseFloat(inp.value) : inp.value;
  const twin = $("#side").querySelectorAll(`input[data-k="${k}"]`);
  twin.forEach((o) => o !== inp && (o.value = inp.type === "range" ? +(+raw).toFixed(4) : raw));
  const f = findItem(S.sel), j = S.jobs[S.selJob];
  if (k.startsWith("xf.") && f) {
    const xf = getXf(f.j, f.it), n = k.slice(3);
    xf[n] = n === "x" || n === "y" || n === "scale" || n === "opacity" ? raw / 100 : raw;
    setXf(f.j, f.it, xf);
  } else if (k.startsWith("t.") && f) {
    const path = k === "t.in" ? f.it.in : f.it.out;
    if (path) setPath(f.j.R.P, path, frame(raw));
    markDirty(f.j); buildTimeline();
  } else if (k.startsWith("p.") && j) {
    setPath(j.R.P, k.slice(2), raw);
    j.R.T = j.R.P.theme || {};
    j.R.scene.onParams?.(j.R);
    markDirty(j); buildTimeline();
  }
  draw();
}
function renderInspectorValues() {
  const f = findItem(S.sel); if (!f) return;
  const xf = getXf(f.j, f.it), { tin, tout } = itemTimes(f.j, f.it);
  const vals = { "xf.x": xf.x * 100, "xf.y": xf.y * 100, "xf.rot": xf.rot, "xf.scale": xf.scale * 100, "xf.opacity": xf.opacity * 100, "t.in": tin, "t.out": tout };
  $("#side").querySelectorAll("input[data-k]").forEach((i) => { if (i.dataset.k in vals && document.activeElement !== i) i.value = +(+vals[i.dataset.k]).toFixed(3); });
}

// ------------------------------------------------------------------ undo / save
function snapshot() { return JSON.stringify(S.jobs.map((j) => ({ p: j.R.P, s: j.info.start, e: j.info.end }))); }
function pushUndo() {
  const snap = snapshot();
  if (S.undo.at(-1) === snap) return;
  S.undo.push(snap); S.redo = [];
  if (S.undo.length > 200) S.undo.shift();
}
// Restore into the existing objects so scenes that hold references (e.g. a card's params) stay live.
function assignDeep(dst, src) {
  for (const k of Object.keys(dst)) if (!(k in src)) delete dst[k];
  for (const [k, v] of Object.entries(src)) {
    if (v && typeof v === "object" && dst[k] && typeof dst[k] === "object" && Array.isArray(v) === Array.isArray(dst[k])) assignDeep(dst[k], v);
    else dst[k] = v;
  }
}
function restore(snap) {
  JSON.parse(snap).forEach((st, i) => {
    const j = S.jobs[i];
    assignDeep(j.R.P, st.p); j.R.T = j.R.P.theme || {};
    j.info.start = j.R.start = st.s; j.info.end = j.R.end = st.e;
    j.R.scene.onParams?.(j.R);
    markDirty(j);
  });
  buildTimeline(); renderSide(); draw();
}
function undo() { if (S.undo.length < 2) return; S.redo.push(S.undo.pop()); restore(S.undo.at(-1)); }
function redoFn() { if (!S.redo.length) return; const s = S.redo.pop(); S.undo.push(s); restore(s); }
function markDirty(j) { S.dirty.add(j); const st = $("#status"); st.textContent = "unsaved •"; st.classList.add("dirty"); }
async function save() {
  for (const j of S.dirty) {
    // The render range grows to cover every timed piece (+0.3s), never shrinks on its own.
    let s = j.info.start, e = j.info.end;
    for (const it of itemsOf(j)) { const { tin, tout, timed } = itemTimes(j, it); if (timed) { s = Math.min(s, tin - 0.3); e = Math.max(e, tout + 0.3); } }
    j.info.start = j.R.start = Math.max(0, frame(s)); j.info.end = j.R.end = Math.min(proj.duration, frame(e));
    const r = await fetch(`/save?j=${j.info.i}`, { method: "POST", body: JSON.stringify({ params: j.R.P, start: j.info.start, end: j.info.end }) });
    if (!r.ok) { $("#status").textContent = "save failed"; return; }
  }
  S.dirty.clear();
  const st = $("#status"); st.textContent = "saved ✓"; st.classList.remove("dirty");
  buildTimeline();
}
addEventListener("beforeunload", (e) => { if (S.dirty.size) { e.preventDefault(); e.returnValue = ""; } });

// ------------------------------------------------------------------ buttons + keys
$("#b-play").onclick = () => (S.playing ? pause() : play());
$("#b-before").onclick = () => { S.before = !S.before; draw(); };
$("#b-wipe").onclick = () => { S.wipe = !S.wipe; applyView(); };
$("#b-save").onclick = save;
$("#b-undo").onclick = undo;
$("#b-redo").onclick = redoFn;
addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" && !["range", "checkbox", "color"].includes(e.target.type)) return;
  const mod = e.metaKey || e.ctrlKey, f = findItem(S.sel), fr = 1 / fps;
  if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); save(); return; }
  if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? redoFn() : undo(); return; }
  const nudge = (d) => {
    if (!f) return;
    const { tin, tout } = itemTimes(f.j, f.it);
    if (f.it.in) setPath(f.j.R.P, f.it.in, frame(Math.max(0, tin + d)));
    if (f.it.out) setPath(f.j.R.P, f.it.out, frame(tout + d));
    markDirty(f.j); pushUndo(); buildTimeline(); renderInspectorValues(); draw();
  };
  const map = {
    " ": () => (S.playing ? pause() : play()),
    ArrowLeft: () => (e.altKey ? nudge(-(e.shiftKey ? 10 : 1) * fr) : seek(S.t - (e.shiftKey ? 5 : 1))),
    ArrowRight: () => (e.altKey ? nudge((e.shiftKey ? 10 : 1) * fr) : seek(S.t + (e.shiftKey ? 5 : 1))),
    ",": () => { if (S.playing) pause(); seek(S.t - fr); },
    ".": () => { if (S.playing) pause(); seek(S.t + fr); },
    i: () => { if (f?.it.in) { setPath(f.j.R.P, f.it.in, S.t); markDirty(f.j); pushUndo(); buildTimeline(); renderInspectorValues(); draw(); } },
    o: () => { if (f?.it.out) { setPath(f.j.R.P, f.it.out, S.t); markDirty(f.j); pushUndo(); buildTimeline(); renderInspectorValues(); draw(); } },
    b: () => { S.before = !S.before; draw(); },
    w: () => { S.wipe = !S.wipe; applyView(); },
    h: () => { document.body.classList.toggle("ui-hidden"); layout(); },
    Escape: () => select(null, null),
    "=": () => setZoom(S.zoom * 1.25), "-": () => setZoom(S.zoom / 1.25),
  };
  if (map[e.key]) { e.preventDefault(); map[e.key](); }
});

// ------------------------------------------------------------------ start (after every declaration above)
layout();
addEventListener("resize", layout);
pushUndo();
buildTimeline();
renderSide();
seek(parseFloat(qs.get("t") ?? proj.jobs[0]?.start ?? 0));
loadTimelineHelpers();
requestAnimationFrame(tick);
