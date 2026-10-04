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


def load_job(path):
    """Load a job JSON and fill size/fps/range from the video when present."""
    path = os.path.abspath(path)
    with open(path) as f:
        job = json.load(f)
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
            params = deep_merge(params, {"theme": themes[theme]})
        job["_tune"] = presets.get("tune", [])
        job["_output"] = presets.get("output", "alpha")
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


# ---------------------------------------------------------------- server
# Routes:
#   /r/<path>     repo files (engine, skills)
#   /f/<abspath>  any local file under $HOME or /tmp, /private, /Volumes (job assets, frames)
#   /job.json     the current job (params resolved)
#   /scene        the style's scene.html

class _Handler(http.server.SimpleHTTPRequestHandler):
    job = None
    allowed = (os.path.expanduser("~"), "/tmp", "/private", "/Volumes")

    def log_message(self, *a):
        pass

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
        p = urllib.parse.unquote(url.path)
        if p == "/job.json":
            body = json.dumps({k: v for k, v in self.job.items() if not k.startswith("_") or k in ("_tune", "_video_info", "_dir", "_output")}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif p == "/subject_rect":
            body = json.dumps(subject_rect(self.job) if self.job.get("subject") else None).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif p == "/scene":
            self._send_file(os.path.join(self.job["_style_dir"], "scene.html"))
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
            extra = getattr(self.server, "extra_routes", {})
            if p in extra:
                return self._send_file(extra[p])
            self.send_error(404)


    def do_POST(self):
        """Player 'save to job': write tuned params back into the job file."""
        if urllib.parse.urlparse(self.path).path != "/save":
            return self.send_error(404)
        params = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        with open(self.job["_path"]) as f:
            raw = json.load(f)
        raw["params"] = params
        with open(self.job["_path"], "w") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        self.job["params"] = params
        self.send_response(204)
        self.end_headers()


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    request_queue_size = 256
    allow_reuse_address = True


def serve(job, port=0, extra_routes=None):
    """Start the asset server in a background thread; returns (server, base_url)."""
    handler = type("H", (_Handler,), {"job": job})
    srv = _Server(("127.0.0.1", port), handler)
    srv.extra_routes = extra_routes or {}
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def need(tool):
    if not shutil.which(tool):
        die(f"'{tool}' not found on PATH")
