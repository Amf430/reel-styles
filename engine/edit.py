"""Montage: a project can cut its footage before the motion layers go on.

project.json:
  { "video": "../clip.mp4",
    "edit": { "clips": [ { "src": "../clip.mp4", "in": 0.0, "out": 3.2 },
                         { "src": "../b-roll.mp4", "in": 5.0, "out": 9.5 } ] },
    "jobs": [...] }

The clips play one after another (the sequence). Every job's times are on the sequence, so the
motion layers line up with the cut. conform() renders the sequence once to
reel_work/.reel_cache/edit_<hash>.mp4 (cached by content); render.py and the editor's helpers use it
as the project video. Source files are never modified.
"""
import hashlib
import json
import os
import threading

import common

_LOCK = threading.Lock()
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".mxf")


def resolve(project_dir, src):
    return src if os.path.isabs(src) else os.path.normpath(os.path.join(project_dir, src))


def clips_of(raw, project_dir):
    """The edit's clips with absolute sources, or None when the project has no edit."""
    ed = raw.get("edit") or {}
    clips = [c for c in ed.get("clips", []) if c.get("out", 0) > c.get("in", 0)]
    if not clips:
        return None
    return [{"src": resolve(project_dir, c["src"]), "in": float(c["in"]), "out": float(c["out"])} for c in clips]


def conform(clips, cache_dir, size=None, fps=None):
    """One file for the whole sequence (H.264 CRF 14, AAC). Returns its path."""
    first = common.probe(clips[0]["src"])
    w, h = size or (first["w"], first["h"])
    fps = fps or first["fps"]
    key = json.dumps([[c["src"], os.path.getmtime(c["src"]), round(c["in"], 3), round(c["out"], 3)] for c in clips] + [w, h, fps])
    out = os.path.join(cache_dir, f"edit_{hashlib.sha1(key.encode()).hexdigest()[:12]}.mp4")
    with _LOCK:   # the editor can ask twice at once; build each cut a single time
        if os.path.exists(out):
            return out
        return _build(clips, out, w, h, fps)


def _build(clips, out, w, h, fps):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    srcs = sorted({c["src"] for c in clips})
    idx = {s: i for i, s in enumerate(srcs)}
    has_a = {s: common.probe(s)["has_audio"] for s in srcs}
    inputs = []
    for s in srcs:
        inputs += ["-i", s]
    parts, cat = [], ""
    for k, c in enumerate(clips):
        i, a, b = idx[c["src"]], c["in"], c["out"]
        parts.append(f"[{i}:v]trim={a:.4f}:{b:.4f},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,"
                     f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={common.fps_arg(fps)},format=yuv420p[v{k}]")
        if has_a[c["src"]]:
            parts.append(f"[{i}:a]atrim={a:.4f}:{b:.4f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{k}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{b - a:.4f}[a{k}]")
        cat += f"[v{k}][a{k}]"
    parts.append(f"{cat}concat=n={len(clips)}:v=1:a=1[v][a]")
    tmp = f"{out}.{os.getpid()}.part.mp4"
    print(f"montage: building the cut ({len(clips)} clips) …", flush=True)
    common.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", tmp])
    os.replace(tmp, out)
    return out


def media_files(project_dir):
    """Video files next to the project (its folder and the folder above), for the editor's «add clip»."""
    seen, out = set(), []
    for d in (os.path.dirname(project_dir), project_dir):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            p = os.path.join(d, n)
            if n.startswith(".") or not n.lower().endswith(VIDEO_EXT) or p in seen or not os.path.isfile(p):
                continue
            seen.add(p)
            out.append(p)
    return out
