"""Earth Engine helpers: cloud-masked composites and exact-grid pixel pulls."""
import numpy as np
from pyproj import Transformer

from . import config as C

_ee = None


def ee():
    """Return the earthengine module (must already be initialised by the caller)."""
    global _ee
    if _ee is None:
        import ee as _m
        _ee = _m
    return _ee


def init(project):
    """Authenticate (if needed) and initialise Earth Engine."""
    E = ee()
    try:
        E.Initialize(project=project)
    except Exception:
        E.Authenticate()
        E.Initialize(project=project)


_to_utm = Transformer.from_crs("EPSG:4326", C.CRS, always_xy=True)
_to_ll = Transformer.from_crs(C.CRS, "EPSG:4326", always_xy=True)


def to_utm(lat, lon):
    return _to_utm.transform(lon, lat)


def to_latlon(x, y):
    lon, lat = _to_ll.transform(x, y)
    return lat, lon


class Grid:
    """A north-up UTM grid of square pixels, centred on a point."""

    def __init__(self, lat, lon, half_m=C.BOX_HALF_M, scale=C.SCALE_M):
        cx, cy = to_utm(lat, lon)
        self.scale = scale
        self.n = int(round(2 * half_m / scale))
        self.x0 = round((cx - half_m) / scale) * scale
        self.y0 = round((cy + half_m) / scale) * scale

    def ee_grid(self):
        return {"dimensions": {"width": self.n, "height": self.n},
                "affineTransform": {"scaleX": self.scale, "shearX": 0, "translateX": self.x0,
                                    "shearY": 0, "scaleY": -self.scale, "translateY": self.y0},
                "crsCode": C.CRS}

    def rc(self, lat, lon):
        x, y = to_utm(lat, lon)
        return int((self.y0 - y) // self.scale), int((x - self.x0) // self.scale)

    def latlon(self, r, c):
        return to_latlon(self.x0 + (c + 0.5) * self.scale, self.y0 - (r + 0.5) * self.scale)

    def geometry(self):
        E = ee()
        x1, y1 = self.x0 + self.n * self.scale, self.y0 - self.n * self.scale
        return E.Geometry.Rectangle([self.x0, y1, x1, self.y0], E.Projection(C.CRS), False)


def pull(img, grid, bands):
    """Pixels of `img` on `grid` as {band: 2-D float array}; masked pixels are NaN."""
    E = ee()
    img = E.Image(img).select(bands).toFloat().unmask(-9999)
    arr = E.data.computePixels({"expression": img, "fileFormat": "NUMPY_NDARRAY", "grid": grid.ee_grid()})
    out = {}
    for b in bands:
        a = np.asarray(arr[b], dtype=np.float32)
        a[a <= -9998] = np.nan
        out[b] = a
    return out


def mask_clouds(img):
    scl = img.select("SCL")
    ok = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return img.updateMask(ok.And(img.select("cs_cdf").gte(C.CS_CLEAR)))


def composite(region, start, end):
    """Median of cloud-masked Sentinel-2 SR scenes (SCL + Cloud Score+, amendment A1)."""
    E = ee()
    col = (E.ImageCollection(C.S2).filterBounds(region).filterDate(start, end)
           .filter(E.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", C.MAX_CLOUD_PCT))
           .linkCollection(E.ImageCollection(C.CS_PLUS), ["cs_cdf"])
           .map(mask_clouds))
    return col.median()


def ndvi(img):
    return img.normalizedDifference(["B8", "B4"]).rename("ndvi")


def mndwi(img):
    return img.normalizedDifference(["B3", "B11"]).rename("mndwi")


def ndti(img):
    """Normalised difference turbidity index (red vs green) for water pixels."""
    return img.normalizedDifference(["B4", "B3"]).rename("ndti")


def rgb8(arrs):
    """Sentinel-2 B4/B3/B2 reflectance (x10000) -> uint8 RGB, same stretch as the kill gate."""
    rgb = np.stack([arrs["B4"], arrs["B3"], arrs["B2"]], -1)
    rgb = np.nan_to_num(rgb, nan=0.0)
    return np.clip(rgb / 2500 * 255, 0, 255).astype(np.uint8)
