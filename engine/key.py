#!/usr/bin/env python3
"""Cut the presenter out of the footage → ProRes 4444 with alpha.

  key.py VIDEO --out subject.mov                       chroma key, key colour sampled from the corners
  key.py VIDEO --out s.mov --color "#2fb34a"           chroma key on a given colour
  key.py VIDEO --out s.mov --mode plate --plate empty.png   static camera + a clean frame of the empty set
  options: --start/--end (seconds), --similarity, --blend, --despill auto|green|blue|none,
           (difference key: whites and greys stay solid)
           --matte x,y,w,h (0..1, keep only this box: hides stands/lights at the edges),
           --choke N (shrink alpha by N px), --soften S (alpha blur sigma)

Writes next to --out: <name>.mov, <name>_still.png (alpha), <name>.json (bbox/feet), <name>_qc.jpg.
Only works when the background is separable (green/blue screen, or a plain set with a locked camera).
"""
import argparse
import json
import os
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def raw_frame(path, t, w, h, pix="rgb24", vf_extra=""):
    vf = f"scale={w}:{h}:flags=area" + (("," + vf_extra) if vf_extra else "")
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", vf,
                        "-f", "rawvideo", "-pix_fmt", pix, "-"], capture_output=True)
    return r.stdout


def sample_key_color(video, t):
    """Median colour of patches inset from the edges (screen area, away from vignetted corners)."""
    W, H = 64, 36
    buf = raw_frame(video, t, W, H)
    px = []
    for (cx, cy) in [(0.06, 0.12), (0.94, 0.12), (0.06, 0.45), (0.94, 0.45), (0.5, 0.05), (0.25, 0.08), (0.75, 0.08)]:
        x0, y0 = int(cx * (W - 4)), int(cy * (H - 3))
        for y in range(y0, y0 + 3):
            for x in range(x0, x0 + 4):
                i = (y * W + x) * 3
                px.append(buf[i:i + 3])
    # Keep the most saturated half (drops patches that landed on the subject or a stand).
    px.sort(key=lambda p: max(p) - min(p), reverse=True)
    px = px[: max(1, len(px) // 2)]
    r, g, b = (int(statistics.median(p[c] for p in px)) for c in range(3))
    return r, g, b


def alpha_stats(png):
    """bbox + feet line of a keyed still, as fractions of the frame."""
    W, H = 270, 480
    info = common.probe(png)
    H = max(2, round(W * info["h"] / info["w"]))
    buf = subprocess.run(["ffmpeg", "-v", "error", "-i", png, "-vf", f"scale={W}:{H},format=rgba,alphaextract", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    rows = [y for y in range(H) if max(buf[y * W:(y + 1) * W]) > 128]
    cols = [x for x in range(W) if max(buf[y * W + x] for y in range(0, H, 2)) > 128]
    if not rows or not cols:
        return None
    feet = rows[-1] / (H - 1)
    # Feet x: centre of the opaque pixels on the lowest ~3% rows.
    low = [x for y in rows[-max(1, H // 33):] for x in range(W) if buf[y * W + x] > 128]
    return {"bbox": [cols[0] / W, rows[0] / H, (cols[-1] - cols[0] + 1) / W, (rows[-1] - rows[0] + 1) / H],
            "feet_y": round(feet, 4), "feet_x": round(sum(low) / len(low) / W, 4) if low else 0.5,
            "touches_bottom": rows[-1] >= H - 2}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["chroma", "plate"], default="chroma")
    ap.add_argument("--color", default="auto")
    ap.add_argument("--similarity", type=float, default=0.0, help="raise (0.05–0.2) if green remains; lower if edges eat in")
    ap.add_argument("--blend", type=float, default=0.05, help="edge softness")
    ap.add_argument("--despill", default="auto")
    ap.add_argument("--plate")
    ap.add_argument("--threshold", type=float, default=0.08, help="plate mode sensitivity")
    ap.add_argument("--matte", help="x,y,w,h in 0..1")
    ap.add_argument("--choke", type=int, default=1)
    ap.add_argument("--soften", type=float, default=0.8)
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    a = ap.parse_args()

    common.need("ffmpeg")
    info = common.probe(a.video)
    W, H, fps = info["w"], info["h"], info["fps"]
    end = a.end if a.end is not None else info["duration"]
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stem = os.path.splitext(out)[0]
    mid = (a.start + end) / 2

    chain = []
    inputs = ["-ss", f"{a.start:.4f}", "-t", f"{end - a.start:.4f}", "-i", a.video]
    if a.mode == "chroma":
        if a.color == "auto":
            r, g, b = sample_key_color(a.video, mid)
            print(f"key colour sampled from corners: #{r:02x}{g:02x}{b:02x}")
        else:
            c = a.color.lstrip("#")
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        spill = a.despill
        screen = "green" if g >= b else "blue"
        if spill == "auto":
            spill = screen
        # Difference key: "screen-ness" = key channel minus the larger of the other two.
        # Whites/greys/skin score ~0 → stay opaque (chromakey's UV distance partly keys white).
        k, o1, o2 = ("g", "r", "b") if screen == "green" else ("b", "r", "g")
        kc = {"r": r, "g": g, "b": b}
        strength = max(8, kc[k] - max(kc[o1], kc[o2]))
        lo = strength * (0.18 + a.similarity)          # below → fully opaque
        hi = strength * (0.18 + a.similarity + 0.25 + a.blend * 2)  # above → fully transparent
        diff = f"({k}(X,Y)-max({o1}(X,Y),{o2}(X,Y)))"
        alpha = f"255*clip(1-({diff}-{lo:.1f})/{hi - lo:.1f},0,1)"
        mix = 0.0 if spill == "none" else 0.85
        # Despill: pull the key channel down toward the other two by `mix` of the excess.
        kexp = f"{k}(X,Y)-{mix}*max(0,{diff})"
        ch = {c: f"{c}(X,Y)" for c in "rgb"}
        ch[k] = kexp
        chain.append(f"[0:v]format=gbrap,geq=r='{ch['r']}':g='{ch['g']}':b='{ch['b']}':a='{alpha}'[k]")
        last = "k"
    else:
        if not a.plate:
            common.die("--mode plate needs --plate (a clean frame of the empty set)")
        inputs += ["-loop", "1", "-t", f"{1 / fps:.5f}", "-i", a.plate]
        chain.append(f"[1:v]scale={W}:{H},fps={common.fps_arg(fps)},format=yuva444p[p];[0:v]format=yuva444p[v];"
                     f"[p][v]concat=n=2:v=1:a=0,backgroundkey=threshold={a.threshold}:similarity=0.1:blend=0.02,"
                     f"trim=start_frame=1,setpts=PTS-STARTPTS[k]")
        last = "k"

    if a.matte:
        x, y, w, h = [float(v) for v in a.matte.split(",")]
        X, Y, Wm, Hm = int(x * W), int(y * H), int(w * W) // 2 * 2, int(h * H) // 2 * 2
        chain.append(f"[{last}]format=yuva444p,crop={Wm}:{Hm}:{X}:{Y},pad={W}:{H}:{X}:{Y}:color=black@0[m]")
        last = "m"
    if a.choke > 0 or a.soften > 0:
        ops = ",".join(["erosion"] * a.choke + ([f"gblur=sigma={a.soften}"] if a.soften > 0 else []))
        chain.append(f"[{last}]format=yuva444p,split[c][a];[a]alphaextract,{ops}[am];[c][am]alphamerge[e]")
        last = "e"
    chain.append(f"[{last}]format=yuva444p10le[out]")

    common.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(chain), "-map", "[out]",
                "-c:v", "prores_ks", "-profile:v", "4444", "-vendor", "apl0", "-pix_fmt", "yuva444p10le", out])
    # Browser-playable copy with alpha (Chrome can't decode ProRes) for player.py.
    common.run(["ffmpeg", "-y", "-v", "error", "-i", out, "-vf", "scale=iw/2:-2", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                "-b:v", "0", "-crf", "32", "-deadline", "realtime", "-cpu-used", "8", "-an", stem + "_preview.webm"])
    still = stem + "_still.png"
    common.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{(end - a.start) / 2:.3f}", "-i", out, "-frames:v", "1",
                "-pix_fmt", "rgba", still])
    stats = alpha_stats(still) or {}
    stats.update({"video": os.path.abspath(a.video), "start": a.start, "end": end, "size": [W, H], "fps": fps, "layer": out})
    with open(stem + ".json", "w") as f:
        json.dump(stats, f, indent=2)
    qc = stem + "_qc.jpg"
    common.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0xff00ff:s={W}x{H}", "-i", still,
                "-frames:v", "1", "-filter_complex", "[0][1]overlay,scale=-2:720", qc])
    print(f"subject: {out}\nstill:   {still}\nqc:      {qc}  (magenta = removed)\nstats:   {json.dumps({k: stats.get(k) for k in ('bbox', 'feet_y', 'feet_x', 'touches_bottom')})}")
    if stats.get("touches_bottom"):
        print("note: the subject touches the bottom edge (feet out of frame) → shadow.py will skip the cast shadow")


if __name__ == "__main__":
    main()
