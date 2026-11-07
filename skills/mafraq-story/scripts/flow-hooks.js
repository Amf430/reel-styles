// Browser hooks for driving Google Flow (labs.google/flow) through Claude in Chrome.
// Paste each block with the javascript tool on the Flow tab. They are idempotent.

// 1) Upload hook: Flow opens a hidden <input type=file>. This catches it and gives it
//    id="captured-file-input" so `find "captured file input"` + `file_upload` can fill it.
//    The files you upload must sit under a folder Chrome may read (e.g. ~/Desktop/علاء).
if (!window.__hooked) {
  const oc = HTMLInputElement.prototype.click, os = HTMLInputElement.prototype.showPicker;
  const cap = (el) => {
    el.id = 'captured-file-input'; el.setAttribute('aria-label', 'captured file input');
    if (!el.isConnected) { el.style.cssText = 'display:block;position:fixed;top:0;left:0;width:10px;height:10px;opacity:0.01'; document.body.appendChild(el); }
    window.__cap = el;
  };
  HTMLInputElement.prototype.click = function () { if (this.type === 'file') { cap(this); return; } return oc.call(this); };
  HTMLInputElement.prototype.showPicker = function () { if (this.type === 'file') { cap(this); return; } return os && os.call(this); };
  window.__hooked = true;
}

// 2) Download hook: keep every blob Flow creates, so a script can POST it to the local receiver
//    (scripts/flow-recv.py on 127.0.0.1:8799) instead of the Downloads folder.
if (!window.__dlHooked) {
  window.__dl = [];
  const oco = URL.createObjectURL;
  URL.createObjectURL = function (o) { const u = oco.call(URL, o); window.__blobs = window.__blobs || {}; window.__blobs[u] = o; return u; };
  window.__dlHooked = true;
}

// 3) Download one image as 2K. `id` is a unique piece of the image's src (Flow shows it in the
//    file name, e.g. "1719778b"), `name` the file name to save (without .jpg).
//    The JS tool times out after ~45 s, so for many images run a loop in the background and
//    read window.__res later (see references/art-flow.md).
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
window.__up2k = async function (id, name) {
  const el = [...document.querySelectorAll('img')].find((i) => i.src.includes(id)); if (!el) return name + ': not found';
  el.scrollIntoView({ block: 'center' }); await sleep(700);
  const r = el.getBoundingClientRect(); const x = r.x + r.width / 2, y = r.y + r.height / 2;
  el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: x, clientY: y, button: 2 }));
  await sleep(700);
  const dl = [...document.querySelectorAll('[role=menuitem], button, li, div')]
    .filter((e) => e.childElementCount < 6 && (e.textContent || '').trim().startsWith('تنزيل') && e.getBoundingClientRect().width > 0).pop();
  if (!dl) return name + ': no download item';
  dl.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); dl.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true })); dl.click(); await sleep(800);
  const k2 = [...document.querySelectorAll('[role=menuitem], button, li, div')]
    .filter((e) => /^2K/.test((e.textContent || '').trim()) && e.getBoundingClientRect().width > 0 && e.childElementCount < 6).pop();
  if (!k2) return name + ': no 2K item';
  const before = Object.keys(window.__blobs || {}).length;
  k2.click();
  for (let t = 0; t < 90; t++) {
    await sleep(1000);
    const ks = Object.keys(window.__blobs || {});
    if (ks.length > before) {
      const b = window.__blobs[ks[ks.length - 1]];
      const resp = await fetch('http://127.0.0.1:8799/' + name + '.jpg', { method: 'POST', body: b });
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      return name + ': ' + b.size + ' ' + resp.status + ' in ' + t + 's';
    }
  }
  return name + ': timeout';
};

// Background batch (returns at once; poll window.__res):
// window.__res = []; (async () => { for (const [id, name] of JOBS) window.__res.push(await window.__up2k(id, name)); })();
