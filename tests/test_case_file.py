"""The case file the citizen reads: plain words, honest strength of evidence, nothing unescaped."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_eyes import case_file, demo, readout, share  # noqa: E402


def _r(**checks):
    r = {"status": "SCAR", "spot": {"lat": 6.28442, "lon": -0.46118, "name": "Birim, N4 bridge"},
         "scar": {"area_ha": 17.0, "distance_km": 19.0}, "checks": {}}
    r["checks"].update({k: {"pass": v} for k, v in checks.items()})
    return r


# --- everyday scale ---

def test_area_is_put_in_football_pitches():
    assert case_file.pitches(17.0) == "about 24 football pitches"
    assert case_file.pitches(0.7) == "about 1 football pitch"


def test_tiny_or_missing_area_has_no_pitch_comparison():
    assert case_file.pitches(0.3) == "smaller than a football pitch"
    assert case_file.pitches(None) == ""


# --- how sure are we ---

def test_evidence_level_follows_the_card_wording():
    assert case_file.evidence_level(_r(A=True, B=True)) == 1                       # possible
    assert case_file.evidence_level(_r(A=True, B=True, C=True)) == 2               # clearing confirmed
    assert case_file.evidence_level(_r(A=True, B=True, C=True, D=True, E=True)) == 3   # likely source


def test_no_ladder_when_nothing_upstream_drains_here():
    assert case_file.evidence_level(_r(A=False)) == 0
    assert case_file.evidence_level(_r(A=True, B=False)) == 0
    assert case_file.evidence_level({"status": "CLOUDY", "checks": {}}) == 0


def test_ladder_says_what_would_move_it_up():
    assert "radar" in case_file.next_step(_r(A=True, B=True)).lower()
    nxt = case_file.next_step(_r(A=True, B=True, C=True, D=True)).lower()
    assert "muddier" in nxt and "mining" not in nxt
    assert "authorities" in case_file.next_step(_r(A=True, B=True, C=True, D=True, E=True)).lower()


def test_ladder_never_claims_proof():
    html = case_file.verdict_html(_r(A=True, B=True, C=True, D=True, E=True))
    assert 'class="rung on"' in html and html.count('class="rung on"') == 1
    assert "Proven" in html and "only the authorities" in html.lower()


# --- the river trace ---

def test_trace_runs_from_the_spot_to_the_clearing_in_river_order():
    keys = [s["key"] for s in case_file.stations(demo.demo_report())]
    assert keys == ["clip", "E", "B", "A", "D", "C", "F"]


def test_trace_states_match_the_checks():
    st = {s["key"]: s["state"] for s in case_file.stations(demo.demo_report())}
    assert st == {"clip": "yes", "E": "unknown", "B": "yes", "A": "yes", "D": "yes", "C": "unknown", "F": "no"}


def test_trace_without_a_clip_says_so_instead_of_failing():
    r = _r(A=True, B=True)
    clip = next(s for s in case_file.stations(r) if s["key"] == "clip")
    assert clip["state"] == "skip" and "no clip" in clip["detail"].lower()


def test_bank_shot_is_named_on_the_trace():
    r = _r(A=True, B=True)
    r["ground"] = {"water_found": True, "muddy": True, "label": "muddy brown", "view": "bank"}
    clip = next(s for s in case_file.stations(r) if s["key"] == "clip")
    assert clip["detail"] == "water looks muddy brown, filmed from the bank"


def test_glare_clip_is_unknown_not_a_fail():
    r = _r(A=True, B=True)
    r["ground"] = {"water_found": True, "muddy": None, "label": "too bright to judge (glare)"}
    clip = next(s for s in case_file.stations(r) if s["key"] == "clip")
    assert clip["state"] == "unknown" and "glare" in clip["detail"]


# --- the two eyes ---

def test_sky_eye_has_before_and_after_images_and_a_slider():
    html = case_file.eyes_html(demo.demo_report())
    assert html.count("data:image/jpeg;base64,") >= 2 and 'type="range"' in html


def test_eyes_without_images_render_nothing_rather_than_breaking():
    assert case_file.eyes_html(_r(A=False)) == ""


def test_model_words_are_escaped():
    r = demo.demo_report()
    r["ground"]["label"] = "<script>alert(1)</script>"
    html = case_file.eyes_html(r) + case_file.trace_html(r)
    assert "<script>" not in html and "&lt;script&gt;" in html


# --- share ---

def test_whatsapp_preview_shows_the_message_escaped():
    html = share.preview_html("Mud <b>here</b>\nsecond line", card_png=None)
    assert "&lt;b&gt;here" in html and "<b>here" not in html


def test_whatsapp_preview_uses_the_real_card(tmp_path):
    from PIL import Image
    p = tmp_path / "card.png"
    Image.fromarray(np.zeros((40, 30, 3), np.uint8)).save(p)
    assert "data:image/jpeg;base64," in share.preview_html("hi", card_png=str(p))


def test_next_steps_point_somewhere_useful():
    html = share.next_steps_html().lower()
    assert "minerals commission" in html and "another spot" in html


# --- the live readout ---

def test_readout_lights_steps_from_the_pipeline_log():
    steps = readout.steps(["Tracing the catchment above the filming spot (HydroBASINS level 12)...",
                           "Searching 307 km² upstream for new scars (Sentinel-2, NDVI drop)..."], finished=False)
    assert [s["state"] for s in steps[:3]] == ["done", "live", "wait"]
    assert "307 km²" in steps[0]["detail"]


def test_cached_place_skips_straight_to_the_checks():
    steps = readout.steps(["Satellite checks: cached result for this place (same dates, same cut-offs)."],
                          finished=False)
    assert all(s["state"] == "done" for s in steps[:4])


def test_finished_run_is_all_done_and_clip_step_only_with_a_clip():
    steps = readout.steps(["Done: something"], finished=True)
    assert all(s["state"] == "done" for s in steps)
    assert not any(s["key"] == "clip" for s in steps)
    with_clip = readout.steps(["Ground eye: SAM 3.1 on the clip (running alongside the satellite checks)..."],
                              finished=False)
    assert any(s["key"] == "clip" and s["state"] == "live" for s in with_clip)


def test_demo_run_does_not_pretend_the_satellite_ran_live():
    steps = readout.steps(["Demo mode: cached Birim, N4 bridge result from 28 Oct 2026 (no Earth Engine...).",
                           "Done (demo): x"], finished=True)
    assert all("recorded run" in s["detail"] for s in steps if s["key"] != "card")


def test_failed_run_says_so_in_plain_words():
    html = readout.html(["Something failed: ValueError: bad"], finished=True, failed=True)
    assert "didn't finish" in html.lower()


# --- the clip is the citizen's evidence ---

def test_result_without_a_clip_asks_for_one():
    html = case_file.verdict_html(_r(A=True, B=True)).lower()
    assert "add a clip" in html


def test_result_with_a_clip_does_not_nag():
    r = _r(A=True, B=True)
    r["ground"] = {"water_found": True, "muddy": True, "label": "muddy brown"}
    assert "add a clip" not in case_file.verdict_html(r).lower()


def test_no_clip_nudge_when_there_is_nothing_upstream():
    assert "add a clip" not in case_file.verdict_html(_r(A=False)).lower()
