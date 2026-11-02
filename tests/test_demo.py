import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_eyes import card, config as C, demo, pipeline  # noqa: E402


def test_is_demo_mode_when_env_set(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    assert demo.is_demo_mode()


def test_is_demo_mode_without_meta_key(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert demo.is_demo_mode()


def test_share_llm_is_true():
    assert C.SHARE_LLM is True


def test_share_text_falls_back_to_template_without_key(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    r = {"status": "NONE", "checks": {"A": {"pass": False}}, "scar": {}, "spot": {}}
    assert "No new forest clearing" in card.share_text(r)   # no Meta call, no crash


def test_field_evidence_palette_constants():
    assert card.GRAPHITE == "#15130F" and card.BONE == "#F2EDE4" and card.SILT == "#C9A27E"
    assert card.LATERITE == "#9C5A34" and card.LIME == "#D4FF3A" and card.WA == "#25D366"
    assert card.CONTOUR_COLOR == card.LIME


def test_demo_credit_and_recorded_run_date():
    r = demo.demo_report()
    assert "Goldenwabbit" in r["ground"]["credit"] and "CC BY-SA 4.0" in r["ground"]["credit"]
    assert r["date"] == "2026-10-28"          # recorded run, not today
    assert "Copernicus" in r["credit_sat"] and "2023" in r["credit_sat"] and "2026" in r["credit_sat"]


def test_demo_sam_boxes_are_labelled_illustrative():
    r = demo.demo_report()
    assert r["scar"]["boxes_illustrative"] is True
    assert "not live SAM output" in r["scar"]["outline_method"]
    assert "not SAM output" in r["ground"]["method"]


def test_demo_report_shape():
    r = demo.demo_report()
    assert r["status"] == "SCAR" and r["spot"]["name"] == "Birim, N4 bridge"
    assert abs(r["scar"]["area_ha"] - 17.0) < 0.01 and abs(r["scar"]["distance_km"] - 19.0) < 0.5
    assert {k: v["pass"] for k, v in r["checks"].items()} == \
        {"A": True, "B": True, "C": None, "D": True, "E": None, "F": False}
    assert r["ground"]["label"] == "muddy brown" and r["ground"]["water_found"]
    m = r["scar"]["mask"]
    assert isinstance(m, np.ndarray) and m.dtype == bool and m.any()
    assert r["ground"]["still"].ndim == 3


def test_headline_of_demo_report():
    h = card.headline(demo.demo_report())
    assert h[0] == "Possible forest clearing, 19 km upstream."
    assert "since early 2023" in h[1] and "17.0 ha" in h[1]
    assert "our check only, not yet confirmed" in h[1]
    assert "muddy brown" in "\n".join(h) and not any("%" in x for x in h)
    share = card.share_text(demo.demo_report(), use_llm=False)
    assert "Possible forest clearing, 19 km upstream." in share
    assert "our check only, not yet confirmed" in share


def test_pipeline_run_offline_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(pipeline, "CACHE_DIR", str(tmp_path / "cache"))
    logs = []
    r = pipeline.run(6.28442, -0.46118, name="Birim, N4 bridge",
                     out_dir=str(tmp_path / "o"), log=logs.append)
    assert os.path.isfile(r["card_png"]) and os.path.getsize(r["card_png"]) > 10_000
    assert r["share_text"] and r["status"] == "SCAR"
    assert r["timings"].get("demo") is True
    assert any("Demo mode" in x for x in logs)
    assert os.path.isfile(os.path.join(str(tmp_path / "o"), "report.json"))


def test_pipeline_run_demo_for_non_demo_point(tmp_path, monkeypatch):
    """Any point in demo mode returns the cached report with a clear 'not analysed live' log."""
    monkeypatch.setenv("DEMO_MODE", "1")
    logs = []
    r = pipeline.run(0.0, 0.0, name="Custom point", out_dir=str(tmp_path / "o"), log=logs.append)
    assert r["demo"] is True and any("not analysed live" in x for x in logs)


def test_demo_meta_badge_and_muse_quote():
    r = demo.demo_report()
    assert r["meta"]["sam_refined"] == 8 and r["meta"]["muse_quote"] == "muddy brown"
    assert "Muse Spark" in r["ground"]["label_source"]
    n, muse = card._meta_info(r)
    assert n == 8 and muse == 'Muse Spark: \u201cmuddy brown\u201d'


def test_demo_sam_boxes_within_image():
    r = demo.demo_report()
    boxes = r["scar"]["sam_boxes"]
    assert 1 <= len(boxes) <= 3
    h, w = r["scar"]["rgb_after"].shape[:2]
    for l, t, rr, b in boxes:
        assert 0 <= l < rr < w and 0 <= t < b < h


def test_card_renders_demo_meta(tmp_path):
    r = demo.demo_report()
    p = card.render(r, str(tmp_path / "card.png"))
    assert os.path.getsize(p) > 10_000


def test_whatsapp_url_built_offline():
    u = card.whatsapp_url("Forest cleared upstream. This doesn't mean the water is safe.")
    assert u.startswith("https://wa.me/?text=")
    from urllib.parse import unquote
    assert unquote(u.split("=", 1)[1]) == "Forest cleared upstream. This doesn't mean the water is safe."


def test_share_html_block():
    from two_eyes import app
    html = app._share_html(card.whatsapp_url("hi"))
    assert "wa.me" in html and "Download" in html
    assert app._share_html("") == ""


def test_app_chip_texts():
    from two_eyes import app
    chip = app._chip_html()
    assert "SAM 3.1 refined 8 scars" in chip and "Muse Spark" in chip and "muddy brown" in chip


def test_picking_a_known_spot_fills_its_coordinates_and_hides_the_custom_fields():
    from two_eyes import app
    name = list(app.DEMO_SPOTS)[1]
    assert app.spot_pick(name) == (app.DEMO_SPOTS[name], False)


def test_picking_custom_point_keeps_typed_coordinates_and_shows_the_fields():
    from two_eyes import app
    assert app.spot_pick("Custom point") == (None, True)


def test_dropdown_label_is_readable_on_bone():
    from two_eyes import app
    css = app.build_css()
    selector = '[data-testid="block-info"]'
    assert selector in css and app.LATERITE in css.split(selector, 1)[1][:60]


def test_sample_result_is_the_recorded_birim_case_in_its_own_folder(tmp_path, monkeypatch):
    from two_eyes import app
    monkeypatch.chdir(tmp_path)
    s = app.sample_result()
    assert os.path.exists(s["card_png"]) and os.path.join("two_eyes_out", "sample") in s["card_png"]
    assert "wa.me" in s["share_html"]
    assert "Birim" in str(s["report"]["spot"])
    assert s["share_text"]
