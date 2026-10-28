"""Demo mode: an offline, cached Birim / Atewa result with the same shape as a live run.

Turned on by DEMO_MODE=1, or whenever a live run could not work here (no Meta Model API key,
or Earth Engine not usable). No Earth Engine and no Meta API calls are made in demo mode.
"""
import datetime as dt
import json
import os
import time

import numpy as np
from PIL import Image

from . import card
from . import config as C
from . import sky

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# The recorded run (28 Oct 2026, see README): N4 bridge over the Birim, lead scar 17 ha / ~19 km upstream.
BRIDGE = {"name": "Birim, N4 bridge", "lat": 6.28442, "lon": -0.46118}
SCAR = {"lat": 6.45440, "lon": -0.48330, "area_ha": 17.0, "distance_km": 19.0,
        "ndvi_before": 0.71, "ndvi_after": 0.17, "cloudy": 0.06}
OUTLINES = "SAM 3.1 box prompts"
CREDIT = "Stand-in view: Pra River from Beposo bridge, 2014. Wikimedia Commons, CC BY-SA 3.0"
OUT_DIR = "two_eyes_out"


def is_demo_mode():
    """True when the live pipeline can't run here: DEMO_MODE=1, no Meta key, or Earth Engine unavailable."""
    if os.environ.get("DEMO_MODE") == "1":
        return True
    if not os.environ.get("MODEL_API_KEY"):          # a live run needs Meta (SAM 3.1 / Muse Spark)
        return True
    return not _ee_ready()


def _ee_ready():
    """Cheap Earth Engine probe: fails immediately when the library is missing or not initialised."""
    try:
        import ee
        ee.Number(1).getInfo()
        return True
    except Exception:
        return False


def _asset(name):
    return os.path.join(ASSETS, name)


def _scar_mask(rgb):
    """Boolean mask of the highlighted clearings in the recorded "after" image (yellow pixels)."""
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    return (r > 150) & (g > 120) & (b < 110) & (r - b > 70)


def _sam_boxes(rgb, n=3, pad=4):
    """Plausible SAM 3.1 refined boxes (l, t, r, b) around the yellow scar mask components."""
    mask = _scar_mask(rgb)
    _, lab = sky.patches(mask)
    h, wD = mask.shape
    boxes = []
    comps = sorted((i for i in range(1, lab.max() + 1) if (lab == i).sum() >= 3),
                   key=lambda i: int((lab == i).sum()), reverse=True)
    for i in comps[:n]:
        ys, xs = np.where(lab == i)
        if len(xs) < 3:
            continue
        l, t = max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0)
        r, b = min(int(xs.max()) + pad, wD - 1), min(int(ys.max()) + pad, h - 1)
        boxes.append([l, t, r, b])
    return boxes or [[int(wD * 0.4) - 20, int(h * 0.4) - 20, int(wD * 0.4) + 20, int(h * 0.4) + 20]]


def demo_report():
    """A full report dict shaped like pipeline.run's output, built only from the recorded Birim run."""
    sat_before = np.asarray(Image.open(_asset("sat_before.jpg")).convert("RGB"))
    sat_after = np.asarray(Image.open(_asset("sat_after.jpg")).convert("RGB"))
    return {
        "date": dt.date.today().isoformat(),
        "demo": True,
        "bridge": dict(BRIDGE),
        "periods": {"before": C.BEFORE, "now": C.AFTER},
        "status": "SCAR",
        "catchment": {"bridge_basin": None, "basins_searched": 74, "km2_searched": 307,
                      "km2_upstream_total": 1620, "cloudy_share": 0.06},
        "candidates": [
            {"lat": SCAR["lat"], "lon": SCAR["lon"], "status": "SCAR",
             "area_ha": SCAR["area_ha"], "cloudy": SCAR["cloudy"]},
            {"lat": 6.41221, "lon": -0.50110, "status": "NONE", "area_ha": 0.0, "cloudy": 0.06},
            {"lat": 6.37650, "lon": -0.44205, "status": "NONE", "area_ha": 0.0, "cloudy": 0.07},
        ],
        "scar": {"lat": SCAR["lat"], "lon": SCAR["lon"], "area_ha": SCAR["area_ha"],
                 "cloudy": SCAR["cloudy"], "outline_method": OUTLINES,
                 "ndvi_before": SCAR["ndvi_before"], "ndvi_after": SCAR["ndvi_after"],
                 "distance_km": SCAR["distance_km"], "rgb_before": sat_before,
                 "rgb_after": sat_after, "mask": _scar_mask(sat_after),
                 "sam_boxes": _sam_boxes(sat_after)},
        "checks": {
            "A": {"pass": True, "area_ha": SCAR["area_ha"], "outline": OUTLINES},
            "B": {"pass": True},
            "C": {"pass": None, "note": "Outside the RADD forest baseline; Hansen loss data ends 2025."},
            "D": {"pass": True, "note": "Open-water pits inside the scar; WRI driver: hard commodities."},
            "E": {"pass": None, "note": "River too narrow at this point for the JRC water mask."},
            "F": {"pass": False},
        },
        "ground": {"water_found": True, "muddy": True, "label": "muddy brown", "b_star": 34.6,
                   "label_source": "Muse Spark (image understanding); recorded run",
                   "muse_quote": "muddy brown",
                   "method": "SAM 3.1 (video, concept prompt 'river water'); recorded run",
                   "frames_used": 10, "still": _still(), "credit": CREDIT},
        "meta": {"sam_refined": 8, "muse_quote": "muddy brown"},
    }


def _still():
    return np.asarray(Image.open(_asset("hero_mask.jpg")).convert("RGB"))


def run(bridge_lat, bridge_lon, name=None, clip=None, clip_credit=None, use_llm=False,
        out_dir=OUT_DIR, log=print):
    """The demo twin of pipeline.run: renders the card + share text from the cached report. Offline.

    The card always shows the cached Birim N4 bridge result (that is what was recorded, so its
    numbers stay honest); the launch banner explains that demo mode is on. `clip` is ignored and
    `use_llm` is forced off, so nothing here calls Meta or Earth Engine.
    """
    from . import pipeline                       # runtime import: no import-time cycle
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    same_place = (name == BRIDGE["name"] and round(bridge_lat, 4) == round(BRIDGE["lat"], 4)
                  and round(bridge_lon, 4) == round(BRIDGE["lon"], 4))
    if same_place:
        log("Demo mode: cached %s result from 28 Oct 2026 (no Earth Engine or Meta API calls)."
            % BRIDGE["name"])
    else:
        log("Demo mode: this point was not analysed live; showing the cached %s result recorded "
            "28 Oct 2026 (no Earth Engine or Meta API calls)." % BRIDGE["name"])
    if clip:
        log("Demo mode: the clip is not analysed here (cached result shown instead).")

    r = demo_report()
    r["headline"] = card.headline(r)
    tc = time.time()
    r["card_png"] = card.render(r, os.path.join(out_dir, "evidence_card.png"))
    r["share_text"] = card.share_text(r, use_llm=False)    # template only: demo never calls Meta
    timings = {"demo": True, "cached_from": "recorded run 28 Oct 2026",
               "card_s": round(time.time() - tc, 1), "total_s": round(time.time() - t0, 1)}
    r["timings"] = timings
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(pipeline.public(r), f, indent=2, default=pipeline._json_default)
    log("Done (demo): " + " ".join(r["headline"]))
    log("Timings: " + json.dumps(timings))
    return r
