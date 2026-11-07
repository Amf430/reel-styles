"""Step 1 of the voice: find every spoken chunk in one long take and transcribe each chunk alone.

Usage (mlx-whisper runs through uvx, no install):
  ffmpeg -i take.mp3 -ac 1 -ar 44100 take.wav
  uvx --python 3.11 --from mlx-whisper python -I vo-split.py take.wav chunks_dir > chunks.txt

Prints one line per chunk: `cNN start-end text`. Read it, mark the chunks that are stage cues read
aloud by mistake (e.g. «العم همس», «أنت»), then group the rest into lines for vo-cut.py.
Short chunks transcribe badly; trust the timings, not the spelling.
"""
import sys, re, subprocess, os
import mlx_whisper

src, out = sys.argv[1], sys.argv[2]
NOISE, MIN_PAUSE = "-38dB", "0.18"   # pauses quieter than NOISE and longer than MIN_PAUSE seconds split chunks
os.makedirs(out, exist_ok=True)
o = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", f"silencedetect=noise={NOISE}:d={MIN_PAUSE}", "-f", "null", "-"],
                   capture_output=True, text=True).stderr
ss = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", o)]
se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", o)]
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src],
                           capture_output=True, text=True).stdout)
speech, prev = [], 0.0
for a, b in zip(ss, se):
    if a - prev > 0.08: speech.append((prev, a))
    prev = b
if dur - prev > 0.08: speech.append((prev, dur))
for i, (a, b) in enumerate(speech):
    f = f"{out}/c{i:02d}.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{max(0, a - 0.05):.3f}", "-to", f"{b + 0.05:.3f}", "-i", src, f])
    t = mlx_whisper.transcribe(f, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="ar",
                               condition_on_previous_text=False)["text"].strip()
    print(f"c{i:02d} {a:6.2f}-{b:6.2f} {t}", flush=True)
