"""Episode 1 build script: writes the whole HyperFrames project (index.html + compositions/*.html) as static HTML.
Copy it per episode as build-epNN.py and edit the DATA sections only:
  VO        absolute start of every voice line (the clock of the film)
  SCENES    sub-compositions and their shots: (id, local start, local end, camera move)
  CAPS      caption groups per line: (word count, key-word index, position low|top|mid|big)
  per-scene overlays (notification, phone screen, chat bubbles, rule card, choice cards) in their own blocks
  SFX       sound list at the bottom
Usage: python3 build-epNN.py <project_dir> <words.json from vo-words.py>
Then: npx hyperframes check --json ; npx hyperframes snapshot --review ; npx hyperframes render -o ../epNN-v1.mp4
"""
import json, os, sys

P = sys.argv[1]            # project dir
W = json.load(open(sys.argv[2]))  # word timings per line (line-local seconds)
os.makedirs(f"{P}/compositions", exist_ok=True)
TOTAL = 65.0
r2 = lambda x: round(x, 3)

# ---------- shared style ----------
FONTS = """
@font-face{font-family:'DINAr';src:url('assets/fonts/din-medium.ttf');font-weight:500}
@font-face{font-family:'DINAr';src:url('assets/fonts/din-bold.ttf');font-weight:700}
@font-face{font-family:'DINAr';src:url('assets/fonts/din-black.ttf');font-weight:900}
"""
VARS = "--amber:#EBA23C;--red:#C8302A;--ink:#0E0C0A;--paper:#EFE6D2;--white:#F7F2E8;"

# ---------- voice lines (absolute start of each file) ----------
VO = {"01-n": 0.25, "02-u": 4.75, "03-n": 7.45, "04-n": 8.65, "05-n": 11.75, "06-n": 14.35,
      "07-n": 17.35, "08-n": 19.15, "09-n": 23.6, "12-n": 33.45, "13-u": 37.7, "13-h": 39.75,
      "14-u": 40.75, "15-u": 43.7, "16-u": 45.5, "17-n": 47.0, "18-n": 57.3}

# ---------- scenes: (id, abs start, duration, shots[(id, local start, local end, cam)]) ----------
# cam: (origin, s0, s1, x0, x1, y0, y1, ease)
SCENES = [
 ("night", 0.0, 8.45, [
   ("s01", 0.0, 2.1, ("510px 990px", 1.0, 1.07, 0, 0, 0, 0, "power1.inOut")),
   ("s02", 2.1, 4.55, ("540px 700px", 1.06, 1.0, 0, 0, 0, 0, "power1.out")),
   ("s03", 4.55, 8.45, ("530px 930px", 1.03, 1.13, 0, 0, 0, 0, "power1.inOut"))]),
 ("majed", 8.45, 10.5, [
   ("s04", 0.0, 3.1, ("540px 900px", 1.05, 1.05, 0, 0, 30, -30, "power1.inOut")),
   ("s05", 3.1, 5.7, ("560px 900px", 1.0, 1.06, 0, 0, 0, 0, "power1.inOut")),
   ("s06", 5.7, 8.7, ("420px 900px", 1.02, 1.08, 0, 0, 0, 0, "power1.inOut")),
   ("s07", 8.7, 10.5, ("540px 820px", 1.0, 1.03, 0, 0, 0, 0, "none"))]),
 ("window", 18.95, 7.65, [
   ("s08", 0.0, 1.2, ("540px 960px", 1.1, 1.1, 25, -25, 0, 0, "none")),
   ("s09", 1.2, 4.5, ("430px 960px", 1.0, 1.18, 0, 0, 0, 0, "power1.inOut")),
   ("s10", 4.5, 5.25, ("600px 900px", 1.0, 1.04, 0, 0, 0, 0, "none")),
   ("s11", 5.8, 7.65, ("540px 960px", 1.04, 1.0, 0, 0, 0, 0, "power1.out"))]),
 ("rule", 26.6, 3.0, []),
 ("morning", 29.6, 7.95, [
   ("s12", 0.0, 3.7, ("540px 900px", 1.0, 1.05, 0, 0, 0, 0, "power1.inOut")),
   ("s13", 3.7, 4.95, ("640px 1250px", 1.0, 1.1, 0, 0, 0, 0, "power1.in")),
   ("s14", 4.95, 7.95, ("540px 900px", 1.06, 1.0, 0, 0, -20, 10, "power1.out"))]),
 ("coffee", 37.55, 27.45, [
   ("s15", 0.0, 3.0, ("540px 1000px", 1.0, 1.07, 0, 0, 0, 0, "power1.inOut")),
   ("s16", 3.0, 6.0, ("540px 960px", 1.1, 1.1, 0, 0, 0, -90, "power2.inOut")),
   ("s17", 6.0, 7.7, ("560px 700px", 1.0, 1.16, 0, 0, 0, 0, "power2.in")),
   ("s18", 7.7, 27.45, ("540px 900px", 1.15, 1.03, 0, 0, 0, 0, "expo.out"))]),
]

