// محرّر الريلز: مونتاج (مقاطع من ملف أو أكثر: قص، حذف، تقصير، ترتيب، إضافة) + طبقات الموشن فوقه
// (iframe لكل جوب يشغّل مشهد الستايل في وضع embed) + تايملاين + تحويل لكل قطعة + تعديل النصوص والألوان والخطوط.
// الفريمات من نفس renderFrame() اللي يستخدمه التصدير.
import { getPath, setPath, clamp } from "/r/engine/web/base.js";

const $ = (s) => document.querySelector(s);
const qs = new URLSearchParams(location.search);
const LABEL_W = 150;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const base = (p) => p.split("/").pop();

const S = {
  proj: null, jobs: [], srcs: {}, clips: [], cur: 0, bg: null, box: { x: 0, y: 0, w: 0, h: 0 },
  t: 0, playing: false, before: false, wipe: false, wipeX: 0.5, safe: false,
  zoom: 60, sel: null, selJob: 0, selClip: null, undo: [], redo: [], dirty: new Set(), editDirty: false,
  peaks: {}, thumbs: {}, srcCuts: {}, cuts: [], drawing: false, again: false, mtimes: null,
};

// ------------------------------------------------------------------ boot
window.__editor = S;
const proj = (S.proj = await (await fetch("/project.json")).json());
const fps = proj.fps;
const frame = (t) => Math.round(t * fps) / fps;
const box = $("#box");
S.bg = document.createElement("canvas");
box.appendChild(S.bg);

// One <video> per source file; the montage plays them clip by clip.
function source(path) {
  if (S.srcs[path]) return S.srcs[path];
  const el = document.createElement("video");
  el.src = "/f" + encodeURI(path); el.preload = "auto"; el.playsInline = true; el.style.display = "none";
  document.body.appendChild(el);
  const s = (S.srcs[path] = { path, el, info: proj.sources[path] || null });
  el.addEventListener("seeked", () => { if (!S.playing) draw(); });
  return s;
}
S.clips = proj.clips.map((c) => ({ ...c }));
for (const c of S.clips) source(c.src);
const dur = () => S.clips.reduce((a, c) => a + (c.out - c.in), 0);
function starts() { let a = 0; return S.clips.map((c) => { const s = a; a += c.out - c.in; return s; }); }
function locate(t) {
  const st = starts();
  for (let k = 0; k < S.clips.length; k++) {
    const c = S.clips[k], len = c.out - c.in;
    if (t < st[k] + len - 1e-6 || k === S.clips.length - 1) return { k, c, start: st[k], st: clamp(c.in + (t - st[k]), c.in, c.out) };
  }
  return { k: 0, c: S.clips[0], start: 0, st: 0 };
}
const curEl = () => S.srcs[S.clips[S.cur]?.src]?.el;

for (const info of proj.jobs) {
  const f = document.createElement("iframe");
  f.src = `/scene?j=${info.i}&embed=1`;
  box.appendChild(f);
  const job = { info, iframe: f, R: null };
  S.jobs.push(job);
  if (info.output === "opaque" && info.subject) { job.subCanvas = document.createElement("canvas"); box.appendChild(job.subCanvas); }
}
const safeEl = document.createElement("div");
safeEl.id = "safe";
box.appendChild(safeEl);
const gzLayer = document.createElement("div");
gzLayer.id = "gz-layer";
gzLayer.innerHTML = `<div id="gz"><div class="h rot"></div><div class="h scl"></div></div>`;
box.appendChild(gzLayer);

await Promise.all(S.jobs.map((j) => new Promise((res) => {
  const wait = () => { const R = j.iframe.contentWindow?.__reel; if (R && R.ready) R.ready.then(() => { j.R = R; res(); }); else setTimeout(wait, 50); };
  j.iframe.addEventListener("load", wait); wait();
})));
for (const j of S.jobs) if (j.subCanvas) await mountSubject(j);
for (const j of S.jobs) if (j.info.behind) await mountMatte(j);
await Promise.all(Object.values(S.srcs).map((s) => new Promise((r) => (s.el.readyState >= 2 ? r() : s.el.addEventListener("loadeddata", r, { once: true })))));

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
  drawSafe();
  setTimeout(draw, 30);
}

async function draw() {
  if (S.drawing) { S.again = true; return; }
  S.drawing = true;
  try {
    const ctx = S.bg.getContext("2d"), el = curEl();
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, S.bg.width, S.bg.height);
    if (el && el.readyState >= 2) {
      // fit the source into the frame (a clip from another file may have another size)
      const sw = el.videoWidth || S.bg.width, sh = el.videoHeight || S.bg.height, k = Math.min(S.bg.width / sw, S.bg.height / sh);
      ctx.drawImage(el, (S.bg.width - sw * k) / 2, (S.bg.height - sh * k) / 2, sw * k, sh * k);
    }
    syncMattes();
    for (const j of S.jobs) { j.R.source = S.bg; await j.R.renderFrame(S.t); drawSubject(j); }
    applyView(); updateGizmo(); updateClock();
  } catch (e) { console.error(e); }
  S.drawing = false;
  if (S.again) { S.again = false; draw(); }
}

function tick() {
  if (S.playing) {
    const c = S.clips[S.cur], el = curEl(), st0 = starts()[S.cur];
    S.t = st0 + (el.currentTime - c.in);
    if (el.currentTime >= c.out - 0.5 / fps || el.ended) {
      if (S.cur + 1 < S.clips.length) {
        const n = S.clips[S.cur + 1], ne = S.srcs[n.src].el;
        if (ne !== el) el.pause();
        S.cur++; ne.currentTime = n.in; ne.play(); S.t = st0 + (c.out - c.in);
      } else { S.t = dur(); pause(); }
    }
    followPlayhead();
    draw();
  }
  requestAnimationFrame(tick);
}

function seek(t) {
  S.t = clamp(frame(t), 0, dur());
  const L = locate(S.t), prev = curEl();
  S.cur = L.k;
  const el = curEl();
  if (prev && prev !== el) prev.pause();
  if (Math.abs(el.currentTime - L.st) > 1e-3) el.currentTime = L.st; else draw();
  updateClock();
}
function play() {
  if (S.t >= dur() - 1 / fps) seek(0);
  const L = locate(S.t); S.cur = L.k;
  S.playing = true; const el = curEl(); el.currentTime = L.st; el.play(); syncSubjects(true); $("#b-play").textContent = "❚❚";
}
function pause() {
  S.playing = false; for (const s of Object.values(S.srcs)) s.el.pause();
  syncSubjects(false); $("#b-play").textContent = "▶"; seek(S.t);
}

function applyView() {
  const layers = S.jobs.flatMap((j) => [j.iframe, j.subCanvas].filter(Boolean));
  for (const el of layers) {
    el.style.visibility = S.before ? "hidden" : "visible";
    el.style.clipPath = S.wipe && !S.before ? `inset(0 0 0 ${S.wipeX * 100}%)` : "none";
  }
  $("#b-before").textContent = S.before ? "قبل" : "بعد";
  $("#b-before").classList.toggle("on", S.before);
  $("#b-wipe").classList.toggle("on", S.wipe);
  $("#b-safe").classList.toggle("on", S.safe);
  safeEl.style.display = S.safe ? "block" : "none";
}

