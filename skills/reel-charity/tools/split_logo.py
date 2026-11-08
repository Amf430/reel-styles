#!/usr/bin/env python3
"""Split a logo image into parts for the layered-colour build (lib/logobuild.js).

    python3 split_logo.py logo.png --out project/logo [--merge 6] [--max-side 1600]

Every connected shape becomes a part (shapes closer than --merge px are kept together, so a
word's letters travel as one). Writes <out>/<part>.png (cropped, full colour) and <out>/parts.js
(LOGO: size, focus point, one line per part with its reveal kind and start time). Open parts.js and change any
part's kind / at / dur by hand — that file is the build.

Background: transparent PNGs use alpha; opaque images treat the corner colour as background.
Needs: pip3 install pillow numpy scipy
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage


def foreground(img, tol):
    rgba = np.asarray(img.convert("RGBA")).astype(np.int16)
    alpha = rgba[..., 3]
    if alpha.min() < 250:
        return rgba, alpha > 24
    corners = np.array([rgba[0, 0, :3], rgba[0, -1, :3], rgba[-1, 0, :3], rgba[-1, -1, :3]])
    bg = np.median(corners, axis=0)
    dist = np.abs(rgba[..., :3] - bg).sum(axis=2)
    mask = dist > tol
    rgba[..., 3] = np.where(mask, 255, 0)
    return rgba, mask


def guess_kind(w, h, area, total):
    if area < total * 0.004:
        return "rain"
    if h > w * 2.4:
        return "ttb"
    if w > h * 4:
        return "cx"
    if area > total * 0.18:
        return "rtl"
    return "pop" if w < h * 1.4 and area < total * 0.05 else "rtl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logo")
    ap.add_argument("--out", required=True)
    ap.add_argument("--merge", type=int, default=6, help="px gap under which shapes stay one part")
    ap.add_argument("--max-side", type=int, default=1600)
    ap.add_argument("--tol", type=int, default=60, help="colour distance from the background (opaque images)")
    ap.add_argument("--max-parts", type=int, default=48)
    ap.add_argument("--focus", help="x,y in %% of the logo where the rings land (default: centre of the biggest shape)")
    a = ap.parse_args()

    img = Image.open(a.logo)
    s = min(1.0, a.max_side / max(img.size))
    if s < 1:
        img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    rgba, mask = foreground(img, a.tol)
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise SystemExit("no logo found — is the background uniform?")
    pad = 4
    x0, x1 = max(0, xs.min() - pad), min(mask.shape[1], xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(mask.shape[0], ys.max() + pad + 1)
    rgba, mask = rgba[y0:y1, x0:x1], mask[y0:y1, x0:x1]
    H, W = mask.shape

    merge = a.merge
    while True:
        grown = ndimage.binary_dilation(mask, iterations=merge) if merge else mask
        labels, n = ndimage.label(grown)
        if n <= a.max_parts:
            break
        merge += 3
    labels = labels * mask
    total = int(mask.sum())

    parts = []
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        if sl is None:
            continue
        own = labels[sl] == i
        area = int(own.sum())
        if area < 12:
            continue
        crop = rgba[sl].copy()
        crop[..., 3] = np.where(own, crop[..., 3], 0)
        h, w = own.shape
        parts.append({"crop": crop, "x": sl[1].start, "y": sl[0].start, "w": w, "h": h, "area": area})

    # read order: right to left, top to bottom inside a column; big strokes first, marks last
    parts.sort(key=lambda p: (-(p["x"] + p["w"]), p["y"]))
    big = max(parts, key=lambda p: p["area"])
    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):
        if f.startswith("part") and f.endswith(".png"):
            os.remove(os.path.join(a.out, f))

    out, n_main, n_rain = [], 0, 0
    for k, p in enumerate(parts):
        name = f"part{k:02d}"
        Image.fromarray(p["crop"].astype(np.uint8)).save(os.path.join(a.out, f"{name}.png"))
        kind = guess_kind(p["w"], p["h"], p["area"], total)
        if kind == "rain":
            at, n_rain = 1.2 + n_rain * 0.06, n_rain + 1
        else:
            at, n_main = n_main * 0.12, n_main + 1
        out.append({
            "name": name, "kind": kind,
            "x": round(p["x"] / W * 100, 3), "y": round(p["y"] / H * 100, 3),
            "w": round(p["w"] / W * 100, 3), "h": round(p["h"] / H * 100, 3),
            "at": round(at, 2), "dur": 0.6 if kind != "rain" else 0.5,
        })
    focus = [round((big["x"] + big["w"] / 2) / W * 100, 2), round((big["y"] + big["h"] / 2) / H * 100, 2)]
    if a.focus:
        focus = [float(v) for v in a.focus.split(",")]
    with open(os.path.join(a.out, "parts.js"), "w") as f:
        f.write("// written by split_logo.py — edit kind / at / dur per part to direct the build\n")
        f.write(f"const LOGO = {{ w: {W}, h: {H}, focus: {json.dumps(focus)}, parts: [\n")
        for p in out:
            f.write("  " + json.dumps(p, ensure_ascii=False) + ",\n")
        f.write("] };\n")
    kinds = {}
    for p in out:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print(f"{len(out)} parts ({', '.join(f'{v} {k}' for k, v in kinds.items())}) · {W}×{H} · merge {merge}px → {a.out}/parts.js")


if __name__ == "__main__":
    main()