# ---------- phone-screen mapping (square-to-quad homography → matrix3d) ----------
def quad_matrix(w, h, q, inset=0.04):
    cx = sum(p[0] for p in q) / 4; cy = sum(p[1] for p in q) / 4
    q = [(cx + (x - cx) * (1 - inset), cy + (y - cy) * (1 - inset)) for x, y in q]
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = q
    dx1, dx2, dy1, dy2 = x1 - x2, x3 - x2, y1 - y2, y3 - y2
    sx, sy = x0 - x1 + x2 - x3, y0 - y1 + y2 - y3
    den = dx1 * dy2 - dx2 * dy1
    g = (sx * dy2 - dx2 * sy) / den; hh = (dx1 * sy - sx * dy1) / den
    a, b, c = x1 - x0 + g * x1, x3 - x0 + hh * x3, x0
    d, e, f = y1 - y0 + g * y1, y3 - y0 + hh * y3, y0
    m = [a / w, d / w, 0, g / w, b / h, e / h, 0, hh / h, 0, 0, 1, 0, c, f, 0, 1]
    return "matrix3d(" + ",".join(f"{v:.6f}" for v in m) + ")"

S03_SCREEN = quad_matrix(320, 640, [(573, 630), (877, 715), (522, 1239), (188, 1122)])

# ---------- captions ----------
# (line, [ (word count, key word index or None, position) ], colour role)
CAPS = {
 "01-n": ([(3, 2, "low"), (3, 0, "low"), (3, 2, "low")], "n"),
 "02-u": ([(2, 0, "top"), (3, 2, "top")], "u"),
 "03-n": ([(1, 0, "top")], "n"),
 "04-n": ([(3, 0, "low"), (4, 3, "low")], "n"),
 "05-n": ([(3, 0, "low"), (2, 1, "low")], "n"),
 "08-n": ([(3, 2, "low"), (3, 2, "low"), (3, 2, "low")], "n"),
 "09-n": ([(2, 1, "low"), (2, 1, "low")], "n"),
 "12-n": ([(1, 0, "low"), (3, 2, "low"), (2, 1, "low")], "n"),
 "13-u": ([(3, 1, "low")], "u"),
 "13-h": ([(1, 0, "low")], "n"),
 "14-u": ([(3, 2, "mid"), (2, 1, "mid")], "u"),
 "15-u": ([(3, 2, "low")], "u"),
 "16-u": ([(1, 0, "big")], "u"),
 "17-n": ([(4, 3, "top")], "n"),
}

def caption_groups():
    gs = []
    for line, (spec, role) in CAPS.items():
        ws = W[line]; i = 0; t0 = VO[line]
        for n, key, pos in spec:
            grp = ws[i:i + n]; i += n
            gs.append({"line": line, "role": role, "pos": pos, "key": key,
                       "words": [(w["text"], t0 + w["start"]) for w in grp],
                       "start": t0 + grp[0]["start"] - 0.12, "last": t0 + grp[-1]["end"]})
    gs.sort(key=lambda g: g["start"])
    for j, g in enumerate(gs):
        nxt = gs[j + 1]["start"] if j + 1 < len(gs) else TOTAL
        g["end"] = min(max(g["last"] + 0.45, g["start"] + 0.9), nxt - 0.02)
    return gs

# ---------- writers ----------
def scene_file(cid, dur, css, body, js):
    return f"""<template>
  <style>
    {FONTS}
    #root{{position:absolute;inset:0;overflow:hidden;background:transparent;{VARS}font-family:'DINAr',sans-serif}}
    .shot{{position:absolute;inset:0;overflow:hidden;background:#000}}
    .cam{{position:absolute;inset:0}}
    .cam img.plate{{position:absolute;left:0;top:-7.5px;width:1080px;height:1935px;display:block}}
    {css}
  </style>
  <div id="root" data-composition-id="{cid}" data-width="1080" data-height="1920">
{body}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
{js}
    window.__timelines["{cid}"] = tl;
  </script>
</template>
"""

