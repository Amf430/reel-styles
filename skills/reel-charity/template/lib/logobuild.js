// Layered-colour logo build: the logo is split into parts (tools/split_logo.py writes logo/parts.js),
// every part arrives as a stack of accent colours under the real artwork, then the accents fade.
// Rings close in from the frame and land on the logo's focus point; faint pulses ring out after.
//
// LOGO = { w, h, focus: [x%, y%], parts: [{ name, kind, x, y, w, h, at, dur }] }   (x/y/w/h in % of the logo)
// kinds: rtl · ltr · ttb · btt (wipes) · cx · cy (open from the centre line) · pop · rain · slide

const WIPE_FROM = {
  rtl: "inset(0% 0% 0% 100%)",
  ltr: "inset(0% 100% 0% 0%)",
  ttb: "inset(0% 0% 100% 0%)",
  btt: "inset(100% 0% 0% 0%)",
  cx: "inset(0% 50% 0% 50%)",
  cy: "inset(50% 0% 50% 0%)",
};
const FULL = "inset(0% 0% 0% 0%)";

// box: the element the logo fills (its aspect should match LOGO.w / LOGO.h)
function mountLogo(box, logo, accents, src = "logo") {
  box.classList.add("lb");
  logo.parts.forEach((p, i) => {
    const part = document.createElement("div");
    part.className = `lb-part lb-${p.kind}`;
    Object.assign(part.style, { left: `${p.x}%`, top: `${p.y}%`, width: `${p.w}%`, height: `${p.h}%` });
    const url = `url(${src}/${p.name}.png)`;
    const stack = p.kind === "rain" ? accents.slice(0, 1) : [accents[i % 2 ? 1 : 0], accents[2] ?? accents[1]];
    for (const c of stack) {
      const layer = document.createElement("div");
      layer.className = "lb-layer";
      layer.style.background = c;
      layer.style.webkitMaskImage = layer.style.maskImage = url;
      part.appendChild(layer);
    }
    const img = document.createElement("img");
    img.className = "lb-layer";
    img.src = `${src}/${p.name}.png`;
    part.appendChild(img);
    box.appendChild(part);
  });
  const [fx, fy] = logo.focus;
  box.insertAdjacentHTML("beforeend",
    `<svg class="lb-trace" viewBox="0 0 100 ${(100 * logo.h) / logo.w}" preserveAspectRatio="none">
       <circle class="lb-ring" cx="${fx}" cy="${(fy * logo.h) / logo.w}" r="3.2" fill="none" stroke="${accents[0]}"
         stroke-width=".45" stroke-linecap="round" pathLength="100" stroke-dasharray="100" stroke-dashoffset="100"
         transform="rotate(-90 ${fx} ${(fy * logo.h) / logo.w})"/></svg>`);
}

// accents first, the real artwork last; then the accents fade so no colour fringe stays
function lbWipe(tl, part, from, at, dur, ease, gap = 0.08) {
  const layers = [...part.children];
  layers.forEach((l, i) => tl.fromTo(l, { clipPath: from }, { clipPath: FULL, duration: dur, ease }, at + i * gap));
  layers.slice(0, -1).forEach((l) => tl.to(l, { opacity: 0, duration: 0.25 }, at + dur + layers.length * gap + 0.1));
}

// speed > 1 compresses the build (a closing reprise runs faster than the opening)
function buildLogo(tl, box, logo, t0, speed = 1) {
  const at = (s) => t0 + s / speed;
  const d = (s) => s / speed;
  const ring = box.querySelector(".lb-ring");
  tl.fromTo(ring, { attr: { "stroke-dashoffset": 100 } }, { attr: { "stroke-dashoffset": 0 }, duration: d(0.5), ease: "power2.inOut" }, at(0));
  tl.to(ring, { attr: { r: 8 }, opacity: 0, duration: d(0.5), ease: "power2.out" }, at(0.5));
  const parts = [...box.querySelectorAll(".lb-part")];
  logo.parts.forEach((p, i) => {
    const el = parts[i];
    const t = at(0.35 + p.at);
    const dur = d(p.dur ?? 0.6);
    if (WIPE_FROM[p.kind]) {
      lbWipe(tl, el, WIPE_FROM[p.kind], t, dur, p.kind === "cx" || p.kind === "cy" ? "expo.out" : "power2.inOut");
    } else if (p.kind === "pop") {
      [...el.children].forEach((l, j) => tl.fromTo(l, { scale: 0 }, { scale: 1, duration: dur, ease: "back.out(2.6)" }, t + j * 0.07));
      [...el.children].slice(0, -1).forEach((l) => tl.to(l, { opacity: 0, duration: 0.2 }, t + dur + 0.25));
    } else if (p.kind === "rain") {
      [...el.children].slice(0, -1).forEach((l) => tl.set(l, { opacity: 0 }, at(0)));
      tl.fromTo(el, { y: -60, opacity: 0, rotation: -10 }, { y: 0, opacity: 1, rotation: 0, duration: dur, ease: "bounce.out" }, t);
    } else if (p.kind === "slide") {
      tl.fromTo(el, { x: 120, filter: "blur(8px)" }, { x: 0, filter: "blur(0px)", duration: dur * 1.2, ease: "expo.out" }, t);
      lbWipe(tl, el, WIPE_FROM.rtl, t, dur, "power3.out");
    }
  });
}

// the logo's focus point on screen, for rings to land on: rect = { left, top, width, height } of the box
function focusPoint(rect, logo) {
  return { x: rect.left + (rect.width * logo.focus[0]) / 100, y: rect.top + (rect.height * logo.focus[1]) / 100 };
}

// coloured rings close in from the frame and land on the focus point — SVG circles, outermost first
function ringsTo(tl, rings, from, to, at, duration = 0.62, immediateRender = true) {
  rings.forEach((ring, i) => {
    tl.fromTo(ring,
      { attr: { cx: from.x, cy: from.y, r: from.r + i * 60, "stroke-width": from.w }, opacity: 1 },
      { attr: { cx: to.x, cy: to.y, r: Math.max(4, to.r - i * 5), "stroke-width": to.w }, duration, ease: "power3.inOut", immediateRender },
      at + i * 0.09);
    tl.to(ring, { opacity: 0, duration: 0.3, ease: "power1.out" }, at + duration + 0.12 + i * 0.05);
  });
}

// faint rings pulse outward from the focus point after the build
function pulseRings(tl, rings, at, every = 0.55) {
  rings.forEach((ring, i) => {
    tl.fromTo(ring, { scale: 0.2, opacity: 0.55 }, { scale: 2.6, opacity: 0, duration: 2.2, ease: "power1.out", transformOrigin: "50% 50%" }, at + i * every);
  });
}
