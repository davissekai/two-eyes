import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_eyes import card, checks, demo, ground, sky, trace  # noqa: E402
from two_eyes import config as C  # noqa: E402
from two_eyes import pipeline  # noqa: E402


def test_scar_pixels_rule():
    nb = np.array([[0.8, 0.8, 0.5, np.nan]])
    na = np.array([[0.3, 0.7, 0.1, 0.1]])
    assert sky.scar_pixels(nb, na).tolist() == [[True, False, False, False]]


def test_patches_min_size_and_4_connectivity():
    m = np.zeros((20, 20), bool)
    m[0:7, 0:8] = True                      # 56 px >= 50 -> kept
    m[10:14, 10:14] = True                  # 16 px -> dropped
    keep, lab = sky.patches(m)
    assert keep.sum() == 56 and lab.max() == 1
    d = np.zeros((20, 20), bool)
    d[np.arange(20), np.arange(20)] = True  # diagonal: 4-connected pieces of 1 px
    assert not sky.patches(d)[0].any()


def test_component_at():
    m = np.zeros((50, 50), bool)
    m[10:20, 10:20] = True
    m[40:45, 40:45] = True
    got = sky.component_at(m, 22, 22, 5)
    assert got.sum() == 100


def test_upstream_and_downstream():
    props = {1: {"NEXT_DOWN": 0}, 2: {"NEXT_DOWN": 1}, 3: {"NEXT_DOWN": 1}, 4: {"NEXT_DOWN": 2}, 5: {"NEXT_DOWN": 9}}
    up = {}
    for b, p in props.items():
        up.setdefault(p["NEXT_DOWN"], []).append(b)
    assert trace.upstream_ids(1, up) == {1, 2, 3, 4}
    assert trace.upstream_ids(5, up) == {5}
    assert trace.downstream_chain(4, props) == [4, 2, 1]


def test_nearest_upstream_cap():
    class B:
        P = {1: {"NEXT_DOWN": 0, "SUB_AREA": 100}, 2: {"NEXT_DOWN": 1, "SUB_AREA": 100},
             3: {"NEXT_DOWN": 2, "SUB_AREA": 500}}

        def upstream(self, s):
            return {1, 2, 3}

        def area_km2(self, ids):
            return sum(self.P[i]["SUB_AREA"] for i in ids)
    order, area, total = pipeline.nearest_upstream(B(), 1, cap_km2=600)
    assert order == [1, 2] and area == 200 and total == 700


def test_yydoy():
    assert checks.yydoy_to_date(23001) == "2023-01-01"
    assert checks.yydoy_to_date(24060) == "2024-02-29"


def _report(**k):
    r = {"date": "2026-10-28", "status": "SCAR", "spot": {"lat": 6.28442, "lon": -0.46118, "name": "N4 Birim bridge"},
         "scar": {"area_ha": 4.3, "distance_km": 13.1}, "checks": {}}
    r["checks"].update(k)
    return r


def test_headlines_follow_the_table():
    assert "No new forest clearing" in card.headline({"status": "NONE", "checks": {"A": {"pass": False}}})[0]
    assert "Clouds" in card.headline({"status": "CLOUDY", "checks": {}})[0]
    t = card.headline(_report(A={"pass": True}, B={"pass": True}))
    assert "Possible forest clearing" in t[0]
    assert any("not yet confirmed" in x for x in t)
    t = card.headline(_report(A={"pass": True}, B={"pass": True}, C={"pass": True, "radd_first": "2024-02-01"}))
    assert "confirmed by radar alerts from 2024-02-01" in t[0] and "Cause not confirmed" in t[0]
    t = card.headline(_report(A={"pass": True}, B={"pass": True}, C={"pass": True}, D={"pass": True},
                              E={"pass": True}, F={"pass": True, "protected_areas": [{"name": "Atewa Range"}]}))
    assert any("Likely source of this mud, not proven" in x for x in t)
    assert any("Atewa Range" in x and "Only the authorities" in x for x in t)
    assert not any("%" in x for x in t)


def test_muddiness_labels():
    brown = np.zeros((40, 40, 3), np.uint8); brown[:] = (150, 110, 60)
    blue = np.zeros((40, 40, 3), np.uint8); blue[:] = (60, 100, 150)
    m = np.ones((40, 40), bool)
    assert ground.muddiness([brown], {0: m})["label"] == "muddy brown"
    assert ground.muddiness([blue], {0: m})["label"] == "clear or green"
    assert ground.muddiness([blue], {})["water_found"] is False


def test_colour_is_read_from_the_middle_of_the_water_not_the_muddy_edge():
    # Bank shot: clear water mid-river, a band of brown shallows along the mask edge.
    f = np.zeros((100, 100, 3), np.uint8); f[:] = (60, 100, 150)
    m = np.zeros((100, 100), bool); m[5:95, 5:95] = True
    edge = m & ~np.pad(np.ones((40, 40), bool), 30)
    f[edge] = (150, 110, 60)
    assert edge.sum() > (m & ~edge).sum()           # the shallows outnumber the open water
    assert ground.muddiness([f], {0: m})["label"] == "clear or green"


def test_small_water_mask_still_gets_a_reading():
    f = np.zeros((40, 40, 3), np.uint8); f[:] = (150, 110, 60)
    m = np.zeros((40, 40), bool); m[10:25, 10:25] = True    # 225 px: too small to trim an edge off
    assert ground.muddiness([f], {0: m})["label"] == "muddy brown"