def shot_html(sid, a, b, inner_extra="", outer_extra="", wrap_beat=False):
    img = f'<img class="plate" id="{sid}-img" src="assets/shots/{sid}.jpg" alt="">'
    if wrap_beat:
        img = f'<div class="beat" id="{sid}-beat" style="position:absolute;inset:0">{img}</div>'
    return (f'    <div id="{sid}" class="clip shot" data-start="{r2(a)}" data-duration="{r2(b - a)}" data-track-index="1">\n'
            f'      <div class="cam" id="{sid}-cam" data-layout-allow-overflow>{img}{inner_extra}</div>{outer_extra}\n    </div>\n')

def cam_js(sid, a, b, cam):
    o, s0, s1, x0, x1, y0, y1, ease = cam
    return (f'    tl.fromTo("#{sid}-cam",{{scale:{s0},x:{x0},y:{y0},transformOrigin:"{o}"}},'
            f'{{scale:{s1},x:{x1},y:{y1},duration:{r2(b - a)},ease:"{ease}"}},{r2(a)});\n')

files = {}

# ===== night: s01 notification, s03 voice note on the phone screen =====
sc = SCENES[0]
css = """
.notif{position:absolute;left:60px;right:60px;top:420px;padding:26px 30px;border-radius:34px;
  background:rgba(26,23,20,.94);box-shadow:0 18px 40px rgba(0,0,0,.55);direction:rtl;color:var(--white)}
.notif .row{display:flex;align-items:center;gap:22px}
.notif .ic{width:76px;height:76px;border-radius:20px;background:var(--amber);flex:none;display:flex;align-items:center;justify-content:center}
.notif .ic i{width:40px;height:30px;background:var(--ink);border-radius:15px 15px 15px 4px;display:block}
.notif .tx{flex:1}
.notif .t1{display:flex;justify-content:space-between;font-weight:700;font-size:36px;line-height:1.25}
.notif .t1 small{font-weight:500;font-size:28px;opacity:.6}
.notif .t2{font-weight:500;font-size:34px;line-height:1.35;opacity:.92}
.screen{position:absolute;left:0;top:0;width:320px;height:640px;transform-origin:0 0;direction:rtl;
  background:linear-gradient(180deg,#F4CB86,#E9A64F);border-radius:18px;overflow:hidden;color:var(--ink)}
.screen .hd{height:64px;background:rgba(14,12,10,.88);color:#F4CB86;font-weight:700;font-size:22px;display:flex;align-items:center;padding:0 18px}
.screen .who{font-weight:700;font-size:15px;margin:26px 20px 6px;color:#7a1c16}
.vbub{position:relative;margin:0 14px 0 40px;height:86px;border-radius:18px 4px 18px 18px;background:rgba(255,248,235,.92);
  display:flex;align-items:center;gap:10px;padding:0 14px}
.vbub .play{width:0;height:0;border-top:14px solid transparent;border-bottom:14px solid transparent;border-right:22px solid var(--ink);flex:none}
.vbub .wave{flex:1;display:flex;align-items:center;gap:3px;height:50px;direction:ltr;justify-content:flex-end}
.vbub .wave i{display:block;width:5px;border-radius:3px;background:#5d544a}
.vbub .dur{font-weight:700;font-size:15px;flex:none}
.del{position:absolute;inset:0;border-radius:18px 4px 18px 18px;background:rgba(255,248,235,.96);display:flex;align-items:center;
  padding:0 16px;font-weight:500;font-style:italic;font-size:17px;color:#6b6259;opacity:0}
"""
bars = [10, 18, 30, 22, 40, 28, 14, 34, 46, 26, 16, 38, 24, 12, 30, 44, 20, 32, 18, 26, 36, 14, 22, 10]
wave = "".join(f'<i class="wb" style="height:{h}px"></i>' for h in bars)
s03_screen = f'''<div class="screen" data-layout-ignore style="transform:{S03_SCREEN}">
        <div class="hd">العائلة 🌴</div>
        <div class="who">عمي أبو ماجد</div>
        <div class="vbub" id="vbub"><div class="play"></div><div class="wave" id="wave">{wave}</div><div class="dur" id="vdur">٠:٠٤</div>
          <div class="del" id="vdel">🚫 تم حذف هذه الرسالة</div></div>
      </div>'''
notif = '''<div class="notif" id="notif"><div class="row"><div class="ic"><i></i></div><div class="tx">
        <div class="t1"><span>العائلة 🌴</span><small>الآن</small></div>
        <div class="t2">عمي أبو ماجد: 🎤 رسالة صوتية (٠:٠٤)</div></div></div></div>'''
