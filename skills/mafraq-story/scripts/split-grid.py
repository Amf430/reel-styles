# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow", "numpy"]
# ///
"""Split a comic grid (cream/white gutters) into panel-NN.png.
Usage: python3 split-grid.py grid.jpg out_dir   (run with: uv run split-grid.py ...)"""
import sys, os
import numpy as np
from PIL import Image
src, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
im = Image.open(src).convert('RGB'); a = np.asarray(im).astype(int)
lum = a.mean(axis=2)
bg = lum > 215  # cream/white gutter pixels
def runs(mask):
    out=[]; s=None
    for i,v in enumerate(mask):
        if not v and s is None: s=i
        if v and s is not None: out.append((s,i)); s=None
    if s is not None: out.append((s,len(mask)))
    return [r for r in out if r[1]-r[0]>40]
def split(x0,y0,x1,y1,axis,depth=0):
    sub = bg[y0:y1, x0:x1]
    if axis==0: segs = runs(sub.mean(axis=1) > 0.97)
    else: segs = runs(sub.mean(axis=0) > 0.97)
    if len(segs)<=1:
        if depth>=1 and axis==1: return [(x0,y0,x1,y1)] if not segs else [(x0+(segs[0][0] if axis==1 else 0), y0+(segs[0][0] if axis==0 else 0), x0+(segs[0][1] if axis==1 else x1-x0), y0+(segs[0][1] if axis==0 else y1-y0))]
        if depth>=3: return [(x0,y0,x1,y1)]
        if segs:
            s=segs[0]
            nx0,ny0,nx1,ny1 = (x0,y0+s[0],x1,y0+s[1]) if axis==0 else (x0+s[0],y0,x0+s[1],y1)
        else: nx0,ny0,nx1,ny1=x0,y0,x1,y1
        return split(nx0,ny0,nx1,ny1,1-axis,depth+1) if depth<3 else [(nx0,ny0,nx1,ny1)]
    res=[]
    for s in segs:
        nx0,ny0,nx1,ny1 = (x0,y0+s[0],x1,y0+s[1]) if axis==0 else (x0+s[0],y0,x0+s[1],y1)
        res += split(nx0,ny0,nx1,ny1,1-axis,depth+1)
    return res
H,W = lum.shape
panels = split(0,0,W,H,0)
panels = sorted(set(panels), key=lambda p:(round(p[1]/80), p[0]))
for k,(x0,y0,x1,y1) in enumerate(panels,1):
    im.crop((x0,y0,x1,y1)).save(os.path.join(outdir, f'panel-{k:02d}.png'))
    print(k, x0,y0,x1,y1, x1-x0, y1-y0)
