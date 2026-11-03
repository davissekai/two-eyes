"""Web UI (Gradio): check a river spot, watch the check run, read the case file, share the card.

Local:   DEMO_MODE=1 python -m two_eyes.app        (offline demo, no API keys needed)
Colab:   from two_eyes.app import launch; launch(share=True)
"""
import os
import queue
import threading
import time

from . import case_file, demo, pipeline, readout
from . import share as share_ui   # `share` is launch()'s public-link flag
from .look import ASSETS, LATERITE, build_css  # noqa: F401  (LATERITE: tests check the label colour)

DEMO_SPOTS = {
    "Birim, N4 bridge (6.28442, -0.46118)": (6.28442, -0.46118),
    "Birim, N6 bridge (6.38624, -0.55278)": (6.38624, -0.55278),
    "Densu, Akwadum bridge (6.111737, -0.343074)": (6.111737, -0.343074),
}
CUSTOM = "Custom point"

# The bundled bridge/hero imagery is the Goldenwabbit photo, not the old Pra/Beposo clip.
HERO_CREDIT = "Photo: Goldenwabbit, Wikimedia Commons, CC BY-SA 4.0"

# Asks the phone for its position and says plainly what happened. Needs https or localhost;
# on failure the fields stay empty to type in, and the message says why.
LOCATE_JS = """async () => {
  const fail = (why) => [null, null, `<p class="gps-msg bad">${why} Or pick a spot below.</p>`];
  if (!navigator.geolocation || !window.isSecureContext)
    return fail("This page can't use your location (it needs a secure https link).");
  try {
    const p = await new Promise((ok, no) => navigator.geolocation.getCurrentPosition(ok, no,
      {enableHighAccuracy: true, timeout: 15000}));
    const c = p.coords;
    return [c.latitude, c.longitude, `<p class="gps-msg">Location found: ${c.latitude.toFixed(4)}, ` +
      `${c.longitude.toFixed(4)} (within about ${Math.round(c.accuracy)} m).</p>`];
  } catch (e) {
    return fail(e.code === 1 ? "Location is blocked. Allow location for this site in your browser settings."
                             : "Couldn't get a GPS fix. Try again in the open, away from buildings.");
  }
}"""
# The brand is light mode only; Gradio would otherwise follow a dark phone and turn the text white.
LIGHT_JS = "() => { document.body.classList.remove('dark'); document.documentElement.classList.remove('dark'); }"
SCROLL_JS = ("() => { const el = document.getElementById('readout'); "
             "if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'}); }")


def spot_pick(spot):
    """What picking a spot does to the form: (coordinates to fill or None, show the custom fields).

    Coordinates only matter for a custom point, so the fields stay hidden for the named spots.
    """
    if spot in DEMO_SPOTS:
        return DEMO_SPOTS[spot], False
    return None, True


def sections(r):
    """Every case-file section for one report (live or demo), as HTML, plus the card and message."""
    return {
        "verdict": case_file.verdict_html(r),
        "trace": case_file.trace_html(r) if case_file.evidence_level(r) else "",
        "eyes": case_file.eyes_html(r),
        "preview": share_ui.preview_html(r["share_text"], r["card_png"]),
        "share_html": share_ui.buttons_html(r["share_text"]),
        "card_png": r["card_png"],
        "share_text": r["share_text"],
        "report": pipeline.public(r),
    }


def sample_result():
    """Render the recorded Birim case offline (tests / explicit DEMO_MODE tooling only).

    Never call this to populate the live UI on load — the page must stay empty until
    the user supplies a filming spot and a clip.
    """
    r = demo.run(demo.SPOT["lat"], demo.SPOT["lon"], name=demo.SPOT["name"],
                 out_dir=os.path.join(demo.OUT_DIR, "sample"), log=lambda *a: None)
    return sections(r)


def _resolve(spot, lat, lon):
    """Coordinates to check. Typed lat/lon that disagree with the chosen spot win (custom point)."""
    if spot in DEMO_SPOTS:
        blat, blon = DEMO_SPOTS[spot]
        if lat is not None and lon is not None and abs(lat - blat) < 1e-4 and abs(lon - blon) < 1e-4:
            return float(lat), float(lon), spot.split(" (")[0]
    if lat is None or lon is None:
        return None
    return float(lat), float(lon), "Your spot"


