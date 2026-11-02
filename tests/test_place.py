"""Where the citizen filmed: any public spot on the river, shown to others only to about 1 km."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from two_eyes import card, demo, ground, pipeline  # noqa: E402


def _report():
    return {"status": "SCAR", "spot": {"lat": 6.28442, "lon": -0.46118, "name": "Birim, N4 bridge"},
            "scar": {"lat": 6.45441, "lon": -0.48332, "area_ha": 17.0, "distance_km": 19.0},
            "checks": {"A": {"pass": True}, "B": {"pass": False}}}


def test_public_report_shows_the_filming_spot_only_to_about_1_km():
    spot = pipeline.public(_report())["spot"]
    assert (spot["lat"], spot["lon"]) == (6.28, -0.46)
    assert spot["name"] == "Birim, N4 bridge"


def test_public_report_keeps_the_clearing_precise_so_officials_can_find_it():
    scar = pipeline.public(_report())["scar"]
    assert (scar["lat"], scar["lon"]) == (6.45441, -0.48332)


def test_public_report_does_not_change_the_report_it_was_given():
    r = _report()
    pipeline.public(r)
    assert r["spot"]["lat"] == 6.28442


def test_public_report_without_a_spot_location_does_not_crash():
    assert pipeline.public({"spot": {}})["spot"] == {}
    assert "spot" not in pipeline.public({"status": "NONE"})


def test_card_location_is_rounded_and_says_so():
    assert card.location_text({"lat": 6.28442, "lon": -0.46118}) == "6.28, -0.46 (to about 1 km)"
    assert card.location_text({"lat": -0.004, "lon": 0.0}) == "0.00, 0.00 (to about 1 km)"


def test_card_location_without_coordinates_is_a_dash():
    assert card.location_text({}) == "—"
    assert card.location_text({"lat": None, "lon": 1.0}) == "—"


def test_checks_talk_about_the_spot_not_a_bridge():
    assert dict(card.BADGES)["B"] == "Drains to this spot"
    assert "bridge" not in " ".join(card.headline(_report())).lower()


def test_colour_question_allows_bank_shots():
    q = ground.COLOUR_QUESTION.lower()
    assert "riverbank" in q and "from a bridge." not in q


def test_demo_report_names_its_spot():
    assert demo.demo_report()["spot"]["name"] == "Birim, N4 bridge"
