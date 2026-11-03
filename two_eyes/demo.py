"""Demo mode: offline Birim result shaped like a live run.

Turned on by DEMO_MODE=1, or whenever a live run could not work here (no Meta Model API key,
or Earth Engine not usable). No Earth Engine and no Meta API calls are made in demo mode.

The satellite scar outlines and SAM boxes come from a recorded Meta SAM 3.1 run on the bundled
Birim Sentinel tiles (28 Oct 2026), cached under two_eyes/assets/recorded/. Lead area 17.0 ha and
~19 km upstream stay from the prior Earth Engine catchment run (visual-tile px are not hectare).
"""
import json
import os
import time

import numpy as np
from PIL import Image

from . import card
from . import config as C

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
RECORDED = os.path.join(ASSETS, "recorded")

# The recorded run (28 Oct 2026, see README "End-to-end demo"): N4 bridge over the Birim.
# Lead scar 17.0 ha, ~19 km upstream. SAM boxes/mask from recorded Meta run under assets/recorded/.
SPOT = {"name": "Birim, N4 bridge", "lat": 6.28442, "lon": -0.46118}
SCAR = {"lat": 6.45440, "lon": -0.48330, "area_ha": 17.0, "distance_km": 19.0,
        "ndvi_before": 0.71, "ndvi_after": 0.17, "cloudy": 0.06}
CREDIT = "Photo: Goldenwabbit, Wikimedia Commons, CC BY-SA 4.0"
DATE = "2026-10-28"
OUTLINES = "SAM 3.1 box prompts (recorded Meta run 28 Oct 2026)"
COPERNICUS_CREDIT = "Contains modified Copernicus Sentinel data 2023, 2026"
OUT_DIR = "two_eyes_out"


def _load_meta():
    path = os.path.join(RECORDED, "birim_meta.json")
    with open(path) as f:
        return json.load(f)


def is_demo_mode():
    """True when the live pipeline can't run here: DEMO_MODE=1, no Meta key, or Earth Engine unavailable."""
    if os.environ.get("DEMO_MODE") == "1":
        return True
    if not os.environ.get("MODEL_API_KEY"):
        return True
    return not _ee_ready()


def _ee_ready():
    try:
        import ee
        ee.Number(1).getInfo()
        return True
    except Exception:
        return False


def _asset(name):
    return os.path.join(ASSETS, name)


def _recorded_mask():
    """Boolean SAM mask from the recorded Meta run (PNG; .npy is gitignored)."""
    png = os.path.join(RECORDED, "sam_mask.png")
    if os.path.isfile(png):
        arr = np.asarray(Image.open(png).convert("L"))
        return arr > 127
    # Fallback: yellow-paint NDVI outline if recorded mask missing
    rgb = np.asarray(Image.open(_asset("sat_after.jpg")).convert("RGB"))
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    return (r > 150) & (g > 120) & (b < 110) & (r - b > 70)


def _recorded_boxes():
    meta = _load_meta()
    return [list(b) for b in meta.get("sam_boxes") or []]


def _sat_after_display():
    """Prefer neutralized after tile (no illustrative yellow paint) for honesty."""
    neut = os.path.join(RECORDED, "sat_after_neutral.jpg")
    if os.path.isfile(neut):
        return np.asarray(Image.open(neut).convert("RGB"))
    return np.asarray(Image.open(_asset("sat_after.jpg")).convert("RGB"))


