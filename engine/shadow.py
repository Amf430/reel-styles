#!/usr/bin/env python3
"""Floor shadow for a keyed subject → ProRes 4444 alpha layer (sits between backdrop and subject).

  shadow.py subject.mov --out shadow.mov
  options: --opacity 0.5   --length 0.32 (cast length, × subject height)   --skew -0.8 (lean; − = left)
           --blur 14        --contact 0.55 (dark pad under the feet; 0 = off)
           --rect x,y,w,h   where the subject is placed in the final frame (0..1); default: full frame

Reads <subject>.json written by key.py for the feet line. The cast shadow is the subject's own
silhouette flipped onto the floor, so it moves with them.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def build(subject, out, size, rect, opacity=0.5, length=0.32, skew=-0.8, blur=14, contact=0.55, start=None, dur=None):
    """Shared by composite.py. rect = subject placement (x,y,w,h in 0..1 of the output frame)."""
    stem = os.path.splitext(subject)[0]
    with open(stem + ".json") as f:
        st = json.load(f)
    W, H = size
    sw, sh = st["size"]
    rx, ry, rw, rh = rect
    pw, ph = int(round(rw * W)) // 2 * 2, int(round(rh * H)) // 2 * 2   # placed subject size
    px, py = int(round(rx * W)), int(round(ry * H))
    feet_y = py + st["feet_y"] * ph                                       # floor line in output px
    feet_x = px + st["feet_x"] * pw
    bw, bh = st["bbox"][2] * pw, st["bbox"][3] * ph                       # silhouette size in output px
    cast = (not st.get("touches_bottom")) and length > 0
    sigma = blur * H / 1080

    parts = [f"color=c=black@0:s={W}x{H}:r={st['fps']},format=yuva444p[canvas]"]
    inp = ["-i", subject]
    parts.append(f"[0:v]scale={pw}:{ph},format=rgba,colorchannelmixer=rr=0:gg=0:bb=0:aa={opacity},split=2[s1][s2]")
    last = "canvas"
    if cast:
        ch = max(2, int(round(ph * length)) // 2 * 2)
        # Flip, squash onto the floor, lean with shear (pivot = feet row = top of the flipped image).
        shx = skew * (ph / ch) * 0.5
        pad_x = int(abs(shx) * ch) + 4
        parts.append(f"[s1]vflip,scale={pw}:{ch},pad={pw + 2 * pad_x}:{ch}:{pad_x}:0:color=black@0,"
                     f"shear=shx={shx:.3f}:fillcolor=black@0,gblur=sigma={sigma:.1f},"
                     f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*(1-0.75*Y/H)'[cast]")
        # Shear pivots on the image centre; shift so the feet row (y=0 of the flipped image) stays put.
        dx = int(round(shx * ch / 2))
        flip_top = feet_y - (ph - st["feet_y"] * ph) * (ch / ph)
        parts.append(f"[{last}][cast]overlay=x={px - pad_x - dx}:y={int(flip_top)}[c1]")
        last = "c1"
    else:
        parts.append("[s1]nullsink")
    if contact > 0:
        cw, chh = max(4, int(bw * 0.9)) // 2 * 2, max(4, int(bh * 0.035)) // 2 * 2
        parts.append(f"color=c=black:s={cw}x{chh}:r={st['fps']},format=rgba,geq=r=0:g=0:b=0:"
                     f"a='255*{contact}*max(0,1-((X-W/2)/(W/2))^2-((Y-H/2)/(H/2))^2)',gblur=sigma={sigma * 0.7:.1f}[pad]")
        parts.append(f"[{last}][pad]overlay=x={int(feet_x - cw / 2)}:y={int(feet_y - chh * 0.55)}:shortest=0[c2]")
        last = "c2"
    parts.append("[s2]nullsink")
    parts.append(f"[{last}]trim=duration={dur if dur else st['end'] - st['start']:.4f},format=yuva444p10le[out]")
    common.run(["ffmpeg", "-y", "-v", "error", *inp, "-filter_complex", ";".join(parts), "-map", "[out]",
                "-c:v", "prores_ks", "-profile:v", "4444", "-vendor", "apl0", "-pix_fmt", "yuva444p10le", out])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subject")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", help="W,H of the output frame (default: subject size)")
    ap.add_argument("--rect", default="0,0,1,1")
    ap.add_argument("--opacity", type=float, default=0.5)
    ap.add_argument("--length", type=float, default=0.32)
    ap.add_argument("--skew", type=float, default=-0.8)
    ap.add_argument("--blur", type=float, default=14)
    ap.add_argument("--contact", type=float, default=0.55)
    a = ap.parse_args()
    with open(os.path.splitext(a.subject)[0] + ".json") as f:
        st = json.load(f)
    size = [int(v) for v in a.size.split(",")] if a.size else st["size"]
    out = build(os.path.abspath(a.subject), os.path.abspath(a.out), size, [float(v) for v in a.rect.split(",")],
                a.opacity, a.length, a.skew, a.blur, a.contact)
    print(f"shadow: {out}")


if __name__ == "__main__":
    main()
