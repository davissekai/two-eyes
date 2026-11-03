"""Muse Spark scar judge: before/after Sentinel chips -> cause / evidence / confidence.

Frozen prompt SCAR_JUDGE_VERSION=1. Cache every verdict. 'unclear' is a valid cause.
"""
import json
import os

import numpy as np
from PIL import Image

from . import muse
from . import meta_cache

SCAR_JUDGE_VERSION = "1"

# FROZEN — change only with a version bump and a re-score.
SCAR_JUDGE_PROMPT = """You are a remote-sensing assistant judging a forest clearing in Ghana.
You see two Sentinel-2 true-colour chips of the SAME place: image 1 = BEFORE, image 2 = AFTER.
Decide what the AFTER clearing most likely is.

Answer ONLY a JSON object with this schema:
{
  "cause": "mining pits" | "farm" | "road" | "settlement" | "cloud artefact" | "unclear",
  "evidence": "<one short sentence naming what you see>",
  "confidence": "low" | "medium" | "high"
}

Rules:
- "mining pits" only if you see open-water pits, bare dug earth, or muddy ponds typical of galamsey.
- "cloud artefact" if the change looks like residual cloud/shadow, not ground.
- "unclear" is a valid and preferred answer when unsure. Do not guess.
- No other keys. No markdown.
"""

CAUSES = ("mining pits", "farm", "road", "settlement", "cloud artefact", "unclear")
CONF = ("low", "medium", "high")


def _crop(rgb, box, pad=40):
    H, W = rgb.shape[:2]
    l, t, r, b = box
    l, t = max(l - pad, 0), max(t - pad, 0)
    r, b = min(r + pad, W), min(b + pad, H)
    return rgb[t:b, l:r]


def judge_scar(rgb_before, rgb_after, box, scar_id=None):
    """Return verdict dict for one scar box. Cached by image digests + box + prompt version."""
    before = _crop(rgb_before, box)
    after = _crop(rgb_after, box)
    if before.size < 10 or after.size < 10:
        return {"cause": "unclear", "evidence": "chip too small", "confidence": "low",
                "scar_id": scar_id, "cached": False}
    tag = f"scar_judge_v{SCAR_JUDGE_VERSION}:{scar_id}:{box}"
    text = muse.respond(SCAR_JUDGE_PROMPT, images=[before, after], schema_name="scar_judge",
                        cache_tag=tag)
    try:
        d = muse.parse_json(text)
    except Exception as ex:
        return {"cause": "unclear", "evidence": f"parse error: {type(ex).__name__}",
                "confidence": "low", "scar_id": scar_id, "raw": text[:300]}
    cause = d.get("cause") if d.get("cause") in CAUSES else "unclear"
    conf = d.get("confidence") if d.get("confidence") in CONF else "low"
    return {"cause": cause, "evidence": str(d.get("evidence", ""))[:200],
            "confidence": conf, "scar_id": scar_id}


def looks_like_mining(verdict):
    return verdict and verdict.get("cause") == "mining pits" and verdict.get("confidence") in ("medium", "high")


def score_labelled(cases):
    """cases: list of dicts with keys box, label (cause), rgb_before, rgb_after, scar_id.
    Returns {n, correct, hit_rate, rows}."""
    rows = []
    correct = 0
    for c in cases:
        v = judge_scar(c["rgb_before"], c["rgb_after"], c["box"], scar_id=c.get("scar_id"))
        ok = v["cause"] == c["label"]
        # Accept 'unclear' as non-error when label is unclear; otherwise count mismatch.
        if ok:
            correct += 1
        rows.append({"scar_id": c.get("scar_id"), "label": c["label"], "pred": v["cause"],
                     "confidence": v["confidence"], "evidence": v.get("evidence"), "ok": ok})
    n = len(cases)
    return {"n": n, "correct": correct, "hit_rate": round(correct / n, 3) if n else 0.0, "rows": rows}