body = ""; js = ""
for sid, a, b, cam in sc[3]:
    extra = s03_screen if sid == "s03" else ""
    outer = f'\n      {notif}' if sid == "s01" else ""
    body += shot_html(sid, a, b, extra, outer)
    js += cam_js(sid, a, b, cam)
js += """    tl.fromTo("#notif",{y:-18,opacity:.8},{y:0,opacity:1,duration:.4,ease:"expo.out"},0);
    tl.to("#notif",{y:-40,opacity:0,duration:.22,ease:"power3.in"},1.82);
    // phone buzz: two bursts shake the frame a few pixels
    [[0,.42],[.62,1.04]].forEach(([a,b])=>{ for(let t=a,i=0;t<b;t+=.035,i++){ tl.to("#s01-img",{x:(i%2?3:-3),duration:.035,ease:"none"},t);} tl.to("#s01-img",{x:0,duration:.035},b); });
    // voice note plays while the uncle whispers (4.75 → 7.09), then it is deleted
    const wb=[...document.querySelectorAll("#wave .wb")].reverse();
    wb.forEach((el,i)=>tl.fromTo(el,{backgroundColor:"#5d544a"},{backgroundColor:"#C8302A",duration:.05},4.85+i*(2.2/wb.length)));
    tl.fromTo("#vdel",{opacity:0},{opacity:1,duration:.12,ease:"power2.out"},7.5);
    tl.fromTo("#vbub",{x:0},{keyframes:[{x:-5,duration:.04},{x:5,duration:.04},{x:-3,duration:.04},{x:0,duration:.04}]},7.5);
"""
files["night"] = scene_file("night", sc[2], css, body, js)

# ===== majed: s05 chat header card, s06/s07 Majed's messages =====
sc = SCENES[1]
css = """
.card{position:absolute;left:70px;right:70px;direction:rtl;color:var(--white)}
.chathead{top:330px;padding:24px 28px;border-radius:30px;background:rgba(26,23,20,.94);display:flex;align-items:center;gap:22px;box-shadow:0 16px 36px rgba(0,0,0,.5)}
.chathead .av{width:92px;height:92px;border-radius:50%;background:var(--paper);flex:none;position:relative;overflow:hidden;border:3px solid var(--amber)}
.chathead .av b{position:absolute;left:50%;top:22px;width:46px;height:52px;margin-left:-23px;border-radius:50%;background:#fff;border:2px solid var(--ink)}
.chathead .nm{font-weight:900;font-size:44px;line-height:1.1}
.chathead .ls{font-weight:500;font-size:34px;opacity:.75;margin-top:4px}
.chathead .badge{margin-right:auto;min-width:58px;height:58px;border-radius:29px;background:var(--amber);color:var(--ink);font-weight:900;font-size:34px;display:flex;align-items:center;justify-content:center}
.bub{position:absolute;right:90px;max-width:820px;padding:24px 34px 18px;border-radius:34px 8px 34px 34px;background:var(--paper);color:var(--ink);
  direction:rtl;font-weight:700;font-size:52px;line-height:1.3;box-shadow:8px 8px 0 #000;border:4px solid #000}
.bub small{display:block;text-align:left;font-weight:500;font-size:28px;opacity:.55;margin-top:2px}
"""
body = ""; js = ""
for sid, a, b, cam in sc[3]:
    outer = ""
    if sid == "s05":
        outer = '\n      <div class="card chathead" id="chathead"><div class="av"><b></b></div><div><div class="nm">ماجد</div><div class="ls">آخر ظهور: قبل ٣ أيام</div></div><div class="badge">١</div></div>'
    if sid == "s06":
        outer = '\n      <div class="bub" id="bub1a" style="top:330px">إذا صار لي شي…<br>لا تصدّق أحد.<small>١١:٤٨ م</small></div>'
    if sid == "s07":
        outer = ('\n      <div class="bub" id="bub1b" style="top:250px;opacity:.55;font-size:40px">إذا صار لي شي… لا تصدّق أحد.</div>'
                 '\n      <div class="bub" id="bub2" style="top:430px">حتى أبوي.<small>١١:٤٨ م</small></div>')
    body += shot_html(sid, a, b, "", outer)
    js += cam_js(sid, a, b, cam).replace('duration:1.8,ease:"none"', 'duration:.66,ease:"none"') if sid == "s07" else cam_js(sid, a, b, cam)
