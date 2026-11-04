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
                 "[MIN] Location: Test bridge (about 6.00, -1.00).",
                 "[MIN] NDVI dropped from 0.70 to 0.20 over about 3.0 ha.",
                 "[MIN] Likely source, not proven."]
    kept = card_muse._filter_sentences(sentences, r["checks"], allow_ground=False)
    assert kept  # MIN lines survive
    assert all(not s.startswith("[") for s in kept)
    text = card_muse.write_card(r, use_llm=False)
    # No clearing → never claim a likely source
    assert "Likely source" not in text and "not proven" not in text
    assert "Test bridge" in text or "NDVI" in text
    filtered = card_muse._filter_sentences(
        ["[A] Scar.", "[B] Drains here.", "[D] Mining."], r["checks"], allow_ground=False)
    assert filtered == []
    assert "Likely source" not in " ".join(card_muse.minimum_card(r))


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


def test_minimum_card_rounds_the_spot_to_about_1km():
    from two_eyes import card_muse
    r = {"spot": {"name": "My bridge", "lat": 6.284423, "lon": -0.461187}, "scar": {}}
    line = card_muse.minimum_card(r)[0]
    assert "6.28" in line and "-0.46" in line and "6.2844" not in line and "My bridge" in line


def test_card_writer_drops_sentences_that_leak_check_jargon():
    from two_eyes import card_muse
    checks = {"A": {"pass": True}, "B": {"pass": True}}
    kept = card_muse._filter_sentences(
        ["[A] Check A passed.", "[B] The clearing drains to the filming spot.", "[MIN] Likely source, not proven."],
        checks)
    assert "Check A passed." not in kept and "The clearing drains to the filming spot." in kept


def test_unnamed_spot_is_called_the_filming_spot():
    from two_eyes import card_muse
    line = card_muse.minimum_card({"spot": {"name": "Your spot", "lat": 5.65, "lon": -0.28}, "scar": {}})[0]
    assert "Your spot" not in line and "the filming spot" in line


def test_share_text_omits_likely_source_when_no_clearing():
    """A clear / no-scar result must not end with 'Likely source, not proven'."""
    r = {
        "status": "NONE",
        "spot": {"name": "Accra", "lat": 5.556, "lon": -0.197},
        "scar": {},
        "checks": {k: {"pass": False} for k in "ABCDEF"},
        "ground": {"water_found": False},
    }
    assert "Likely source" not in " ".join(card_muse.minimum_card(r))
    out = card_muse.write_card(r, use_llm=False)
    assert "Likely source" not in out
    # Muse that wrongly hedges is stripped
    sentences = ["[MIN] Location: Accra.", "[MIN] Likely source, not proven."]
    kept = card_muse._filter_sentences(sentences, r["checks"])
    # write_card path with mocked muse
    import two_eyes.card_muse as cm
    class Fake:
        @staticmethod
        def respond(*a, **k):
            return '{"sentences": ["[MIN] Location: Accra (about 5.56, -0.20).", "[MIN] Likely source, not proven."]}'
        @staticmethod
        def parse_json(t):
            import json
            return json.loads(t)
    # route through write_card with use_llm True by stubbing muse + SHARE_LLM
    from two_eyes import config as C
    old_share = C.SHARE_LLM
    C.SHARE_LLM = True
    try:
        import two_eyes.muse as muse_mod
        real_respond, real_parse = muse_mod.respond, muse_mod.parse_json
        muse_mod.respond = Fake.respond
        muse_mod.parse_json = Fake.parse_json
        try:
            text = card_muse.write_card(r, use_llm=True)
        finally:
            muse_mod.respond, muse_mod.parse_json = real_respond, real_parse
    finally:
        C.SHARE_LLM = old_share
    assert "Likely source" not in text
    assert "Accra" in text or "Location" in text


def test_share_text_keeps_likely_source_when_scar_drains_here():
    r = {
        "status": "SCAR",
        "spot": {"name": "Birim, N4 bridge", "lat": 6.28442, "lon": -0.46118},
        "scar": {"ndvi_before": 0.72, "ndvi_after": 0.18, "area_ha": 17.0},
        "checks": {"A": {"pass": True}, "B": {"pass": True}, "C": {"pass": True},
                   "D": {"pass": True}, "E": {"pass": True}, "F": {"pass": False}},
        "ground": {"water_found": True, "label": "muddy brown"},
    }
    assert card_muse.claims_source(r) is True
    assert "Likely source, not proven." in card_muse.minimum_card(r)
    assert "Likely source, not proven" in card_muse.write_card(r, use_llm=False)



def test_share_text_no_likely_source_when_only_clearing_confirmed():
    """Ladder at "Clearing confirmed" (mining seen, river below not measured): share text must not say likely source."""
    r = {
        "status": "SCAR",
        "spot": {"name": "Black Volta", "lat": 8.153, "lon": -2.034},
        "scar": {"ndvi_before": 0.72, "ndvi_after": 0.18, "area_ha": 5.1},
        "checks": {"A": {"pass": True}, "B": {"pass": True}, "C": {"pass": True},
                   "D": {"pass": True}, "E": {"pass": None}, "F": {"pass": False}},
        "ground": {"water_found": True, "label": "muddy brown"},
    }
    assert card_muse.claims_source(r) is False
    assert "Likely source" not in " ".join(card_muse.minimum_card(r))
    text = card_muse.write_card(r, use_llm=False)
    assert "Likely source" not in text and "not proven" not in text
