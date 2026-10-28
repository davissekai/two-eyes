"""Bridge point (+ optional clip) -> evidence report and card."""
import datetime as dt
import hashlib
import json
import math
import os
import pickle
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from . import config as C
from . import card, checks, demo, sky
from .trace import Basins, check_b


def km(lat1, lon1, lat2, lon2):
    return 6371 * math.hypot(math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2)),
                             math.radians(lat2 - lat1))


def nearest_upstream(basins, start, cap_km2=C.MAX_SEARCH_KM2):
    """Upstream basins in breadth-first order (closest first), stopping at cap_km2."""
    up_index = {}
    for b, p in basins.P.items():
        up_index.setdefault(p["NEXT_DOWN"], []).append(b)
    order, seen, q, area = [], {start}, deque([start]), 0.0
    while q:
        b = q.popleft()
        if area + basins.P[b]["SUB_AREA"] > cap_km2 and order:
            break
        order.append(b)
        area += basins.P[b]["SUB_AREA"]
        for u in up_index.get(b, []):
            if u not in seen:
                seen.add(u)
                q.append(u)
    total = basins.area_km2(basins.upstream(start))
    return order, area, total


def _inside(prev, lat, lon):
    for p in prev:
        if p.get("all_scars") is None:
            continue
        r, c = p["grid"].rc(lat, lon)
        m = p["all_scars"]
        if 0 <= r < m.shape[0] and 0 <= c < m.shape[1] and m[r, c]:
            return True
    return False


CACHE_DIR = os.environ.get("TWO_EYES_CACHE", os.path.expanduser("~/.two_eyes_cache"))
CACHE_VERSION = "v2"   # bump when the sky pipeline changes


def _cache_key(lat, lon, focus):
    k = json.dumps([CACHE_VERSION, round(lat, 5), round(lon, 5), focus, C.BEFORE, C.AFTER, C.NDVI_FOREST,
                    C.NDVI_DROP, C.MIN_SCAR_HA, C.MAX_CLOUDY, C.CS_CLEAR, C.MAX_CANDIDATES])
    return os.path.join(CACHE_DIR, hashlib.sha1(k.encode()).hexdigest()[:16] + ".pkl")


def sky_part(bridge_lat, bridge_lon, focus=None, use_sam=True, log=print, timings=None):
    """Everything that depends only on the place and the fixed dates (checks A-F). Cacheable."""
    t = timings if timings is not None else {}
    clock = time.time()
    r = {"checks": {}, "candidates": []}
    log("Tracing the catchment above the bridge (HydroBASINS level 12)...")
    basins = Basins(bridge_lat, bridge_lon)
    bb = basins.basin_of(bridge_lat, bridge_lon)
    ids, searched, total = nearest_upstream(basins, bb)
    r["catchment"] = {"bridge_basin": bb, "basins_searched": len(ids), "km2_searched": round(searched),
                      "km2_upstream_total": round(total)}
    t["catchment_s"] = round(time.time() - clock, 1); clock = time.time()

    if focus:
        cands, cloud = [{"lat": focus[0], "lon": focus[1], "area_ha_ndvi": None}], None
    else:
        log(f"Searching {searched:.0f} km² upstream for new scars (Sentinel-2, NDVI drop)...")
        cands, cloud = sky.find_candidates(basins.geometry(ids), limit=C.MAX_CANDIDATES * 2)
        r["catchment"]["cloudy_share"] = round(cloud, 3)
    t["search_s"] = round(time.time() - clock, 1); clock = time.time()

    todo = cands[:C.MAX_CANDIDATES]
    log(f"{len(cands)} candidate patch(es). Refining {len(todo)} with SAM 3.1, in parallel...")
    with ThreadPoolExecutor(max_workers=max(1, len(todo))) as ex:
        results = list(ex.map(lambda c: sky.analyse_box(c["lat"], c["lon"], use_sam=use_sam), todo))
    boxes = []
    for cnd, bx in zip(todo, results):
        if _inside(boxes, cnd["lat"], cnd["lon"]):        # same scar seen from a neighbouring box
            continue
        boxes.append(bx)
        r["candidates"].append({"lat": cnd["lat"], "lon": cnd["lon"], "status": bx["status"],
                                "area_ha": bx["area_ha"], "cloudy": bx["cloudy"]})
        log(f"  {cnd['lat']:.5f}, {cnd['lon']:.5f}: {bx['status']} {bx['area_ha']} ha")
    t["refine_s"] = round(time.time() - clock, 1); clock = time.time()

    scars = [b for b in boxes if b["status"] == "SCAR"]
    if not scars:
        all_cloudy = bool(boxes) and all(b["status"] == "CLOUDY" for b in boxes)
        no_view = not boxes and cloud is not None and cloud > C.MAX_CLOUDY
        r["status"] = "CLOUDY" if (all_cloudy or no_view) else "NONE"
        r["checks"]["A"] = {"pass": False if r["status"] == "NONE" else None}
        r["scar"] = {"rgb_before": boxes[0]["rgb_before"], "rgb_after": boxes[0]["rgb_after"]} if boxes else {}
        return r
    s = max(scars, key=lambda b: b["area_ha"])
    clat, clon = s["centroid"]
    r["status"] = "SCAR"
    r["scar"] = {"lat": clat, "lon": clon, "area_ha": s["area_ha"], "cloudy": s["cloudy"],
                 "outline_method": s["outline_method"], "ndvi_before": s["ndvi_before"],
                 "ndvi_after": s["ndvi_after"], "distance_km": km(bridge_lat, bridge_lon, clat, clon),
                 "rgb_before": s["rgb_before"], "rgb_after": s["rgb_after"], "mask": s["mask"]}
    r["checks"]["A"] = {"pass": True, "area_ha": s["area_ha"], "outline": s["outline_method"]}
    log("Checks B-F, in parallel...")
    geom = sky.scar_geometry(s)
    scar_basin = basins.basin_of(clat, clon)

    def safe(fn):
        try:
            return fn()
        except Exception as ex:
            return {"pass": None, "error": f"{type(ex).__name__}: {ex}"[:300]}
    jobs = {"B": lambda: check_b(basins, bb, clat, clon),
            "C": lambda: checks.check_c(geom, s["area_ha"]),
            "D": lambda: checks.check_d(geom),
            "E": lambda: checks.check_e(basins, scar_basin),
            "F": lambda: checks.check_f(geom)}
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(safe, fn) for k, fn in jobs.items()}
        for k in "BCDEF":
            r["checks"][k] = futs[k].result()
    t["checks_s"] = round(time.time() - clock, 1)
    return r


