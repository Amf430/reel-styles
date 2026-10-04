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
        job["_output"] = presets.get("output", "alpha")
    job["_base_params"] = params
    job["params"] = deep_merge(params, job.get("params", {}))
    job.setdefault("out", os.path.join(job["_dir"], "out", style))
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
    jobs = [load_job(j if os.path.isabs(j) else os.path.join(d, j), video) for j in raw["jobs"]]
    return {"_path": path, "_dir": d, "video": video, "jobs": jobs}


def project_info(project):
    """What the editor needs to lay out the whole video."""
    v = project.get("video")
    info = probe(v) if v else {"w": 1920, "h": 1080, "fps": 30, "duration": max(j["end"] for j in project["jobs"]), "has_audio": False}
    return {
        "video": v, "size": [info["w"], info["h"]], "fps": info["fps"], "duration": info["duration"], "has_audio": info["has_audio"],
        "jobs": [{"i": i, "style": j["style"], "name": j.get("name") or os.path.splitext(os.path.basename(j["_path"]))[0],
                  "start": j["start"], "end": j["end"], "output": j.get("_output", "alpha"), "subject": j.get("subject"),
                  "file": j["_path"]} for i, j in enumerate(project["jobs"])],
    }


def _cache_dir(project):
    d = os.path.join(project["_dir"], ".reel_cache")
    os.makedirs(d, exist_ok=True)
    return d


def audio_peaks(project, per_sec=50):
    """Peak envelope of the soundtrack (0..1, per_sec values per second) for the timeline."""
    out = os.path.join(_cache_dir(project), f"peaks_{per_sec}.json")
    v = project.get("video")
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


def thumb_strip(project, n=48, h=72):
    out = os.path.join(_cache_dir(project), f"thumbs_{n}.jpg")
    v = project.get("video")
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(v):
        return out
    dur = probe(v)["duration"]
    run(["ffmpeg", "-y", "-v", "error", "-i", v, "-vf", f"fps={n / max(dur, 0.1):.5f},scale=-2:{h},tile={n}x1", "-frames:v", "1", "-q:v", "4", out])
    return out


def scene_cuts(project, threshold=0.32):
    out = os.path.join(_cache_dir(project), "cuts.json")
    v = project.get("video")
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
        if p == "/job.json":
            job = self._job(q)
            self._json({k: v for k, v in job.items() if not k.startswith("_") or k in ("_tune", "_video_info", "_dir", "_output")})
        elif p == "/project.json":
            self._json(project_info(self.project))
        elif p == "/subject_rect":
            job = self._job(q)
            self._json(subject_rect(job) if job.get("subject") else None)
        elif p == "/scene":
            self._send_file(os.path.join(self._job(q)["_style_dir"], "scene.html"))
        elif p == "/player":
            self._send_file(os.path.join(ENGINE, "web", "player.html"))
        elif p == "/peaks.json":
            self._send_file(audio_peaks(self.project))
        elif p == "/thumbs.jpg":
            self._send_file(thumb_strip(self.project))
        elif p == "/cuts.json":
            self._send_file(scene_cuts(self.project))
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

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != "/save":
            return self.send_error(404)
        job = self._job(urllib.parse.parse_qs(url.query))
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
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
        self.send_response(204)
        self.end_headers()


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
