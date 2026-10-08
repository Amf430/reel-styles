#!/usr/bin/env python3
"""OpenStreetMap tiles for reel-map, fetched once and cached (run automatically before render/editor).

  maptiles.py job.json          resolve the places, download the tiles the camera needs, write the manifest

Places can be [lat, lon], a Google Maps link (…@24.8,46.6,15z or ?q=lat,lon) or a name ("حي النرجس، الرياض",
looked up with Nominatim). Tiles: © OpenStreetMap contributors (ODbL) — the scene always shows the credit.
Follows the OSM tile policy: identified User-Agent, local cache, no bulk downloads.
"""
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import mlenv  # noqa: E402

UA = "reel-styles/1.0 (+https://github.com/Amf430/reel-styles)"
TILE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
CACHE = os.path.join(mlenv.HOME, "tiles")


def _get(url, path=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ar,en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    return data


def resolve(place):
    """[lat, lon] from coordinates, a Google Maps URL, or a place name (Nominatim, cached)."""
    if isinstance(place, (list, tuple)):
        return [float(place[0]), float(place[1])]
    s = str(place)
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", s) or re.search(r"[?&](?:q|ll|query)=(-?\d+\.\d+),\s*(-?\d+\.\d+)", s) \
        or re.fullmatch(r"\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*", s)
    if m:
        return [float(m.group(1)), float(m.group(2))]
    os.makedirs(CACHE, exist_ok=True)
    gpath = os.path.join(CACHE, "geocode.json")
    cache = json.load(open(gpath)) if os.path.exists(gpath) else {}
    if s not in cache:
        # Nominatim stumbles on "حي …" and the Arabic comma; try the plain forms too.
        plain = re.sub(r"\s+", " ", re.sub(r"(^|\s)(حي|حى|شارع|طريق)\s+", " ", s.replace("،", " ").replace(",", " "))).strip()
        for q in dict.fromkeys([s, s.replace("،", ","), plain]):
            url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": q, "format": "json", "limit": 1})
            res = json.loads(_get(url))
            time.sleep(1.1)  # Nominatim: max 1 request/second
            if res:
                cache[s] = [float(res[0]["lat"]), float(res[0]["lon"])]
                break
        else:
            common.die(f"place not found: {s} — give coordinates or a Google Maps link")
        json.dump(cache, open(gpath, "w"), ensure_ascii=False, indent=1)
    return cache[s]


def world_px(lat, lon, z):
    """Web Mercator pixel coordinates at zoom z (256px tiles)."""
    s = 256 * 2 ** z
    x = (lon + 180) / 360 * s
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * s
    return x, y


def prepare(job):
    """Resolve places and fetch the tiles for every zoom level the camera passes through."""
    P = job["params"]
    center = resolve(P["center"])
    places = {"center": center}
    for i, r in enumerate(P.get("route", {}).get("points", []) or []):
        places[f"route{i}"] = resolve(r)
    for i, poi in enumerate(P.get("pois", []) or []):
        if poi.get("at") is not None:
            places[f"poi{i}"] = resolve(poi["at"])
    W, H = job["size"]
    vw, vh, _ = common.viewport(job)
    cam = P.get("camera", {})
    z0, z1 = float(cam.get("zoom_from", 11)), float(cam.get("zoom_to", 15))
    # Route endpoints must stay in view at the widest zoom: cover them too.
    pts = [center] + [v for k, v in places.items() if k.startswith(("route", "poi"))]
    levels = {}
    for L in range(int(math.floor(min(z0, z1))), int(math.ceil(max(z0, z1))) + 1):
        L = max(1, min(19, L))
        cx, cy = world_px(center[0], center[1], L)
        # View at this level (with margin for pans/route), plus every point of interest.
        half_w, half_h = vw * 0.8, vh * 0.8
        xs = [cx - half_w, cx + half_w] + [world_px(a, b, L)[0] for a, b in pts]
        ys = [cy - half_h, cy + half_h] + [world_px(a, b, L)[1] for a, b in pts]
        tx0, tx1 = int(min(xs) // 256), int(max(xs) // 256)
        ty0, ty1 = int(min(ys) // 256), int(max(ys) // 256)
        if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > 400:
            common.die(f"zoom {L} needs too many tiles — narrow the zoom range or bring the points closer")
        files = []
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                n = 2 ** L
                path = os.path.join(CACHE, str(L), str(tx % n), f"{ty}.png")
                if not os.path.exists(path):
                    _get(TILE.format(z=L, x=tx % n, y=ty), path)
                    time.sleep(0.05)
                files.append(path)
        levels[str(L)] = {"tx0": tx0, "ty0": ty0, "nx": tx1 - tx0 + 1, "ny": ty1 - ty0 + 1, "files": files}
    manifest = {"places": places, "levels": levels, "attribution": "© OpenStreetMap"}
    out = os.path.join(job["_dir"], ".reel_cache", f"map_{os.path.splitext(os.path.basename(job['_path']))[0]}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(manifest, open(out, "w"), ensure_ascii=False)
    job["map_manifest"] = out  # top-level: never saved into the job's params
    return out


if __name__ == "__main__":
    j = common.load_job(sys.argv[1])
    print(prepare(j))
