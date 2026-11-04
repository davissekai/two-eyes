"""Muse Spark writes the evidence card under check-grounded rules.

Every sentence Muse emits must name the check it rests on (A–F or GROUND).
Code deletes any sentence whose check did not pass. A minimum card always survives:
location and NDVI change when present. The hedging line 'Likely source, not proven'
is added only when a clearing that drains to the spot was found.
"""
import json
import re

from . import config as C
from . import muse

CARD_WRITER_VERSION = "2"

CARD_WRITER_PROMPT = """You write a short WhatsApp evidence card for a Ghana river-monitoring app.
You receive the check results as JSON. Write 2–5 sentences. EACH sentence MUST start with a
tag in square brackets naming the single check it rests on, then a space, then the sentence.
Allowed tags: [A] [B] [C] [D] [E] [F] [GROUND] [MIN].

Rules:
- Only write a tagged sentence when that check passed (pass == true). For unknown/null/false, do not write that tag (except [MIN]).
- [MIN] sentences are the minimum card and always allowed: name the location and state the NDVI change if given.
- When status is SCAR and checks A, B, C, D and E all passed, also end with exactly: Likely source, not proven.
- Otherwise never write "Likely source" or "not proven".
- No percentages. No accusations against named people. No Twi. Plain English for someone with no science
  background: say what the satellite saw and where the water goes.
- The tag is only for the app. Never mention checks, check letters, "passed", "pass" or the JSON inside the
  sentence text itself.
- Return ONLY JSON: {"sentences": ["[A] ...", "[MIN] ...", ...]}
"""


def _check_passed(checks, tag):
    if tag == "MIN":
        return True
    if tag == "GROUND":
        return True  # filtered by caller via ground flag
    c = (checks or {}).get(tag) or {}
    return c.get("pass") is True


def _public_spot(r):
    """The filming spot as others may see it: name plus coordinates rounded to about 1 km (privacy)."""
    from .card import public_point
    b = dict(r.get("spot") or r.get("bridge") or {})
    if (b.get("name") or "").strip().lower() in ("", "your spot"):
        b["name"] = "the filming spot"     # a placeholder, not a place name: never write "at Your spot"
    if b.get("lat") is not None and b.get("lon") is not None:
        b["lat"], b["lon"] = public_point(b["lat"], b["lon"])
    return b



def claims_source(r):
    """True only when the confidence ladder itself reaches "Likely source", so the share text never
    claims more than the result screen does."""
    if r.get("status") != "SCAR":
        return False
    from .case_file import evidence_level
    return evidence_level(r) >= 3


def minimum_card(r):
    """Always-surviving lines: location, NDVI change when present; hedging only when a source was found."""
    b = _public_spot(r)
    s = r.get("scar") or {}
    name = b.get("name") or "the filming spot"
    if b.get("lat") is not None and b.get("lon") is not None:
        lines = [f"Location: {name} (about {b['lat']:.2f}, {b['lon']:.2f})."]
    else:
        lines = [f"Location: {name}."]
    if s.get("ndvi_before") is not None and s.get("ndvi_after") is not None:
        lines.append(
            f"NDVI dropped from {s['ndvi_before']:.2f} to {s['ndvi_after']:.2f}"
            + (f" over about {s['area_ha']:.1f} ha" if s.get("area_ha") else "")
            + "."
        )
    elif s.get("area_ha"):
        lines.append(f"New clearing about {s['area_ha']:.1f} ha upstream.")
    if claims_source(r):
        lines.append("Likely source, not proven.")
    return lines


_JARGON = re.compile(r"\bchecks?\s+[A-F]\b|\bpass(ed)?\b|\bcheck\s+(result|passed)", re.I)


def _filter_sentences(sentences, checks, allow_ground=True):
    kept = []
    for s in sentences or []:
        s = str(s).strip()
        if not s.startswith("[") or "]" not in s:
            continue
        tag = s[1:s.index("]")].strip().upper()
        body = s[s.index("]") + 1:].strip()
        if not body or _JARGON.search(body):
            continue
        if tag == "GROUND" and not allow_ground:
            continue
        if tag == "MIN":
            kept.append(body)
            continue
        if _check_passed(checks, tag):
            kept.append(body)
    return kept


def write_card(r, use_llm=True):
    """Return share/card text. Muse draft filtered by checks; minimum card always appended if empty."""
    checks = r.get("checks") or {}
    ground = r.get("ground") or {}
    allow_ground = bool(ground.get("water_found"))
    payload = {
        "bridge": _public_spot(r),
        "scar": {k: (r.get("scar") or {}).get(k)
                 for k in ("area_ha", "distance_km", "ndvi_before", "ndvi_after", "lat", "lon")},
        "checks": {k: {"pass": (checks.get(k) or {}).get("pass"),
                       "note": (checks.get(k) or {}).get("note")}
                   for k in "ABCDEF"},
        "ground": {"water_found": ground.get("water_found"), "label": ground.get("label"),
                   "muddy": ground.get("muddy")},
        "status": r.get("status"),
    }
    sentences = []
    muse_ok = False
    if use_llm and C.SHARE_LLM:
        try:
            prompt = CARD_WRITER_PROMPT + "\n\nCheck results:\n" + json.dumps(payload)
            text = muse.respond(prompt, cache_tag=f"card_writer_v{CARD_WRITER_VERSION}", effort=C.CARD_WRITER_EFFORT)
            data = muse.parse_json(text)
            sentences = _filter_sentences(data.get("sentences"), checks, allow_ground=allow_ground)
            muse_ok = True
        except Exception:
            sentences = []
            muse_ok = False
    min_lines = minimum_card(r)
    # Muse unavailable (no key / network): return None so share_text falls back to headline template
    if use_llm and not muse_ok:
        return None
    # Muse ran but every sentence was dropped → minimum card always survives
    if not sentences:
        return " ".join(min_lines)
    hedge = claims_source(r)
    # Drop Muse lines that claim a source when the checks don't support it; drop duplicate caution
    body = []
    for s in sentences:
        low = s.lower()
        if "likely source" in low or "not proven" in low:
            if hedge:
                continue  # we'll append the canonical caution once
            continue  # no source found: never keep hedging claims
        body.append(s)
    out = list(body)
    if hedge:
        out.append("Likely source, not proven.")
    # Ensure location/NDVI appear somehow
    joined = " ".join(out)
    if not any(x in joined.lower() for x in ("location", "bridge", "ndvi", "clearing", "ha")):
        extras = [ln for ln in min_lines if "likely source" not in ln.lower()]
        out = extras + out
    return " ".join(out)