js += """    tl.fromTo("#chathead",{y:-30,opacity:0,filter:"blur(8px)"},{y:0,opacity:1,filter:"blur(0px)",duration:.45,ease:"expo.out"},3.25);
    tl.fromTo("#bub1a",{scale:.6,opacity:0,transformOrigin:"100% 0%"},{scale:1,opacity:1,duration:.35,ease:"back.out(1.4)"},5.85);
    tl.fromTo("#bub2",{scale:.6,opacity:0,transformOrigin:"100% 0%"},{scale:1,opacity:1,duration:.35,ease:"back.out(1.4)"},8.85);
    // punch-in on «أبوي»
    tl.to("#s07-cam",{scale:1.13,duration:.14,ease:"power4.out"},9.38);
"""
files["majed"] = scene_file("majed", sc[2], css, body, js)

# ===== window: lights out =====
sc = SCENES[2]
body = ""; js = ""
for sid, a, b, cam in sc[3]:
    body += shot_html(sid, a, b)
    js += cam_js(sid, a, b, cam)
js += """    tl.fromTo("#s11-img",{opacity:0},{opacity:1,duration:.4,ease:"power2.out"},5.8);
"""
files["window"] = scene_file("window", sc[2], "", body, js)

# ===== rule card =====
css = """
#rule-bg{position:absolute;inset:0;background:#000}
.rule{position:absolute;left:96px;right:96px;top:640px;padding:54px 48px 60px;background:var(--paper);color:var(--ink);direction:rtl;
  border:6px solid #000;box-shadow:14px 14px 0 var(--red);text-align:center}
.rule .lb{display:inline-block;font-weight:900;font-size:40px;color:var(--paper);background:var(--red);padding:6px 26px 10px;margin-bottom:26px}
.rule .tx{font-weight:900;font-size:76px;line-height:1.35}
"""
body = ('    <div id="rule-bg" class="clip" data-start="0" data-duration="3" data-track-index="1"></div>\n'
        '    <div id="rule-wrap" class="clip" data-start="0" data-duration="3" data-track-index="2" style="position:absolute;inset:0">\n'
        '      <div class="rule" id="rule-card"><div class="lb">قاعدة البيت ١</div><div class="tx">اللي يصير في البيت…<br>يبقى في البيت.</div></div>\n    </div>\n')
js = """    tl.fromTo("#rule-card",{scale:1.28,rotation:-2,opacity:0,filter:"blur(10px)"},{scale:1,rotation:-2,opacity:1,filter:"blur(0px)",duration:.2,ease:"power4.out"},.04);
    tl.fromTo("#rule-card",{x:0},{keyframes:[{x:-10,duration:.04},{x:8,duration:.04},{x:-5,duration:.04},{x:0,duration:.05}]},.24);
    tl.to("#rule-card",{opacity:0,filter:"blur(8px)",duration:.2,ease:"power2.in"},2.76);
"""
files["rule"] = scene_file("rule", 3.0, css, body, js)

# ===== morning: Saud's message in the family group =====
sc = SCENES[4]
css = """
.grp{position:absolute;left:60px;right:60px;top:300px;direction:rtl;background:rgba(24,22,20,.95);border-radius:32px;padding:20px 26px 28px;color:var(--white);box-shadow:0 16px 36px rgba(0,0,0,.5)}
.grp .hd{font-weight:700;font-size:34px;opacity:.85;padding-bottom:16px;border-bottom:2px solid rgba(255,255,255,.12);margin-bottom:20px}
.grp .msg{background:#2f2b27;border-radius:8px 28px 28px 28px;padding:16px 24px 12px;margin-left:60px}
.grp .nm{font-weight:900;font-size:32px;color:var(--amber)}
.grp .tx{font-weight:700;font-size:44px;line-height:1.35}
.grp .tm{text-align:left;font-weight:500;font-size:28px;opacity:.55}
"""
body = ""; js = ""
for sid, a, b, cam in sc[3]:
    outer = ""
    if sid == "s12":
        outer = '\n      <div class="grp" id="grp"><div class="hd">العائلة 🌴</div><div class="msg"><div class="nm">سعود</div><div class="tx">صباح الخير 🌞 وش هالفويس اللي انحذف يا أبو ماجد 😂</div><div class="tm">٦:٠٥ ص</div></div></div>'
    body += shot_html(sid, a, b, "", outer)
    js += cam_js(sid, a, b, cam)
js += """    tl.fromTo("#grp",{y:-30,opacity:0},{y:0,opacity:1,duration:.45,ease:"expo.out"},.3);
    tl.to("#grp",{opacity:0,duration:.2,ease:"power2.in"},3.48);
"""
files["morning"] = scene_file("morning", sc[2], css, body, js)

