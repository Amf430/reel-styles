#!/usr/bin/env python3
"""Word-level timings of the speech → words.json (for reel-captions and anything word-synced).

  transcribe.py clip.mp4 --out reel_work/words.json                 Whisper on this Mac (Arabic by default)
  transcribe.py clip.mp4 --out words.json --model large-v3          slower, most accurate
  transcribe.py --srt subs.srt --out words.json                     from an SRT (CapCut…): words spread inside each line
  options: --lang ar|en|auto  --start/--end (seconds)  --prompt "أسماء وأماكن تتكرر"  (helps spelling)

words.json: {"words": [{"w": "شقة", "s": 1.20, "e": 1.48, "g": 0}, …], "segments": [{"text", "s", "e"}]}
("g" = the line/sentence the word belongs to; captions never join two lines into one phrase.)
Fix spelling by editing "w" only; keep "s"/"e". The first Whisper run downloads the model (~800MB for
large-v3-turbo) into ~/.reel-styles/models.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import mlenv  # noqa: E402

WORKER = r'''
import json, sys
from faster_whisper import WhisperModel
wav, model, lang, prompt, models_dir, offset = sys.argv[1:7]
m = WhisperModel(model, device="cpu", compute_type="int8", download_root=models_dir)
segs, info = m.transcribe(wav, language=None if lang == "auto" else lang, word_timestamps=True,
                          vad_filter=True, initial_prompt=prompt or None, beam_size=5)
out = {"lang": info.language, "words": [], "segments": []}
off = float(offset)
for gi, s in enumerate(segs):
    out["segments"].append({"text": s.text.strip(), "s": round(s.start + off, 3), "e": round(s.end + off, 3)})
    for w in s.words or []:
        t = w.word.strip()
        if t:
            out["words"].append({"w": t, "s": round(w.start + off, 3), "e": round(w.end + off, 3), "g": gi})
print(json.dumps(out, ensure_ascii=False))
'''


def from_srt(path):
    text = open(path, encoding="utf-8-sig").read()
    words, segs = [], []
    ts = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    for block in re.split(r"\n\s*\n", text.strip()):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", block)
        if not m:
            continue
        s, e = ts(*m.groups()[:4]), ts(*m.groups()[4:])
        line = " ".join(block[m.end():].strip().splitlines()).strip()
        toks = line.split()
        if not toks:
            continue
        gi = len(segs)
        segs.append({"text": line, "s": round(s, 3), "e": round(e, 3)})
        # Spread the line's duration over its words by length (speech takes longer on longer words).
        span = max(0.05, (e - s) - 0.05)
        total = sum(len(t) + 1 for t in toks)
        t = s
        for tok in toks:
            d = span * (len(tok) + 1) / total
            words.append({"w": tok, "s": round(t, 3), "e": round(t + d, 3), "g": gi})
            t += d
    return {"lang": "srt", "words": words, "segments": segs}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--out", required=True)
    ap.add_argument("--srt")
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float)
    a = ap.parse_args()

    if a.srt:
        data = from_srt(a.srt)
    else:
        if not a.video:
            common.die("give a video, or --srt")
        py = mlenv.ensure(["faster-whisper"])
        with tempfile.TemporaryDirectory() as d:
            wav = os.path.join(d, "a.wav")
            cut = ["-ss", f"{a.start}"] + (["-t", f"{a.end - a.start}"] if a.end else [])
            common.run(["ffmpeg", "-y", "-v", "error", *cut, "-i", a.video, "-vn", "-ac", "1", "-ar", "16000", wav])
            print(f"transcribing with {a.model} …", flush=True)
            r = subprocess.run([py, "-c", WORKER, wav, a.model, a.lang, a.prompt, mlenv.MODELS, str(a.start)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                common.die("whisper failed:\n" + "\n".join(r.stderr.strip().splitlines()[-12:]))
            data = json.loads(r.stdout.strip().splitlines()[-1])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"words:   {a.out}  ({len(data['words'])} words, {len(data['segments'])} lines)")
    for s in data["segments"][:6]:
        print(f"  {s['s']:7.2f}  {s['text']}")


if __name__ == "__main__":
    main()
