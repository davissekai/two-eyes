"""Check A, the sky eye: NDVI-first scar candidates, outlines refined with SAM 3.1 box prompts.

Same rule as the kill gate (amendment A1):
  scar pixel = clear in both composites AND NDVI_before > NDVI_FOREST AND NDVI_before - NDVI_now > NDVI_DROP
  keep 4-connected patches >= MIN_SCAR_HA; SAM 3.1 box prompts refine each patch; keep refined AND NDVI pixels.
"""
import json

import numpy as np
from scipy import ndimage

from . import config as C
from . import earth
from .earth import ee

BANDS = ["B2", "B3", "B4", "B8", "B11"]
MIN_PX = int(round(C.MIN_SCAR_HA / C.PIXEL_HA))


# ---------- pure numpy (unit-tested) ----------

def ndvi_np(a):
    return (a["B8"] - a["B4"]) / (a["B8"] + a["B4"] + 1e-9)


def scar_pixels(nb, na):
    valid = ~np.isnan(nb) & ~np.isnan(na)
    with np.errstate(invalid="ignore"):
        return valid & (nb > C.NDVI_FOREST) & ((nb - na) > C.NDVI_DROP)


def patches(mask):
    """Keep 4-connected patches of at least MIN_SCAR_HA. Returns (kept mask, labels)."""
    lab, n = ndimage.label(mask)
    if n == 0:
        return np.zeros_like(mask, dtype=bool), lab
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= MIN_PX])
    return keep, ndimage.label(keep)[0]


def boxes_of(lab):
    return [(sl[1].start, sl[0].start, sl[1].stop, sl[0].stop) for sl in ndimage.find_objects(lab) if sl]


def component_at(mask, r, c, radius_px):
    """Union of the mask's components touching a disc around (r, c)."""
    H, W = mask.shape
    yy, xx = np.ogrid[:H, :W]
    near = (yy - r) ** 2 + (xx - c) ** 2 <= radius_px ** 2
    lab, _ = ndimage.label(mask)
    ids = np.unique(lab[near & mask])
    ids = ids[ids > 0]
    return np.isin(lab, ids) if ids.size else np.zeros_like(mask, dtype=bool)


def cloudy_share(a_before, a_after):
    return float(max(np.isnan(a_before["B4"]).mean(), np.isnan(a_after["B4"]).mean()))


# ---------- Earth Engine ----------

def _scar_image(region):
    b = earth.composite(region, *C.BEFORE)
    a = earth.composite(region, *C.AFTER)
    nb, na = earth.ndvi(b), earth.ndvi(a)
    scar = nb.gt(C.NDVI_FOREST).And(nb.subtract(na).gt(C.NDVI_DROP)).selfMask()
    big = scar.connectedPixelCount(MIN_PX + 1, False).gte(MIN_PX)
    return scar.updateMask(big), b, a


def find_candidates(region, limit=C.MAX_CANDIDATES * 3):
    """Candidate scar polygons in a region (e.g. the catchment above a bridge), largest first."""
    E = ee()
    scar, b, a = _scar_image(region)
    vec = scar.reduceToVectors(geometry=region, crs=C.CRS, scale=C.SCALE_M, geometryType="polygon",
                               eightConnected=False, maxPixels=1e10, tileScale=4)
    vec = vec.map(lambda f: f.set("area_ha", f.geometry().area(1).divide(1e4),
                                  "c", f.geometry().centroid(1).coordinates()))
    vec = vec.filter(E.Filter.gte("area_ha", C.MIN_SCAR_HA)).sort("area_ha", False).limit(limit)
    feats = vec.getInfo()["features"]
    clear = (b.select("B4").mask().And(a.select("B4").mask())
             .reduceRegion(E.Reducer.mean(), region, 60, maxPixels=1e10, tileScale=4).getInfo())
    cands = [{"lat": f["properties"]["c"][1], "lon": f["properties"]["c"][0],
              "area_ha_ndvi": round(f["properties"]["area_ha"], 2)} for f in feats]
    return cands, 1 - float(clear.get("B4") or 0)


def analyse_box(lat, lon, use_sam=True):
    """Kill-gate analysis in a 2 km box centred on (lat, lon). Returns the scar touching the centre."""
    E = ee()
    g = earth.Grid(lat, lon)
    region = g.geometry()
    both = (earth.composite(region, *C.BEFORE).select(BANDS, [f"b_{b}" for b in BANDS])
            .addBands(earth.composite(region, *C.AFTER).select(BANDS, [f"a_{b}" for b in BANDS])))
    px = earth.pull(both, g, [f"b_{b}" for b in BANDS] + [f"a_{b}" for b in BANDS])   # one request, not two
    ab = {b: px[f"b_{b}"] for b in BANDS}
    aa = {b: px[f"a_{b}"] for b in BANDS}
    cloudy = cloudy_share(ab, aa)
    out = {"lat": lat, "lon": lon, "cloudy": round(cloudy, 3), "grid": g,
           "rgb_before": earth.rgb8(ab), "rgb_after": earth.rgb8(aa)}
    if cloudy > C.MAX_CLOUDY:
        out.update(status="CLOUDY", area_ha=0.0, mask=None)
        return out
    nb, na = ndvi_np(ab), ndvi_np(aa)
    ndvi_scar = scar_pixels(nb, na)
    cand, lab = patches(ndvi_scar)
    outline = "SAM 3.1 box prompts"
    if not cand.any():
        final = cand
    elif use_sam:
        try:
            from . import sam
            refined = sam.refine_boxes(out["rgb_after"], boxes_of(lab))
            final, _ = patches(refined & ndvi_scar)
        except Exception as ex:                      # API down: say so, keep NDVI outline
            final, outline = cand, f"NDVI only (SAM unavailable: {type(ex).__name__})"
    else:
        final, outline = cand, "NDVI only"
    r, c = g.rc(lat, lon)
    here = component_at(final, r, c, C.SEARCH_RADIUS_M // C.SCALE_M)
    area = float(here.sum() * C.PIXEL_HA)
    rr, cc = np.nonzero(here) if here.any() else (np.array([r]), np.array([c]))
    clat, clon = g.latlon(int(rr.mean()), int(cc.mean()))
    out.update(status="SCAR" if area >= C.MIN_SCAR_HA else "NONE", area_ha=round(area, 2), mask=here,
               all_scars=final, outline_method=outline, centroid=(round(clat, 5), round(clon, 5)),
               ndvi_before=float(np.nanmean(nb[here])) if here.any() else None,
               ndvi_after=float(np.nanmean(na[here])) if here.any() else None)
    return out


def scar_geometry(box):
    """The scar mask as an ee.Geometry (UTM pixel outlines), for checks C-F."""
    from affine import Affine
    from rasterio.features import shapes
    E = ee()
    g, m = box["grid"], box["mask"]
    if m is None or not m.any():
        return None
    tf = Affine(g.scale, 0, g.x0, 0, -g.scale, g.y0)
    polys = [geom["coordinates"] for geom, v in shapes(m.astype("uint8"), mask=m, transform=tf) if v == 1]
    polys = json.loads(json.dumps(polys))          # tuples -> lists for EE
    return E.Geometry.MultiPolygon(polys, E.Projection(C.CRS), False)
