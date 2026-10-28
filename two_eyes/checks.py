"""Checks C-F for one scar. Each returns a dict with 'pass' (True/False/None = not measurable) and evidence."""
import datetime as dt

from . import config as C
from . import earth
from .earth import ee


def yydoy_to_date(v):
    if v is None:
        return None
    v = int(v)
    return (dt.date(2000 + v // 1000, 1, 1) + dt.timedelta(days=v % 1000 - 1)).isoformat()


def _ha(img, region, scale):
    E = ee()
    s = img.multiply(E.Image.pixelArea().divide(1e4)).reduceRegion(
        E.Reducer.sum(), region, scale, maxPixels=1e9).getInfo()
    return float(list(s.values())[0] or 0) if s else 0.0


# ---------- C: do outside alert systems agree? ----------

def check_c(scar_geom, scar_ha):
    E = ee()
    region = scar_geom.buffer(C.CONFIRM_BUFFER_M, 1)
    radd = (E.ImageCollection(C.RADD).filterBounds(region)          # images are per tile: keep this tile only
            .filter(E.Filter.inList("geography", ["africa", "af", "Africa"])))
    alert = E.Image(radd.filter(E.Filter.stringContains("layer", "alert")).sort("system:time_end", False).first())
    base = E.Image(radd.filter(E.Filter.stringContains("layer", "forest_baseline")).sort("layer", False).first())
    a, d = alert.select("Alert"), alert.select("Date")
    hit = a.gte(2).And(d.gte(C.RADD_SINCE_YYDOY)).selfMask()
    radd_ha = _ha(hit, region, 10)
    radd_conf_ha = _ha(a.eq(3).And(d.gte(C.RADD_SINCE_YYDOY)).selfMask(), region, 10)
    dates = d.updateMask(hit).reduceRegion(E.Reducer.minMax(), region, 10, maxPixels=1e9).getInfo()
    in_baseline = _ha(base.select(0).gt(0).selfMask(), scar_geom, 10)
    hansen = E.Image(C.HANSEN).select("lossyear")
    hansen_ha = _ha(hansen.gte(C.HANSEN_SINCE).selfMask(), region, 30)
    need = max(0.1, C.CONFIRM_MIN_SHARE * scar_ha)
    ok = radd_ha >= need or hansen_ha >= need
    # RADD only watches primary humid forest (its baseline) and Hansen v1.13 ends in 2025, so silence
    # from them is evidence of absence only where RADD watches the scar. Elsewhere: not confirmable.
    covered = in_baseline >= 0.5 * scar_ha
    return {"pass": True if ok else (False if covered else None),
            "note": None if (ok or covered) else "outside RADD's forest baseline; Hansen data ends 2025",
            "radd_ha": round(radd_ha, 2), "radd_confirmed_ha": round(radd_conf_ha, 2),
            "radd_first": yydoy_to_date(dates.get("Date_min")), "radd_last": yydoy_to_date(dates.get("Date_max")),
            "scar_in_radd_forest_ha": round(in_baseline, 2), "hansen_loss_2023_2025_ha": round(hansen_ha, 2),
            "sources": ["RADD radar alerts (Wageningen University / Global Forest Watch)",
                        "Hansen/UMD Global Forest Change v1.13"]}


# ---------- D: does it look like mining? ----------

def check_d(scar_geom):
    E = ee()
    now = earth.composite(scar_geom.buffer(500, 1), *C.AFTER)
    water = earth.mndwi(now).gt(C.MNDWI_WATER)
    bare = earth.ndvi(now).lt(C.BARE_NDVI)
    st = (water.rename("water").addBands(bare.rename("bare"))
          .reduceRegion(E.Reducer.mean(), scar_geom, 10, maxPixels=1e9).getInfo())
    drv = E.Image(C.DRIVERS)
    dv = drv.select(["classification", "probability_2"]).reduceRegion(
        E.Reducer.mode(), scar_geom.centroid(1).buffer(600, 1), 1000).getInfo()
    pond = float(st.get("water") or 0)
    driver = dv.get("classification")
    p_mining = (dv.get("probability_2") or 0) * 0.004
    ok = pond >= C.POND_MIN_SHARE or driver == C.DRIVER_HARD_COMMODITIES
    return {"pass": bool(ok), "pond_share": round(pond, 3), "bare_share": round(float(st.get("bare") or 0), 3),
            "wri_driver_class": driver, "wri_mining_probability": round(p_mining, 2),
            "sources": ["Sentinel-2 water index (MNDWI) inside the scar",
                        "WRI/Google DeepMind drivers of forest loss v1.3 (2001-2025, 1 km)"]}


# ---------- E: is the river muddier below the scar? ----------

def _river_ndti(basins, ids, period):
    E = ee()
    if not ids:
        return None, 0
    geom = basins.geometry(ids)
    occ = E.Image(C.JRC_WATER).select("occurrence").gte(C.WATER_OCCURRENCE)
    img = earth.composite(geom, *period)
    water = occ.And(earth.mndwi(img).gt(C.MNDWI_WATER))
    st = (earth.ndti(img).updateMask(water).rename("ndti")
          .addBands(water.selfMask().rename("n"))
          .reduceRegion(E.Reducer.mean().combine(E.Reducer.count(), sharedInputs=False), geom, 10,
                        maxPixels=1e10, tileScale=4).getInfo())
    return st.get("ndti_mean"), int(st.get("n_count") or 0)


def check_e(basins, scar_basin):
    above_ids = [b for b, p in basins.P.items() if p["NEXT_DOWN"] == scar_basin]
    below_ids = basins.downstream(scar_basin)[1:3]
    above, na = _river_ndti(basins, above_ids, C.AFTER)
    below, nb = _river_ndti(basins, below_ids, C.AFTER)
    below_before, nbb = _river_ndti(basins, below_ids, C.BEFORE)
    out = {"ndti_above_now": above, "ndti_below_now": below, "ndti_below_before": below_before,
           "water_px_above": na, "water_px_below": nb, "water_px_below_before": nbb,
           "sources": ["Sentinel-2 turbidity index (NDTI) on JRC Global Surface Water pixels"]}
    if below is not None and nb >= C.MIN_WATER_PX and above is not None and na >= C.MIN_WATER_PX:
        out.update(method="below vs above the scar", delta=round(below - above, 3),
                   **{"pass": (below - above) >= C.MUDDIER_DELTA})
    elif below is not None and nb >= C.MIN_WATER_PX and below_before is not None and nbb >= C.MIN_WATER_PX:
        out.update(method="below the scar, now vs before", delta=round(below - below_before, 3),
                   **{"pass": (below - below_before) >= C.MUDDIER_DELTA})
    else:
        out.update(method="river too narrow to measure from space", delta=None, **{"pass": None})
    return out


# ---------- F: protected area / licences ----------

def check_f(scar_geom):
    E = ee()
    wdpa = E.FeatureCollection(C.WDPA).filterBounds(scar_geom)
    info = wdpa.select(["NAME", "DESIG_ENG", "IUCN_CAT"]).limit(5).getInfo()["features"]
    areas = [{"name": f["properties"].get("NAME"), "designation": f["properties"].get("DESIG_ENG")} for f in info]
    return {"pass": bool(areas), "protected_areas": areas,
            "licence_check": "not automated: check the Minerals Commission public map",
            "licence_map": C.LICENCE_MAP_URL,
            "sources": ["World Database on Protected Areas (UNEP-WCMC / IUCN)"]}