# ===== coffee: the uncle, the phone, the choice =====
sc = SCENES[5]
css = """
.chip{position:absolute;left:50%;top:1300px;width:640px;margin-left:-320px;direction:rtl;text-align:center;background:var(--paper);color:var(--ink);
  border:4px solid #000;box-shadow:8px 8px 0 #000;font-weight:700;font-size:38px;padding:12px 20px 16px;border-radius:14px}
.chip:after{content:"";position:absolute;left:50%;bottom:-26px;margin-left:-14px;border-left:14px solid transparent;border-right:14px solid transparent;border-top:22px solid #000}
.dim{position:absolute;inset:0;background:#050403;opacity:0}
.choice{position:absolute;left:120px;right:120px;direction:rtl;background:var(--paper);color:var(--ink);border:6px solid #000;box-shadow:12px 12px 0 #000;padding:26px 40px 34px;text-align:center}
.choice .lb{display:inline-block;font-weight:900;font-size:84px;line-height:1.15;padding:0 22px 8px;background:var(--amber)}
.choice .q{font-weight:700;font-size:46px;line-height:1.35;margin-top:18px}
.cta{position:absolute;left:100px;right:100px;top:1190px;direction:rtl;text-align:center;color:var(--white);font-weight:900;font-size:56px;line-height:1.3;
  text-shadow:0 4px 0 #000,0 0 24px rgba(0,0,0,.8)}
.cta em{font-style:normal;color:var(--amber)}
.cta small{display:block;font-weight:700;font-size:36px;color:rgba(247,242,232,.7);margin-top:14px}
"""
body = ""; js = ""
for sid, a, b, cam in sc[3]:
    inner = ""; outer = ""; beat = False
    if sid == "s16":
        inner = '<div class="chip" id="chip">رسالة صوتية · أُرسلت ٢:١٤ ص</div>'
    if sid == "s18":
        beat = True
        outer = ('\n      <div class="dim" id="dim"></div>'
                 '\n      <div class="choice" id="ch1" style="top:520px"><div class="lb">أواجهه</div><div class="q">«إيه سمعته. وين ماجد؟»</div></div>'
                 '\n      <div class="choice" id="ch2" style="top:860px"><div class="lb">أسكت</div><div class="q">«أي فويس؟»</div></div>'
                 '\n      <div class="cta" id="cta">علّق: <em>أواجهه</em> أو <em>أسكت</em><small id="next">تابع للحلقة ٢</small></div>')
    body += shot_html(sid, a, b, inner, outer, wrap_beat=beat)
    js += cam_js(sid, a, b, cam).replace(f'duration:{r2(b - a)},ease:"expo.out"', 'duration:.5,ease:"expo.out"')
# local = abs - 37.55
L = lambda t: r2(t - 37.55)
js += f"""    tl.fromTo("#chip",{{y:20,opacity:0}},{{y:0,opacity:1,duration:.35,ease:"expo.out"}},{L(41.0)});
    tl.set("#s18-beat",{{scale:1,transformOrigin:"540px 900px"}},0);
    [45.30,46.25,47.20].forEach(t=>tl.fromTo("#s18-beat",{{scale:1}},{{keyframes:[{{scale:1.022,duration:.08,ease:"power2.out"}},{{scale:1,duration:.3,ease:"power2.inOut"}}],transformOrigin:"540px 900px"}},t-37.55));
    tl.fromTo("#dim",{{opacity:0}},{{opacity:.66,duration:.8,ease:"power2.inOut"}},{L(46.8)});
    tl.fromTo("#ch1",{{scale:1.12,rotation:-1.5,opacity:0}},{{scale:1,rotation:-1.5,opacity:1,duration:.22,ease:"power4.out"}},{L(49.25)});
    tl.fromTo("#ch1 .q",{{opacity:.15}},{{opacity:1,duration:.3,ease:"power2.out"}},{L(51.6)});
    tl.fromTo("#ch2",{{scale:1.12,rotation:1.5,opacity:0}},{{scale:1,rotation:1.5,opacity:1,duration:.22,ease:"power4.out"}},{L(54.3)});
    tl.fromTo("#ch2 .q",{{opacity:.15}},{{opacity:1,duration:.3,ease:"power2.out"}},{L(55.9)});
    tl.fromTo("#cta",{{opacity:0,filter:"blur(8px)"}},{{opacity:1,filter:"blur(0px)",duration:.3,ease:"power3.out"}},{L(57.4)});
    tl.fromTo("#next",{{opacity:0}},{{opacity:1,duration:.3,ease:"power2.out"}},{L(62.0)});
    tl.fromTo("#ch1",{{y:0}},{{keyframes:[{{y:-14,duration:.12,ease:"power2.out"}},{{y:0,duration:.25,ease:"power2.inOut"}}]}},{L(58.98)});
    tl.fromTo("#ch2",{{y:0}},{{keyframes:[{{y:-14,duration:.12,ease:"power2.out"}},{{y:0,duration:.25,ease:"power2.inOut"}}]}},{L(59.92)});
"""
files["coffee"] = scene_file("coffee", sc[2], css, body, js)

