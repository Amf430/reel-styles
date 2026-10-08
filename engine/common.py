"""Shared helpers: paths, ffprobe, job loading, Chromium discovery, local asset server."""
import glob
import http.server
import json
import mimetypes
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import urllib.parse

ENGINE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ENGINE)
SKILLS = os.path.join(REPO, "skills")


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, quiet=True):
    """Run a command list; raise with stderr on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join(r.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"command failed: {' '.join(cmd[:6])} ...\n{tail}")
    if not quiet:
        print(r.stdout)
    return r.stdout


def probe(path):
    """Return {w, h, fps, duration, has_audio} for a video or image."""
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
    info = json.loads(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        die(f"no video stream in {path}")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rot = abs(int(float(sd["rotation"])))
    if rot in (90, 270):
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    dur = float(info["format"].get("duration") or v.get("duration") or 0)
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    return {"w": w, "h": h, "fps": round(fps, 3), "duration": dur, "has_audio": has_audio}


def fps_arg(fps):
    """ffmpeg-friendly frame rate (keeps 29.97/23.976 exact)."""
    known = {29.97: "30000/1001", 23.976: "24000/1001", 59.94: "60000/1001"}
    return known.get(round(fps, 3), str(fps))


def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_job(path, video=None):
    """Load a job JSON and fill size/fps/range from the video when present."""
    path = os.path.abspath(path)
    with open(path) as f:
        job = json.load(f)
    if not video and not job.get("video"):
        # A job inside a project folder takes the project's video.
        pj = os.path.join(os.path.dirname(path), "project.json")
        if os.path.exists(pj):
            with open(pj) as f:
                pv = json.load(f).get("video")
            if pv:
                video = pv if os.path.isabs(pv) else os.path.normpath(os.path.join(os.path.dirname(pj), pv))
    if video and not job.get("video"):
        job["video"] = video
    job["_path"] = path
    job["_dir"] = os.path.dirname(path)
    style = job.get("style") or die("job needs a 'style' (e.g. reel-glass)")
    sdir = os.path.join(SKILLS, style)
    if not os.path.isdir(sdir):
        die(f"unknown style '{style}' (no {sdir})")
    job["_style_dir"] = sdir

    def absp(p):
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(job["_dir"], p))

    if job.get("video"):
        job["video"] = absp(job["video"])
        info = probe(job["video"])
        job.setdefault("size", [info["w"], info["h"]])
        job.setdefault("fps", info["fps"])
        job.setdefault("start", 0)
        job.setdefault("end", info["duration"])
        job["_video_info"] = info
    job.setdefault("size", [1920, 1080])
    job.setdefault("fps", 30)
    job.setdefault("start", 0)
    job.setdefault("end", job["start"] + 5)

    # Theme + defaults from the style's presets.json, then the job's params on top.
    presets_path = os.path.join(sdir, "presets.json")
    params = {}
    if os.path.exists(presets_path):
        with open(presets_path) as f:
            presets = json.load(f)
        params = presets.get("defaults", {})
        theme = job.get("theme") or presets.get("default_theme")
        if theme:
            themes = presets.get("themes", {})
            if theme not in themes:
                die(f"theme '{theme}' not in {style}: {', '.join(themes)}")
            th = dict(themes[theme])
            # A theme may set top-level defaults too ("params"); the job's own params still win.
            params = deep_merge(params, th.pop("params", {}))
            params = deep_merge(params, {"theme": th})
        job["_tune"] = presets.get("tune", [])
        job["_prepare"] = presets.get("prepare")
        job["_output"] = presets.get("output", "alpha")
    job["_base_params"] = params
    job["params"] = deep_merge(params, job.get("params", {}))
    job.setdefault("out", os.path.join(job["_dir"], "out", style))
    if job.get("_prepare"):
        # Style-specific one-time data (e.g. map tiles), cached; see the module's prepare().
        import importlib
        importlib.import_module(job["_prepare"]).prepare(job)
    job["out"] = absp(job["out"])
    return job


def subject_rect(job, meta=None):
    """Where the keyed subject goes (x,y,w,h of the output frame, the whole keyed frame scaled into it).

    job.subject.rect wins; else the scene's own placement (studio3d); else auto-fit: the person is
    `height` of the frame tall, feet on `floor` (+ a little in front of the cove), centred at `x`.
    """
    meta = meta or {}
    sub = job["subject"]
    if sub.get("rect"):
        return sub["rect"]
    if meta.get("subject_rect"):
        return meta["subject_rect"]
    src = sub["layer"] if os.path.isabs(sub["layer"]) else os.path.join(job["_dir"], sub["layer"])
    with open(os.path.splitext(src)[0] + ".json") as f:
        st = json.load(f)
    W, H = job["size"]
    sw, sh = st["size"]
    k = sub.get("height", 0.72) / st["bbox"][3]            # keyed-frame height as a fraction of output height
    rh = k
    rw = k * (sw / sh) / (W / H)
    floor = sub.get("feet", job["params"].get("floor", 0.85) + 0.035)
    ry = floor - st["feet_y"] * rh
    rx = sub.get("x", 0.5) - st["feet_x"] * rw
    return [round(v, 4) for v in (rx, ry, rw, rh)]


def viewport(job):
    """CSS viewport + device scale. 4K renders at 2x of a ~1080p viewport."""
    w, h = job["size"]
    scale = job.get("scale") or (2 if max(w, h) > 2200 else 1)
    return int(round(w / scale)), int(round(h / scale)), scale


def timecode(t):
    m, s = divmod(t, 60)
    return f"{int(m)}m{s:05.2f}".replace(".", "s")


def chromium_path():
    """Find a Chromium Playwright can drive, tolerating package/browser version skew."""
    env = os.environ.get("REEL_CHROMIUM")
    if env and os.path.exists(env):
        return env
    roots = [os.path.expanduser("~/Library/Caches/ms-playwright"), os.path.expanduser("~/.cache/ms-playwright"), "/opt/pw-browsers"]
    pats = ["chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell",
            "chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
            "chromium-*/chrome-linux*/chrome"]
    for root in roots:
        for pat in pats:
            hits = sorted(glob.glob(os.path.join(root, pat)))
            if hits:
                return hits[-1]
    return None  # let Playwright use its own default


def launch_args():
    args = ["--disable-web-security", "--autoplay-policy=no-user-gesture-required", "--hide-scrollbars"]
    if sys.platform == "darwin":
        args.append("--use-angle=metal")  # real GPU for WebGL scenes
    return args


def deep_diff(cur, base):
    """What `cur` changes relative to `base` (saved jobs keep only the user's edits)."""
    out = {}
    for k, v in cur.items():
        b = base.get(k) if isinstance(base, dict) else None
        if isinstance(v, dict) and isinstance(b, dict):
            d = deep_diff(v, b)
            if d:
                out[k] = d
        elif v != b:
            out[k] = v
    return out


# ---------------------------------------------------------------- projects
# A project is one video and every job on it (reel_work/project.json):
#   { "video": "../clip.mp4", "jobs": ["glass.json", "neon.json"] }
# A single job file works as a one-job project.

def load_project(path):
    path = os.path.abspath(path)
    with open(path) as f:
        raw = json.load(f)
    d = os.path.dirname(path)
    if "jobs" not in raw:
        job = load_job(path)
        return {"_path": path, "_dir": d, "video": job.get("video"), "jobs": [job]}
    video = raw.get("video")
    if video and not os.path.isabs(video):
        video = os.path.normpath(os.path.join(d, video))
    import edit
    clips = edit.clips_of(raw, d)
    source = video
    if clips:
        # Montage: the motion layers sit on the cut sequence, not on the raw footage.
        video = edit.conform(clips, os.path.join(d, ".reel_cache"))
    jobs = [load_job(j if os.path.isabs(j) else os.path.join(d, j), video) for j in raw["jobs"]]
    return {"_path": path, "_dir": d, "video": video, "jobs": jobs, "clips": clips, "source": source}


def project_info(project):
    """What the editor needs to lay out the whole video."""
    v = project.get("video")
    info = probe(v) if v else {"w": 1920, "h": 1080, "fps": 30, "duration": max(j["end"] for j in project["jobs"]), "has_audio": False}
    clips = project.get("clips") or ([{"src": project.get("source") or v, "in": 0.0, "out": info["duration"]}] if v else [])
    srcs = {}
    for c in clips:
        if c["src"] not in srcs:
            si = probe(c["src"])
            srcs[c["src"]] = {"duration": si["duration"], "has_audio": si["has_audio"], "w": si["w"], "h": si["h"]}
    return {
        "video": v, "size": [info["w"], info["h"]], "fps": info["fps"], "duration": info["duration"], "has_audio": info["has_audio"],
        "clips": clips, "sources": srcs, "edited": bool(project.get("clips")),
        "mtime": os.path.getmtime(project["_path"]) if os.path.exists(project.get("_path", "")) else 0, "can_edit": "jobs" in project and project.get("_path", "").endswith(".json"),
        "jobs": [{"i": i, "style": j["style"], "name": j.get("name") or os.path.splitext(os.path.basename(j["_path"]))[0],
                  "start": j["start"], "end": j["end"], "output": j.get("_output", "alpha"), "subject": j.get("subject"),
                  "behind": j.get("behind"), "mtime": os.path.getmtime(j["_path"]),
                  "file": j["_path"]} for i, j in enumerate(project["jobs"])],
    }


def _cache_dir(project):
    d = os.path.join(project["_dir"], ".reel_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _key(path):
    import hashlib
    return hashlib.sha1(path.encode()).hexdigest()[:10]


def audio_peaks(project, per_sec=50, src=None):
    """Peak envelope of the soundtrack (0..1, per_sec values per second) for the timeline."""
    v = src or project.get("video")
    out = os.path.join(_cache_dir(project), f"peaks_{per_sec}_{_key(v)}.json")
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(v):
        return out
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", v, "-vn", "-ac", "1", "-ar", str(per_sec * 80), "-f", "s16le", "-"], capture_output=True)
    import array
    a = array.array("h", r.stdout)
    peaks = [max(1, max((abs(x) for x in a[i:i + 80]), default=0)) / 32768 for i in range(0, len(a), 80)]
    top = max(peaks or [1])
    with open(out, "w") as f:
        json.dump({"per_sec": per_sec, "peaks": [round(p / top, 3) for p in peaks]}, f)
    return out


def thumb_strip(project, n=48, h=72, src=None):
    v = src or project.get("video")
    dur = probe(v)["duration"]
    n = max(4, min(400, int(round(dur * 2)))) if src else n   # per source: 2 thumbs a second
    out = os.path.join(_cache_dir(project), f"thumbs_{n}_{_key(v)}.jpg")
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(v):
        return out
    run(["ffmpeg", "-y", "-v", "error", "-i", v, "-vf", f"fps={n / max(dur, 0.1):.5f},scale=-2:{h},tile={n}x1", "-frames:v", "1", "-q:v", "4", out])
    return out


def scene_cuts(project, threshold=0.32, src=None):
    v = src or project.get("video")
    out = os.path.join(_cache_dir(project), f"cuts_{_key(v)}.json")
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(v):
        return out
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", v, "-an", "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    import re
    cuts = [round(float(m), 3) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]
    with open(out, "w") as f:
        json.dump(cuts, f)
    return out


# ---------------------------------------------------------------- server
# Routes:
#   /player            the editor (engine/web/player.html)
#   /project.json      video + jobs overview        /job.json?j=N   job N (params resolved)
#   /scene?j=N         style scene of job N         /subject_rect?j=N
#   /peaks.json /thumbs.jpg /cuts.json              timeline helpers (cached in reel_work/.reel_cache)
#   POST /save?j=N     {params, start, end} → job file (only the user's edits are written)
#   /r/<path>          repo files     /f/<abspath>  local files under $HOME, /tmp, /private, /Volumes

class _Handler(http.server.SimpleHTTPRequestHandler):
    project = None
    allowed = (os.path.expanduser("~"), "/tmp", "/private", "/Volumes")

    def log_message(self, *a):
        pass

    def _job(self, q):
        i = int((q.get("j") or ["0"])[0])
        return self.project["jobs"][i]

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self.send_error(404, path)
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith((".js", ".mjs")):
            ctype = "text/javascript"
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            a, b = rng[6:].split("-")
            start = int(a) if a else 0
            end = int(b) if b else size - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        p, q = urllib.parse.unquote(url.path), urllib.parse.parse_qs(url.query)
        src = (q.get("src") or [None])[0]
        if src and not os.path.abspath(src).startswith(self.allowed):
            return self.send_error(403)
        if p == "/job.json":
            if q.get("fresh"):
                self._reload_job(q)
            job = self._job(q)
            self._json({k: v for k, v in job.items() if not k.startswith("_") or k in ("_tune", "_video_info", "_dir", "_output")})
        elif p == "/project.json":
            # the editor (re)opens: read the project fresh, so edits saved earlier or made from the chat show up
            try:
                if self.project.get("_path", "").endswith(".json") and os.path.exists(self.project["_path"]):
                    fresh = load_project(self.project["_path"])
                    self.project.clear()
                    self.project.update(fresh)
                self._json(project_info(self.project))
            except (Exception, SystemExit) as e:
                self.send_error(500, f"project failed to load: {e}"[:300])
        elif p == "/subject_rect":
            job = self._job(q)
            self._json(subject_rect(job) if job.get("subject") else None)
        elif p == "/scene":
            self._send_file(os.path.join(self._job(q)["_style_dir"], "scene.html"))
        elif p == "/player":
            self._send_file(os.path.join(ENGINE, "web", "player.html"))
        elif p == "/peaks.json":
            self._send_file(audio_peaks(self.project, src=src))
        elif p == "/thumbs.jpg":
            self._send_file(thumb_strip(self.project, src=src))
        elif p == "/cuts.json":
            self._send_file(scene_cuts(self.project, src=src))
        elif p == "/probe.json":
            self._json(probe(src))
        elif p == "/media.json":
            import edit
            self._json(edit.media_files(self.project["_dir"]))
        elif p == "/mtimes.json":
            files = [self.project["_path"]] + [j["_path"] for j in self.project["jobs"]]
            self._json([os.path.getmtime(f) if os.path.exists(f) else 0 for f in files])
        elif p == "/render_status.json":
            self._json(render_status(self.project))
        elif p.startswith("/r/"):
            full = os.path.normpath(os.path.join(REPO, p[3:]))
            if not full.startswith(REPO):
                return self.send_error(403)
            self._send_file(full)
        elif p.startswith("/f/"):
            full = os.path.normpath("/" + p[3:])
            if not full.startswith(self.allowed):
                return self.send_error(403)
            self._send_file(full)
        else:
            self.send_error(404)

    def _reload_job(self, q):
        i = int((q.get("j") or ["0"])[0])
        old = self.project["jobs"][i]
        self.project["jobs"][i] = load_job(old["_path"], self.project.get("video"))

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/save_edit":
            return self._save_edit()
        if url.path == "/render":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            ok = start_render(self.project, body.get("job"), body.get("mblur", 1), body.get("scale"))
            return self._json({"ok": ok})
        if url.path != "/save":
            return self.send_error(404)
        job = self._job(urllib.parse.parse_qs(url.query))
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if body.get("mtime") and os.path.getmtime(job["_path"]) > body["mtime"] + 1e-3:
            return self._conflict()     # changed on disk since this editor loaded it: never overwrite blindly
        with open(job["_path"]) as f:
            raw = json.load(f)
        raw["params"] = deep_diff(body["params"], job["_base_params"])
        for k in ("start", "end"):
            if body.get(k) is not None:
                raw[k] = round(float(body[k]), 3)
                job[k] = raw[k]
        with open(job["_path"], "w") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        job["params"] = body["params"]
        self._json({"mtime": os.path.getmtime(job["_path"])})

    def _conflict(self):
        body = json.dumps({"error": "changed"}).encode()
        self.send_response(409)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


    def _save_edit(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        path, d = self.project["_path"], self.project["_dir"]
        if body.get("mtime") and os.path.getmtime(path) > body["mtime"] + 1e-3:
            return self._conflict()
        with open(path) as f:
            raw = json.load(f)
        if "jobs" not in raw:
            return self.send_error(400, "montage needs a project.json")
        rel = lambda s: os.path.relpath(s, d) if s.startswith(os.path.dirname(d)) else s
        clips = [{"src": rel(c["src"]), "in": round(float(c["in"]), 3), "out": round(float(c["out"]), 3)} for c in body.get("clips", [])]
        source = self.project.get("source")
        if len(clips) == 1 and source and os.path.normpath(os.path.join(d, clips[0]["src"])) == source and clips[0]["in"] == 0 \
                and abs(clips[0]["out"] - probe(source)["duration"]) < 0.05:
            raw.pop("edit", None)          # the untouched original: no edit to keep
        else:
            raw["edit"] = {"clips": clips}
        with open(path, "w") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        self._json({"mtime": os.path.getmtime(path)})


# ---------------------------------------------------------------- render from the editor
_RENDER = {"proc": None, "log": None, "jobs": None, "started": 0}


def start_render(project, job_name=None, mblur=1, scale=None):
    if _RENDER["proc"] and _RENDER["proc"].poll() is None:
        return False
    import time
    log = os.path.join(_cache_dir(project), "render.log")
    cmd = [sys.executable, os.path.join(ENGINE, "render.py"), project["_path"], "--mblur", str(int(mblur or 1))]
    if job_name:
        cmd += ["--job", job_name]
    if scale:
        cmd += ["--scale", str(scale)]
    _RENDER.update(proc=subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT, cwd=project["_dir"]),
                   log=log, jobs=[j for j in project["jobs"] if not job_name or job_name in (j.get("name"), os.path.splitext(os.path.basename(j["_path"]))[0])],
                   started=time.time(), mblur=int(mblur or 1))
    return True


def render_status(project):
    import glob
    import time
    p = _RENDER["proc"]
    if not p:
        return {"state": "idle"}
    done = total = 0
    for j in _RENDER["jobs"] or []:
        n = int(round((j["end"] - j["start"]) * j["fps"])) * _RENDER["mblur"]
        total += n
        have = len(glob.glob(os.path.join(j["out"], "_frames", "f_*.png")))
        layer = glob.glob(os.path.join(j["out"], f"{j.get('name') or j['style']}_*.mov"))
        recent = [x for x in layer if os.path.getmtime(x) >= _RENDER["started"]]
        done += n if recent else min(have, n)
    tail = ""
    try:
        with open(_RENDER["log"]) as f:
            tail = f.read()[-1500:]
    except OSError:
        pass
    state = "running" if p.poll() is None else ("done" if p.returncode == 0 else "failed")
    return {"state": state, "progress": round(done / total, 3) if total else 0, "log": tail, "elapsed": round(time.time() - _RENDER["started"], 1)}


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    request_queue_size = 256
    allow_reuse_address = True


def serve(project, port=0):
    """Start the asset server in a background thread; returns (server, base_url).
    Accepts a project (load_project) or a single job (load_job)."""
    if "jobs" not in project:
        project = {"_path": project["_path"], "_dir": project["_dir"], "video": project.get("video"), "jobs": [project]}
    handler = type("H", (_Handler,), {"project": project})
    srv = _Server(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def need(tool):
    if not shutil.which(tool):
        die(f"'{tool}' not found on PATH")