def run(bridge_lat, bridge_lon, name=None, clip=None, clip_credit=None, focus=None, use_sam=True, use_llm=True,
        out_dir="two_eyes_out", log=print, use_cache=True):
    """Run every check for a filming point.

    focus: optional (lat, lon) of a known scar to analyse instead of searching the whole catchment.
    The satellite part depends only on the place and the fixed dates, so it is cached on disk; the
    citizen's clip is always analysed fresh, in parallel with the satellite work.
    """
    if demo.is_demo_mode():
        return demo.run(bridge_lat, bridge_lon, name=name, clip=clip, clip_credit=clip_credit,
                        out_dir=out_dir, log=log)
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    timings = {}
    pool = ThreadPoolExecutor(max_workers=2)

    def ground_job():
        tg = time.time()
        try:
            from . import ground
            g = ground.analyse_clip(clip, use_sam=use_sam, use_vlm=use_llm)
            g["credit"] = clip_credit
        except Exception as ex:
            g = {"water_found": False, "error": f"{type(ex).__name__}: {ex}"[:300]}
        timings["ground_s"] = round(time.time() - tg, 1)
        return g
    gfut = pool.submit(ground_job) if clip else None
    if clip:
        log("Ground eye: SAM 3.1 on the clip (running alongside the satellite checks)...")

    path = _cache_key(bridge_lat, bridge_lon, focus)
    sky_r = None
    if use_cache and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                sky_r = pickle.load(f)
            log("Satellite checks: cached result for this place (same dates, same cut-offs).")
            timings["sky_cached"] = True
        except Exception:
            sky_r = None
    if sky_r is None:
        sky_r = sky_part(bridge_lat, bridge_lon, focus=focus, use_sam=use_sam, log=log, timings=timings)
        if use_cache:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(sky_r, f)

    r = {"date": dt.date.today().isoformat(), "bridge": {"lat": bridge_lat, "lon": bridge_lon, "name": name},
         "periods": {"before": C.BEFORE, "now": C.AFTER}}
    r.update(sky_r)
    if gfut:
        r["ground"] = gfut.result()
    pool.shutdown(wait=False)

    tc = time.time()
    r["headline"] = card.headline(r)
    with ThreadPoolExecutor(max_workers=1) as ex:     # LLM share text overlaps the card render
        share = ex.submit(card.share_text, r, use_llm)
        r["card_png"] = card.render(r, os.path.join(out_dir, "evidence_card.png"))   # matplotlib: main thread
        r["share_text"] = share.result()
    timings["card_s"] = round(time.time() - tc, 1)
    timings["total_s"] = round(time.time() - t0, 1)
    r["timings"] = timings
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(public(r), f, indent=2, default=_json_default)
    log("Done: " + " ".join(r["headline"]))
    log("Timings: " + json.dumps(timings))
    return r


def warm(bridges, log=print):
    """Pre-compute the satellite part for demo bridges so live runs only wait for the clip.
    No-op in demo mode (when Earth Engine is not available, for example)."""
    if demo.is_demo_mode():
        log("Warm skipped: demo mode (no Earth Engine or Meta API calls).")
        return
    for lat, lon in bridges:
        try:
            t = time.time()
            run(lat, lon, use_llm=False, log=lambda *a: None)
            log(f"warmed {lat}, {lon} in {time.time() - t:.0f}s")
        except Exception as ex:
            log(f"warm skipped {lat}, {lon}: {type(ex).__name__}: {ex}")


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def public(r):
    """Report without image arrays (for JSON / sharing)."""
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if not isinstance(v, np.ndarray) and k != "grid"}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    return strip(r)
