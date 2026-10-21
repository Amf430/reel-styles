"""Motion gallery: render a short preview of every move in catalog.json and build one browsable page.

  python3 gallery/build.py                 render what changed + rebuild the page
  python3 gallery/build.py --only glass-   only ids starting with this
  python3 gallery/build.py --force         re-render everything
Output (outside the repo): ~/.reel-styles/gallery/site/index.html + previews/
"""
import argparse, hashlib, json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORK = os.path.expanduser("~/.reel-styles/gallery")
SITE = os.path.join(WORK, "site")
BG = os.path.join(WORK, "bg.mp4")
CHROMA = os.path.join(WORK, "chroma.mp4")
CUT = os.path.join(WORK, "cut.mp4")      # bg until 1.7s, then a second shot: for transitions
CUT_AT = 1.7
DUR = 3.5
WORDS = [("هذي", 0.25, 0.5), ("أفضل", 0.5, 0.95), ("شقة", 0.95, 1.3), ("شفتها", 1.3, 1.75),
         ("بسعر", 1.85, 2.2), ("850", 2.2, 2.7), ("ألف", 2.7, 3.2)]


def sub(v, m):
    if isinstance(v, str):
        return m.get(v, v)
    if isinstance(v, list):
        return [sub(x, m) for x in v]
    if isinstance(v, dict):
        return {k: sub(x, m) for k, x in v.items()}
    return v


def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def shrink(src, dst, start=0, dur=None, poster=2.0):
    """Small looping web preview + poster frame."""
    t = ["-t", str(dur)] if dur else []
    ff("-ss", str(start), "-i", src, *t, "-vf", "scale=540:-2,fps=30", "-c:v", "libx264", "-crf", "30", "-preset", "slow",
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", dst)
    ff("-ss", str(poster), "-i", dst, "-frames:v", "1", "-q:v", "5", dst[:-4] + ".jpg")


def job_for(e, d):
    m = {"@bg": BG + ".png", "@words": os.path.join(d, "words.json")}
    if "example" in e:
        j = json.load(open(os.path.join(REPO, "skills", e["example"])))
        j.update(name=e["id"], video=CHROMA if e.get("keyed") else BG)
        t0 = j.get("start", 0)
        if e.get("keyed") and not os.path.exists(os.path.join(d, j["subject"]["layer"])):
            subprocess.run([sys.executable, os.path.join(REPO, "engine", "key.py"), CHROMA, "--out", os.path.join(d, j["subject"]["layer"]),
                            "--start", str(t0), "--end", str(j.get("end", t0 + 5))], check=True, capture_output=True)
        return j, (t0, t0 + 5)
    j = {"style": e["skill"], "name": e["id"], "video": CUT if e.get("cut") else BG, "start": 0, "end": DUR, "params": sub(e.get("params", {}), m)}
    if e.get("theme"):
        j["theme"] = e["theme"]
    return j, None


def render(e, force):
    pv = os.path.join(SITE, "previews", e["id"] + ".mp4")
    d = os.path.join(WORK, "jobs", e["id"])
    if "clip" in e:
        c = e["clip"]
        key = json.dumps(c, sort_keys=True)
    else:
        os.makedirs(d, exist_ok=True)
        json.dump({"words": [{"w": w, "s": s, "e": t, "g": 0} for w, s, t in WORDS],
                   "segments": [{"text": " ".join(w for w, _, _ in WORDS), "s": 0.25, "e": 3.2}]},
                  open(os.path.join(d, "words.json"), "w"), ensure_ascii=False)
        job, rng = job_for(e, d)
        key = json.dumps(job, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha1(key.encode()).hexdigest()[:12]
    stamp = pv + ".hash"
    if not force and os.path.exists(pv) and os.path.exists(stamp) and open(stamp).read() == h:
        return e["id"], "cached"
    try:
        if "clip" in e:
            shrink(os.path.expanduser(c["src"]), pv, c.get("from", 0), c.get("dur", 6), e.get("poster", 2.0))
        else:
            jf = os.path.join(d, "job.json")
            json.dump(job, open(jf, "w"), ensure_ascii=False, indent=1)
            shutil.rmtree(os.path.join(d, "out"), ignore_errors=True)
            cmd = [sys.executable, os.path.join(REPO, "engine", "render.py"), jf, "--workers", "4"]
            if rng:
                cmd += ["--range", f"{rng[0]},{rng[1]}"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            open(os.path.join(d, "render.log"), "w").write(r.stdout + r.stderr)
            if r.returncode:
                return e["id"], "FAILED: " + (r.stderr.strip().splitlines() or ["?"])[-1][:200]
            src = next((os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(d, "out")) for f in fs if f.endswith("_preview.mp4")), None)
            if not src:
                return e["id"], "FAILED: no preview"
            shrink(src, pv, poster=e.get("poster", 2.0))
        open(stamp, "w").write(h)
        return e["id"], "ok"
    except Exception as ex:
        return e["id"], f"FAILED: {ex}"[:240]


def page(cat):
    have = [dict(e, has=os.path.exists(os.path.join(SITE, "previews", e["id"] + ".mp4"))) for e in cat]
    for e in have:
        e.pop("params", None)
        pre = os.path.join(REPO, "skills", e["skill"], "presets.json")
        if os.path.exists(pre):
            e["themes"] = list(json.load(open(pre, encoding="utf-8")).get("themes", {}))
    html = open(os.path.join(HERE, "page.html"), encoding="utf-8").read()
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(
        html.replace("/*CATALOG*/[]", json.dumps(have, ensure_ascii=False)))
    shutil.copy(os.path.join(HERE, "catalog.json"), os.path.join(SITE, "catalog.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--page", action="store_true", help="rebuild the page only")
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    cat = json.load(open(os.path.join(HERE, "catalog.json"), encoding="utf-8"))
    os.makedirs(os.path.join(SITE, "previews"), exist_ok=True)
    if not a.page:
        alt = os.path.join(WORK, "bg_alt.mp4")
        for f, extra in ((BG, []), (CHROMA, ["--chroma"]), (alt, ["--alt"])):
            if not os.path.exists(f):
                subprocess.run([os.path.expanduser("~/.reel-styles/venv/bin/python"), os.path.join(HERE, "make_bg.py"), f, *extra], check=True)
        if not os.path.exists(CUT):
            ff("-i", BG, "-i", alt, "-filter_complex", f"[0:v]trim=0:{CUT_AT},setpts=PTS-STARTPTS[a];[1:v]trim={CUT_AT}:40,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1[v]",
               "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", CUT)
        todo = [e for e in cat if e["id"].startswith(a.only)]
        with ThreadPoolExecutor(a.jobs) as pool:
            for i, (k, s) in enumerate(pool.map(lambda e: render(e, a.force), todo), 1):
                print(f"[{i}/{len(todo)}] {k}: {s}", flush=True)
    page(cat)
    print("page:", os.path.join(SITE, "index.html"))


if __name__ == "__main__":
    main()