def run_live(spot, lat, lon, clip):
    """Run a check in a thread and yield (readout HTML, log text, sections or None) as the log grows.

    The last yield carries the sections when the check worked, or None when it failed.
    """
    lines, q, box = [], queue.Queue(), {}
    point = _resolve(spot, lat, lon)
    if point is None:
        fix = "We need a place to check. Tap \"I'm at the river now\", pick a spot, or type both coordinates."
        lines.append("Something failed: no coordinates. " + fix)
        yield readout.html(lines, finished=True, failed=True, reason=fix), "\n".join(lines), None
        return
    lat_f, lon_f, name = point
    if not clip:
        fix = ("We need your film of the river. Upload a photo or video of the water — "
               "results are computed from what you send, nothing is preloaded.")
        lines.append("Something failed: no clip. " + fix)
        yield readout.html(lines, finished=True, failed=True, reason=fix), "\n".join(lines), None
        return

    def work():
        try:
            box["r"] = pipeline.run(lat_f, lon_f, name=name, clip=clip,
                                    clip_credit=HERO_CREDIT if clip else None,
                                    log=lambda *a: q.put(" ".join(map(str, a))))
        except Exception as ex:
            box["error"] = f"Something failed: {type(ex).__name__}: {ex}"

    t0, worker = time.time(), threading.Thread(target=work, daemon=True)
    worker.start()
    while worker.is_alive() or not q.empty():
        try:
            lines.append(q.get(timeout=0.5))
        except queue.Empty:
            continue
        yield readout.html(lines, finished=False), "\n".join(lines), None
    if "error" in box:
        lines += [box["error"], "Offline? Set DEMO_MODE=1 to use the recorded offline demo (explicit flag only)."]
        yield readout.html(lines, finished=True, failed=True), "\n".join(lines), None
        return
    yield (readout.html(lines, finished=True, elapsed_s=time.time() - t0), "\n".join(lines),
           sections(box["r"]))


def _chip_html():
    """Capability chips for the empty page — never claim a recorded run as a live result."""
    chips = [
        '<span class="chip">Needs your clip + location</span>',
        '<span class="chip">SAM 3.1 scar refine</span>',
        '<span class="chip">Muse Spark colour</span>',
        '<span class="chip">Catchment trace upstream</span>',
    ]
    return '<div class="chip-row">' + "".join(chips) + "</div>"


def _empty_state_html():
    """Shown until the user runs a check with real inputs."""
    return (
        '<div class="empty-state" id="empty-state">'
        '<p class="mono">Waiting for your check</p>'
        '<h3>No brief yet</h3>'
        '<p>Pick a filming spot and upload a photo or video of the river. '
        'Results are computed from what you send — nothing is preloaded.</p>'
        '<ol>'
        '<li>Choose where you are (GPS, a known spot, or typed coordinates)</li>'
        '<li>Upload your film of the water</li>'
        '<li>Tap <b>Check upstream</b></li>'
        '</ol></div>'
    )


def _hero_html():
    """Thesis, the three things a citizen does, safety up front, and the machine eye on a real river."""
    photo = case_file.data_uri(os.path.join(ASSETS, "bridge.jpg"), max_side=900)
    reticle = ('<svg class="reticle" viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="50" '
               'fill="none" stroke="#D4FF3A" stroke-width="2"/><g stroke="#D4FF3A" stroke-width="2">'
               '<line x1="60" y1="4" x2="60" y2="16"/><line x1="60" y1="104" x2="60" y2="116"/>'
               '<line x1="4" y1="60" x2="16" y2="60"/><line x1="104" y1="60" x2="116" y2="60"/></g></svg>')
    return (
        '<div class="hero"><div>'
        '<h1>Film the river. <em>Find the source.</em></h1>'
        '<p class="lede">Your phone sees the muddy river. The satellite sees where the mud comes from.</p>'
        '<ol class="steps">'
        '<li><span><b>Find a safe, public spot by the river</b><small>A bridge, a riverbank, a ferry landing '
        'or a footpath crossing.</small></span></li>'
        '<li><span><b>Film the water for 10 seconds</b><small>This is your evidence: it shows the river is muddy today.</small></span></li>'
        '<li><span><b>Share the evidence card</b><small>We look upstream from space and write it up for '
        'you.</small></span></li></ol>'
        '<div class="safe"><span>Public places only</span><span>Your location is rounded to 1 km</span>'
        '<span>No name or number kept</span></div></div>'
        f'<div class="photo-col"><div class="photo"><img src="{photo}" alt="Aerial view of a bridge over a '
        f'brown river through forest">{reticle}<span class="tag">Water · muddy</span>'
        f'<span class="cap">{HERO_CREDIT}</span></div></div></div>')


