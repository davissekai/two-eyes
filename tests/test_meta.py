"""Meta live pieces: scar judge cache, card_muse filter, privacy fail-closed."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_eyes import card_muse, privacy, scar_judge, meta_cache, demo, card  # noqa: E402


def test_scar_judge_score_recorded():
    path = os.path.join(os.path.dirname(__file__), "..", "two_eyes", "assets", "recorded",
                        "scar_judge_score.json")
    import json
    d = json.load(open(path))
    assert d["n"] >= 8
    assert 0.0 <= d["hit_rate"] <= 1.0
    # Honest recorded rate from Muse on real Atewa EE chips (was Birim 5/8 stand-in)
    assert d["correct"] == int(round(d["hit_rate"] * d["n"]))


def test_card_muse_minimum_survives_all_checks_fail():
    r = {
        "bridge": {"name": "Test bridge", "lat": 6.0, "lon": -1.0},
        "scar": {"ndvi_before": 0.7, "ndvi_after": 0.2, "area_ha": 3.0},
        "checks": {k: {"pass": False} for k in "ABCDEF"},
        "ground": {"water_found": False},
        "status": "NONE",
    }
    # Force filter path with fake Muse sentences that all name failing checks
    sentences = ["[A] Big scar.", "[D] Mining pits.", "[GROUND] Muddy water.",
                 "[MIN] Location: Test bridge (6.0000, -1.0000).",
                 "[MIN] NDVI dropped from 0.70 to 0.20 over about 3.0 ha.",
                 "[MIN] Likely source, not proven."]
    kept = card_muse._filter_sentences(sentences, r["checks"], allow_ground=False)
    assert kept  # MIN lines survive
    assert all(not s.startswith("[") for s in kept)
    text = card_muse.write_card(r, use_llm=False)
    assert "Likely source, not proven" in text
    assert "Test bridge" in text or "NDVI" in text
    # Even if Muse returned only failing-check sentences, filter + minimum yields caution
    filtered = card_muse._filter_sentences(
        ["[A] Scar.", "[B] Drains here.", "[D] Mining."], r["checks"], allow_ground=False)
    assert filtered == []
    # write_card without llm returns minimum
    assert "Likely source, not proven." in card_muse.minimum_card(r)


def test_card_muse_drops_failed_check_sentences():
    checks = {"A": {"pass": True}, "B": {"pass": False}, "C": {"pass": None},
              "D": {"pass": True}, "E": {"pass": False}, "F": {"pass": False}}
    sents = ["[A] New clearing upstream.", "[B] It drains here.",
             "[D] Open-water pits visible.", "[E] River muddier below.",
             "[MIN] Likely source, not proven."]
    kept = card_muse._filter_sentences(sents, checks, allow_ground=True)
    joined = " ".join(kept)
    assert "New clearing" in joined and "Open-water pits" in joined
    assert "drains here" not in joined and "muddier" not in joined


def test_privacy_fail_closed_on_detection_error(monkeypatch):
    rgb = np.zeros((64, 64, 3), dtype=np.uint8)

    def boom(*a, **k):
        raise RuntimeError("sam down")

    monkeypatch.setattr(privacy.sam, "concept_boxes", boom)
    with pytest.raises(privacy.PrivacyBlurError):
        privacy.detect_privacy_boxes(rgb)


def test_privacy_blur_applies_boxes(monkeypatch):
    rgb = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)

    def fake_boxes(img, prompt):
        if prompt == "face":
            return [(10, 10, 30, 30)], None
        return [], None

    monkeypatch.setattr(privacy.sam, "concept_boxes", fake_boxes)
    boxes = privacy.detect_privacy_boxes(rgb)
    assert boxes == [(10, 10, 30, 30)]
    out = privacy.blur_frames([rgb])[0]
    assert out.shape == rgb.shape
    # Blurred ROI should differ from original
    assert not np.array_equal(out[10:30, 10:30], rgb[10:30, 10:30])


def test_meta_cache_hit_no_bump(tmp_path, monkeypatch):
    monkeypatch.setenv("TWO_EYES_META_CACHE", str(tmp_path))
    # reload path via env — meta_cache.CACHE_DIR is module-level; set directly
    meta_cache.CACHE_DIR = str(tmp_path)
    key = meta_cache.make_key("test", "x")
    assert meta_cache.get(key) is None
    meta_cache.put(key, {"output_text": "hi"})
    hit = meta_cache.get(key)
    assert hit["output_text"] == "hi"


def test_demo_recorded_mask_and_scar_judge():
    r = demo.demo_report()
    assert r["scar"]["mask"].any()
    assert r["meta"]["sam_refined"] == 9
    sj = r.get("scar_judge") or {}
    assert sj.get("n") >= 8
    assert sj.get("hit_rate") is not None


def test_share_text_uses_card_muse_when_llm(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "fake")
    from two_eyes import config as C
    # Stub write_card to prove routing
    called = {}
    def fake_write(r, use_llm=True):
        called["ok"] = True
        return "Location: stub. NDVI dropped. Likely source, not proven."
    monkeypatch.setattr("two_eyes.card_muse.write_card", fake_write)
    r = demo.demo_report()
    out = card.share_text(r, use_llm=True)
    assert called.get("ok") and "Likely source, not proven" in out
