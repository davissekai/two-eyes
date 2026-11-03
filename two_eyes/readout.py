"""Live readout of a check, in plain words, built from the pipeline's log lines as they arrive.

A real run takes about 80 s for a new place; showing each step as it happens keeps people from
thinking the page has frozen.
"""
import re
from html import escape

from . import config as C

# key, plain-language title, log prefix that starts the step
_STEPS = [
    ("trace", "Following the river upstream", "Tracing the catchment"),
    ("compare", f"Comparing satellite photos from {C.BEFORE[0][:4]} and {C.AFTER[0][:4]}", "Searching"),
    ("outline", "Outlining cleared patches with SAM 3.1", None),
    ("checks", "Checking other sources", "Checks B-F"),
    ("clip", "Reading the colour of your clip", "Ground eye"),
    ("card", "Writing your evidence card", "Done"),
]


def _detail(key, lines):
    """A short technical sub-line for a step, from the log, when there is one."""
    for ln in lines:
        if key == "trace" and ln.startswith("Searching"):
            m = re.search(r"([\d,]+) km²", ln)
            if m:
                return f"{m.group(1)} km² of land drains to this spot"
        if key == "outline" and "candidate patch" in ln:
            m = re.match(r"(\d+) candidate patch\(es\)\. Refining (\d+)", ln)
            if m:
                return f"{m.group(1)} cleared patches found; outlining the {m.group(2)} biggest"
        if key == "checks" and ln.startswith("Checks B-F"):
            return "radar alerts, forest-loss maps, protected areas"
    if key == "compare":
        return "Sentinel-2, clouds removed"
    if key == "clip":
        return "SAM 3.1 finds the water, Muse Spark reads its colour"
    return ""


def steps(lines, finished):
    """Each step with state done / live / wait. The clip step appears only when a clip was sent."""
    has_clip = any(ln.startswith("Ground eye") for ln in lines)
    cached = any(ln.startswith("Satellite checks: cached") for ln in lines)
    demo = any(ln.startswith("Demo mode") for ln in lines)
    started = {}
    for i, ln in enumerate(lines):
        for key, _, prefix in _STEPS:
            if prefix and ln.startswith(prefix) and key not in started:
                started[key] = i
        if "candidate patch" in ln and "outline" not in started:
            started["outline"] = i
    sky = ["trace", "compare", "outline", "checks"]
    out, last_sky = [], max((sky.index(k) for k in started if k in sky), default=-1)
    for key, title, _ in _STEPS:
        if key == "clip" and not has_clip:
            continue
        if finished or (cached and key in sky):
            state = "done"
        elif key in sky:
            idx = sky.index(key)
            state = "done" if idx < last_sky else "live" if idx == last_sky else "wait"
        elif key == "clip":
            state = "live"
        else:
            state = "wait"
        if demo and key != "card":
            detail = "from the recorded run, not checked live"
        elif cached and key in sky:
            detail = "already on file for this place"
        else:
            detail = _detail(key, lines)
        out.append({"key": key, "title": title, "state": state, "detail": detail})
    return out


def html(lines, finished, failed=False, elapsed_s=None, reason=None):
    """The readout panel. reason: what the person can do about a failure, when it is theirs to fix."""
    if failed:
        head = "The check didn't finish"
    elif finished:
        head = f"Done in {elapsed_s:.0f} s" if elapsed_s is not None else "Done"
    else:
        head = "Checking upstream…"
    st = steps(lines, finished and not failed)
    done = sum(s["state"] == "done" for s in st)
    items = "".join(
        f'<li class="{s["state"]}"><span class="dot"></span><span>{escape(s["title"])}'
        f'<small>{escape(s["detail"])}</small></span></li>' for s in st)
    note = ""
    if failed:
        note = (f'<p class="fail">{escape(reason)}</p>' if reason else
                '<p class="fail">Something went wrong on our side. Check your connection and try again; '
                'the technical details are under "How the checks ran".</p>')
    return (f'<div class="readout" aria-live="polite"><div class="readout-top"><span class="mono">{head}</span></div>'
            f'<div class="bar"><i style="width:{round(100 * done / max(len(st), 1))}%"></i></div>'
            f'<ol class="run">{items}</ol>{note}</div>')

