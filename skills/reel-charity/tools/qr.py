#!/usr/bin/env python3
"""Make the end card's QR and prove it scans from the rendered video.

    python3 qr.py make https://example.org --out project/assets/qr.svg [--color "#1f2a30"]
    python3 qr.py check out/end.mp4 --at 18 --expect https://example.org

`check` grabs the frame with ffmpeg and decodes it with OpenCV. A wrong domain is reported,
never fixed silently — ask whoever owns the link.
Needs: pip3 install qrcode opencv-python-headless
"""
import argparse
import subprocess
import sys
import tempfile


def make(a):
    import qrcode

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=1)
    qr.add_data(a.url)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    rects = "".join(f'<rect x="{x}" y="{y}" width="1.02" height="1.02"/>' for y, row in enumerate(m) for x, v in enumerate(row) if v)
    with open(a.out, "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" shape-rendering="crispEdges">'
                f'<rect width="{n}" height="{n}" fill="#fff"/><g fill="{a.color}">{rects}</g></svg>')
    print(f"{a.out} · {n}×{n} modules · {a.url}")


def check(a):
    import cv2

    with tempfile.NamedTemporaryFile(suffix=".png") as t:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.at), "-i", a.video, "-frames:v", "1", t.name], check=True)
        frame = cv2.imread(t.name)
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(frame)
    if not data:
        sys.exit(f"✗ no QR read at {a.at}s")
    if a.expect and data != a.expect:
        sys.exit(f"✗ QR reads {data!r}, expected {a.expect!r}")
    print(f"✓ QR at {a.at}s reads {data}")


ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
m = sub.add_parser("make")
m.add_argument("url")
m.add_argument("--out", required=True)
m.add_argument("--color", default="#1f2a30")
c = sub.add_parser("check")
c.add_argument("video")
c.add_argument("--at", type=float, required=True)
c.add_argument("--expect")
a = ap.parse_args()
make(a) if a.cmd == "make" else check(a)
