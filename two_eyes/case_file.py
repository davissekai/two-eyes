"""The case file a citizen reads after a check: verdict, how sure we are, the river trace, the two eyes.

Every function takes the report dict (live or demo) and returns an HTML string for the Gradio page.
Words that came from a model or a person are escaped; nothing here calls a network service.
"""
import base64
import html
import io

import numpy as np

from . import config as C

PITCH_HA = 0.714          # FIFA pitch, 105 m x 68 m: the size most people can picture
LIME = (212, 255, 58)

# Ladder rungs, weakest first. Rung 4 is never "on": only the authorities can prove it.
RUNGS = ["Possible clearing", "Clearing confirmed", "Likely source", "Proven"]


def data_uri(img, max_side=720, quality=85):
    """JPEG data URI of an RGB array or an image path, downscaled so the page stays light."""
    from PIL import Image
    im = Image.open(img).convert("RGB") if isinstance(img, str) else Image.fromarray(np.asarray(img, np.uint8))
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def pitches(area_ha):
    """Area as something people can picture: football pitches."""
    if area_ha is None:
        return ""
    n = round(area_ha / PITCH_HA)
    if n < 1:
        return "smaller than a football pitch"
    return f"about {n} football pitch" + ("" if n == 1 else "es")


def _passes(r):
    k = r.get("checks") or {}
    return {x: k.get(x, {}).get("pass") for x in "ABCDEF"}


def evidence_level(r):
    """0 = nothing to rank, 1 possible, 2 clearing confirmed, 3 likely source (same rules as card.headline)."""
    p = _passes(r)
    if r.get("status") == "CLOUDY" or not p["A"] or not p["B"]:
        return 0
    if p["C"] and p["D"] and p["E"]:
        return 3
    return 2 if p["C"] else 1


def next_step(r):
    """One sentence on what would move the result up a rung."""
    level, p = evidence_level(r), _passes(r)
    if level == 1:
        return ("If radar alerts or forest-loss maps pick up this clearing, it becomes a confirmed "
                "clearing.")
    if level == 2:
        missing = []
        if not p["D"]:
            missing.append("signs of mining show inside the clearing")
        if not p["E"]:
            missing.append("the river measures muddier just below it")
        return "If " + " and ".join(missing) + ", it becomes the likely source of this mud."
    if level == 3:
        return "Only the authorities can prove it is illegal mining. This is evidence to hand them."
    return ""


def _verdict_title(r):
    p, s = _passes(r), r.get("scar") or {}
    if r.get("status") == "CLOUDY":
        return "Clouds blocked the satellite's view upstream. Try again in a few weeks."
    if not p["A"]:
        return "No new forest clearing upstream since early %s." % C.BEFORE[0][:4]
    if not p["B"]:
        return "A new clearing was found nearby, but its water drains to another river."
    return "Forest has been cleared upstream, and its water flows past where you stood."


def verdict_html(r):
    """Headline, big numbers at human scale, and the evidence ladder."""
    s, level = r.get("scar") or {}, evidence_level(r)
    numbers = ""
    if level and s.get("area_ha") is not None:
        numbers = (
            '<div class="numbers">'
            f'<div><b>{s["area_ha"]:.0f} ha</b><span>{pitches(s["area_ha"])}</span></div>'
            f'<div><b>{s.get("distance_km", 0):.0f} km</b><span>upstream of you</span></div>'
            f'<div><b>{C.BEFORE[0][:4]}</b><span>cleared since early that year</span></div>'
            '</div>')
    ladder = ""
    if level:
        rungs = "".join(
            f'<div class="rung {"on" if i + 1 == level else "off"}">'
            f'<span class="mono">{"Now" if i + 1 == level else ("Officials only" if i == 3 else "")}</span>'
            f'{name}</div>' for i, name in enumerate(RUNGS))
        ladder = (
            '<div class="ladder"><div class="label">How sure are we?</div>'
            f'<div class="rungs">{rungs}</div>'
            f'<p class="next">{html.escape(next_step(r))}</p>'
            '<p class="hint">Only the authorities can say it is illegal. We give you evidence, not a verdict.</p>'
            '</div>')
    return (f'<div class="verdict"><div class="panel"><h3>{_verdict_title(r)}</h3>{numbers}{_confluence_note(r)}</div>'
            f'{"<div class=panel>" + ladder + "</div>" if ladder else ""}</div>')


