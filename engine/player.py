#!/usr/bin/env python3
"""The editor: the whole video with every job on it — timeline, transforms, live preview.

  player.py reel_work/project.json [--port 8765] [--t 12]     (or a single job.json)

project.json: { "video": "../clip.mp4", "jobs": ["glass.json", "neon.json"] }
What you see is what render.py exports. Ctrl/Cmd+S writes timings, transforms and style values
back into the job files (only your edits, not the defaults).
"""
import argparse
import os
import sys
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("project")
ap.add_argument("--port", type=int, default=8765)
ap.add_argument("--t", type=float)
ap.add_argument("--no-open", action="store_true")
a = ap.parse_args()

project = common.load_project(a.project)
srv, base = common.serve(project, a.port)
url = f"{base}/player" + (f"?t={a.t}" if a.t is not None else "")
print(f"editor: {url}\n(ctrl-c to stop)")
if not a.no_open:
    webbrowser.open(url)
try:
    while True:
        time.sleep(3600)
except KeyboardInterrupt:
    srv.shutdown()
