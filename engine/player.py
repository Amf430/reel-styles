#!/usr/bin/env python3
"""Live preview of a style job over its video, identical to the export.

  player.py JOB.json [--port 8765] [--t 3.2]

Keys: space play/pause · ←/→ ±1s (shift ±5s) · , . one frame · l loop
      b before/after · w wipe (move the mouse) · h hide UI
Sliders on the left change the style live; "save to job" writes them into JOB.json.
"""
import argparse
import os
import sys
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("job")
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--t", type=float)
ap.add_argument("--no-open", action="store_true")
a = ap.parse_args()

job = common.load_job(a.job)
srv, base = common.serve(job, a.port)
url = f"{base}/scene" + (f"?t={a.t}" if a.t is not None else "")
print(f"player: {url}\n(ctrl-c to stop)")
if not a.no_open:
    webbrowser.open(url)
try:
    while True:
        time.sleep(3600)
except KeyboardInterrupt:
    srv.shutdown()
