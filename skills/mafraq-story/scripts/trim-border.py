# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow", "numpy"]
# ///
"""Flow often ignores "no border" and paints a cream paper margin and a black frame line around the panel.
This finds that margin, crops it off (plus a small inset past the frame line), and writes a 1536x2752 jpg (2K, same frame as the 1080x1935 plate)
cropped to fill (the edit's .plate size). Images with no margin are only resized.
Usage: uv run trim-border.py <in_dir> <out_dir>      (names are kept; prints the crop per image)"""
import sys, os, glob
import numpy as np
from PIL import Image

W, H = 1536, 2752
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)

def edge(lum, axis, rev):
    # lines (rows or cols) that are bright and flat count as margin
    m = lum.mean(axis=axis); s = lum.std(axis=axis)
    idx = range(len(m) - 1, -1, -1) if rev else range(len(m))
    n = 0
    for i in idx:
        if m[i] > 200 and s[i] < 30: n += 1
        else: break
    return n

for f in sorted(glob.glob(os.path.join(src, "*.jpg")) + glob.glob(os.path.join(src, "*.png"))):
    im = Image.open(f).convert("RGB"); w, h = im.size
    lum = np.asarray(im.convert("L"), dtype=np.float32)
    t, b = edge(lum, 1, False), edge(lum, 1, True)
    l, r = edge(lum, 0, False), edge(lum, 0, True)
    framed = sum(x > 4 for x in (t, b, l, r)) >= 3   # a margin on one side only is bright sky, not a frame
    inset = int(0.012 * w)                            # step past the black frame line
    box = (l + inset, t + inset, w - r - inset, h - b - inset) if framed else (0, 0, w, h)
    im = im.crop(box); cw, ch = im.size
    sc = max(W / cw, H / ch); im = im.resize((round(cw * sc), round(ch * sc)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    im.crop((x, y, x + W, y + H)).save(os.path.join(out, os.path.basename(f).rsplit(".", 1)[0] + ".jpg"), quality=92)
    print(f"{os.path.basename(f):32s} {w}x{h} margin t{t} b{b} l{l} r{r} -> crop {box}")