def _confluence_note(r):
    """When two rivers meet at the spot, say which one we followed and how to check the other."""
    sn = r.get("snap") or {}
    if not sn.get("ambiguous"):
        return ""
    chosen = next((o["kind"] for o in sn.get("options", []) if o["reach"] == sn.get("reach")), "nearest river")
    other = "bigger river" if chosen == "smaller stream" else "smaller stream"
    return (f'<p class="next caution">Two rivers meet near where you stood. We followed the {chosen}, the '
            f'one closest to you. If you filmed the {other}, walk a little way along it and check again.</p>')


def _state(v):
    return {True: "yes", False: "no"}.get(v, "unknown")


def stations(r):
    """The checks in river order, from the citizen's spot up to the clearing.

    Each: key, title (a plain question), state (yes / no / unknown / skip), detail (one short line).
    """
    k, p, s = r.get("checks") or {}, _passes(r), r.get("scar") or {}
    g = r.get("ground")
    if not g:
        clip = ("skip", "no clip added")
    elif not g.get("water_found"):
        clip = ("unknown", "no river water found in the clip")
    elif g.get("muddy") is None:
        clip = ("unknown", g.get("label") or "colour hard to judge")
    else:
        clip = ("yes" if g["muddy"] else "no", "water looks " + (g.get("label") or "clear")
                + (", filmed from the bank" if g.get("view") == "bank" else ""))
    area = f'{s["area_ha"]:.0f} ha since {C.BEFORE[0][:4]}' if s.get("area_ha") is not None else "no new clearing"
    return [
        {"key": "clip", "title": "Your clip", "state": clip[0], "detail": clip[1]},
        {"key": "E", "title": "Muddier below?", "state": _state(p["E"]),
         "detail": {True: "the river turns muddier below the clearing", False: "no change in colour"}.get(
             p["E"], "river too narrow to measure from space here")},
        {"key": "B", "title": "Drains here", "state": _state(p["B"]),
         "detail": {True: "its water flows past you", False: "it drains to another river"}.get(
             p["B"], "could not trace the river")},
        {"key": "A", "title": "Forest cleared", "state": _state(p["A"]), "detail": area},
        {"key": "D", "title": "Looks like mining", "state": _state(p["D"]),
         "detail": {True: "open pits full of water", False: "no mining pits seen"}.get(
             p["D"], "could not tell")},
        {"key": "C", "title": "Others saw it?", "state": _state(p["C"]),
         "detail": {True: "radar or forest-loss alerts agree", False: "no outside alerts here"}.get(
             p["C"], "alerts don't cover this area yet")},
        {"key": "F", "title": "Protected forest?", "state": _state(p["F"]),
         "detail": _protected_detail(k.get("F") or {}, p["F"])},
    ]


def _protected_detail(f, v):
    if v:
        names = ", ".join(a["name"] for a in f.get("protected_areas", []) if a.get("name"))
        return "inside " + (names or "a protected area")
    return "no; licence check is by hand" if v is False else "could not check"


_MARK = {"yes": "✓", "no": "–", "unknown": "?", "skip": "·"}


def trace_html(r):
    """The river trace: your spot, the checks as stations along the river, the clearing."""
    spot, s = r.get("spot") or {}, r.get("scar") or {}
    km = f'{s["distance_km"]:.0f} km of river' if s.get("distance_km") is not None else ""
    items = []
    for st in stations(r):
        tag = f'<span class="km">{km}</span>' if st["key"] == "B" and km else ""
        items.append(
            f'<li class="{st["state"]}"><span class="mark">{_MARK[st["state"]]}</span>'
            f'<span><b>{st["title"]}</b><small>{html.escape(st["detail"])}</small></span>{tag}</li>')
    you = html.escape(spot.get("name") or "Your spot")
    there = f'{s["lat"]:.2f}, {s["lon"]:.2f}' if s.get("lat") is not None else "upstream"
    return (
        '<div class="trace-wrap"><div class="trace-head"><span class="label">From where you stood to the clearing</span>'
        '<span class="legend"><span><i class="mark yes">✓</i>agrees</span>'
        '<span><i class="mark">?</i>couldn\'t check</span><span><i class="mark">–</i>no</span></span></div>'
        '<div class="trace">'
        f'<div class="eye">{_EYE_GROUND}<span><b>You</b>{you}</span></div>'
        f'<ol class="stations">{"".join(items)}</ol>'
        f'<div class="eye">{_EYE_SKY}<span><b>Clearing</b>{there}</span></div>'
        '</div></div>')


