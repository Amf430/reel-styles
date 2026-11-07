"""Step 2 of the voice: clean the take and cut it into one file per line.

Usage: python3 vo-cut.py take.wav lines.json out_dir
lines.json = [["01-n", 0.85, 4.74], ["02-u", 7.92, 10.02], ...]   (id, speech start, speech end in the take,
             taken from vo-split.py; a line may span several chunks, cue chunks are simply left out)

Chain (measured on a phone recording with a -66 dB floor, so no denoise):
  highpass 75 Hz -> gentle compressor (2.5:1) -> loudnorm -16 LUFS / -1.5 dBTP, 48 kHz mono.
Each line gets 0.12 s of air on both sides with 40/60 ms fades. Also writes preview.mp3
(all lines in order with 0.45 s gaps) to listen to and to re-transcribe as a check.
"""
import json, subprocess, sys, os, tempfile

src, spec, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
os.makedirs(out, exist_ok=True)
tmp = tempfile.mkdtemp()
proc = f"{tmp}/proc.wav"
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-af",
                "highpass=f=75,acompressor=threshold=-24dB:ratio=2.5:attack=8:release=120:makeup=2,loudnorm=I=-16:TP=-1.5:LRA=9",
                "-ar", "48000", "-ac", "1", proc], check=True)
PAD = 0.12
for lid, a, b in spec:
    s = max(0, a - PAD); e = b + PAD; d = e - s
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", proc, "-af",
                    f"afade=t=in:d=0.04,afade=t=out:st={d - 0.06:.3f}:d=0.06", f"{out}/{lid}.wav"], check=True)
    print(lid, f"{d:.2f}s")
gap = f"{tmp}/gap.wav"
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-t", "0.45", "-i", "anullsrc=r=48000:cl=mono", gap], check=True)
with open(f"{tmp}/cat.txt", "w") as f:
    for lid, _, _ in spec: f.write(f"file '{os.path.abspath(out)}/{lid}.wav'\nfile '{gap}'\n")
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/cat.txt", "-b:a", "192k",
                f"{out}/preview.mp3"], check=True)
print("preview:", f"{out}/preview.mp3")
