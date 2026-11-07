# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow", "numpy", "scipy"]
# ///
"""Find the glowing (amber) phone screen in each shot and print its 4 corners in 1080x1920 canvas pixels,
ready for quad_matrix() in the episode build script.  Usage: python3 screen-quad.py <shots_dir> s03 s06 ...
(run with: uv run screen-quad.py ...)"""
from PIL import Image
import numpy as np, sys
from scipy import ndimage
for s in sys.argv[2:]:
    im=np.asarray(Image.open(f"{sys.argv[1]}/{s}.jpg").convert("RGB")).astype(int)
    r,g,b=im[...,0],im[...,1],im[...,2]
    m=(r>190)&(g>120)&(r-b>60)
    lab,n=ndimage.label(m); 
    if n==0: print(s,"none"); continue
    sizes=ndimage.sum(m,lab,range(1,n+1)); i=sizes.argmax()+1
    ys,xs=np.nonzero(lab==i)
    k=1080/1536
    pts=np.stack([xs,ys],1); sm=pts.sum(1); df=pts[:,0]-pts[:,1]
    tl=pts[sm.argmin()]; br=pts[sm.argmax()]; tr=pts[df.argmax()]; bl=pts[df.argmin()]
    f=lambda p:(round(p[0]*k),round(p[1]*k-7.5))
    print(s,int(sizes.max()),"TL",f(tl),"TR",f(tr),"BR",f(br),"BL",f(bl))
