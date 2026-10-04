#!/usr/bin/env python3
"""Cut the subject out of ordinary footage (no green screen) with an AI matte → same outputs as key.py.

  segment.py clip.mp4 --out reel_work/keyed/subject.mov --start 3 --end 9 --quality balanced

Quality (pick per job — don't pay for "best" on a simple shot):
  fast       MediaPipe selfie segmenter. People only, soft edges, ~real time.        (~1MB model)
  balanced   ISNet general. People, buildings, objects; good edges. ~0.3s/frame.     (~180MB model)
  best       BiRefNet. Finest edges (hair, railings). ~1–3s/frame.                   (~970MB model)
Options: --every N (compute every Nth frame, hold in between — for slow-moving shots)
         --smooth 0..0.9 (temporal smoothing against flicker, default 0.35)  --threshold (hard cut, off by default)
Models download once into ~/.reel-styles/models (needs internet the first time).
"""
import argparse
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import key  # noqa: E402
import mlenv  # noqa: E402

MODELS = {
    "fast": ("selfie_segmenter.tflite",
             "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"),
    "balanced": ("isnet-general-use.onnx", "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"),
    "best": ("BiRefNet-general-epoch_244.onnx", "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-epoch_244.onnx"),
}
PACKAGES = {"fast": ["numpy", "mediapipe"], "balanced": ["numpy", "onnxruntime", "opencv-python-headless"],
            "best": ["numpy", "onnxruntime", "opencv-python-headless"]}

WORKER = r'''
import sys, subprocess, numpy as np
src, out, quality, model, W, H, fps, start, dur, every, smooth, thr = sys.argv[1:13]
W, H, every, smooth, thr = int(W), int(H), int(every), float(smooth), float(thr)

if quality == "fast":
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=BaseOptions(model_asset_path=model), output_confidence_masks=True))
    def matte(rgb):
        r = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
        return r.confidence_masks[0].numpy_view().astype(np.float32).reshape(H, W)
else:
    import cv2, onnxruntime as ort
    providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    try:
        sess = ort.InferenceSession(model, providers=providers)
    except Exception:
        sess = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
    name, S = sess.get_inputs()[0].name, 1024
    if quality == "best":
        mean, std = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])
    else:
        mean, std = np.array([0.5, 0.5, 0.5]), np.array([1.0, 1.0, 1.0])
    def matte(rgb):
        x = cv2.resize(rgb, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        x = ((x - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)
        p = sess.run(None, {name: x})[0][0, 0]
        if quality == "best":
            p = 1 / (1 + np.exp(-p))
        p = (p - p.min()) / max(1e-6, p.max() - p.min())
        return cv2.resize(p, (W, H), interpolation=cv2.INTER_LINEAR)

dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", start, "-t", dur, "-i", src, "-vf", f"scale={W}:{H}",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", fps,
                        "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444", "-vendor", "apl0", "-pix_fmt", "yuva444p10le", out],
                       stdin=subprocess.PIPE)
prev, n, m = None, 0, None
size = W * H * 3
while True:
    buf = dec.stdout.read(size)
    if len(buf) < size:
        break
    rgb = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    if m is None or n % every == 0:
        m = matte(rgb)
        if prev is not None and smooth > 0:
            m = smooth * prev + (1 - smooth) * m
        prev = m
    a = (m > thr).astype(np.float32) if thr > 0 else m
    rgba = np.dstack([rgb, (np.clip(a, 0, 1) * 255).astype(np.uint8)])
    enc.stdin.write(rgba.tobytes())
    n += 1
    if n % 30 == 0:
        print(f"  {n} frames", flush=True)
enc.stdin.close(); enc.wait(); dec.wait()
print(f"done {n}")
'''


def fetch_model(quality):
    fname, url = MODELS[quality]
    path = os.path.join(mlenv.MODELS, fname)
    if not os.path.exists(path):
        os.makedirs(mlenv.MODELS, exist_ok=True)
        print(f"downloading {fname} (one-time) …", flush=True)
        urllib.request.urlretrieve(url, path + ".part")
        os.replace(path + ".part", path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", choices=list(MODELS), default="balanced")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--smooth", type=float, default=0.35)
    ap.add_argument("--threshold", type=float, default=0)
    a = ap.parse_args()

    info = common.probe(a.video)
    W, H, fps = info["w"], info["h"], info["fps"]
    end = a.end if a.end is not None else info["duration"]
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    py = mlenv.ensure(PACKAGES[a.quality])
    model = fetch_model(a.quality)
    print(f"segmenting {end - a.start:.1f}s at {a.quality} …", flush=True)
    r = subprocess.run([py, "-c", WORKER, a.video, out, a.quality, model, str(W), str(H), common.fps_arg(fps),
                        f"{a.start:.4f}", f"{end - a.start:.4f}", str(max(1, a.every)), str(a.smooth), str(a.threshold)])
    if r.returncode != 0:
        common.die("segmentation failed (see above)")
    key.finalize(out, a.video, a.start, end, W, H, fps)


if __name__ == "__main__":
    main()
