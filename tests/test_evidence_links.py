"""Check it yourself: links that open the same public satellite data at the clearing, so anyone can verify."""
import base64
import json
import os
import sys
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_eyes import config as C, evidence_links  # noqa: E402

SCAR = {"lat": 6.4544, "lon": -0.4833, "area_ha": 17.0, "distance_km": 19.0}
SPOT = {"lat": 6.28442, "lon": -0.46118, "name": "Birim, N4 bridge"}


def _r(scar=SCAR, **checks):
    checks = checks or {"A": True, "B": True}
    return {"status": "SCAR", "spot": SPOT, "scar": scar, "checks": {k: {"pass": v} for k, v in checks.items()}}


def _query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_every_link_opens_at_the_clearing_not_where_the_person_stood():
    links = evidence_links.links(_r())
    assert len(links) == 3
    for link in links:
        assert link["url"].startswith("https://")
        assert "6.28" not in link["url"]     # the spot's latitude never leaves in a link
    gnw = json.loads(base64.b64decode(unquote(_query(links[0]["url"])["map"])))
    assert gnw["center"] == {"lat": 6.4544, "lng": -0.4833}
    assert {d["dataset"] for d in gnw["datasets"]} >= {"radd-deforestation-alerts"}


def test_before_and_after_photos_use_the_same_dates_as_the_check():
    _, before, after = evidence_links.links(_r())
    qb, qa = _query(before["url"]), _query(after["url"])
    assert (qb["lat"], qb["lng"]) == ("6.4544", "-0.4833")
    assert qb["fromTime"].startswith(C.BEFORE[0]) and qb["toTime"].startswith(C.BEFORE[1])
    assert qa["fromTime"].startswith(C.AFTER[0]) and qa["toTime"].startswith(C.AFTER[1])
    assert C.BEFORE[0][:4] in before["title"] and C.AFTER[0][:4] in after["title"]


def test_no_links_when_there_is_no_clearing_to_look_at():
    assert evidence_links.links(_r(A=False)) == []
    assert evidence_links.links(_r(A=True, B=False)) == []
    assert evidence_links.links({"status": "CLOUDY", "checks": {}}) == []
    assert evidence_links.links_html(_r(A=False)) == ""


def test_broken_scar_coordinates_give_no_links_rather_than_bad_ones():
    for scar in ({"area_ha": 17.0}, {"lat": None, "lon": -0.48}, {"lat": "6.4", "lon": -0.48},
                 {"lat": 95.0, "lon": -0.48}, {"lat": float("nan"), "lon": -0.48}):
        assert evidence_links.links(_r(scar=scar)) == [], scar


def test_panel_opens_links_safely_and_says_they_are_outside_data():
    html = evidence_links.links_html(_r())
    assert html.count('target="_blank" rel="noopener"') == 3
    assert "&amp;" in html and "&lng" not in html          # query strings escaped inside href
    assert "Check it yourself" in html and "Global Nature Watch" in html and "Copernicus" in html
