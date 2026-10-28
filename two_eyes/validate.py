"""Regression: rerun the kill gate through the production code path (sky.analyse_box)."""
from . import config as C
from . import sky

CERSGIS = {"lat": 6 + 13 / 60 + 53 / 3600, "lon": -(34 / 60 + 2 / 3600), "ref_ha": 5.49}


def run(controls, use_sam=True, log=print):
    """controls: {"intact_forest": (lat, lon), "cocoa_farm": (lat, lon)} from the kill gate."""
    rows = []
    b = sky.analyse_box(CERSGIS["lat"], CERSGIS["lon"], use_sam=use_sam)
    ok = b["status"] == "SCAR" and abs(b["area_ha"] - CERSGIS["ref_ha"]) <= C.AREA_TOL * CERSGIS["ref_ha"]
    rows.append({"site": "cersgis_clearing", "area_ha": b["area_ha"], "ref_ha": CERSGIS["ref_ha"],
                 "cloudy": b["cloudy"], "outline": b.get("outline_method"), "pass": bool(ok)})
    for name, (lat, lon) in controls.items():
        b = sky.analyse_box(lat, lon, use_sam=use_sam)
        total = float(b["all_scars"].sum() * C.PIXEL_HA) if b.get("all_scars") is not None else 0.0
        rows.append({"site": name, "false_scar_ha": round(total, 2), "cloudy": b["cloudy"],
                     "pass": b["status"] != "CLOUDY" and total < C.MIN_SCAR_HA})
    for r in rows:
        log(r)
    verdict = "PASS" if all(r["pass"] for r in rows) else "FAIL"
    log("Regression vs kill gate:", verdict)
    return rows, verdict
