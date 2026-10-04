#!/usr/bin/env python3
"""Render a style job (or every job of a project) to ProRes layers and a preview.

  render.py project.json                  every job + one preview of the whole video with all layers
  render.py project.json --job cards      one job of the project (by name or file stem)
  render.py JOB.json                      full render: layer .mov + preview .mp4
  render.py JOB.json --stills 1.2,3.5     a few stills (+ composited over the video) to check quickly
  render.py JOB.json --range 2,4          only part of the job's range
  render.py JOB.json --mblur 4            motion blur: 4 sub-frames over a 180° shutter
  render.py JOB.json --workers 6          parallel browsers (default: 4)
"""
import argparse
import glob
import json
import multiprocessing as mp
import os
import shutil
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def _worker(args):
    base, vp, scale, jobs, alpha, want_meta = args
    from playwright.sync_api import sync_playwright
    meta = None
    with sync_playwright() as p:
        exe = common.chromium_path()
        browser = p.chromium.launch(executable_path=exe, args=common.launch_args()) if exe else p.chromium.launch(args=common.launch_args())
        page = browser.new_page(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=scale)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.goto(f"{base}/scene?render=1")
        try:
            page.wait_for_function("window.__reel && window.__reel.ready", timeout=60000)
            page.evaluate("window.__reel.ready")
        except Exception:
            raise RuntimeError("scene failed to load:\n" + "\n".join(errors[-10:]))
        for t, frame_url, out in jobs:
            page.evaluate("([t,u]) => window.__reel.frame(t,u)", [t, frame_url])
            page.screenshot(path=out, omit_background=alpha, type="png")
        if want_meta:
            meta = page.evaluate("window.__reel.meta()")
        if errors:
            print("scene console errors:\n  " + "\n  ".join(errors[-5:]), file=sys.stderr)
        browser.close()
    return meta


def extract_frames(job, times, d, which=True):
    """Frames handed to the scene per t: the footage (glass) or the keyed subject with alpha (studio3d shadow)."""
    os.makedirs(d, exist_ok=True)
    if which == "subject":
        sub = job["subject"]["layer"]
        src = sub if os.path.isabs(sub) else os.path.join(job["_dir"], sub)
        with open(os.path.splitext(src)[0] + ".json") as f:
            offset = json.load(f).get("start", 0)
        ext, vf, q = "png", f"fps={common.fps_arg(job['fps'])},scale=iw/2:ih/2,format=rgba", []
    else:
        src, offset = job["video"], 0
        w, h = job["size"]
        ext, vf, q = "jpg", f"fps={common.fps_arg(job['fps'])},scale={w}:{h}", ["-q:v", "2"]
    t0, t1 = times[0] - offset, times[-1] - offset
    common.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0, t0):.4f}", "-i", src, "-t", f"{t1 - t0 + 2 / job['fps']:.4f}",
                "-vf", vf, *q, os.path.join(d, f"s_%06d.{ext}")])
    have = sorted(glob.glob(os.path.join(d, f"s_*.{ext}")))
    return [have[max(0, min(len(have) - 1, int(round((t - offset - max(0, t0)) * job["fps"]))))] for t in times]


def render_frames(job, times, outdir, workers, alpha, needs_frames):
    os.makedirs(outdir, exist_ok=True)
    srv, base = common.serve(job)
    vw, vh, scale = common.viewport(job)
    frames = [None] * len(times)
    if (needs_frames == "subject" and job.get("subject")) or (needs_frames is True and job.get("video")):
        frames = [f"{base}/f{urllib.parse.quote(p)}" for p in extract_frames(job, times, os.path.join(outdir, "_src"), needs_frames)]
    items = [(t, frames[i], os.path.join(outdir, f"f_{i:06d}.png")) for i, t in enumerate(times)]
    n = max(1, min(workers, len(items) // 8 or 1))
    chunks = [items[i::n] for i in range(n)]
    t_start = time.time()
    with mp.get_context("spawn").Pool(n) as pool:
        metas = pool.map(_worker, [(base, (vw, vh), scale, c, alpha, i == 0) for i, c in enumerate(chunks)])
    srv.shutdown()
    print(f"rendered {len(items)} frames in {time.time() - t_start:.1f}s ({n} workers)")
    return metas[0] or {}


def encode(job, frames_dir, out_path, alpha, fps, mblur=1):
    pat = os.path.join(frames_dir, "f_%06d.png")
    vf = []
    if mblur > 1:
        vf.append(f"tmix=frames={mblur}:weights=1")
        vf.append(f"select='not(mod(n+1\\,{mblur}))'")
        vf.append(f"setpts=N/({common.fps_arg(fps)})/TB")
    w, h = job["size"]
    vf.append(f"scale={w}:{h}:flags=lanczos")
    codec = ["-c:v", "prores_ks", "-profile:v", "4444" if alpha else "3", "-vendor", "apl0",
             "-pix_fmt", "yuva444p10le" if alpha else "yuv422p10le"]
    in_rate = fps * mblur
    common.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(in_rate), "-i", pat, "-vf", ",".join(vf), *codec,
                "-r", common.fps_arg(fps), out_path])


