"""Check it yourself: links that open the same public satellite data at the clearing.

Corroboration a reader can see with their own eyes, not our word for it. Every link points at the
clearing (already shown on the trace), never at where the person stood.
"""
import base64
import html
import json
import math
from urllib.parse import quote, urlencode

from . import config as C
from .case_file import evidence_level

GNW_MAP = "https://globalnaturewatch.org/map/"           # Global Forest Watch's new name; old links redirect here
COPERNICUS = "https://browser.dataspace.copernicus.eu/"
ZOOM = 14                                                # about 3 km across on a phone: the clearing and its river
ALERT_LAYERS = [("radd-deforestation-alerts", "deforestation-alerts-radd"),
                ("glad-s2-deforestation-alerts", "deforestation-alerts-glad-s2")]


def _clearing(r):
    """(lat, lon) of the clearing, or None when there is no traced clearing or its numbers are unusable."""
    s = r.get("scar") or {}
    lat, lon = s.get("lat"), s.get("lon")
    if evidence_level(r) == 0 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lat, lon)):
        return None
    return (round(lat, 4), round(lon, 4)) if abs(lat) <= 90 and abs(lon) <= 180 else None


def gnw_url(lat, lon):
    """Global Nature Watch map at the clearing, asking for the radar and Sentinel-2 deforestation alerts.

    The site reads its whole map state from one base64 JSON parameter. It honours the centre; whether it
    switches the alert layers on depends on the site, so the link's title only promises the map.
    """
    state = {"center": {"lat": lat, "lng": lon}, "zoom": ZOOM,
             "datasets": [{"dataset": d, "layers": [layer], "opacity": 1, "visibility": True}
                          for d, layer in ALERT_LAYERS]}
    encoded = base64.b64encode(json.dumps(state, separators=(",", ":")).encode()).decode()
    return f"{GNW_MAP}?map={quote(encoded)}"


def copernicus_url(lat, lon, start, end):
    """Copernicus Browser at the clearing: the clearest Sentinel-2 true-colour photo between two dates."""
    return COPERNICUS + "?" + urlencode({
        "zoom": ZOOM, "lat": lat, "lng": lon, "themeId": "DEFAULT-THEME", "datasetId": "S2_L2A_CDAS",
        "layerId": "1_TRUE_COLOR", "cloudCoverage": 30,
        "fromTime": f"{start}T00:00:00.000Z", "toTime": f"{end}T23:59:59.999Z"})


def links(r):
    """The outside sources for this result: [{title, by, url}], empty when there is no clearing to look at."""
    at = _clearing(r)
    if not at:
        return []
    before, after = C.BEFORE[0][:4], C.AFTER[0][:4]
    return [
        {"title": "Forest-loss map at the clearing", "by": "Global Nature Watch (formerly Global Forest Watch)",
         "url": gnw_url(*at)},
        {"title": f"Satellite photo, early {before}", "by": "Copernicus Browser, ESA Sentinel-2",
         "url": copernicus_url(*at, *C.BEFORE)},
        {"title": f"Satellite photo, early {after}", "by": "Copernicus Browser, ESA Sentinel-2",
         "url": copernicus_url(*at, *C.AFTER)},
    ]


def links_html(r):
    """The 'Check it yourself' panel, or nothing when there are no links."""
    items = "".join(
        f'<li><a href="{html.escape(x["url"])}" target="_blank" rel="noopener">'
        f'<b>{html.escape(x["title"])}</b><small>{html.escape(x["by"])}</small></a></li>' for x in links(r))
    if not items:
        return ""
    return ('<div class="panel check-links"><div class="label">Check it yourself</div>'
            '<p class="hint">The same public satellite data we used, opened at the clearing. '
            'Copernicus may ask you to tap “Use anonymously” first.</p>'
            f'<ul>{items}</ul></div>')
