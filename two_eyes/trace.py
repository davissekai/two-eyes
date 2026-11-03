"""Check B: what drains to the filming point (HydroBASINS level 12, NEXT_DOWN links)."""
from . import config as C
from .earth import ee


class NoRiverHere(ValueError):
    """The spot is not inside any river basin (open sea, a big lake, a bad coordinate). Plain message."""


class Basins:
    """HydroBASINS level-12 basins around a point, with upstream/downstream walks."""

    def __init__(self, lat, lon, pad_deg=0.6):
        E = ee()
        self.fc = E.FeatureCollection(C.HYBAS).filterBounds(
            E.Geometry.Rectangle([lon - pad_deg, lat - pad_deg, lon + pad_deg, lat + pad_deg]))
        info = self.fc.select(["HYBAS_ID", "NEXT_DOWN", "MAIN_BAS", "SUB_AREA"]).getInfo()["features"]
        self.P = {f["properties"]["HYBAS_ID"]: f["properties"] for f in info}
        self._up = {}
        for b, p in self.P.items():
            self._up.setdefault(p["NEXT_DOWN"], []).append(b)

    def basin_of(self, lat, lon):
        E = ee()
        f = self.fc.filterBounds(E.Geometry.Point([lon, lat])).first()
        found = E.Algorithms.If(f, f.get("HYBAS_ID"), None).getInfo()
        if found is None:
            raise NoRiverHere("We couldn't find land that drains to a river at this spot. "
                              "Check the location: stand by a river, on land.")
        return found

    def upstream(self, start):
        return upstream_ids(start, self._up)

    def downstream(self, start):
        return downstream_chain(start, self.P)

    def area_km2(self, ids):
        return sum(self.P[b]["SUB_AREA"] for b in ids if b in self.P)

    def geometry(self, ids):
        E = ee()
        return self.fc.filter(E.Filter.inList("HYBAS_ID", list(ids))).geometry().dissolve(maxError=30)


def upstream_ids(start, up_index):
    """All basins draining to `start`, including itself. up_index: {basin: [basins whose NEXT_DOWN is it]}."""
    seen, stack = {start}, [start]
    while stack:
        for b in up_index.get(stack.pop(), []):
            if b not in seen:
                seen.add(b)
                stack.append(b)
    return seen


def downstream_chain(start, props):
    chain, cur = [start], start
    while props.get(cur, {}).get("NEXT_DOWN") in props and props[cur]["NEXT_DOWN"] not in chain:
        cur = props[cur]["NEXT_DOWN"]
        chain.append(cur)
    return chain


def check_b(basins, spot_basin, scar_lat, scar_lon):
    """Badge for one scar: does it drain to the filming spot?"""
    b = basins.basin_of(scar_lat, scar_lon)
    up = basins.upstream(spot_basin)
    if b not in up:
        return {"pass": False, "basin": b, "note": "drains elsewhere"}
    if b == spot_basin:
        return {"pass": True, "basin": b, "same_basin": True,
                "note": "same small basin as the filming spot: probably upstream, not certain"}
    return {"pass": True, "basin": b, "same_basin": False, "note": "drains to the filming spot"}
