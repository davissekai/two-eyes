import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_eyes import card, checks, ground, sky, trace  # noqa: E402
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
    r = {"date": "2026-10-28", "status": "SCAR", "bridge": {"lat": 6.28442, "lon": -0.46118, "name": "N4 Birim bridge"},
         "scar": {"area_ha": 4.3, "distance_km": 13.1}, "checks": {}}
    r["checks"].update(k)
    return r


def test_headlines_follow_the_table():
    assert "No new forest clearing" in card.headline({"status": "NONE", "checks": {"A": {"pass": False}}})[0]
    assert "Clouds" in card.headline({"status": "CLOUDY", "checks": {}})[0]
    t = card.headline(_report(A={"pass": True}, B={"pass": True}))
    assert "Possible forest clearing" in t[0] and "not yet confirmed" in t[0]
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
