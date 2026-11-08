#!/usr/bin/env python3
"""Measure how full a motion frame is, the way reel-artdirect wants it: dense at the bottom and the sides,
calm in the top centre, never an empty frame. Needs only ffmpeg.

  framecheck.py video.mp4 [--fps 2] [--start 0] [--dur 0]
  framecheck.py frame1.png frame2.png ...

A pixel counts as "set" when it differs from the backdrop colour (the most common colour of the frame).
"""
import argparse, subprocess, sys
from collections import Counter

W, H = 192, 108
# zones as fractions of the frame: (x0, y0, x1, y1)
ZONES = {
    "bottom": (0.0, 0.62, 1.0, 1.0),     # the ground: should carry the mass
    "sides": None,                        # left + right 14% bands, under the top fifth
    "calm": (0.25, 0.05, 0.75, 0.30),    # the title zone: only text lives here
}
# calm is relative: the title zone must be clearly quieter than the mass around it (a textured backdrop raises both)
RULES = {"all": 0.30, "bottom": 0.45, "sides": 0.25, "calm_ratio": 0.65, "empty": 0.12}


def frames_from_video(path, fps, start, dur):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", path]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = W * H * 3
    return [(start + i / fps, raw[i * n:(i + 1) * n]) for i in range(len(raw) // n)]


def frame_from_image(path):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    return path, subprocess.run(cmd, capture_output=True, check=True).stdout


def measure(buf):
    # a 4x4-pixel cell is "set" when it carries detail (an edge, a shape) or a colour far from the backdrop;
    # smooth gradients and soft glows do not count, so a pretty but empty backdrop still reads as empty
    px = [tuple(buf[i:i + 3]) for i in range(0, len(buf), 3)]
    bg = Counter((r // 8, g // 8, b // 8) for r, g, b in px).most_common(1)[0][0]
    bg = tuple(c * 8 + 4 for c in bg)
    lum = [0.3 * r + 0.59 * g + 0.11 * b for r, g, b in px]
    CW, CH = W // 4, H // 4
    full = []
    for cy in range(CH):
        for cx in range(CW):
            idx = [(cy * 4 + y) * W + cx * 4 + x for y in range(4) for x in range(4)]
            ls = [lum[i] for i in idx]
            mean = [sum(px[i][c] for i in idx) / 16 for c in range(3)]
            far = max(abs(mean[c] - bg[c]) for c in range(3)) > 40
            full.append(max(ls) - min(ls) > 10 or far)

    def share(x0, y0, x1, y1):
        cells = [full[y * CW + x] for y in range(int(y0 * CH), int(y1 * CH)) for x in range(int(x0 * CW), int(x1 * CW))]
        return sum(cells) / max(1, len(cells))

    sides = (share(0, 0.2, 0.14, 1) + share(0.86, 0.2, 1, 1)) / 2
    return {"all": sum(full) / len(full), "bottom": share(*ZONES["bottom"]), "sides": sides, "calm": share(*ZONES["calm"])}


def verdict(m):
    bad = []
    if m["all"] < RULES["empty"]: bad.append("EMPTY")
    elif m["all"] < RULES["all"]: bad.append("thin")
    if m["bottom"] < RULES["bottom"]: bad.append("bare-bottom")
    if m["sides"] < RULES["sides"]: bad.append("bare-sides")
    if m["calm"] > RULES["calm_ratio"] * (m["bottom"] + m["sides"]) / 2: bad.append("busy-title-zone")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--fps", type=float, default=2)
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--dur", type=float, default=0)
    a = ap.parse_args()
    if len(a.inputs) == 1 and not a.inputs[0].lower().endswith((".png", ".jpg", ".jpeg")):
        frames = frames_from_video(a.inputs[0], a.fps, a.start, a.dur)
    else:
        frames = [frame_from_image(p) for p in a.inputs]
    print(f"{'frame':>10}  all  bottom sides calm  flags")
    flagged = 0
    for name, buf in frames:
        m = measure(buf)
        bad = verdict(m)
        flagged += bool(bad)
        label = f"{name:7.1f}s" if isinstance(name, float) else str(name)[-10:]
        print(f"{label:>10}  {m['all']:.2f} {m['bottom']:.2f}   {m['sides']:.2f}  {m['calm']:.2f}  {' '.join(bad)}")
    print(f"\n{flagged}/{len(frames)} frames flagged  (rules: {RULES})")
    sys.exit(1 if flagged > len(frames) * 0.2 else 0)


if __name__ == "__main__":
    main()
