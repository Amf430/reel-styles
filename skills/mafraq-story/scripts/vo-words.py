"""Step 3 of the voice: word timings per line, for word-by-word captions.

Usage: uvx --python 3.11 --from mlx-whisper python -I vo-words.py <lines_dir> script.json words.json
script.json = {"01-n": "ثنتين وربع الفجر. فويس من عمك… في قروب العيلة.", ...}   (the text as it should be
              shown, spelled right; Whisper's spelling of dialect is not used, only its timings)
Optional 4th arg overrides.json = {"12-n": [[0.12, 0.61, ["الصبح…"]], [1.13, 2.35, ["عمك","يصب","فنجالين."]]]}
  for lines whose Whisper word count does not match: give each pause-chunk (line-local seconds, from
  vo-split.py minus the line's start) and its words; time is spread inside a chunk by letter count.

Output: {"01-n": [{"text","start","end"}, ...]} in line-local seconds (the line file starts at 0).
"""
import json, sys
import mlx_whisper

d, T, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
OV = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}

def spread(chunks):
    res = []
    for a, b, ws in chunks:
        L = [len(w) + 1 for w in ws]; tot = sum(L); c = a
        for w, l in zip(ws, L):
            dd = (b - a) * l / tot; res.append({"text": w, "start": round(c, 2), "end": round(c + dd, 2)}); c += dd
    return res

W = {}
for k, t in T.items():
    if k in OV:
        W[k] = spread(OV[k]); print(k, "override"); continue
    r = mlx_whisper.transcribe(f"{d}/{k}.wav", path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="ar",
                               word_timestamps=True, condition_on_previous_text=False)
    ww = [w for s in r["segments"] for w in s.get("words", [])]
    sw = t.split()
    if len(ww) == len(sw):
        W[k] = [{"text": a, "start": round(float(w["start"]), 2), "end": round(float(w["end"]), 2)} for a, w in zip(sw, ww)]
        how = "match"
    else:
        s0 = float(ww[0]["start"]) if ww else 0.1; e0 = float(ww[-1]["end"]) if ww else 0.5
        W[k] = spread([(s0, e0, sw)]); how = f"spread ({len(ww)} heard vs {len(sw)} written) - consider an override"
    if W[k] and W[k][0]["start"] < 0.12: W[k][0]["start"] = 0.12   # vo-cut.py adds 0.12 s of air
    print(k, how)
json.dump(W, open(out, "w"), ensure_ascii=False, indent=1)
