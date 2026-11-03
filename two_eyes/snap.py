"""Snap the filming spot onto the river it looks at, before tracing upstream.

A phone on a riverbank can be 10-30 m off, and near a confluence that can put the point in the
wrong level-12 basin, so the trace would follow the wrong stream. We move the point onto the
nearest mapped river line (HydroRIVERS) and flag the case where two different rivers are about
equally close, which is a question only the person standing there can answer.
"""
from . import config as C
from . import earth


def nearest_on_line(lat, lon, coords):
    """Closest point to (lat, lon) on a polyline of [lon, lat] pairs: (lat, lon, distance in m)."""
    px, py = earth.to_utm(lat, lon)
    pts = [earth.to_utm(c[1], c[0]) for c in coords]
    best = None
    for (ax, ay), (bx, by) in zip(pts, pts[1:] or pts):
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
        qx, qy = ax + t * dx, ay + t * dy
        d = ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5
        if best is None or d < best[2]:
            best = (qx, qy, d)
    qlat, qlon = earth.to_latlon(best[0], best[1])
    return qlat, qlon, best[2]


def choose(reaches, max_m=C.SNAP_MAX_M, ambiguous_m=C.SNAP_AMBIGUOUS_M):
    """Pick the river reach to snap to, or None when no mapped river is within max_m.

    reaches: [{id, lat, lon, dist_m, upland_km2}], one per piece of line found nearby (a reach can
    appear more than once). Ambiguous when a different river lies within ambiguous_m of the nearest.
    """
    near = sorted((r for r in reaches if r["dist_m"] <= max_m), key=lambda r: r["dist_m"])
    if not near:
        return None
    best, seen, others = near[0], {near[0]["id"]}, []
    for r in near[1:]:
        if r["id"] not in seen and r["dist_m"] - best["dist_m"] <= ambiguous_m:
            others.append(r)
        seen.add(r["id"])
    out = {"lat": best["lat"], "lon": best["lon"], "moved_m": round(best["dist_m"]), "reach": best["id"],
           "ambiguous": bool(others), "options": []}
    if others:
        rivals = [best] + others
        biggest = max(r["upland_km2"] or 0 for r in rivals)
        out["options"] = [{"reach": r["id"], "lat": r["lat"], "lon": r["lon"], "dist_m": round(r["dist_m"]),
                           "kind": "bigger river" if (r["upland_km2"] or 0) == biggest else "smaller stream"}
                          for r in rivals]
    return out


def _lines(geom):
    """Polylines ([lon, lat] lists) of a GeoJSON LineString or MultiLineString."""
    if geom["type"] == "LineString":
        return [geom["coordinates"]]
    if geom["type"] == "MultiLineString":
        return geom["coordinates"]
    return []


def snap_to_river(lat, lon):
    """Earth Engine side: fetch HydroRIVERS reaches near the spot and choose one (or None)."""
    E = earth.ee()
    area = E.Geometry.Point([lon, lat]).buffer(C.SNAP_MAX_M)
    feats = (E.FeatureCollection(C.HYRIVERS).filterBounds(area)
             .map(lambda f: E.Feature(f.geometry().intersection(area, 1), f.toDictionary(["REACH_ID", "UPLAND_SKM"])))
             .limit(20).getInfo()["features"])
    reaches = []
    for f in feats:
        for line in _lines(f.get("geometry") or {"type": None}):
            if line:
                qlat, qlon, d = nearest_on_line(lat, lon, line)
                reaches.append({"id": f["properties"]["REACH_ID"], "lat": qlat, "lon": qlon, "dist_m": d,
                                "upland_km2": f["properties"].get("UPLAND_SKM")})
    return choose(reaches)
