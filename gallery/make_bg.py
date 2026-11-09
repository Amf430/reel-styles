"""Neutral 'studio' background for gallery previews: warm gradient, soft bokeh, presenter silhouette."""
import random, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
out = sys.argv[1]
CHROMA = "--chroma" in sys.argv
ALT = "--alt" in sys.argv         # second shot (cool daylight) so transitions have something to cut to   # green-screen presenter for the plate styles (backdrop / studio3d)
random.seed(7)
img = Image.new("RGB", (W, H))
px = img.load()
top, bot = ((168, 196, 214), (62, 96, 112)) if ALT else ((34, 40, 56), (92, 70, 58))
for y in range(H):
    k = y / H
    c = tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3))
    for x in range(W):
        px[x, y] = c
bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(bok)
for _ in range(26):
    r = random.randint(40, 140)
    x, y = random.randint(-50, W + 50), random.randint(0, int(H * 0.7))
    col = random.choice([(255, 196, 140), (255, 230, 190), (150, 190, 255), (255, 160, 110)])
    d.ellipse((x - r, y - r, x + r, y + r), fill=col + (random.randint(35, 80),))
bok = bok.filter(ImageFilter.GaussianBlur(28))
img.paste(bok, (0, 0), bok)
if CHROMA:
    img = Image.new("RGB", (W, H), (20, 180, 60))
sil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
s = ImageDraw.Draw(sil)
shade = (40, 46, 70, 255) if CHROMA else (18, 16, 20, 235)
skin = (196, 150, 122, 255) if CHROMA else shade
s.ellipse((W / 2 - 150, 820, W / 2 + 150, 1180), fill=skin)               # head
s.rectangle((W / 2 - 70, 1150, W / 2 + 70, 1260), fill=skin)              # neck
s.rounded_rectangle((W / 2 - 400, 1230, W / 2 + 400, H + 200), 260, fill=shade)  # shoulders
sil = sil.filter(ImageFilter.GaussianBlur(1 if CHROMA else 6))
img.paste(sil, (0, 0), sil)
if not CHROMA:
    img = img.filter(ImageFilter.GaussianBlur(1.5))
img.save(out + ".png")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", out + ".png", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-t", "40", "-vf", "scale=1188:2112,zoompan=z='1+0.04*on/1200':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,format=yuv420p",
                "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-shortest", out], check=True)
