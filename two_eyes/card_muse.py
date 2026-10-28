"""Muse Spark writes the evidence card under check-grounded rules.

Every sentence Muse emits must name the check it rests on (A–F or GROUND).
Code deletes any sentence whose check did not pass. A minimum card always survives:
location, NDVI change, and 'Likely source, not proven'.
"""
import json

from . import config as C
from . import muse

CARD_WRITER_VERSION = "1"

CARD_WRITER_PROMPT = """You write a short WhatsApp evidence card for a Ghana river-monitoring app.
You receive the check results as JSON. Write 2–5 sentences. EACH sentence MUST start with a
tag in square brackets naming the single check it rests on, then a space, then the sentence.
Allowed tags: [A] [B] [C] [D] [E] [F] [GROUND] [MIN].

Rules:
- Only write a tagged sentence when that check passed (pass == true). For unknown/null/false, do not write that tag (except [MIN]).
- [MIN] sentences are the minimum card and always allowed: name the location, state the NDVI change if given, and end with exactly: Likely source, not proven.
- No percentages. No accusations against named people. No Twi. Plain English.
- Return ONLY JSON: {"sentences": ["[A] ...", "[MIN] ...", ...]}
"""


def _check_passed(checks, tag):
    if tag == "MIN":
        return True
    if tag == "GROUND":
        return True  # filtered by caller via ground flag
    c = (checks or {}).get(tag) or {}
    return c.get("pass") is True


def minimum_card(r):
    """Always-surviving lines: location, NDVI change when present, caution."""
    b = r.get("bridge") or {}
    s = r.get("scar") or {}
    name = b.get("name") or "this bridge"
    loc = f"{b.get('lat', 0):.4f}, {b.get('lon', 0):.4f}"
    lines = [f"Location: {name} ({loc})."]
    if s.get("ndvi_before") is not None and s.get("ndvi_after") is not None:
        lines.append(
            f"NDVI dropped from {s['ndvi_before']:.2f} to {s['ndvi_after']:.2f}"
            + (f" over about {s['area_ha']:.1f} ha" if s.get("area_ha") else "")
            + "."
        )
    elif s.get("area_ha"):
        lines.append(f"New clearing about {s['area_ha']:.1f} ha upstream.")
    lines.append("Likely source, not proven.")
    return lines


def _filter_sentences(sentences, checks, allow_ground=True):
    kept = []
    for s in sentences or []:
        s = str(s).strip()
        if not s.startswith("[") or "]" not in s:
            continue
        tag = s[1:s.index("]")].strip().upper()
        body = s[s.index("]") + 1:].strip()
        if not body:
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
        "bridge": r.get("bridge"),
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
            text = muse.respond(prompt, cache_tag=f"card_writer_v{CARD_WRITER_VERSION}")
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
    # Drop Muse lines that duplicate the closing caution; ensure caution present
    body = [s for s in sentences if "not proven" not in s.lower()]
    # Prefer Muse body + required caution
    out = body + [min_lines[-1]]
    # Ensure location/NDVI appear somehow
    joined = " ".join(out)
    if "Likely source, not proven" not in joined:
        out.append("Likely source, not proven.")
    if not any(x in joined.lower() for x in ("location", "bridge", "ndvi", "clearing", "ha")):
        out = min_lines[:-1] + out
    return " ".join(out)