def demo_report():
    """Full report dict shaped like pipeline.run, built from the recorded Birim Meta run."""
    sat_before = np.asarray(Image.open(_asset("sat_before.jpg")).convert("RGB"))
    sat_after = _sat_after_display()
    meta = _load_meta()
    boxes = _recorded_boxes()
    mask = _recorded_mask()
    # Resize mask if tile size differs
    if mask.shape[:2] != sat_after.shape[:2]:
        mask = np.asarray(
            Image.fromarray(mask.astype(np.uint8) * 255).resize(
                (sat_after.shape[1], sat_after.shape[0]), Image.NEAREST)
        ) > 127
    muse = meta.get("muse") or {}
    n_refined = int(meta.get("sam_refined") or len(boxes) or 0)
    return {
        "date": DATE,
        "demo": True,
        "recorded_meta": True,
        "credit_sat": COPERNICUS_CREDIT,
        "spot": dict(SPOT),
        "periods": {"before": C.BEFORE, "now": C.AFTER},
        "status": "SCAR",
        "catchment": {"spot_basin": None, "basins_searched": 74, "km2_searched": 307,
                      "km2_upstream_total": 1620, "cloudy_share": 0.06},
        "candidates": [
            {"lat": SCAR["lat"], "lon": SCAR["lon"], "status": "SCAR",
             "area_ha": SCAR["area_ha"], "cloudy": SCAR["cloudy"]},
            {"lat": 6.41221, "lon": -0.50110, "status": "NONE", "area_ha": 0.0, "cloudy": 0.06},
            {"lat": 6.37650, "lon": -0.44205, "status": "NONE", "area_ha": 0.0, "cloudy": 0.07},
        ],
        "scar": {"lat": SCAR["lat"], "lon": SCAR["lon"], "area_ha": SCAR["area_ha"],
                 "cloudy": SCAR["cloudy"], "outline_method": OUTLINES,
                 "boxes_illustrative": False,
                 "boxes_recorded_meta": True,
                 "ndvi_before": SCAR["ndvi_before"], "ndvi_after": SCAR["ndvi_after"],
                 "distance_km": SCAR["distance_km"], "rgb_before": sat_before,
                 "rgb_after": sat_after, "mask": mask,
                 "sam_boxes": boxes},
        "checks": {
            "A": {"pass": True, "area_ha": SCAR["area_ha"], "outline": OUTLINES},
            "B": {"pass": True},
            "C": {"pass": None, "note": "Outside the RADD forest baseline; Hansen loss data ends 2025."},
            "D": {"pass": True, "note": "Open-water pits inside the scar; WRI driver: hard commodities."},
            "E": {"pass": None, "note": "River too narrow at this point for the JRC water mask."},
            "F": {"pass": False},
        },
        "ground": {"water_found": True, "muddy": True,
                   "label": muse.get("label") or "muddy brown",
                   "b_star": 34.6,
                   "label_source": muse.get("label_source") or "Muse Spark (image understanding); recorded Meta run",
                   "muse_quote": muse.get("label") or "muddy brown",
                   "muse_reason": muse.get("reason"),
                   # Water mask on the still is an illustrative painted overlay for the card, not live SAM.
                   "method": "Recorded Muse Spark colour on bridge still (Meta run 28 Oct 2026); water mask on still is illustrative painted overlay for the card",
                   "frames_used": 10, "frame": _frame(), "still": _still(), "credit": CREDIT,
                   # Median RGB of the painted water pixels in the bundled photo (not a live measurement).
                   "rgb": [217, 190, 158]},
        "meta": {"sam_refined": n_refined, "muse_quote": muse.get("label") or "muddy brown",
                 "recorded": True, "recorded_date": DATE,
                 "api_calls_recorded": meta.get("api_calls_total"),
                 "note": meta.get("note")},
        "scar_judge": _scar_judge_summary(),
    }


def _scar_judge_summary():
    path = os.path.join(RECORDED, "scar_judge_score.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        d = json.load(f)
    return {"n": d.get("n"), "correct": d.get("correct"), "hit_rate": d.get("hit_rate"),
            "note": d.get("note")}


def _frame():
    return np.asarray(Image.open(_asset("bridge.jpg")).convert("RGB").resize((720, 404)))


def _still():
    return np.asarray(Image.open(_asset("hero_mask.jpg")).convert("RGB"))


def run(lat, lon, name=None, clip=None, clip_credit=None, use_llm=False,
        out_dir=OUT_DIR, log=print):
    """Demo twin of pipeline.run: card + share from the recorded Birim Meta cache. Offline."""
    from . import pipeline
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    same_place = (name == SPOT["name"] and round(lat, 4) == round(SPOT["lat"], 4)
                  and round(lon, 4) == round(SPOT["lon"], 4))
    if same_place:
        log("Demo mode: recorded Meta run for %s (28 Oct 2026); no live Earth Engine or Meta API calls."
            % SPOT["name"])
    else:
        log("Demo mode: this point was not analysed live; showing the recorded %s Meta run from "
            "28 Oct 2026 (no Earth Engine or Meta API calls)." % SPOT["name"])
    if clip:
        log("Demo mode: the clip is not analysed here (recorded result shown instead).")

    r = demo_report()
    r["headline"] = card.headline(r)
    tc = time.time()
    r["card_png"] = card.render(r, os.path.join(out_dir, "evidence_card.png"))
    # Card text: Muse writer under rules when use_llm, else template; demo defaults template
    # so pytest stays offline. Live path uses card_muse via card.share_text.
    r["share_text"] = card.share_text(r, use_llm=False)
    timings = {"demo": True, "cached_from": "recorded Meta run 28 Oct 2026",
               "card_s": round(time.time() - tc, 1), "total_s": round(time.time() - t0, 1)}
    r["timings"] = timings
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(pipeline.public(r), f, indent=2, default=pipeline._json_default)
    log("Done (demo): " + " ".join(r["headline"]))
    log("Timings: " + json.dumps(timings))
    return r