# ===== HUD: the story bar =====
css = """
.hud{position:absolute;left:56px;top:196px;direction:rtl;background:rgba(10,9,8,.62);border-radius:16px;padding:14px 22px 16px;color:var(--white);
  font-weight:700;font-size:34px;line-height:1.38;border:2px solid rgba(235,162,60,.35)}
.hud .dot{display:inline-block;width:16px;height:16px;border-radius:50%;background:var(--red);margin-left:12px;vertical-align:middle}
.hud .tm{position:relative;height:47px}
.hud .tm span{position:absolute;right:0;top:0;white-space:nowrap}
.hud .mj{display:inline-block;transform-origin:100% 50%}
"""
body = ('    <div id="hud-box" class="clip" data-start="0" data-duration="65" data-track-index="1" style="position:absolute;inset:0">\n'
        '      <div class="hud" id="hud"><div><i class="dot" id="hud-dot"></i>اليوم ٣</div>'
        '<div class="tm"><span id="tm1">٢:١٤ ص</span><span id="tm2" style="opacity:0">٦:٠٥ ص</span></div>'
        '<div><span class="mj" id="hud-mj">ماجد: مفقود</span></div></div>\n    </div>\n')
js = """    tl.set("#hud-mj",{scale:1,color:"#F7F2E8"},0);
    [8.7,9.7,10.7].forEach(t=>tl.fromTo("#hud-mj",{scale:1,color:"#F7F2E8"},{keyframes:[{scale:1.12,color:"#E0473E",duration:.12,ease:"power2.out"},{scale:1,color:"#E0473E",duration:.5,ease:"power2.inOut"}]},t));
    tl.to("#hud-mj",{color:"#F7F2E8",duration:.4},11.4);
    tl.fromTo("#tm1",{opacity:1},{opacity:0,duration:.06},26.64);
    tl.fromTo("#tm2",{opacity:0},{opacity:1,duration:.06},26.7);
    tl.fromTo("#hud",{x:0},{keyframes:[{x:-6,duration:.04},{x:6,duration:.04},{x:0,duration:.05}]},26.64);
    tl.fromTo("#hud-dot",{scale:1},{keyframes:[{scale:1.7,duration:.1},{scale:1,duration:.35}]},45.55);
    tl.fromTo("#hud",{opacity:1},{opacity:.45,duration:.6},46.9);
"""
files["hud"] = scene_file("hud", TOTAL, css, body, js)

# ===== captions =====
css = """
.cap{position:absolute;left:0;right:0;direction:rtl;text-align:center;padding:0 90px}
.cap.low{top:1150px}.cap.top{top:410px}
.cap.mid{top:880px}
.cap.top .in,.cap.mid .in{background:rgba(8,7,6,.6);padding:4px 30px 12px;border-radius:16px}.cap.big{top:1120px}
.cap .in{display:inline-block;font-weight:900;font-size:70px;line-height:1.3;color:var(--white);
  text-shadow:0 4px 0 #000,0 0 3px #000,0 0 22px rgba(0,0,0,.85)}
.cap.big .in{font-size:110px}
.cap .w{display:inline-block;opacity:.35;margin:0 .1em}
"""
body = ""; js = ""
for k, g in enumerate(caption_groups()):
    gid = f"c{k:02d}"
    spans = "".join(f'<span class="w" id="{gid}w{i}">{t}</span>' for i, (t, _) in enumerate(g["words"]))
    body += (f'    <div id="{gid}" class="clip cap {g["pos"]}" data-start="{r2(g["start"])}" data-duration="{r2(g["end"] - g["start"])}" data-track-index="1">'
             f'<div class="in" id="{gid}-in">{spans}</div></div>\n')
    s, e = g["start"], g["end"]
    js += f'    tl.fromTo("#{gid}-in",{{opacity:0,filter:"blur(6px)"}},{{opacity:1,filter:"blur(0px)",duration:.13,ease:"power3.out"}},{r2(s)});\n'
    for i, (t, ts) in enumerate(g["words"]):
        col = ("#E0473E" if g["role"] == "u" else "#EBA23C") if (g["key"] == i or g["line"] == "02-u") else "#F7F2E8"
        js += f'    tl.fromTo("#{gid}w{i}",{{opacity:.35,color:"#F7F2E8"}},{{opacity:1,color:"{col}",duration:.1,ease:"power2.out"}},{r2(max(s + 0.02, ts - 0.04))});\n'
    js += f'    tl.to("#{gid}-in",{{opacity:0,duration:.12,ease:"power2.in"}},{r2(e - 0.13)});\n'
