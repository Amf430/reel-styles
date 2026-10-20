"""Sound effects for a layer: a scene's meta() may list {"sfx": [{"t", "id", "v"?, "gain"?, "len"?}]}
(t = seconds on the video timeline, id = a reel-sfx sound, v = variant index, gain in dB, len = cut after
seconds, from = skip this many seconds of the sound). mix() lays them on one WAV that starts with the layer, for its own track in Premiere.

The sounds come from reel-sfx (~/.reel-styles/sfx); the library is generated on first use.
"""
import json
import os
import subprocess
import sys

import common

LIB = os.path.expanduser(os.path.join(os.environ.get("REEL_HOME", "~/.reel-styles"), "sfx"))
SYNTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "reel-sfx", "synth.py")


def library():
    idx = os.path.join(LIB, "index.json")
    if not os.path.exists(idx):
        print("generating the reel-sfx library (one-time) …", flush=True)
        subprocess.run([sys.executable, SYNTH, "--out", LIB], check=True)
    with open(idx) as f:
        return {s["id"]: s for s in json.load(f)["sounds"]}


def mix(events, t0, dur, out_wav, gain_db=0.0):
    """Mix the events into a stereo 48 kHz WAV of length dur that starts at t0. Returns the path or None."""
    lib = library()
    inputs, parts, n = [], [], 0
    for e in sorted(events, key=lambda e: e["t"]):
        s = lib.get(e["id"])
        at = e["t"] - t0
        if not s or at < -0.05 or at >= dur:
            if not s:
                print(f"sfx: unknown sound '{e['id']}' (skipped)", file=sys.stderr)
            continue
        f = os.path.join(LIB, s["files"][int(e.get("v", 0)) % len(s["files"])])
        inputs += ["-i", f]
        chain = []
        if e.get("from"):   # start partway into the sound (a build-up that must still end on its beat)
            chain.append(f"atrim=start={e['from']:.3f},asetpts=PTS-STARTPTS")
        if e.get("len"):
            chain.append(f"atrim=0:{e['len']:.3f},afade=t=out:st={max(0, e['len'] - 0.08):.3f}:d=0.08")
        chain.append(f"adelay={max(0, at) * 1000:.0f}:all=1")
        chain.append(f"volume={e.get('gain', 0) + gain_db:.1f}dB")
        parts.append(f"[{n}:a]{','.join(chain)}[s{n}]")
        n += 1
    if not n:
        return None
    mixed = "".join(f"[s{i}]" for i in range(n))
    fc = ";".join(parts) + f";{mixed}amix=inputs={n}:normalize=0:dropout_transition=0,apad=whole_dur={dur:.4f},atrim=0:{dur:.4f},alimiter=limit=0.89[a]"
    common.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[a]",
                "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", out_wav])
    return out_wav
