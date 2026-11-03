"""SAM 3.1 on Meta Model API: box prompts on images, concept prompts on video.

Every API response is cached to disk; a cache hit never re-calls Meta.
"""
import base64
import hashlib
import io
import os

import numpy as np
from PIL import Image

from . import config as C
from . import meta_cache
from .secrets import ensure_model_api_key

_client = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI
        ensure_model_api_key()
        key = os.environ.get("MODEL_API_KEY")
        if not key:
            raise RuntimeError("MODEL_API_KEY is not set (put it in ~/.secrets/MODEL_API_KEY).")
        _client = OpenAI(base_url=C.META_BASE_URL, api_key=key)
    return _client


def _png_data_url(rgb):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _png_bytes(rgb):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return buf.getvalue()


def _call(text, media_part, cache_extra=""):
    """Cached SAM responses.create. Returns output_text string."""
    # Hash text + a stable digest of the media (not the full data-URL) for the cache key.
    media_digest = ""
    if isinstance(media_part, dict):
        for k in ("image_url", "video_url"):
            if k in media_part and isinstance(media_part[k], str):
                # data URL: hash the payload after the comma
                raw = media_part[k]
                payload = raw.split(",", 1)[-1] if "," in raw else raw
                media_digest = hashlib.sha256(payload.encode() if isinstance(payload, str) else payload).hexdigest()
                break
    key = meta_cache.make_key("sam", C.SAM_MODEL, text, media_digest, cache_extra)
    hit = meta_cache.get(key)
    if hit is not None and "output_text" in hit:
        return hit["output_text"] or ""
    resp = client().responses.create(
        model=C.SAM_MODEL,
        input=[{"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}, media_part]}],
        metadata={"mask_encoding": "one_bit"})
    text_out = resp.output_text or ""
    meta_cache.put(key, {"output_text": text_out, "model": C.SAM_MODEL})
    meta_cache.bump_calls(1)
    return text_out


def _records(text, video=False):
    if not text.strip():
        return []                      # zero matches is a valid answer
    from meta_sam_parser import image_segmentation_format, video_segmentation_format, CompletedOutcome
    parser = (video_segmentation_format() if video else image_segmentation_format()).create_parser()
    parser.push(text if text.endswith("\n") else text + "\n")
    return [r for r in parser.finish(CompletedOutcome()).result.records if hasattr(r, "mask")]


def _bounds(rec):
    b = rec.bounds
    get = lambda *names: next(getattr(b, n) for n in names if hasattr(b, n))
    return int(get("left", "x1")), int(get("top", "y1"))


def _paste(rec, full):
    from meta_sam_parser import decode_mask_to_raster
    m = rec.mask
    h, w = full.shape
    tile = np.frombuffer(decode_mask_to_raster(m), dtype=np.uint8).reshape(m.height, m.width).astype(bool)
    x1, y1 = _bounds(rec)
    full[y1:y1 + m.height, x1:x1 + m.width] |= tile[: h - y1, : w - x1]


def _shrink(mask_up, k):
    h, w = mask_up.shape[0] // k, mask_up.shape[1] // k
    return mask_up[: h * k, : w * k].reshape(h, k, w, k).mean(axis=(1, 3)) >= 0.5


def refine_boxes(rgb, boxes):
    """Box-prompt SAM 3.1 on a 10 m RGB tile.

    rgb: (H, W, 3) uint8 on the 10 m grid. boxes: [(left, top, right, bottom)] half-open, 10 m grid.
    Returns a boolean mask on the 10 m grid (union of all objects).
    """
    from meta_sam_parser import build_object_prompt, PromptObject, FramePrompt, PromptBox
    k = C.UPSCALE
    H, W = rgb.shape[:2]
    big = np.asarray(Image.fromarray(rgb).resize((W * k, H * k), Image.NEAREST))
    url = _png_data_url(big)
    out = np.zeros((H, W), dtype=bool)
    for i in range(0, len(boxes), 16):
        objs = [PromptObject(id=j + 1, prompts=[FramePrompt(frame=0, box=PromptBox(l * k, t * k, r * k, b * k))])
                for j, (l, t, r, b) in enumerate(boxes[i:i + 16])]
        text = build_object_prompt(size=(W * k, H * k), objects=objs)
        full = np.zeros((H * k, W * k), dtype=bool)
        for rec in _records(_call(text, {"type": "input_image", "image_url": url},
                                  cache_extra=f"boxes:{boxes[i:i+16]}")):
            _paste(rec, full)
        out |= _shrink(full, k)
    return out


def concept_boxes(rgb, prompt):
    """Concept-prompt SAM 3.1 on a still. Returns list of (l,t,r,b) half-open boxes on the image grid."""
    H, W = rgb.shape[:2]
    url = _png_data_url(rgb)
    text = _call(prompt, {"type": "input_image", "image_url": url}, cache_extra=f"concept:{prompt}:{H}x{W}")
    boxes = []
    full = np.zeros((H, W), dtype=bool)
    for rec in _records(text):
        _paste(rec, full)
        # derive a box from this record's mask bounds
        try:
            x1, y1 = _bounds(rec)
            m = rec.mask
            boxes.append((x1, y1, x1 + m.width, y1 + m.height))
        except Exception:
            pass
    if not boxes and full.any():
        ys, xs = np.where(full)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    return boxes, full


def segment_video(mp4_path, prompt, size):
    """Concept-prompt SAM 3.1 on a clip. Returns {frame_index: bool mask (H, W)}."""
    w, h = size
    raw = open(mp4_path, "rb").read()
    url = "data:video/mp4;base64," + base64.b64encode(raw).decode()
    text = _call(prompt, {"type": "input_video", "video_url": url},
                 cache_extra=f"video:{prompt}:{w}x{h}:{hashlib.sha256(raw).hexdigest()[:16]}")
    frames = {}
    for rec in _records(text, video=True):
        f = rec.identity.frame_index if rec.identity.frame_index is not None else (
            rec.frame.frame_index if rec.frame is not None else 0)
        m = frames.setdefault(f, np.zeros((h, w), dtype=bool))
        _paste(rec, m)
    return frames