_EYE_GROUND = ('<svg viewBox="0 0 56 56" aria-hidden="true"><circle cx="28" cy="28" r="24" fill="none" '
               'stroke="#15130F" stroke-width="3"/><circle cx="28" cy="28" r="7" fill="#9C5A34"/></svg>')
_EYE_SKY = ('<svg viewBox="0 0 56 56" aria-hidden="true"><circle cx="28" cy="28" r="24" fill="none" '
            'stroke="#15130F" stroke-width="3"/><g stroke="#15130F" stroke-width="3">'
            '<line x1="28" y1="0" x2="28" y2="8"/><line x1="28" y1="48" x2="28" y2="56"/>'
            '<line x1="0" y1="28" x2="8" y2="28"/><line x1="48" y1="28" x2="56" y2="28"/></g>'
            '<circle cx="28" cy="28" r="7" fill="#D4FF3A" stroke="#15130F" stroke-width="1.5"/></svg>')


def outlined(rgb, mask):
    """The 'after' tile with the scar edge drawn in lime, the way the machine sees it."""
    from scipy.ndimage import binary_dilation, binary_erosion
    out = np.asarray(rgb, np.uint8).copy()
    if mask is not None and np.any(mask):
        edge = binary_dilation(mask & ~binary_erosion(mask, iterations=1), iterations=1)
        out[edge] = LIME
    return out


def _sky_html(s):
    before, after = s.get("rgb_before"), s.get("rgb_after")
    if before is None or after is None:
        return ""
    b, a = C.BEFORE[0][:4], C.AFTER[0][:4]
    return (
        '<div class="panel eye-card"><div class="eye-head"><span class="label">The sky eye</span>'
        '<span class="mono">Sentinel-2</span></div>'
        '<div class="scrub" style="--x:50%">'
        f'<img src="{data_uri(before)}" alt="Satellite view of the clearing area in early {b}">'
        f'<img class="after" src="{data_uri(outlined(after, s.get("mask")))}" '
        f'alt="Satellite view in early {a}, with the new clearing outlined">'
        f'<span class="tag l">{b}</span><span class="tag r">{a}</span><span class="line"></span>'
        '<span class="knob" aria-hidden="true">↔</span>'
        '<input type="range" min="0" max="100" value="50" aria-label="Slide between the two satellite views" '
        'oninput="this.parentNode.style.setProperty(\'--x\', this.value + \'%\')">'
        '</div>'
        f'<p class="hint">Same forest, {int(a) - int(b)} years apart. Drag to compare: the lime outline marks '
        'what was cleared.</p></div>')


def _ground_html(g):
    if not g or g.get("frame") is None and g.get("still") is None:
        return ""
    frame = g.get("frame") if g.get("frame") is not None else g.get("still")
    toggle = ""
    if g.get("frame") is not None and g.get("still") is not None:
        toggle = (f'<img class="mask" src="{data_uri(g["still"])}" alt="The same frame with the water we measured painted over">')
    label = html.escape(g.get("label") or "")
    swatch = ""
    if g.get("rgb"):
        rr, gg, bb = (int(x) for x in g["rgb"])
        swatch = (
            '<div class="swatches">'
            f'<div class="sw"><i style="background:rgb({rr},{gg},{bb})"></i><span><b>Your river</b>'
            f'<small>{label or "measured colour"}</small></span></div>'
            '<div class="sw"><i style="background:#4E5A3F"></i><span><b>A clear forest river</b>'
            '<small>for comparison</small></span></div></div>')
    frames = f'{g["frames_used"]} frames' if g.get("frames_used") else "your clip"
    return (
        '<div class="panel eye-card"><div class="eye-head"><span class="label">The ground eye</span>'
        '<span class="mono">Your clip</span></div>'
        '<label class="clip"><input type="checkbox" aria-label="Show the water we measured">'
        f'<img src="{data_uri(frame)}" alt="A frame from your clip">{toggle}'
        f'<span class="tag">Water found in {frames}</span>'
        f'<span class="toggle">{"Tap to show the water we measured" if toggle else ""}</span></label>'
        + (f'<p class="quote">“{label.capitalize()}.”</p>' if label else "")
        + swatch
        + (f'<p class="hint">{html.escape(g["credit"])}</p>' if g.get("credit") else "")
        + '</div>')


def eyes_html(r):
    """Sky eye (before/after scrubber) beside the ground eye (the clip, with the water it measured)."""
    parts = [_sky_html(r.get("scar") or {}), _ground_html(r.get("ground"))]
    parts = [p for p in parts if p]
    return f'<div class="eyes">{"".join(parts)}</div>' if parts else ""
