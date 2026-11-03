"""The phone app's server: the app shell, and a small API around the same pipeline the Gradio demo uses.

A check runs in a background thread; the phone polls it for the live readout, then fetches the result.
Polling (not a stream) because phone connections drop, and a poll simply picks up where it left off.
"""
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import case_file, demo, pipeline, readout
from .. import share as share_ui
from ..app import DEMO_SPOTS
from ..look import ASSETS, page_css

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
OUT_ROOT = os.path.join(demo.OUT_DIR, "web")
MAX_CLIP_BYTES = 80 * 1024 * 1024     # a 10 s phone clip is well under this
MAX_JOBS = 50                         # finished checks kept in memory; the oldest are dropped
MAX_RUNNING = 3                       # checks at once; each one calls Earth Engine and the paid models
FAIL_REASON = "Something went wrong on our side. Check your connection and try again."
BUSY = "Two Eyes is busy with other checks. Try again in a minute."

log = logging.getLogger("two_eyes.web")

JOBS = {}
_LOCK = threading.Lock()

app = FastAPI(title="Two Eyes", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
_PAGE_CSS = page_css()


def _result(job_id, r):
    """The case file as HTML pieces for the phone, with the card as a URL instead of a file path."""
    return {
        "verdict": case_file.verdict_html(r),
        "trace": case_file.trace_html(r) if case_file.evidence_level(r) else "",
        "eyes": case_file.eyes_html(r),
        "preview": share_ui.preview_html(r["share_text"], r["card_png"]),
        "share_html": share_ui.buttons_html(r["share_text"]),
        "next_steps": share_ui.next_steps_html(),
        "share_text": r["share_text"],
        "card_url": f"/api/checks/{job_id}/card.png",
    }


def _work(job_id, lat, lon, name, clip):
    """Run one check, feeding its log into the job so polls can show progress."""
    job = JOBS[job_id]
    try:
        # The clip is the person's own footage, so it carries no photo credit.
        r = pipeline.run(lat, lon, name=name, clip=clip, clip_credit=None,
                         out_dir=os.path.join(OUT_ROOT, job_id), log=lambda *a: job["lines"].append(" ".join(map(str, a))))
        job.update(card=r["card_png"], result=_result(job_id, r), state="done")
    except Exception as ex:
        # The type goes to the server log for us; the person sees a plain reason, never internals.
        log.warning("check %s failed: %s: %s", job_id, type(ex).__name__, ex)
        job["state"] = "failed"
    finally:
        job["elapsed"] = time.time() - job["t0"]
        if clip:
            shutil.rmtree(os.path.dirname(clip), ignore_errors=True)


def _forget_oldest():
    """Keep memory and disk bounded: drop the oldest finished checks past MAX_JOBS."""
    done = [k for k, j in JOBS.items() if j["state"] != "running"]
    for k in done[:max(0, len(JOBS) - MAX_JOBS)]:
        JOBS.pop(k, None)
        shutil.rmtree(os.path.join(OUT_ROOT, k), ignore_errors=True)


def _running():
    return sum(j["state"] == "running" for j in JOBS.values())


async def _save_clip(clip):
    """Stream the upload to a private temp folder, refusing it past MAX_CLIP_BYTES."""
    folder = tempfile.mkdtemp(prefix="two-eyes-clip-")
    path, size = os.path.join(folder, "upload"), 0
    with open(path, "wb") as f:
        while chunk := await clip.read(1 << 20):
            size += len(chunk)
            if size > MAX_CLIP_BYTES:
                f.close()
                shutil.rmtree(folder, ignore_errors=True)
                raise HTTPException(413, "That clip is too big. Ten seconds of video is enough.")
            f.write(chunk)
    if size == 0:
        shutil.rmtree(folder, ignore_errors=True)
        return None
    return path


@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as f:
        return f.read()


@app.get("/page.css")
def css():
    return Response(_PAGE_CSS, media_type="text/css", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(os.path.join(STATIC, "manifest.webmanifest"), media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    # Served from the root so it may control the whole app, not just /static.
    return FileResponse(os.path.join(STATIC, "sw.js"), media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})


SPOTS = [{"name": k.split(" (")[0], "lat": v[0], "lon": v[1]} for k, v in DEMO_SPOTS.items()]


def _spot_name(name):
    """Only a known spot's name goes on the card; anything else is "Your spot", so no free text is shown."""
    return name if any(s["name"] == name for s in SPOTS) else "Your spot"


@app.get("/hero.jpg")
def hero():
    return FileResponse(os.path.join(ASSETS, "bridge.jpg"), media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/spots")
def spots():
    return SPOTS


@app.post("/api/checks")
async def start_check(lat: float = Form(..., ge=-90, le=90), lon: float = Form(..., ge=-180, le=180),
                      name: str = Form("", max_length=80), clip: Optional[UploadFile] = File(None)):
    if _running() >= MAX_RUNNING:
        raise HTTPException(429, BUSY)
    path = await _save_clip(clip) if clip is not None else None
    job_id = uuid.uuid4().hex
    with _LOCK:
        if _running() >= MAX_RUNNING:
            if path:
                shutil.rmtree(os.path.dirname(path), ignore_errors=True)
            raise HTTPException(429, BUSY)
        JOBS[job_id] = {"state": "running", "lines": [], "t0": time.time(), "elapsed": None,
                        "result": None, "card": None}
        _forget_oldest()
    threading.Thread(target=_work, args=(job_id, lat, lon, _spot_name(name), path), daemon=True).start()
    return {"id": job_id}


def _job(job_id):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "No check with that id. It may have expired; start a new one.")
    return job


@app.get("/api/checks/{job_id}")
def check_status(job_id: str):
    job = _job(job_id)
    lines, state = list(job["lines"]), job["state"]
    if state == "failed":
        html = readout.html(lines, finished=True, failed=True, reason=FAIL_REASON)
    else:
        html = readout.html(lines, finished=state == "done", elapsed_s=job["elapsed"])
    return {"state": state, "readout_html": html, "result": job["result"]}


@app.get("/api/checks/{job_id}/card.png")
def card_png(job_id: str):
    job = _job(job_id)
    if not job["card"] or not os.path.exists(job["card"]):
        raise HTTPException(404, "The card isn't ready yet.")
    return FileResponse(job["card"], media_type="image/png", filename="two-eyes-evidence-card.png")
