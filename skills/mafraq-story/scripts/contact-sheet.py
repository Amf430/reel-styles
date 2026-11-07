# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""Contact sheet with file names. Usage: python3 contact-sheet.py out.jpg <cols> files...   (run with: uv run contact-sheet.py ...)"""
import sys,glob,os
from PIL import Image, ImageDraw, ImageFont
files=sys.argv[3:]; out=sys.argv[1]; cols=int(sys.argv[2])
W,H=300,537; pad=10
rows=(len(files)+cols-1)//cols
sheet=Image.new('RGB',(pad+cols*(W+pad),pad+rows*(H+pad+26)),(20,20,20)); d=ImageDraw.Draw(sheet)
f=(ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20) if os.path.exists('/System/Library/Fonts/Helvetica.ttc') else ImageFont.load_default())
for k,p in enumerate(files):
    im=Image.open(p).convert('RGB'); im.thumbnail((W,H)); x=pad+(k%cols)*(W+pad); y=pad+(k//cols)*(H+pad+26)
    sheet.paste(im,(x,y+26)); d.text((x,y+2),os.path.basename(p).rsplit('.',1)[0],fill=(230,180,90),font=f)
sheet.save(out,quality=85); print(sheet.size)
