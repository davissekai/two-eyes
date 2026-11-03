"""The phone app's API: start a check, follow it, read the result, get the card."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DEMO_MODE"] = "1"
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from two_eyes.web import server  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "OUT_ROOT", str(tmp_path))
    server.JOBS.clear()
    return TestClient(server.app)


def _wait(client, job_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        body = client.get(f"/api/checks/{job_id}").json()
        if body["state"] != "running":
            return body
        time.sleep(0.2)
    raise AssertionError("check never finished")


def test_app_shell_and_install_files_are_served(client):
    assert "Two Eyes" in client.get("/").text
    assert client.get("/manifest.webmanifest").json()["display"] == "standalone"
    assert client.get("/sw.js").status_code == 200
    assert "--bone" in client.get("/static/app.css").text
    assert ".verdict" in client.get("/page.css").text


def test_spots_people_have_checked_are_listed(client):
    spots = client.get("/api/spots").json()
    assert spots and {"name", "lat", "lon"} <= set(spots[0])


def test_a_check_runs_to_a_result_with_a_card(client):
    job = client.post("/api/checks", data={"lat": 6.28442, "lon": -0.46118}).json()
    body = _wait(client, job["id"])
    assert body["state"] == "done"
    res = body["result"]
    assert "verdict" in res["verdict"] and res["share_text"] and "wa.me" in res["share_html"]
    card = client.get(res["card_url"])
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"


def test_progress_is_readable_while_running(client):
    job = client.post("/api/checks", data={"lat": 6.28442, "lon": -0.46118}).json()
    first = client.get(f"/api/checks/{job['id']}").json()
    assert "readout" in first["readout_html"]
    _wait(client, job["id"])


def test_impossible_coordinates_are_refused(client):
    assert client.post("/api/checks", data={"lat": 95, "lon": 0}).status_code == 422
    assert client.post("/api/checks", data={"lat": 6.2, "lon": -190}).status_code == 422
    assert client.post("/api/checks", data={"lat": "x", "lon": 0}).status_code == 422


def test_unknown_check_is_not_found(client):
    assert client.get("/api/checks/nope").status_code == 404
    assert client.get("/api/checks/nope/card.png").status_code == 404


def test_a_failed_check_says_so_without_leaking_internals(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal path C:/x")
    monkeypatch.setattr(server.pipeline, "run", boom)
    job = client.post("/api/checks", data={"lat": 6.28442, "lon": -0.46118}).json()
    body = _wait(client, job["id"])
    assert body["state"] == "failed" and "didn't finish" in body["readout_html"]
    assert "secret internal path" not in body["readout_html"]


def test_oversized_clip_is_refused(client, monkeypatch):
    monkeypatch.setattr(server, "MAX_CLIP_BYTES", 10)
    r = client.post("/api/checks", data={"lat": 6.28, "lon": -0.46},
                    files={"clip": ("c.mp4", b"x" * 50, "video/mp4")})
    assert r.status_code == 413


def test_only_known_spot_names_reach_the_card(client):
    assert server._spot_name("Birim, N4 bridge") == "Birim, N4 bridge"
    assert server._spot_name("<img src=x onerror=alert(1)>") == "Your spot"
    assert server._spot_name("") == "Your spot"
