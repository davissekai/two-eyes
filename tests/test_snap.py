"""Snapping a phone's position onto the river it is looking at, and noticing when that is unclear."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_eyes import earth, snap  # noqa: E402

LAT, LON = 6.28442, -0.46118


def _offset(lat, lon, dx_m, dy_m):
    x, y = earth.to_utm(lat, lon)
    return earth.to_latlon(x + dx_m, y + dy_m)


def _ns_line(dx_m):
    """A north-south river line dx_m east of the spot, as [lon, lat] pairs."""
    a, b = _offset(LAT, LON, dx_m, -500), _offset(LAT, LON, dx_m, 500)
    return [[a[1], a[0]], [b[1], b[0]]]


def test_nearest_point_on_a_line_is_square_across_from_the_spot():
    lat, lon, d = snap.nearest_on_line(LAT, LON, _ns_line(40))
    assert d == pytest.approx(40, abs=0.5)
    ex, ey = _offset(LAT, LON, 40, 0)
    assert (lat, lon) == pytest.approx((ex, ey), abs=1e-6)


def test_nearest_point_past_the_end_of_a_line_is_its_end():
    a, b = _offset(LAT, LON, 0, 100), _offset(LAT, LON, 0, 300)
    lat, lon, d = snap.nearest_on_line(LAT, LON, [[a[1], a[0]], [b[1], b[0]]])
    assert d == pytest.approx(100, abs=0.5) and (lat, lon) == pytest.approx(a, abs=1e-6)


def test_single_point_line_does_not_crash():
    p = _offset(LAT, LON, 30, 0)
    assert snap.nearest_on_line(LAT, LON, [[p[1], p[0]]])[2] == pytest.approx(30, abs=0.5)


def _reach(rid, dist_m, upland):
    lat, lon = _offset(LAT, LON, dist_m, 0)
    return {"id": rid, "lat": lat, "lon": lon, "dist_m": dist_m, "upland_km2": upland}


def test_one_river_nearby_is_snapped_to():
    s = snap.choose([_reach(1, 25, 1600)])
    assert s["reach"] == 1 and s["moved_m"] == 25 and not s["ambiguous"]


def test_no_mapped_river_nearby_keeps_the_phone_position():
    assert snap.choose([_reach(1, 900, 1600)]) is None
    assert snap.choose([]) is None


def test_two_rivers_close_together_is_flagged_and_the_nearest_wins():
    s = snap.choose([_reach(1, 60, 1600), _reach(2, 30, 40)])
    assert s["reach"] == 2 and s["ambiguous"]
    assert [o["kind"] for o in s["options"]] == ["smaller stream", "bigger river"]


def test_a_second_river_much_further_away_is_not_ambiguous():
    s = snap.choose([_reach(1, 20, 1600), _reach(2, 280, 40)])
    assert s["reach"] == 1 and not s["ambiguous"]


def test_trace_starts_from_the_snapped_point(monkeypatch):
    from two_eyes import pipeline
    monkeypatch.setattr(snap, "snap_to_river", lambda lat, lon: snap.choose([_reach(7, 25, 1600)]))
    lat, lon, info = pipeline.river_point(LAT, LON, log=lambda *a: None)
    assert info["reach"] == 7 and (lat, lon) != (LAT, LON)


def test_trace_falls_back_to_the_phone_position_when_the_river_map_fails(monkeypatch):
    from two_eyes import pipeline

    def boom(lat, lon):
        raise RuntimeError("Earth Engine down")
    monkeypatch.setattr(snap, "snap_to_river", boom)
    lat, lon, info = pipeline.river_point(LAT, LON, log=lambda *a: None)
    assert (lat, lon) == (LAT, LON) and info["moved_m"] == 0 and "error" in info


def test_public_report_keeps_only_what_cannot_locate_the_spot():
    from two_eyes import pipeline
    s = snap.choose([_reach(1, 60, 1600), _reach(2, 30, 40)])
    out = pipeline.public({"snap": s})["snap"]
    assert out == {"ambiguous": True, "followed": "smaller stream", "options": ["smaller stream", "bigger river"]}
    assert pipeline.public({"snap": {"moved_m": 0, "ambiguous": False}})["snap"] == {"ambiguous": False}


def test_case_file_warns_when_two_rivers_meet_here():
    from two_eyes import case_file
    r = {"status": "SCAR", "scar": {"area_ha": 17.0, "distance_km": 19.0},
         "checks": {"A": {"pass": True}, "B": {"pass": True}},
         "snap": snap.choose([_reach(1, 60, 1600), _reach(2, 30, 40)])}
    html = case_file.verdict_html(r).lower()
    assert "two rivers meet" in html and "smaller stream" in html


def test_pieces_of_the_same_river_are_not_two_rivers():
    s = snap.choose([_reach(1, 20, 1600), _reach(1, 40, 1600)])
    assert not s["ambiguous"]