def test_muse_spark_reply_is_parsed_with_the_camera_angle():
    d = ground.parse_colour_reply('Sure! {"water": "muddy", "reason": "brown silt", "view": "bank"}')
    assert d["label"] == "muddy brown" and d["muddy"] is True and d["view"] == "bank"


def test_unusable_muse_spark_reply_is_ignored():
    assert ground.parse_colour_reply("no json here") is None
    assert ground.parse_colour_reply('{"water": "purple"}') is None
    assert ground.parse_colour_reply('{"water": "clear"}')["view"] == "unknown"


def test_muddiness_reports_the_water_colour_for_the_swatch():
    brown = np.zeros((40, 40, 3), np.uint8); brown[:] = (150, 110, 60)
    brown[:5] = (250, 250, 250)                       # bright bank outside the mask
    m = np.zeros((40, 40), bool); m[10:, :] = True
    assert ground.muddiness([brown], {0: m})["rgb"] == [150, 110, 60]


def test_card_renders(tmp_path):
    rgb = (np.random.rand(200, 200, 3) * 255).astype(np.uint8)
    mask = np.zeros((200, 200), bool); mask[80:120, 90:130] = True
    r = _report(A={"pass": True}, B={"pass": True}, C={"pass": True, "radd_first": "2024-02-01"},
                D={"pass": False}, E={"pass": None}, F={"pass": True, "protected_areas": [{"name": "Atewa Range"}]})
    r["scar"].update(rgb_before=rgb, rgb_after=rgb, mask=mask)
    r["ground"] = {"water_found": True, "label": "muddy brown", "still": rgb}
    p = card.render(r, str(tmp_path / "card.png"))
    assert os.path.getsize(p) > 20_000


def test_frozen_cutoffs_unchanged():
    assert (C.NDVI_FOREST, C.NDVI_DROP, C.MIN_SCAR_HA, C.MAX_CLOUDY, C.AREA_TOL, C.CS_CLEAR) == \
        (0.6, 0.20, 0.5, 0.30, 0.5, 0.60)


def test_run_uses_cache_and_reports_timings(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(demo, "is_demo_mode", lambda: False)   # force the live (caching) path

    def fake_sky(lat, lon, focus=None, use_sam=True, log=print, timings=None):
        calls.append(1)
        return {"status": "NONE", "checks": {"A": {"pass": False}}, "candidates": [], "scar": {},
                "catchment": {}}
    monkeypatch.setattr(pipeline, "sky_part", fake_sky)
    monkeypatch.setattr(pipeline, "CACHE_DIR", str(tmp_path / "cache"))
    r1 = pipeline.run(6.28, -0.46, use_llm=False, out_dir=str(tmp_path / "o"), log=lambda *a: None)
    r2 = pipeline.run(6.28, -0.46, use_llm=False, out_dir=str(tmp_path / "o"), log=lambda *a: None)
    assert len(calls) == 1 and r2["timings"].get("sky_cached") is True
    assert "No new forest clearing" in r1["headline"][0] and "total_s" in r2["timings"]


def test_card_credits_sam_only_for_scars_it_actually_outlined():
    r = _report(A={"pass": True})
    r["candidates"] = [{"status": "SCAR", "sam": False}, {"status": "SCAR", "sam": False}]
    assert "SAM 3.1 refined" not in card.checks_by(r) and "NDVI" in card.checks_by(r)
    r["candidates"] = [{"status": "SCAR", "sam": True}, {"status": "SCAR", "sam": False}]
    assert card.checks_by(r) == "SAM 3.1 refined 1 scar"
    r["meta"] = {"sam_refined": 8, "muse_quote": "muddy brown"}
    assert card.checks_by(r) == "SAM 3.1 refined 8 scars · Muse Spark: “muddy brown”"


def test_pipeline_notes_when_sam_did_not_outline_a_candidate(monkeypatch):
    class B:
        def __init__(self, *a): pass
        def basin_of(self, lat, lon): return 1
    monkeypatch.setattr(pipeline, "river_point", lambda lat, lon, log: (lat, lon, {"moved_m": 0, "ambiguous": False}))
    monkeypatch.setattr(pipeline, "Basins", B)
    monkeypatch.setattr(pipeline, "nearest_upstream", lambda b, bb: ([1], 10.0, 10.0))
    monkeypatch.setattr(sky, "find_candidates", lambda g, limit: ([{"lat": 6.3, "lon": -0.4}], 0.0))
    monkeypatch.setattr(pipeline.Basins, "geometry", lambda self, ids: None, raising=False)
    rgb = np.zeros((4, 4, 3), np.uint8)
    monkeypatch.setattr(sky, "analyse_box", lambda lat, lon, use_sam: {
        "status": "NONE", "area_ha": 0.0, "cloudy": 0.0, "outline_method": "NDVI only (SAM unavailable: HTTPError)",
        "rgb_before": rgb, "rgb_after": rgb})
    r = pipeline.sky_part(6.28, -0.46, log=lambda *a: None)
    assert r["candidates"][0]["sam"] is False


def test_long_headline_fits_its_panel_without_running_into_the_rows():
    long = ("Forest cleared upstream since 2023 (39.9 ha, about 4 km upstream), confirmed by "
            "Global Forest Watch loss data. Cause not confirmed.")
    lines, size = card.fit_lead(long, panel_pt=190)
    assert len(lines) * size * card.LEAD_LH <= 0.6 * 190
    assert card.fit_lead("No new forest clearing found.", panel_pt=190)[1] == 22