// المنطقة الآمنة: أماكن أزرار تيك توك/ريلز (طولي) أو شريط يوتيوب (عرضي) — للمعاينة فقط، ما تطلع في الرندر.
function drawSafe() {
  const [fw, fh] = proj.size, portrait = fh > fw, z = (x, y, w, h, t) => `<div class="z" style="left:${x * 100}%;top:${y * 100}%;width:${w * 100}%;height:${h * 100}%"><span>${t}</span></div>`;
  safeEl.innerHTML = portrait
    ? z(0, 0, 1, 250 / 1920, "الحساب والبحث") + z(0, 1 - 420 / 1920, 1, 420 / 1920, "الوصف والصوت") + z(1 - 150 / 1080, 0.35, 150 / 1080, 0.43, "الأزرار")
    : z(0, 0.88, 1, 0.12, "شريط التشغيل");
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

// ------------------------------------------------------------------ items (motion pieces)
function itemsOf(j) { return j.R.items; }
function itemTimes(j, it) {
  const tin = it.in ? getPath(j.R.P, it.in) : null, tout = it.out ? getPath(j.R.P, it.out) : null;
  return { tin: tin ?? j.info.start, tout: tout ?? j.info.end, timed: !!(it.in || it.out) };
}
function findItem(sel) { const j = S.jobs[sel?.j]; const it = j?.R.items.find((x) => x.id === sel.id); return it ? { j, it } : null; }
function select(jIndex, id) {
  S.sel = id == null ? null : { j: jIndex, id };
  if (jIndex != null) S.selJob = jIndex;
  if (id != null) S.selClip = null;
  for (const b of document.querySelectorAll(".bar[data-id]")) b.classList.toggle("sel", !!S.sel && +b.dataset.j === S.sel.j && b.dataset.id === S.sel.id);
  for (const b of document.querySelectorAll(".bar[data-clip]")) b.classList.toggle("sel", S.selClip === +b.dataset.clip);
  renderSide(); updateGizmo();
}
function selectClip(k) { S.sel = null; S.selClip = k; select(null, null); }
function getXf(j, it) { return { x: 0, y: 0, rot: 0, scale: 1, opacity: 1, ...(getPath(j.R.P, it.xf) || {}) }; }
function setXf(j, it, xf) {
  const clean = {};
  if (xf.x) clean.x = +xf.x.toFixed(5); if (xf.y) clean.y = +xf.y.toFixed(5);
  if (xf.rot) clean.rot = +xf.rot.toFixed(2); if (xf.scale !== 1) clean.scale = +xf.scale.toFixed(4);
  if (xf.opacity !== 1) clean.opacity = +xf.opacity.toFixed(3);
  setPath(j.R.P, it.xf, clean);
  markDirty(j);
}
// The params object of a piece ("items.3" for in-path "items.3.in"), and its array + index when it lives in one.
function itemBase(it) { const p = it.in || it.xf || ""; const parts = p.split("."); parts.pop(); return parts.join("."); }
function itemSlot(it) { const b = itemBase(it), m = /^(.*)\.(\d+)$/.exec(b); return m ? { arr: m[1], i: +m[2] } : null; }
function rebuild(j) { j.R.T = j.R.P.theme || {}; j.R.scene.onParams?.(j.R); if (j.R.scene.ready && j.R.scene.onParams === undefined) j.R.scene.ready(j.R); }

function deleteItem(f) {
  const slot = itemSlot(f.it); if (!slot) return;
  const arr = getPath(f.j.R.P, slot.arr); arr.splice(slot.i, 1);
  rebuild(f.j); markDirty(f.j); select(null, null); pushUndo(); buildTimeline(); draw();
}
function duplicateItem(f) {
  const slot = itemSlot(f.it); if (!slot) return;
  const arr = getPath(f.j.R.P, slot.arr), copy = JSON.parse(JSON.stringify(arr[slot.i]));
  const { tin, tout } = itemTimes(f.j, f.it), len = tout - tin;
  if ("in" in copy) copy.in = frame(tout + 0.2); if ("out" in copy) copy.out = frame(tout + 0.2 + len);
  arr.splice(slot.i + 1, 0, copy);
  rebuild(f.j); markDirty(f.j); pushUndo(); buildTimeline();
  const nid = f.j.R.items.find((x) => itemBase(x) === `${slot.arr}.${slot.i + 1}`)?.id;
  select(S.jobs.indexOf(f.j), nid ?? null); draw();
}

// ------------------------------------------------------------------ gizmo (move / rotate / scale on the video)
const gz = $("#gz");
function untransformedRect(j, it) { const w = it.wrap, s = w.style.transform; w.style.transform = ""; const r = it.main.getBoundingClientRect(); w.style.transform = s; return r; }
function itemVisible(j, it) {
  const { tin, tout } = itemTimes(j, it);
  return S.t >= tin && S.t <= tout && it.main.offsetParent !== null && getComputedStyle(it.main).display !== "none";
}
function updateGizmo() {
  const f = findItem(S.sel);
  if (!f || !f.it.xf || !itemVisible(f.j, f.it) || S.before) { gz.style.display = "none"; return; }
  const r = untransformedRect(f.j, f.it), M = f.j.R.xfMatrix(f.it);
  Object.assign(gz.style, { display: "block", width: r.width + "px", height: r.height + "px", transform: M.multiply(new DOMMatrix().translate(r.left, r.top)).toString() });
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
    let hit = null;
    for (let i = S.jobs.length - 1; i >= 0 && !hit; i--) { const it = S.jobs[i].R.itemAt(x, y); if (it && it.xf && itemVisible(S.jobs[i], it)) hit = { j: S.jobs[i], it, i }; }
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
  if (mode === "move") { let dx = x - drag.x0, dy = y - drag.y0; if (e.shiftKey) (Math.abs(dx) > Math.abs(dy) ? (dy = 0) : (dx = 0)); xf.x = xf0.x + dx / S.box.w; xf.y = xf0.y + dy / S.box.h; }
  else if (mode === "rot") { let rot = xf0.rot + ((Math.atan2(y - drag.c.y, x - drag.c.x) - drag.a0) * 180) / Math.PI; if (e.shiftKey) rot = Math.round(rot / 15) * 15; xf.rot = rot; }
  else xf.scale = Math.max(0.05, xf0.scale * (Math.hypot(x - drag.c.x, y - drag.c.y) / Math.max(1, drag.d0)));
  setXf(f.j, f.it, xf);
  draw(); renderInspectorValues();
});
gzLayer.addEventListener("pointerup", () => { if (drag) { drag = null; pushUndo(); } });
gzLayer.addEventListener("dblclick", () => { const f = findItem(S.sel); if (f) { setXf(f.j, f.it, { x: 0, y: 0, rot: 0, scale: 1, opacity: 1 }); pushUndo(); draw(); renderSide(); } });

