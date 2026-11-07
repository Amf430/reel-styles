# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow", "numpy"]
# ///
"""Check every 2K image matches its 1K original (catches a wrong attachment or a swapped download).
Usage: python3 match-2k.py <episode_dir>   (expects <dir>/shots/*.jpg and <dir>/shots-2k/*.jpg, names start with sNN)"""
import sys,glob,os
import numpy as np
from PIL import Image
d=sys.argv[1]
def vec(p):
    a=np.asarray(Image.open(p).convert('L').resize((48,86),Image.BILINEAR)).astype(float).ravel()
    a-=a.mean(); return a/(np.linalg.norm(a)+1e-9)
lo={os.path.basename(p)[:3]:vec(p) for p in sorted(glob.glob(f'{d}/shots/*.jpg'))}
for p in sorted(glob.glob(f'{d}/shots-2k/*.jpg')):
    v=vec(p); w,h=Image.open(p).size
    sc={k:float(v@u) for k,u in lo.items()}; best=max(sc,key=sc.get); me=os.path.basename(p)[:3]
    print(f'{os.path.basename(p):32s} {w}x{h} self={sc.get(me,0):.3f} best={best} {sc[best]:.3f} {"OK" if best==me else "MISMATCH"}')