_GUIDE = ('<div class="field-label"><span class="num">2</span>Film the water <span class="hint">(your evidence)'
          '</span></div><div class="guide"><div class="phone" aria-hidden="true"><i></i></div><ul>'
          '<li>From a bridge, point down at the water</li>'
          '<li>From the bank, aim across at open water, not the muddy edge</li>'
          '<li>Keep still for about 10 seconds, in daylight</li>'
          '<li>Stay somewhere public. Never walk up to a mine</li></ul></div>')

_FOOTER = ('<div id="footnote">Safety: film only from public places, never at mining sites. Clips are re-encoded '
           'with GPS metadata stripped; your spot is shown only to about 1 km; no personal data is kept.<br>'
           f'Imagery: {HERO_CREDIT}. Satellite: Contains modified Copernicus Sentinel data 2023, 2026. '
           'Sources: Sentinel-2 (ESA/Copernicus), HydroBASINS (WWF), RADD (WUR/GFW), Hansen GFC (UMD), '
           'WDPA (UNEP-WCMC), JRC water. Built with Meta SAM 3.1 and Muse Spark.</div>')


def _head(title, right=""):
    return f'<div class="section-head"><h2>{title}</h2>{right}</div>'


def launch(share=False, warm=True):
    import gradio as gr

    empty = {"verdict": "", "trace": "", "eyes": "", "preview": "", "share_html": "",
             "card_png": None, "share_text": "", "report": None}

    def _fill(spot):
        """Spot picks fill the coordinate boxes; 'Custom point' leaves them as typed and shows them."""
        coords, custom = spot_pick(spot)
        if coords:
            return coords[0], coords[1], gr.update(visible=custom)
        return gr.skip(), gr.skip(), gr.update(visible=custom)

    def _go(spot, lat, lon, clip):
        """Stream the readout, then fill the case file. Empty state hides as soon as a run starts."""
        for html, log_text, s in run_live(spot, lat, lon, clip):
            out = {empty_box: gr.update(visible=False), demo_tag: gr.update(visible=False),
                   readout_box: html, log: log_text}
            if s:
                out.update({verdict: s["verdict"], trace: s["trace"], eyes: s["eyes"], preview: s["preview"],
                            share_box: s["share_html"], txt: s["share_text"],
                            card_file: gr.update(value=s["card_png"], visible=True),
                            report: s["report"], results: gr.update(visible=True)})
            else:
                # Keep results hidden while streaming / on failure so no stale brief shows.
                out[results] = gr.update(visible=False)
                if "didn't finish" in html or "Something failed" in log_text or "no clip" in log_text.lower() or "no coordinates" in log_text.lower():
                    out[empty_box] = gr.update(visible=True)
            yield out

    if warm and not demo.is_demo_mode():
        threading.Thread(target=lambda: _quiet_warm(list(DEMO_SPOTS.values())), daemon=True).start()

    banner = ""
    if demo.is_demo_mode():
        banner = ('<div id="demo-banner"><span class="mono">Demo mode (DEMO_MODE=1)</span><br>'
                  'Checks will use the recorded Birim N4 bridge case from 28 Oct 2026 — '
                  'clearly labelled, not a live result. No Earth Engine or Meta API calls.</div>')

    theme = gr.themes.Base(primary_hue="neutral", neutral_hue="neutral")   # page look is set by CSS
    with gr.Blocks(title="Two Eyes: check upstream") as ui:
        gr.HTML(_hero_html() + banner + _chip_html(), elem_classes=["plain"])
        gr.HTML(_head("Check a river", '<span class="mono">Takes about a minute</span>'), elem_classes=["plain"])
        with gr.Row(elem_id="workspace", equal_height=False):
            with gr.Column(elem_id="col-inputs", scale=5):
                with gr.Row(elem_id="row-input", equal_height=False):
                    with gr.Column():
                        gr.HTML('<div class="field-label"><span class="num">1</span>Where are you?</div>',
                                elem_classes=["plain"])
                        locate = gr.Button("📍  Use my current location (GPS)", elem_id="locate")
                        gps_msg = gr.HTML("", elem_classes=["plain"])
                        spot = gr.Dropdown(
                            [(k.split(" (")[0], k) for k in DEMO_SPOTS] +
                            [("Somewhere else (type coordinates)", CUSTOM)],
                            value=CUSTOM, label="Or pick a spot people have checked")
                        with gr.Group(visible=True, elem_id="custom-fields") as custom_fields:
                            lat = gr.Number(label="Latitude", value=None)
                            lon = gr.Number(label="Longitude", value=None)
                    with gr.Column():
                        gr.HTML(_GUIDE, elem_classes=["plain"])
                        clip = gr.Video(label="Your clip of the river (required)", sources=["upload", "webcam"])
                go = gr.Button("Check upstream", variant="primary")
                readout_box = gr.HTML("", elem_id="readout", elem_classes=["plain"])
            with gr.Column(elem_id="col-results", scale=6):
                gr.HTML(_head("What we found"), elem_classes=["plain"])
                demo_tag = gr.HTML(
                    ('<span class="sample-tag">Demo: recorded run will be used if you check '
                     f'with DEMO_MODE=1 — {demo.SPOT["name"]}, 28 Oct 2026</span>'
                     if demo.is_demo_mode() else ""),
                    visible=demo.is_demo_mode(), elem_classes=["plain"])
                empty_box = gr.HTML(_empty_state_html(), elem_classes=["plain"])
                with gr.Column(visible=False) as results:
                    verdict = gr.HTML(empty["verdict"], elem_classes=["plain"])
                    trace = gr.HTML(empty["trace"], elem_classes=["plain"])
                    eyes = gr.HTML(empty["eyes"], elem_classes=["plain"])
                    gr.HTML(_head("Share it"), elem_classes=["plain"])
                    with gr.Row(elem_id="row-share", equal_height=False):
                        preview = gr.HTML(empty["preview"], elem_classes=["plain"])
                        with gr.Column():
                            share_box = gr.HTML(empty["share_html"], elem_classes=["plain"])
                            card_file = gr.DownloadButton("Save the card", value=None, visible=False)
                            txt = gr.Textbox(empty["share_text"], label="Message (edit before you send)",
                                             lines=4, buttons=["copy"])
                            gr.HTML(share_ui.next_steps_html(), elem_classes=["plain"])
        with gr.Accordion("How the checks ran", open=False):
            log = gr.Textbox(label="What the checks did", lines=8)
            report = gr.JSON(None, label="Full report")
        gr.HTML(_FOOTER, elem_classes=["plain"])

        spot.change(_fill, [spot], [lat, lon, custom_fields])
        locate.click(None, None, [lat, lon, gps_msg], js=LOCATE_JS).then(lambda: CUSTOM, None, spot)
        go.click(None, None, None, js=SCROLL_JS).then(
            _go, [spot, lat, lon, clip],
            [empty_box, demo_tag, readout_box, log, verdict, trace, eyes, preview, share_box, txt,
             card_file, report, results])
    # Gradio 6: css and theme live in launch(), not Blocks
    ui.launch(share=share, debug=False, css=build_css(), theme=theme, js=LIGHT_JS)


def _quiet_warm(spots):
    """Pre-compute the demo spots in the background; a failure only means the first run is slower."""
    try:
        pipeline.warm(spots, log=lambda *a: None)
    except Exception as ex:
        print(f"[two_eyes] warm skipped: {type(ex).__name__}: {ex}")


if __name__ == "__main__":
    launch()
