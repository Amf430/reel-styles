// The closing card (Asem → Rohamaa): logo, closing line, 2–3 columns (QR · phone · bank) and a contact strip.
// Lays out inside a 1920×1080 container from CONTENT; endCardIn() puts its entrance on a timeline.
// Used by reel-charity (end/) and reel-diorama (a leaf facing the camera square-on, so the QR scans).

function mountEndCard(root, content) {
  const P = content.palette;
  root.classList.add("ec");
  root.innerHTML = `<div class="ec-logo"></div><div class="ec-tag"></div><div class="ec-cols"></div><div class="ec-bar"></div>`;
  // the logo fits 860×322 at the top
  const k = Math.min(860 / LOGO.w, 322 / LOGO.h);
  const rect = { width: LOGO.w * k, height: LOGO.h * k };
  rect.left = 960 - rect.width / 2; rect.top = 30 + (322 - rect.height) / 2;
  const logo = root.querySelector(".ec-logo");
  Object.assign(logo.style, { left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px` });
  mountLogo(logo, LOGO, [P.primary, P.accent, P.lightAccent]);
  root.querySelector(".ec-tag").textContent = content.tagline;

  const cols = content.columns, gap = cols.length === 2 ? 640 : 580;
  root.querySelector(".ec-cols").innerHTML = cols.map((c, i) => {
    let body = "";
    if (c.type === "qr") body = `<div class="qr"><img src="${c.src}"></div><div class="cap">${c.caption || ""}</div>`;
    if (c.type === "phone") body = `<div class="big">${icon("phone")}<span>${c.value}</span></div>`;
    if (c.type === "bank" && c.accounts.length === 1) {
      const a = c.accounts[0];
      body = `${a.logo ? `<img class="bank" src="${a.logo}">` : `<div class="bankic">${icon("bank")}</div>`}<div class="iban" data-type="${a.iban}">${a.iban}</div>`;
    }
    if (c.type === "bank" && c.accounts.length > 1)
      body = c.accounts.map((a) => `<div class="acct">${a.logo ? `<img src="${a.logo}">` : ""}<span>${a.iban}</span></div>`).join("");
    return `<div class="col" style="left:${960 + ((cols.length - 1) / 2 - i) * gap}px"><div class="tab">${c.title}</div><div class="body">${body}</div></div>`;
  }).join("");
  root.querySelector(".ec-bar").innerHTML = content.bar.map((b) => {
    const lead = b.social ? `<div class="soc">${b.social.map((n) => icon(n)).join("")}</div>` : `<div class="ic">${icon(b.icon)}</div>`;
    return `<div class="item">${lead}${b.ltr ? `<bdi dir="ltr">${b.text}</bdi>` : `<span>${b.text}</span>`}</div>`;
  }).join('<div class="sep"></div>');
  return { logo, rect };
}

// logo builds at t0 (speed > 1 = faster reprise), then the line, the columns, the IBAN types, the strip
function endCardIn(tl, root, t0, speed = 1) {
  buildLogo(tl, root.querySelector(".ec-logo"), LOGO, t0, speed);
  tl.fromTo(root.querySelector(".ec-tag"), { clipPath: "inset(0% 0% 0% 100%)", x: 30 }, { clipPath: "inset(0% 0% 0% 0%)", x: 0, duration: 0.9, ease: "power3.out" }, t0 + 0.35);
  root.querySelectorAll(".col").forEach((col, i) => {
    const at = t0 + 1.6 + i * 0.22;
    tl.fromTo(col.querySelector(".tab"), { clipPath: "inset(0% 0% 0% 100% round 18px)", x: 40 }, { clipPath: "inset(0% 0% 0% 0% round 18px)", x: 0, duration: 0.6, ease: "expo.out" }, at);
    tl.fromTo(col.querySelector(".body"), { y: 40, opacity: 0, scale: 0.85 }, { y: 0, opacity: 1, scale: 1, duration: 0.7, ease: "back.out(1.6)" }, at + 0.2);
    const qr = col.querySelector(".qr img");
    if (qr) tl.fromTo(qr, { clipPath: "inset(0% 0% 100% 0%)" }, { clipPath: "inset(0% 0% 0% 0%)", duration: 0.6, ease: "steps(12)" }, at + 0.35);
  });
  // a single IBAN types itself in; figure spaces hold the width so the pill never jumps
  root.querySelectorAll("[data-type]").forEach((el) => {
    const text = el.dataset.type, n = { v: 0 };
    tl.fromTo(n, { v: 0 }, { v: text.length, duration: 1.1, ease: "none",
      onUpdate: () => { el.textContent = text.slice(0, Math.round(n.v)).padEnd(text.length, " "); } }, t0 + 2.3);
  });
  const bar = root.querySelector(".ec-bar");
  tl.fromTo(bar, { clipPath: "inset(0% 0% 0% 100% round 46px)" }, { clipPath: "inset(0% 0% 0% 0% round 46px)", duration: 0.9, ease: "expo.out" }, t0 + 3.0);
  tl.fromTo(bar.querySelectorAll(".item"), { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out", stagger: 0.1 }, t0 + 3.2);
}

// palette → CSS variables used by charity.css
function applyPalette(P) {
  const css = { "--primary": P.primary, "--accent": P.accent, "--light": P.light, "--ink": P.ink, "--mist": P.mist,
    "--line": `color-mix(in srgb, ${P.primary} 12%, #fff)` };
  Object.entries(css).forEach(([k, v]) => document.documentElement.style.setProperty(k, v));
}
