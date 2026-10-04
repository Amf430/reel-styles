#!/usr/bin/env python3
"""Stack layers (bottom → top) into a preview MP4 — what you'd get in Premiere.

  composite.py --out preview.mp4 --size 1080,1920 --fps 30 --dur 6 plate.mov shadow.mov subject.mov@0.1,0.05,0.8,0.95
  options: --audio SRC --audio-start S   (audio from the original footage)
           layer@x,y,w,h places a layer in a box (0..1 of the frame); images (.png/.jpg) are held for the duration.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

IMAGES = (".png", ".jpg", ".jpeg", ".webp")


def stack(out, size, fps, dur, layers, audio=None, audio_start=0.0, prores=False):
    """layers: list of (path, rect|None). Returns out."""
    W, H = size
    inputs, parts = [], [f"color=c=black:s={W}x{H}:r={common.fps_arg(fps)}:d={dur:.4f}[base]"]
    last = "base"
    for i, (path, rect) in enumerate(layers):
        if path.lower().endswith(IMAGES):
            inputs += ["-loop", "1", "-t", f"{dur:.4f}", "-i", path]
        else:
            inputs += ["-i", path]
        if rect:
            x, y, w, h = rect
            pw, ph = int(round(w * W)) // 2 * 2, int(round(h * H)) // 2 * 2
            parts.append(f"[{i}:v]setpts=PTS-STARTPTS,scale={pw}:{ph},format=yuva444p[l{i}]")
            pos = f"x={int(round(x * W))}:y={int(round(y * H))}"
        else:
            parts.append(f"[{i}:v]setpts=PTS-STARTPTS,scale={W}:{H},format=yuva444p[l{i}]")
            pos = "x=0:y=0"
        parts.append(f"[{last}][l{i}]overlay={pos}:eof_action=pass[o{i}]")
        last = f"o{i}"
    parts.append(f"[{last}]trim=duration={dur:.4f},format={'yuv422p10le' if prores else 'yuv420p'}[v]")
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs]
    if audio:
        cmd += ["-ss", f"{audio_start:.4f}", "-t", f"{dur:.4f}", "-i", audio]
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]"]
    if audio and common.probe(audio)["has_audio"]:
        cmd += ["-map", f"{len(layers)}:a:0", "-c:a", "aac", "-b:a", "192k"]
    if prores:
        cmd += ["-c:v", "prores_ks", "-profile:v", "3", "-vendor", "apl0"]
    else:
        cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-movflags", "+faststart"]
    cmd += ["-shortest", out] if audio else [out]
    common.run(cmd)
    return out


def place(layer, rect, size, out, dur=None):
    """Scale/position an alpha layer into a full-frame ProRes 4444 (drop straight onto the timeline)."""
    W, H = size
    x, y, w, h = rect
    pw, ph = int(round(w * W)) // 2 * 2, int(round(h * H)) // 2 * 2
    fps = common.probe(layer)["fps"]
    fc = (f"color=c=black@0:s={W}x{H}:r={common.fps_arg(fps)},format=yuva444p[c];[0:v]scale={pw}:{ph},format=yuva444p[s];"
          f"[c][s]overlay=x={int(round(x * W))}:y={int(round(y * H))}:shortest=1,format=yuva444p10le[v]")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", layer, "-filter_complex", fc, "-map", "[v]"]
    if dur:
        cmd += ["-t", f"{dur:.4f}"]
    common.run(cmd + ["-c:v", "prores_ks", "-profile:v", "4444", "-vendor", "apl0", "-pix_fmt", "yuva444p10le", out])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("layers", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", required=True)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--audio")
    ap.add_argument("--audio-start", type=float, default=0)
    a = ap.parse_args()
    layers = []
    for spec in a.layers:
        if "@" in spec:
            p, r = spec.rsplit("@", 1)
            layers.append((os.path.abspath(p), [float(v) for v in r.split(",")]))
        else:
            layers.append((os.path.abspath(spec), None))
    print(stack(os.path.abspath(a.out), [int(v) for v in a.size.split(",")], a.fps, a.dur, layers, a.audio, a.audio_start))


if __name__ == "__main__":
    main()
