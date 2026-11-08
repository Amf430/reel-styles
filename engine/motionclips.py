#!/usr/bin/env python3
"""Video clips for reel-motion, turned into cached JPEG frames (run automatically before render/editor).

  motionclips.py job.json          extract every `clip` beat's frames and point the beat at them

Headless Chromium can't be trusted to decode H.264/HEVC frame-accurately, so a clip beat shows an
image sequence instead: one frame per output frame, cached by (file, mtime, start, size, fps).
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import mlenv  # noqa: E402

CACHE = os.path.join(mlenv.HOME, "clips")


def prepare(job):
    fps = job["fps"]
    W, H = job["size"]
    for b in job["params"].get("beats", []) or []:
        if b.get("type") != "clip" or not b.get("src"):
            continue
        src = b["src"] if os.path.isabs(b["src"]) else os.path.normpath(os.path.join(job["_dir"], b["src"]))
        if not os.path.exists(src):
            common.die(f"clip not found: {src}")
        t0, t1 = b.get("in", job["start"]), b.get("out", job["end"])
        dur = max(0.1, (t1 - t0) * b.get("speed", 1)) + 0.5
        ss = float(b.get("from", 0))
        # Frames at the output size's long side keep 4K sharp without bloating 1080p jobs.
        long_side = max(W, H)
        key = hashlib.sha1(json.dumps([src, os.path.getmtime(src), ss, dur, fps, long_side]).encode()).hexdigest()[:16]
        d = os.path.join(CACHE, key)
        if not os.path.exists(os.path.join(d, "done")):
            os.makedirs(d, exist_ok=True)
            common.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss:.3f}", "-t", f"{dur:.3f}", "-i", src,
                        "-vf", f"fps={common.fps_arg(fps)},scale='if(gt(iw,ih),{long_side},-2)':'if(gt(iw,ih),-2,{long_side})'",
                        "-q:v", "3", os.path.join(d, "%05d.jpg")])
            open(os.path.join(d, "done"), "w").close()
        n = len([f for f in os.listdir(d) if f.endswith(".jpg")])
        b["_clip"] = {"dir": d, "n": n, "fps": fps}


if __name__ == "__main__":
    prepare(common.load_job(sys.argv[1]))
    print("ok")