// ------------------------------------------------------------------ montage operations
function editChanged() { S.editDirty = true; markDirty(null); proj.duration = dur(); recomputeCuts(); pushUndo(); buildTimeline(); seek(Math.min(S.t, dur())); renderSide(); }
function splitAt(t) {
  const L = locate(t); if (L.st - L.c.in < 2 / fps || L.c.out - L.st < 2 / fps) return;
  const a = { ...L.c, out: frame(L.st) }, b = { ...L.c, in: frame(L.st) };
  S.clips.splice(L.k, 1, a, b); S.selClip = L.k + 1; editChanged();
}
function deleteClip(k) { if (S.clips.length < 2) return status("لازم يبقى مقطع واحد على الأقل"); S.clips.splice(k, 1); S.selClip = null; editChanged(); }
async function addClip(path) {
  const info = proj.sources[path] || (proj.sources[path] = await (await fetch("/probe.json?src=" + encodeURIComponent(path))).json());
  source(path);
  await new Promise((r) => (S.srcs[path].el.readyState >= 2 ? r() : S.srcs[path].el.addEventListener("loadeddata", r, { once: true })));
  loadSource(path);
  const c = { src: path, in: 0, out: info.duration };
  // insert at the playhead: on a clip boundary, or split the clip there first
  const L = locate(S.t);
  let at = L.k + 1;
  if (L.st - L.c.in > 2 / fps && L.c.out - L.st > 2 / fps) { S.clips.splice(L.k, 1, { ...L.c, out: frame(L.st) }, { ...L.c, in: frame(L.st) }); at = L.k + 1; }
  else if (L.st - L.c.in <= 2 / fps) at = L.k;
  S.clips.splice(at, 0, c); S.selClip = at; editChanged();
}

// ------------------------------------------------------------------ timeline
const inner = $("#tl-inner"), scroller = $("#tl-scroll");
function tx(t) { return LABEL_W + t * S.zoom; }
function buildTimeline() {
  const D = dur(), W = D * S.zoom, st = starts();
  const rows = [];
  rows.push(`<div class="row" id="ruler"><div class="lab">${proj.size[0]}×${proj.size[1]} · ${fps}fps</div><div class="track" style="width:${W}px"><canvas id="ruler-cv"></canvas></div></div>`);
  rows.push(`<div class="row tall" id="vrow"><div class="lab">🎬 الفيديو (${S.clips.length})</div><div class="track" style="width:${W}px">` +
    S.clips.map((c, k) => `<div class="bar clip ${S.selClip === k ? "sel" : ""}" data-clip="${k}" style="left:${st[k] * S.zoom}px;width:${Math.max(3, (c.out - c.in) * S.zoom)}px" title="${esc(base(c.src))} ${c.in.toFixed(2)}–${c.out.toFixed(2)}">
      <canvas class="thumb"></canvas><span class="cname">${esc(base(c.src))}</span><div class="h l"></div><div class="h r"></div></div>`).join("") + `</div></div>`);
  rows.push(`<div class="row" id="arow"><div class="lab">🔊 الصوت</div><div class="track" style="width:${W}px"><canvas id="wave-cv"></canvas></div></div>`);
  S.jobs.forEach((j, ji) => {
    const name = `${j.info.style.replace("reel-", "")} · ${j.info.name}`;
    rows.push(`<div class="row job"><div class="lab" title="${esc(j.info.file)}">✨ ${esc(name)}</div><div class="track" style="width:${W}px">
      <div class="bar jobbar" data-job="${ji}" style="left:${j.info.start * S.zoom}px;width:${(j.info.end - j.info.start) * S.zoom}px">نطاق الرندر
      <div class="h l"></div><div class="h r"></div></div></div></div>`);
    for (const it of itemsOf(j)) {
      const { tin, tout, timed } = itemTimes(j, it), sel = S.sel && S.sel.j === ji && S.sel.id === it.id;
      rows.push(`<div class="row"><div class="lab" title="${esc(it.label)}">${esc(it.label)}</div><div class="track" style="width:${W}px">
        <div class="bar ${timed ? "" : "static"} ${sel ? "sel" : ""}" data-j="${ji}" data-id="${it.id}" style="left:${tin * S.zoom}px;width:${Math.max(4, (tout - tin) * S.zoom)}px">${esc(it.label)}
        ${timed ? `<div class="h l"></div><div class="h r"></div>` : ""}</div></div></div>`);
    }
  });
  inner.innerHTML = rows.join("") + `<div id="playhead"></div><div id="snapline"></div>` + S.cuts.map((c) => `<div class="cut" style="left:${tx(c)}px"></div>`).join("");
  inner.style.width = LABEL_W + W + 40 + "px";
  drawRuler(); drawThumbs(); drawWave(); updateClock();
}
function drawRuler() {
  const cv = $("#ruler-cv"); if (!cv) return;
  const W = Math.min(32000, dur() * S.zoom), H = 25, dpr = devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px";
  const c = cv.getContext("2d"); c.scale(dpr, dpr); c.fillStyle = "#8a8d94"; c.strokeStyle = "#3a3d44"; c.font = "10px ui-monospace, Menlo";
  const step = [1 / fps, 0.1, 0.5, 1, 2, 5, 10, 30, 60].find((s) => s * S.zoom >= 60) || 60;
  for (let t = 0; t <= dur(); t += step / 5) {
    const x = Math.round(t * S.zoom) + 0.5, major = Math.abs(t / step - Math.round(t / step)) < 1e-6;
    c.beginPath(); c.moveTo(x, major ? 10 : 18); c.lineTo(x, H); c.stroke();
    if (major) c.fillText(fmt(t, step < 1), x + 3, 10);
  }
}
function drawThumbs() {
  document.querySelectorAll(".bar.clip").forEach((bar) => {
    const c = S.clips[+bar.dataset.clip], img = S.thumbs[c.src], cv = bar.querySelector(".thumb"), info = proj.sources[c.src];
    const W = Math.min(16000, bar.clientWidth), H = bar.clientHeight, dpr = Math.min(2, devicePixelRatio || 1);
    cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px";
    if (!img || !img.complete || !info) return;
    const g = cv.getContext("2d"); g.scale(dpr, dpr);
    const n = Math.max(1, Math.round(img.naturalWidth / (img.naturalHeight * (info.w / info.h)))), tw = img.naturalWidth / n, th = img.naturalHeight;
    const tileW = H * (tw / th);
    for (let x = 0; x < W; x += tileW) {
      const t = c.in + ((x + tileW / 2) / W) * (c.out - c.in), i = clamp(Math.floor((t / info.duration) * n), 0, n - 1);
      g.drawImage(img, i * tw, 0, tw, th, x, 0, tileW, H);
    }
  });
}
function drawWave() {
  const cv = $("#wave-cv"); if (!cv) return;
  const W = Math.min(32000, dur() * S.zoom), H = 25, dpr = devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px";
  const g = cv.getContext("2d"); g.scale(dpr, dpr); g.fillStyle = "#4a7a6a";
  const st = starts();
  S.clips.forEach((c, k) => {
    const pk = S.peaks[c.src]; if (!pk) return;
    const x0 = st[k] * S.zoom, x1 = Math.min(W, (st[k] + c.out - c.in) * S.zoom);
    for (let x = Math.floor(x0); x < x1; x++) {
      const t = c.in + (x - x0) / S.zoom, a = Math.floor(t * pk.per_sec), b = Math.max(a + 1, Math.floor((t + 1 / S.zoom) * pk.per_sec));
      let m = 0; for (let i = a; i < b && i < pk.peaks.length; i++) m = Math.max(m, pk.peaks[i]);
      const h = Math.max(1, m * (H - 2)); g.fillRect(x, (H - h) / 2, 1, h);
    }
  });
}
async function loadSource(path) {
  try { const img = new Image(); img.src = "/thumbs.jpg?src=" + encodeURIComponent(path); await img.decode(); S.thumbs[path] = img; drawThumbs(); } catch (e) { console.warn(e); }
  try { if (proj.sources[path]?.has_audio) { S.peaks[path] = await (await fetch("/peaks.json?src=" + encodeURIComponent(path))).json(); drawWave(); } } catch (e) { console.warn(e); }
  try { S.srcCuts[path] = await (await fetch("/cuts.json?src=" + encodeURIComponent(path))).json(); recomputeCuts(); buildTimeline(); } catch (e) { console.warn(e); }
}
// Cut lines: clip boundaries + shot changes inside each clip, on the sequence's clock.
function recomputeCuts() {
  const st = starts(), out = [];
  S.clips.forEach((c, k) => { if (k) out.push(st[k]); for (const x of S.srcCuts[c.src] || []) if (x > c.in && x < c.out) out.push(st[k] + x - c.in); });
  S.cuts = out;
}
function updateClock() {
  $("#time").textContent = `${fmt(S.t, true)} / ${fmt(dur(), true)}  f${Math.round(S.t * fps)}`;
  const ph = $("#playhead"); if (ph) ph.style.left = tx(S.t) + "px";
}
function fmt(t, frac) { const m = Math.floor(t / 60), s = t - m * 60; return `${m}:${s.toFixed(frac ? 2 : 0).padStart(frac ? 5 : 2, "0")}`; }
function followPlayhead() {
  const x = tx(S.t), l = scroller.scrollLeft + LABEL_W, r = scroller.scrollLeft + scroller.clientWidth - 30;
  if (x < l || x > r) scroller.scrollLeft = x - LABEL_W - 40;
}