files["captions"] = scene_file("captions", TOTAL, css, body, js)

for cid, html in files.items():
    open(f"{P}/compositions/{cid}.html", "w").write(html)

# ===== root =====
hosts = ""
for cid, a, d, _ in SCENES:
    hosts += (f'      <div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="{a}" data-duration="{d}" '
              f'data-track-index="1" data-track-kind="graphics" data-width="1080" data-height="1920" style="z-index:1"></div>\n')
hosts += ('      <div id="hud" data-composition-id="hud" data-composition-src="compositions/hud.html" data-start="0" data-duration="65" data-track-index="2" data-track-kind="graphics" data-width="1080" data-height="1920" style="z-index:5"></div>\n'
          '      <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="65" data-track-index="3" data-track-kind="captions" data-width="1080" data-height="1920" style="z-index:6"></div>\n')
import subprocess
DUR = lambda f: round(float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f"{P}/{f}"],capture_output=True,text=True).stdout),3)
aud = ""
for k, t in VO.items():
    aud += f'      <audio id="vo-{k}" class="clip" src="assets/vo/{k}.wav" data-start="{t}" data-duration="{DUR("assets/vo/" + k + ".wav")}" data-track-index="10" data-volume="1"></audio>\n'
SFX = [("bedA", "bed", 0, 26.62, 0.16, 0, "", ' data-fade-out="0.25"'),
       ("bedB", "bed", 29.6, 35.4, 0.16, 29.6, "", ' data-fade-in="1.5" data-fade-out="2.5"'),
       ("fx-buzz", "buzz", 0, None, 0.7, 0, "", ""), ("fx-notify", "notify", 0.05, None, 0.3, 0, "", ""),
       ("fx-tap", "tap", 4.62, None, 0.5, 0, "", ""), ("fx-del", "glitch", 7.48, None, 0.4, 0, "", ""),
       ("fx-msg1", "message_in", 14.28, None, 0.45, 0, "", ""), ("fx-msg2", "message_in", 17.28, None, 0.45, 0, "", ""),
       ("fx-punch", "thud", 17.83, None, 0.5, 0, "", ""), ("fx-switch", "click", 24.16, None, 0.9, 0, "", ""),
       ("fx-swell", "reverse_swell", 24.75, 1.85, 0.45, 0.83, "", ""), ("fx-slam", "slam", 26.62, None, 0.75, 0, "", ""),
       ("fx-msg3", "message_in", 29.88, None, 0.45, 0, "", ""), ("fx-tray", "thud", 41.0, None, 0.55, 0, "", ""),
       ("fx-heart", "heartbeat", 45.3, None, 0.8, 0, "", ""), ("fx-dark", "whoosh_soft", 46.75, None, 0.35, 0, "", ""),
       ("fx-card1", "pop_low", 49.25, None, 0.6, 0, "", ""), ("fx-card2", "pop_low", 54.3, None, 0.6, 0, "", ""),
       ("fx-cta", "swipe_ui", 57.38, None, 0.45, 0, "", "")]
for i, (aid, f, t, d, v, ms, _, ex) in enumerate(SFX):
    dd = f' data-duration="{d if d else DUR("assets/sfx/" + f + ".wav")}"'
    mm = f' data-media-start="{ms}"' if ms else ""
    trk = 14 if aid.startswith("bed") else 11 + (i % 3)
    aud += f'      <audio id="{aid}" class="clip" src="assets/sfx/{f}.wav" data-start="{t}"{dd}{mm} data-track-index="{trk}" data-volume="{v}"{ex}></audio>\n'

index = f"""<!doctype html>
<html lang="ar" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
    <style>
      {FONTS}
      :root{{{VARS}--font-display:'DINAr';}}
      *{{margin:0;padding:0;box-sizing:border-box}}
      html,body{{margin:0;width:1080px;height:1920px;overflow:hidden;background:#000}}
      #root{{position:relative;width:100%;height:100%;font-family:'DINAr',sans-serif}}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="1080" data-height="1920">
{hosts}{aud}    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
open(f"{P}/index.html", "w").write(index)
print("written", list(files))
