"""The phone app's API: start a check, follow it, read the result, get the card."""
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DEMO_MODE"] = "1"
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from two_eyes.web import server  # noqa: E402

def _clip_files():
    return {"clip": ("river.mp4", b"fake-bytes", "video/mp4")}




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
    job = client.post("/api/checks", data={"lat": 6.28442, "lon": -0.46118}, files=_clip_files()).json()
    body = _wait(client, job["id"])
    assert body["state"] == "done"
    res = body["result"]
    assert "verdict" in res["verdict"] and res["share_text"] and "wa.me" in res["share_html"]
    card = client.get(res["card_url"])
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"


def test_progress_is_readable_while_running(client):
    job = client.post("/api/checks", data={"lat": 6.28442, "lon": -0.46118}, files=_clip_files()).json()
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
    job = client.post("/api/checks", data={"lat": 6.28442, "lon": -0.46118}, files=_clip_files()).json()
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


def test_a_persons_own_clip_is_not_credited_to_anyone_else(client, monkeypatch):
    seen = {}

    def fake_run(*a, **k):
        seen.update(k)
        raise RuntimeError("stop here")
    monkeypatch.setattr(server.pipeline, "run", fake_run)
    job = client.post("/api/checks", data={"lat": 6.28, "lon": -0.46},
                      files={"clip": ("c.mp4", b"x" * 50, "video/mp4")}).json()
    _wait(client, job["id"])
    assert seen["clip"] and seen["clip_credit"] is None


def test_too_many_checks_at_once_are_turned_away(client, monkeypatch):
    release = threading.Event()

    def slow_run(*a, **k):
        release.wait(10)
        raise RuntimeError("done waiting")
    monkeypatch.setattr(server.pipeline, "run", slow_run)
    monkeypatch.setattr(server, "MAX_RUNNING", 1)
    first = client.post("/api/checks", data={"lat": 6.28, "lon": -0.46}, files=_clip_files())
    second = client.post("/api/checks", data={"lat": 6.28, "lon": -0.46}, files=_clip_files())
    release.set()
    assert first.status_code == 200
    assert second.status_code == 429 and "busy" in second.json()["detail"]
    _wait(client, first.json()["id"])
    assert client.post("/api/checks", data={"lat": 6.28, "lon": -0.46}, files=_clip_files()).status_code == 200


def test_a_hung_check_gives_up_frees_its_slot_and_ignores_a_late_answer(client, monkeypatch):
    release = threading.Event()

    def hung_run(*a, **k):
        release.wait(10)
        return {"card_png": "late.png", "share_text": "late"}
    monkeypatch.setattr(server.pipeline, "run", hung_run)
    monkeypatch.setattr(server, "_result", lambda job_id, r: {"late": True})
    monkeypatch.setattr(server, "MAX_RUNNING", 1)
    monkeypatch.setattr(server, "MAX_CHECK_SECONDS", 0.3)
    job = client.post("/api/checks", data={"lat": 6.28, "lon": -0.46}, files=_clip_files()).json()
    body = _wait(client, job["id"], timeout=5)
    assert body["state"] == "failed" and "too long" in body["readout_html"]
    assert client.post("/api/checks", data={"lat": 6.28, "lon": -0.46}, files=_clip_files()).status_code == 200
    release.set()
    time.sleep(0.3)
    late = client.get(f"/api/checks/{job['id']}").json()
    assert late["state"] == "failed" and late["result"] is None


def test_check_without_clip_is_refused(client):
    r = client.post("/api/checks", data={"lat": 6.28442, "lon": -0.46118})
    assert r.status_code == 400
    assert "film the water" in r.json()["detail"].lower()


def test_empty_clip_is_refused(client):
    files = {"clip": ("clip.mp4", b"", "video/mp4")}
    r = client.post("/api/checks", data={"lat": 6.28442, "lon": -0.46118}, files=files)
    assert r.status_code == 400 and "empty" in r.json()["detail"].lower()


def test_desktop_css_is_wider_than_phone(client):
    css = client.get("/static/app.css").text
    assert "max-width:1100px" in css or "max-width: 1100px" in css
    assert "@media (min-width:900px)" in css or "@media (min-width: 900px)" in css
    assert "max-width:480px" in css  # mobile shell kept


def test_failures_are_explained_in_plain_words():
    from two_eyes.trace import NoRiverHere
    from two_eyes.web import server
    assert "river" in server._plain_reason(NoRiverHere("We couldn't find land that drains to a river")).lower()
    assert server._plain_reason(RuntimeError("boom")) == server.FAIL_REASON
    assert "boom" not in server._plain_reason(RuntimeError("boom"))