// Scrub on the ruler (or any empty track space).
inner.addEventListener("pointerdown", (e) => {
  if (e.target.closest(".bar") || e.target.closest(".lab")) return;
  if (!e.target.closest("#ruler") && !e.target.closest(".track")) return;
  const scrub = (ev) => { const r = inner.getBoundingClientRect(); if (S.playing) pause(); seek((ev.clientX - r.left - LABEL_W) / S.zoom); };
  scrub(e);
  if (!e.target.closest("#ruler") && !e.target.closest("#vrow")) select(null, null);
  const up = () => { removeEventListener("pointermove", scrub); removeEventListener("pointerup", up); };
  addEventListener("pointermove", scrub); addEventListener("pointerup", up);
});

function snapTargets(except) {
  const ts = [S.t, 0, dur(), ...S.cuts];
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
  const x0 = e.clientX, line = $("#snapline");

  // ---- montage clip: edges trim (ripple), body drags to reorder
  if (bar.dataset.clip != null) {
    const k = +bar.dataset.clip, c = S.clips[k], c0 = { ...c }, info = proj.sources[c.src];
    selectClip(k);
    let moved = false, target = k;
    const move = (ev) => {
      const dt = (ev.clientX - x0) / S.zoom;
      if (Math.abs(ev.clientX - x0) > 3) moved = true;
      if (handle === "l") { c.in = frame(clamp(c0.in + dt, 0, c0.out - 2 / fps)); }
      else if (handle === "r") { c.out = frame(clamp(c0.out + dt, c0.in + 2 / fps, info?.duration ?? c0.out)); }
      else {
        // reorder: drop before the clip whose middle is right of the pointer
        const r = inner.getBoundingClientRect(), t = (ev.clientX - r.left - LABEL_W) / S.zoom, st = starts();
        target = S.clips.length; for (let i = 0; i < S.clips.length; i++) if (t < st[i] + (S.clips[i].out - S.clips[i].in) / 2) { target = i; break; }
        const gx = target < S.clips.length ? st[target] : dur();
        line.style.display = "block"; line.style.left = tx(gx) + "px";
        bar.style.opacity = 0.5;
        return;
      }
      proj.duration = dur(); buildTimeline(); const nb = inner.querySelector(`.bar[data-clip="${k}"]`); nb?.classList.add("sel");
      seek(handle === "l" ? starts()[k] : starts()[k] + c.out - c.in - 1 / fps);
    };
    const up = () => {
      removeEventListener("pointermove", move); removeEventListener("pointerup", up); line.style.display = "none";
      if (handle && moved) editChanged();
      else if (!handle && moved && target !== k && target !== k + 1) { const [m] = S.clips.splice(k, 1); S.clips.splice(target > k ? target - 1 : target, 0, m); S.selClip = target > k ? target - 1 : target; editChanged(); }
      else { bar.style.opacity = ""; if (!moved) { const r = inner.getBoundingClientRect(); seek((e.clientX - r.left - LABEL_W) / S.zoom); } }
    };
    addEventListener("pointermove", move); addEventListener("pointerup", up);
    return;
  }

  if (bar.dataset.job != null) { // render range of a job
    const j = S.jobs[+bar.dataset.job], s0 = j.info.start, e0 = j.info.end;
    select(null, null); S.selJob = +bar.dataset.job; renderSide();
    const move = (ev) => {
      const dt = (ev.clientX - x0) / S.zoom, tg = snapTargets(null);
      if (handle !== "r") j.info.start = clamp(snap(s0 + dt, tg, ev.shiftKey).v, 0, (handle ? e0 : dur()) - 0.1);
      if (handle !== "l") j.info.end = clamp(snap(e0 + dt, tg, ev.shiftKey).v, j.info.start + 0.1, dur());
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
  const { tin: in0, tout: out0 } = itemTimes(j, it), tg = snapTargets(it);
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

// Zoom: ctrl/⌘ + wheel (around the pointer), slider and +/- (around the playhead). Plain wheel / trackpad scroll moves.
scroller.addEventListener("wheel", (e) => {
  if (e.ctrlKey || e.metaKey) { e.preventDefault(); setZoom(S.zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX); return; }
  // vertical wheel moves along time when there is nothing to scroll vertically (or with shift)
  const noV = scroller.scrollHeight <= scroller.clientHeight + 1;
  if ((e.shiftKey || noV) && Math.abs(e.deltaX) < Math.abs(e.deltaY)) { e.preventDefault(); scroller.scrollLeft += e.deltaY; }
}, { passive: false });
function setZoom(z, anchorX) {
  const r = scroller.getBoundingClientRect();
  const ax = anchorX ?? clamp(r.left + tx(S.t) - scroller.scrollLeft, r.left + LABEL_W, r.right - 20);
  const tAt = (scroller.scrollLeft + ax - r.left - LABEL_W) / S.zoom;
  S.zoom = clamp(z, 2, Math.min(800, 30000 / Math.max(1, dur())));
  $("#zoom").value = Math.log(S.zoom);
  buildTimeline();
  scroller.scrollLeft = Math.max(0, tAt * S.zoom + LABEL_W - (ax - r.left));
}
function fitZoom() { setZoom((scroller.clientWidth - LABEL_W - 40) / Math.max(0.5, dur())); scroller.scrollLeft = 0; }
$("#zoom").addEventListener("input", (e) => setZoom(Math.exp(+e.target.value)));
$("#zoom").min = Math.log(2); $("#zoom").max = Math.log(800); $("#zoom").step = 0.01;

$("#tl-resize").addEventListener("pointerdown", (e) => {
  const y0 = e.clientY, h0 = $("#tl").offsetHeight;
  const mv = (ev) => { document.documentElement.style.setProperty("--tl-h", clamp(h0 - (ev.clientY - y0), 120, innerHeight - 200) + "px"); layout(); };
  const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
  addEventListener("pointermove", mv); addEventListener("pointerup", up);
});

// ------------------------------------------------------------------ inspector (لوحة التعديل)
const FONTS = ["Tajawal", "Cairo", "Almarai", "IBM Plex Sans Arabic", "Readex Pro", "Noto Kufi Arabic", "Changa", "El Messiri", "Reem Kufi", "Lalezar", "Amiri", "Aref Ruqaa", "Marhey", "Rakkas", "Lemonada", "Mada", "Harmattan", "Baloo Bhaijaan 2"];
const AR = {
  text: "النص", sub: "نص فرعي", label: "التسمية", value: "القيمة", unit: "الوحدة", kicker: "سطر صغير فوق", caption: "تعليق", tag: "التاق",
  size: "الحجم", color: "لون النص", accent: "لون التمييز", accent2: "اللون الثاني", glow: "لون التوهج", core: "لون القلب", tint: "الصبغة", bg: "الخلفية",
  text_color: "لون النص", hl_bg: "لون التظليل", hl_ink: "لون نص التظليل", font: "الخط", weight: "السماكة", fx: "الحركة", type: "النوع", kind: "النوع",
  icon: "الأيقونة", kashida: "الكشيدة", speed: "السرعة", stagger: "الفرق بين الكلمات", x: "الموضع س", y: "الموضع ص", w: "العرض", h: "الارتفاع", d: "القطر",
  cx: "المركز س", cy: "المركز ص", px: "النقطة س", py: "النقطة ص", rot: "الدوران", align: "المحاذاة", radius: "نصف القطر", items: "العناصر", words: "الكلمات",
  phrases: "العبارات", images: "الصور", src: "الملف", img: "الصورة", lines: "السطور", marks: "العلامات", every: "التكرار كل", delta: "النسبة", day: "اليوم",
  month: "الشهر", weekday: "يوم الأسبوع", in_dur: "مدة الدخول", out_dur: "مدة الخروج", anim: "الحركة", out_anim: "حركة الخروج", from: "من", to: "إلى",
  steps: "الخطوات", side: "الجهة", thick: "السماكة", dur: "المدة", strength: "القوة", zoom: "التكبير", s: "الحجم", sfx: "الصوت", sfx_gain: "مستوى الصوت",
};
const SKIP = new Set(["in", "out", "xf", "at", "_"]);
const isColor = (v) => typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v);
function field(label, key, val, { min, max, step, type = "range", unit = "" } = {}) {
  const L = esc(label);
  if (type === "color") return `<div class="field wide"><label>${L}</label><input type="color" data-k="${key}" value="${isColor(val) ? val : "#ffffff"}" title="${isColor(val) ? "" : "تلقائي — اختر لون لتغييره"}"></div>`;
  if (type === "bool") return `<div class="field wide"><label>${L}</label><input type="checkbox" data-k="${key}" ${val ? "checked" : ""}></div>`;
  if (type === "text") return `<div class="field wide"><label>${L}</label><input type="text" dir="auto" data-k="${key}" value="${esc(val)}"></div>`;
  if (type === "area") return `<div class="field wide"><label>${L}</label><textarea dir="auto" rows="2" data-k="${key}">${esc(val)}</textarea></div>`;
  if (type === "font") return `<div class="field wide"><label>${L}</label><select data-k="${key}">${[...new Set([val || "Tajawal", ...FONTS])].map((f) => `<option ${f === (val || "Tajawal") ? "selected" : ""}>${esc(f)}</option>`).join("")}</select></div>`;
  return `<div class="field"><label title="${L}">${L}</label><input type="range" data-k="${key}" min="${min}" max="${max}" step="${step}" value="${val}">
    <input type="number" data-k="${key}" step="${step}" value="${+(+val).toFixed(4)}">${unit}</div>`;
}
// Editable fields of a piece's params object: text, numbers, colours, fonts, nested lists of text.
function paramFields(obj, path, depth = 0) {
  let h = "";
  for (const [k, v] of Object.entries(obj || {})) {
    if (SKIP.has(k) || k.startsWith("_")) continue;
    const key = "p." + (path ? path + "." : "") + k, lab = AR[k] || k;
    if (typeof v === "string") {
      if (isColor(v)) h += field(lab, key, v, { type: "color" });
      else if (k === "font") h += field(lab, key, v, { type: "font" });
      else if (k === "src" || k === "img" || k === "logo") h += field(lab, key, v, { type: "text" });
      else h += field(lab, key, v, { type: v.length > 24 || /[|\n]/.test(v) || k === "text" ? "area" : "text" });
    } else if (typeof v === "number") {
      const r = k === "size" ? [10, 400, 1] : ["x", "y", "cx", "cy", "px", "py", "w", "h", "d", "s"].includes(k) ? [0, 1, 0.005] : k === "rot" ? [-30, 30, 0.5] : [0, Math.max(10, Math.abs(v) * 3), Math.abs(v) < 2 ? 0.01 : 1];
      h += field(lab, key, v, { min: r[0], max: r[1], step: r[2] });
    } else if (typeof v === "boolean") h += field(lab, key, v, { type: "bool" });
    else if (Array.isArray(v) && depth < 2) {
      h += `<div class="sub-h">${esc(lab)}</div>`;
      v.forEach((x, i) => { if (typeof x === "string") h += field(`${lab} ${i + 1}`, `${key}.${i}`, x, { type: "text" }); else if (x && typeof x === "object") h += `<div class="nest">${paramFields(x, `${path ? path + "." : ""}${k}.${i}`, depth + 1)}</div>`; });
    }
  }
  return h;
}
function renderSide() {
  const side = $("#side"), f = findItem(S.sel), j = S.jobs[S.selJob];
  let h = "";
  if (S.selClip != null && S.clips[S.selClip]) {
    const c = S.clips[S.selClip], info = proj.sources[c.src];
    h += `<h2>🎬 مقطع ${S.selClip + 1} من ${S.clips.length}</h2><div class="muted" dir="ltr">${esc(base(c.src))}</div>`;
    h += `<h3>القص</h3>` + field("من (ث)", "c.in", c.in, { min: 0, max: info?.duration ?? c.out, step: 1 / fps }) + field("إلى (ث)", "c.out", c.out, { min: 0, max: info?.duration ?? c.out, step: 1 / fps });
    h += `<div class="btns"><button id="c-split">✂ قص عند المؤشر</button><button id="c-del">🗑 حذف المقطع</button></div>`;
  } else if (f) {
    const xf = getXf(f.j, f.it), { tin, tout, timed } = itemTimes(f.j, f.it), slot = itemSlot(f.it), bp = itemBase(f.it);
    h += `<h2>${esc(f.it.label)}</h2><div class="muted">${esc(f.j.info.style)} · ${esc(f.j.info.name)}</div>`;
    if (slot) h += `<div class="btns"><button id="i-dup">⧉ نسخ</button><button id="i-del">🗑 حذف</button></div>`;
    if (timed) h += `<h3>التوقيت</h3>` + field("دخول (ث)", "t.in", tin, { min: 0, max: dur(), step: 1 / fps }) + field("خروج (ث)", "t.out", tout, { min: 0, max: dur(), step: 1 / fps });
    const obj = bp ? getPath(f.j.R.P, bp) : null;
    if (obj && typeof obj === "object") {
      h += `<h3>المحتوى والشكل</h3><div class="hint">*كلمة* = تمييز · | = سطر جديد</div>` + paramFields(obj, bp);
      const extra = [["size", 100], ["color", "#ffffff"], ["accent", "#ffd400"], ["font", ""]].filter(([k]) => !(k in obj));
      if (extra.length) h += `<div class="add-row">إضافة: ${extra.map(([k, v]) => `<button data-add="${bp}.${k}" data-v="${v}">${AR[k]}</button>`).join(" ")}</div>`;
    }
    if (f.it.xf) {
      h += `<h3>التحويل <button id="xf-reset" class="mini">إعادة</button></h3>`;
      h += field("الموضع س %", "xf.x", xf.x * 100, { min: -100, max: 100, step: 0.1 });
      h += field("الموضع ص %", "xf.y", xf.y * 100, { min: -100, max: 100, step: 0.1 });
      h += field("الدوران °", "xf.rot", xf.rot, { min: -180, max: 180, step: 0.5 });
      h += field("الحجم %", "xf.scale", xf.scale * 100, { min: 5, max: 400, step: 1 });
      h += field("الشفافية %", "xf.opacity", xf.opacity * 100, { min: 0, max: 100, step: 1 });
    }
  } else {
    h += `<h2>${proj.edited || S.clips.length > 1 ? "المونتاج" : esc(base(S.clips[0]?.src || proj.video))}</h2><div class="muted">${fmt(dur(), true)} · ${proj.size.join("×")} · ${S.clips.length} مقطع</div>`;
    h += `<h3>الطبقات</h3><div class="joblist">` + S.jobs.map((x, i) => `<div data-job="${i}" class="${i === S.selJob ? "sel" : ""}">${esc(x.info.style)} · ${esc(x.info.name)}</div>`).join("") + `</div>`;
  }
  if (j && S.selClip == null) {
    h += `<h3>الستايل — ${esc(j.info.style)}${j.R.job.theme ? " · " + esc(j.R.job.theme) : ""}</h3>`;
    if ("font" in j.R.P || /textfx|info|docu|neon|frames|captions/.test(j.info.style)) h += field("خط الستايل", "p.font", j.R.P.font || "Tajawal", { type: "font" });
    for (const s of j.R.job._tune || []) h += field(AR[s.path.split(".").pop()] || s.label || s.path, "p." + s.path, getPath(j.R.P, s.path) ?? (s.type === "color" ? "#ffffff" : 0), s);
  }
  h += `<h3>اختصارات</h3><div id="help"><kbd>مسافة</kbd> تشغيل · <kbd>←</kbd><kbd>→</kbd> ثانية (<kbd>shift</kbd> 5) · <kbd>,</kbd><kbd>.</kbd> فريم<br>
    <kbd>s</kbd> أو <kbd>⌘B</kbd> قص المقطع عند المؤشر · <kbd>Delete</kbd> حذف المحدد · <kbd>⌘D</kbd> نسخ العنصر<br>
    <kbd>i</kbd>/<kbd>o</kbd> دخول/خروج العنصر عند المؤشر · <kbd>alt</kbd>+<kbd>←</kbd><kbd>→</kbd> تحريكه فريم<br>
    على الفيديو: سحب = تحريك · المقبض فوق = دوران · الزاوية = حجم · دبل كلك = إعادة<br>
    <kbd>b</kbd> قبل/بعد · <kbd>w</kbd> مقارنة · <kbd>g</kbd> المنطقة الآمنة · <kbd>h</kbd> إخفاء اللوحات<br>
    <kbd>⌘</kbd>+عجلة = زوم · عجلة/تراكباد = تنقل · <kbd>f</kbd> ملاءمة · <kbd>⌘Z</kbd> تراجع · <kbd>⌘S</kbd> حفظ</div>`;
  side.innerHTML = h;
  side.querySelectorAll("[data-job]").forEach((d) => (d.onclick = () => { S.selJob = +d.dataset.job; renderSide(); }));
  side.querySelector("#xf-reset")?.addEventListener("click", () => { const f2 = findItem(S.sel); setXf(f2.j, f2.it, { x: 0, y: 0, rot: 0, scale: 1, opacity: 1 }); pushUndo(); draw(); renderSide(); });
  side.querySelector("#i-del")?.addEventListener("click", () => deleteItem(findItem(S.sel)));
  side.querySelector("#i-dup")?.addEventListener("click", () => duplicateItem(findItem(S.sel)));
  side.querySelector("#c-split")?.addEventListener("click", () => splitAt(S.t));
  side.querySelector("#c-del")?.addEventListener("click", () => deleteClip(S.selClip));
  side.querySelectorAll("[data-add]").forEach((b) => (b.onclick = () => { const f2 = findItem(S.sel); setPath(f2.j.R.P, b.dataset.add, isNaN(+b.dataset.v) || b.dataset.v === "" ? b.dataset.v : +b.dataset.v); rebuild(f2.j); markDirty(f2.j); pushUndo(); renderSide(); draw(); }));
  side.querySelectorAll("[data-k]").forEach((inp) => {
    inp.addEventListener(inp.tagName === "SELECT" ? "change" : "input", () => onField(inp));
    inp.addEventListener("change", () => pushUndo());
  });
}
async function ensureFont(j, name) {
  if (!name || name === "Tajawal") return;
  const fonts = (j.R.P.google_fonts ||= []);
  if (!fonts.includes(name)) fonts.push(name);
  const doc = j.iframe.contentDocument;
  if (!doc.querySelector(`link[data-font="${name}"]`)) {
    const l = doc.createElement("link"); l.rel = "stylesheet"; l.dataset.font = name;
    l.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name)}:wght@400;700;900&display=block`;
    doc.head.appendChild(l);
    await new Promise((r) => { l.onload = r; l.onerror = r; });
  }
  await Promise.all([400, 700, 900].map((w) => doc.fonts.load(`${w} 40px "${name}"`, "ابجد").catch(() => {})));
}
async function onField(inp) {
  const k = inp.dataset.k, raw = inp.type === "checkbox" ? inp.checked : inp.type === "range" || inp.type === "number" ? parseFloat(inp.value) : inp.value;
  $("#side").querySelectorAll(`[data-k="${k}"]`).forEach((o) => o !== inp && (o.value = inp.type === "range" ? +(+raw).toFixed(4) : raw));
  const f = findItem(S.sel), j = S.jobs[S.selJob];
  if (k.startsWith("c.") && S.selClip != null) {
    const c = S.clips[S.selClip];
    c[k.slice(2)] = frame(raw); if (c.out - c.in < 2 / fps) c.out = c.in + 2 / fps;
    S.editDirty = true; markDirty(null); proj.duration = dur(); recomputeCuts(); buildTimeline(); return;
  }
  if (k.startsWith("xf.") && f) {
    const xf = getXf(f.j, f.it), n = k.slice(3);
    xf[n] = n === "x" || n === "y" || n === "scale" || n === "opacity" ? raw / 100 : raw;
    setXf(f.j, f.it, xf);
  } else if (k.startsWith("t.") && f) {
    const path = k === "t.in" ? f.it.in : f.it.out;
    if (path) setPath(f.j.R.P, path, frame(raw));
    markDirty(f.j); buildTimeline();
  } else if (k.startsWith("p.")) {
    const jj = f && !k.startsWith("p.theme") && k !== "p.font" && !(j.R.job._tune || []).some((s) => "p." + s.path === k) ? f.j : j;
    if (k.endsWith(".font")) await ensureFont(jj, raw);
    setPath(jj.R.P, k.slice(2), raw);
    rebuild(jj);
    markDirty(jj); buildTimeline();
    if (S.sel) for (const b of document.querySelectorAll(".bar[data-id]")) b.classList.toggle("sel", +b.dataset.j === S.sel.j && b.dataset.id === S.sel.id);
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
function snapshot() { return JSON.stringify({ jobs: S.jobs.map((j) => ({ p: j.R.P, s: j.info.start, e: j.info.end })), clips: S.clips }); }
function pushUndo() { const s = snapshot(); if (S.undo.at(-1) === s) return; S.undo.push(s); S.redo = []; if (S.undo.length > 200) S.undo.shift(); }
function assignDeep(dst, src) {
  for (const k of Object.keys(dst)) if (!(k in src)) delete dst[k];
  for (const [k, v] of Object.entries(src)) {
    if (v && typeof v === "object" && dst[k] && typeof dst[k] === "object" && Array.isArray(v) === Array.isArray(dst[k])) assignDeep(dst[k], v);
    else dst[k] = v;
  }
}
function restore(snap) {
  const st = JSON.parse(snap);
  st.jobs.forEach((x, i) => { const j = S.jobs[i]; assignDeep(j.R.P, x.p); j.info.start = j.R.start = x.s; j.info.end = j.R.end = x.e; rebuild(j); markDirty(j); });
  if (JSON.stringify(S.clips) !== JSON.stringify(st.clips)) { S.clips = st.clips; S.editDirty = true; markDirty(null); proj.duration = dur(); recomputeCuts(); }
  buildTimeline(); renderSide(); seek(Math.min(S.t, dur()));
}
function undo() { if (S.undo.length < 2) return; S.redo.push(S.undo.pop()); restore(S.undo.at(-1)); }
function redoFn() { if (!S.redo.length) return; const s = S.redo.pop(); S.undo.push(s); restore(s); }
function status(txt, cls) { const st = $("#status"); st.textContent = txt; st.className = cls || ""; }
function markDirty(j) { if (j) S.dirty.add(j); status("غير محفوظ •", "dirty"); }
async function save() {
  if (S.editDirty) {
    const r = await fetch("/save_edit", { method: "POST", body: JSON.stringify({ clips: S.clips, mtime: proj.mtime }) });
    if (r.status === 409) return status("المشروع تغيّر من برا — ما حفظت عشان ما أكتب فوقه. حدّث الصفحة", "dirty");
    if (!r.ok) return status("فشل حفظ المونتاج", "dirty");
    proj.mtime = (await r.json()).mtime;
    S.editDirty = false;
  }
  for (const j of S.dirty) {
    let s = j.info.start, e = j.info.end;
    for (const it of itemsOf(j)) { const { tin, tout, timed } = itemTimes(j, it); if (timed) { s = Math.min(s, tin - 0.3); e = Math.max(e, tout + 0.3); } }
    j.info.start = j.R.start = Math.max(0, frame(s)); j.info.end = j.R.end = Math.min(dur(), frame(e));
    const r = await fetch(`/save?j=${j.info.i}`, { method: "POST", body: JSON.stringify({ params: j.R.P, start: j.info.start, end: j.info.end, mtime: j.info.mtime }) });
    if (r.status === 409) return status(`«${j.info.name}» تغيّر من برا — ما حفظت عشان ما أكتب فوقه. حدّث الصفحة`, "dirty");
    if (!r.ok) return status("فشل الحفظ", "dirty");
    j.info.mtime = (await r.json()).mtime;
  }
  S.dirty.clear();
  status("محفوظ ✓");
  S.mtimes = await (await fetch("/mtimes.json")).json();
  buildTimeline();
}
addEventListener("beforeunload", (e) => { if (S.dirty.size || S.editDirty) { e.preventDefault(); e.returnValue = ""; } });

// تحديث مباشر: إذا تعدّل ملف الجوب أو المشروع من برا (من الشات)، يتحدث هنا بدون إعادة تحميل.
async function watchFiles() {
  try {
    const m = await (await fetch("/mtimes.json")).json();
    if (!S.mtimes) S.mtimes = m;
    else if (JSON.stringify(m) !== JSON.stringify(S.mtimes)) {
      if (S.dirty.size || S.editDirty) { status("الملف تغيّر من برا وعندك تعديلات ما انحفظت — ما راح أكتب فوقه. حدّث الصفحة", "dirty"); }
      else if (m[0] !== S.mtimes[0]) { location.reload(); return; }
      else {
        for (let i = 1; i < m.length; i++) if (m[i] !== S.mtimes[i]) {
          const j = S.jobs[i - 1], fresh = await (await fetch(`/job.json?j=${j.info.i}&fresh=1`)).json();
          assignDeep(j.R.P, fresh.params); j.R.job._tune = fresh._tune; j.info.start = j.R.start = fresh.start; j.info.end = j.R.end = fresh.end; j.info.mtime = m[i];
          for (const fnt of fresh.params.google_fonts || []) await ensureFont(j, fnt);
          rebuild(j);
        }
        S.mtimes = m; pushUndo(); buildTimeline(); renderSide(); draw(); status("تحدّث من الملف ✓");
      }
    }
  } catch (e) { /* server busy */ }
  setTimeout(watchFiles, 1500);
}

// ------------------------------------------------------------------ render from the editor
async function render() {
  if (S.dirty.size || S.editDirty) await save();
  const r = await (await fetch("/render", { method: "POST", body: JSON.stringify({ mblur: $("#mblur").checked ? 4 : 1 }) })).json();
  if (!r.ok) return status("فيه رندر شغّال", "dirty");
  $("#b-render").disabled = true;
  const poll = async () => {
    const st = await (await fetch("/render_status.json")).json();
    $("#prog").style.width = (st.progress || 0) * 100 + "%";
    $("#prog-wrap").style.display = "block";
    if (st.state === "running") { status(`رندر… ${Math.round((st.progress || 0) * 100)}% · ${st.elapsed}ث`); setTimeout(poll, 1000); return; }
    $("#b-render").disabled = false;
    if (st.state === "done") status("تم الرندر ✓ — الملفات في out/"); else status("فشل الرندر — شوف السجل", "dirty");
    S.lastLog = st.log; console.log(st.log);
  };
  poll();
}

// ------------------------------------------------------------------ add-clip dialog
async function openAdd() {
  const files = await (await fetch("/media.json")).json();
  const dlg = $("#add-dlg");
  dlg.innerHTML = `<div class="dlg"><h3>إضافة مقطع عند المؤشر</h3>${files.length ? files.map((f) => `<div class="file" data-f="${esc(f)}" dir="ltr">${esc(base(f))}</div>`).join("") : `<div class="muted">ما فيه فيديوهات جنب المشروع. حط الملفات في نفس مجلد الفيديو.</div>`}<button id="add-close">إغلاق</button></div>`;
  dlg.style.display = "flex";
  dlg.querySelectorAll(".file").forEach((d) => (d.onclick = async () => { dlg.style.display = "none"; status("يجهّز المقطع…"); await addClip(d.dataset.f); status("أُضيف المقطع •", "dirty"); }));
  $("#add-close").onclick = () => (dlg.style.display = "none");
}

// ------------------------------------------------------------------ buttons + keys
$("#b-play").onclick = () => (S.playing ? pause() : play());
$("#b-before").onclick = () => { S.before = !S.before; draw(); };
$("#b-wipe").onclick = () => { S.wipe = !S.wipe; applyView(); };
$("#b-safe").onclick = () => { S.safe = !S.safe; applyView(); };
$("#b-split").onclick = () => splitAt(S.t);
$("#b-add").onclick = openAdd;
$("#b-fit").onclick = fitZoom;
$("#b-save").onclick = save;
$("#b-undo").onclick = undo;
$("#b-redo").onclick = redoFn;
$("#b-render").onclick = render;
if (!proj.can_edit) { $("#b-split").disabled = $("#b-add").disabled = true; $("#b-split").title = $("#b-add").title = "المونتاج يحتاج project.json"; }
addEventListener("keydown", (e) => {
  const tg = e.target.tagName;
  if (tg === "TEXTAREA" || tg === "SELECT" || (tg === "INPUT" && !["range", "checkbox", "color"].includes(e.target.type))) return;
  const mod = e.metaKey || e.ctrlKey, f = findItem(S.sel), fr = 1 / fps, key = e.key.toLowerCase();
  if (mod && key === "s") { e.preventDefault(); save(); return; }
  if (mod && key === "z") { e.preventDefault(); e.shiftKey ? redoFn() : undo(); return; }
  if (mod && key === "b") { e.preventDefault(); if (proj.can_edit) splitAt(S.t); return; }
  if (mod && key === "d") { e.preventDefault(); if (f) duplicateItem(f); return; }
  const nudge = (d) => {
    if (!f) return;
    const { tin, tout } = itemTimes(f.j, f.it);
    if (f.it.in) setPath(f.j.R.P, f.it.in, frame(Math.max(0, tin + d)));
    if (f.it.out) setPath(f.j.R.P, f.it.out, frame(tout + d));
    markDirty(f.j); pushUndo(); buildTimeline(); renderInspectorValues(); draw();
  };
  const map = {
    " ": () => (S.playing ? pause() : play()),
    arrowleft: () => (e.altKey ? nudge(-(e.shiftKey ? 10 : 1) * fr) : seek(S.t - (e.shiftKey ? 5 : 1))),
    arrowright: () => (e.altKey ? nudge((e.shiftKey ? 10 : 1) * fr) : seek(S.t + (e.shiftKey ? 5 : 1))),
    ",": () => { if (S.playing) pause(); seek(S.t - fr); },
    ".": () => { if (S.playing) pause(); seek(S.t + fr); },
    i: () => { if (f?.it.in) { setPath(f.j.R.P, f.it.in, S.t); markDirty(f.j); pushUndo(); buildTimeline(); renderInspectorValues(); draw(); } },
    o: () => { if (f?.it.out) { setPath(f.j.R.P, f.it.out, S.t); markDirty(f.j); pushUndo(); buildTimeline(); renderInspectorValues(); draw(); } },
    s: () => { if (proj.can_edit) splitAt(S.t); },
    delete: () => (S.selClip != null ? deleteClip(S.selClip) : f && deleteItem(f)),
    backspace: () => (S.selClip != null ? deleteClip(S.selClip) : f && deleteItem(f)),
    b: () => { S.before = !S.before; draw(); },
    w: () => { S.wipe = !S.wipe; applyView(); },
    g: () => { S.safe = !S.safe; applyView(); },
    f: fitZoom,
    h: () => { document.body.classList.toggle("ui-hidden"); layout(); },
    escape: () => { S.selClip = null; select(null, null); },
    "=": () => setZoom(S.zoom * 1.25), "-": () => setZoom(S.zoom / 1.25),
  };
  if (map[key]) { e.preventDefault(); map[key](); }
});

// ------------------------------------------------------------------ start
proj.duration = dur();
layout();
addEventListener("resize", layout);
pushUndo();
recomputeCuts();
buildTimeline();
requestAnimationFrame(() => requestAnimationFrame(fitZoom));
renderSide();
seek(parseFloat(qs.get("t") ?? proj.jobs[0]?.start ?? 0));
for (const p of Object.keys(S.srcs)) loadSource(p);
watchFiles();
requestAnimationFrame(tick);