def preview(job, layer, out_mp4, alpha):
    """Composite the layer over the source segment (with its audio) for review."""
    if not job.get("video"):
        common.run(["ffmpeg", "-y", "-v", "error", "-i", layer, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out_mp4])
        return
    t0, t1 = job["start"], job["end"]
    w, h = job["size"]
    if alpha:
        fc = f"[0:v]scale={w}:{h},setpts=PTS-STARTPTS[b];[1:v]setpts=PTS-STARTPTS[o];[b][o]overlay=0:0:shortest=1,format=yuv420p[v]"
    else:
        fc = f"[1:v]scale={w}:{h},format=yuv420p[v]"
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.4f}", "-t", f"{t1 - t0:.4f}", "-i", job["video"], "-i", layer,
           "-filter_complex", fc, "-map", "[v]"]
    if job.get("_video_info", {}).get("has_audio"):
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", out_mp4]
    common.run(cmd)


def stills(job, times, alpha, needs_frames, workers):
    d = os.path.join(job["out"], "stills")
    tmp = os.path.join(d, "_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    meta = render_frames(job, times, tmp, workers, alpha, needs_frames)
    outs = []
    for i, t in enumerate(times):
        png = os.path.join(d, f"t{t:07.3f}.png")
        shutil.move(os.path.join(tmp, f"f_{i:06d}.png"), png)
        outs.append(png)
        if alpha and job.get("video"):
            comp = png.replace(".png", "_comp.jpg")
            w, h = job["size"]
            common.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.4f}", "-i", job["video"], "-i", png, "-frames:v", "1",
                        "-filter_complex", f"[0:v]scale={w}:{h}[b];[1:v]scale={w}:{h}[o];[b][o]overlay", "-q:v", "2", comp])
            outs[-1] = comp
        elif not alpha and job.get("subject"):
            comp = png.replace(".png", "_comp.jpg")
            sub = job["subject"]["layer"]
            src = sub if os.path.isabs(sub) else os.path.join(job["_dir"], sub)
            with open(os.path.splitext(src)[0] + ".json") as f:
                st = json.load(f)
            W, H = job["size"]
            x, y, w, h = common.subject_rect(job, meta)
            pw, ph = int(round(w * W)) // 2 * 2, int(round(h * H)) // 2 * 2
            common.run(["ffmpeg", "-y", "-v", "error", "-i", png, "-ss", f"{max(0, t - st.get('start', 0)):.4f}", "-i", src,
                        "-frames:v", "1", "-filter_complex",
                        f"[0:v]scale={W}:{H}[b];[1:v]scale={pw}:{ph}[s];[b][s]overlay={int(x * W)}:{int(y * H)}", "-q:v", "2", comp])
            outs[-1] = comp
    shutil.rmtree(tmp, ignore_errors=True)
    if meta:
        with open(os.path.join(d, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
    print("\n".join(outs))
    return outs


def subject_layers(job, meta, plate, name, dur, no_preview):
    """Plate styles: place the keyed subject, build its floor shadow, and stack a preview."""
    import composite
    import shadow
    sub = job["subject"]
    src = sub["layer"] if os.path.isabs(sub["layer"]) else os.path.join(job["_dir"], sub["layer"])
    rect = common.subject_rect(job, meta)
    out = job["out"]
    placed = composite.place(src, rect, job["size"], os.path.join(out, name + "_subject.mov"), dur)
    layers = [(plate, None)]
    sh_cfg = sub.get("shadow", {})
    if sh_cfg is not False and meta.get("shadow_in_plate") is not True:
        sh = shadow.build(src, os.path.join(out, name + "_shadow.mov"), job["size"], rect, dur=dur,
                          **{k: v for k, v in sh_cfg.items() if k in ("opacity", "length", "skew", "blur", "contact")})
        layers.append((sh, None))
        print(f"shadow:  {sh}")
    layers.append((placed, None))
    print(f"subject: {placed}")
    if not no_preview:
        with open(os.path.splitext(src)[0] + ".json") as f:
            st = json.load(f)
        pv = composite.stack(os.path.join(out, name + "_preview.mp4"), job["size"], job["fps"], dur, layers,
                             audio=st.get("video"), audio_start=st.get("start", 0))
        print(f"preview: {pv}")
        return pv
    return None


def style_output(job):
    with open(os.path.join(job["_style_dir"], "presets.json")) as f:
        pr = json.load(f)
    return pr.get("output", "alpha") == "alpha", pr.get("needs_frames", False)


def render_job(job, a):
    """Full render of one job; returns (layer, meta)."""
    alpha, needs_frames = style_output(job)
    os.makedirs(job["out"], exist_ok=True)
    t0, t1 = job["start"], job["end"]
    if a.range:
        t0, t1 = [float(x) for x in a.range.split(",")]
    fps, n = job["fps"], int(round((t1 - t0) * job["fps"]))
    sub = max(1, a.mblur)
    shutter = 0.5 / fps
    times = [t0 + i / fps + (k / sub) * shutter for i in range(n) for k in range(sub)]

    frames_dir = os.path.join(job["out"], "_frames")
    shutil.rmtree(frames_dir, ignore_errors=True)
    meta = render_frames(job, times, frames_dir, a.workers, alpha, needs_frames)

    name = f"{job.get('name') or job['style']}_{common.timecode(t0)}"
    layer = os.path.join(job["out"], name + ".mov")
    encode(job, frames_dir, layer, alpha, fps, sub)
    meta.update({"layer": layer, "start": t0, "end": t1, "fps": fps, "size": job["size"], "alpha": alpha, "name": name})
    with open(os.path.join(job["out"], name + ".meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"layer:   {layer}  (place at {t0:.3f}s on the timeline)")
    if not alpha and job.get("subject"):
        meta["preview"] = subject_layers(job, meta, layer, name, t1 - t0, a.no_preview)
    elif not a.no_preview:
        pv = os.path.join(job["out"], name + "_preview.mp4")
        preview(dict(job, start=t0, end=t1), layer, pv, alpha)
        meta["preview"] = pv
        print(f"preview: {pv}")
    if not a.keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)
    return layer, meta


def project_preview(project, results, out):
    """The whole video with every job's result laid over it at its own time (with the original audio)."""
    v = project["video"]
    info = common.probe(v)
    W, H = info["w"], info["h"]
    inputs, parts, last = ["-i", v], [f"[0:v]scale={W}:{H},format=yuv420p[b0]"], "b0"
    for k, (job, layer, meta) in enumerate(results, start=1):
        src = layer if meta.get("alpha") else meta.get("preview", layer)
        inputs += ["-itsoffset", f"{meta['start']:.4f}", "-i", src]
        parts.append(f"[{k}:v]scale={W}:{H},format=yuva420p[l{k}]")
        parts.append(f"[{last}][l{k}]overlay=eof_action=pass:enable='between(t,{meta['start']:.4f},{meta['end']:.4f})'[b{k}]")
        last = f"b{k}"
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(parts), "-map", f"[{last}]"]
    if info["has_audio"]:
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"]
    common.run(cmd + ["-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", help="project.json or a job .json")
    ap.add_argument("--job", dest="only", help="project mode: render only this job (name or file stem)")
    ap.add_argument("--stills", help="comma-separated times (s) on the video timeline")
    ap.add_argument("--range", help="a,b sub-range to render")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--mblur", type=int, default=1, help="sub-frames per frame for motion blur")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--keep-frames", action="store_true")
    a = ap.parse_args()
    common.need("ffmpeg")

    project = common.load_project(a.job)
    jobs = project["jobs"]
    if a.only:
        jobs = [j for j in jobs if a.only in (j.get("name"), os.path.splitext(os.path.basename(j["_path"]))[0])]
        if not jobs:
            common.die(f"no job '{a.only}' in {a.job}")

    if a.stills:
        for job in jobs:
            alpha, needs_frames = style_output(job)
            os.makedirs(job["out"], exist_ok=True)
            stills(job, [float(x) for x in a.stills.split(",")], alpha, needs_frames, a.workers)
        return

    results = []
    for job in jobs:
        layer, meta = render_job(job, a)
        results.append((job, layer, meta))
    if len(project["jobs"]) > 1 and not a.only and not a.no_preview and project.get("video"):
        out = os.path.join(project["_dir"], "out", "project_preview.mp4")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        print(f"project: {project_preview(project, results, out)}")


if __name__ == "__main__":
    main()
