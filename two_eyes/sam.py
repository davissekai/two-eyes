"""SAM 3.1 on Meta Model API: box prompts on images, concept prompts on video."""
import base64
import io
import os

import numpy as np
from PIL import Image

from . import config as C

_client = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI
        key = os.environ.get("MODEL_API_KEY")
        if not key:
            raise RuntimeError("MODEL_API_KEY is not set (Colab: Secrets -> MODEL_API_KEY).")
        _client = OpenAI(base_url=C.META_BASE_URL, api_key=key)
    return _client


def _png_data_url(rgb):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _call(text, media_part):
    resp = client().responses.create(
        model=C.SAM_MODEL,
        input=[{"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}, media_part]}],
        metadata={"mask_encoding": "one_bit"})
    return resp.output_text or ""


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
        for rec in _records(_call(text, {"type": "input_image", "image_url": url})):
            _paste(rec, full)
        out |= _shrink(full, k)
    return out


def segment_video(mp4_path, prompt, size):
    """Concept-prompt SAM 3.1 on a clip. Returns {frame_index: bool mask (H, W)}."""
    w, h = size
    url = "data:video/mp4;base64," + base64.b64encode(open(mp4_path, "rb").read()).decode()
    text = _call(prompt, {"type": "input_video", "video_url": url})
    frames = {}
    for rec in _records(text, video=True):
        f = rec.identity.frame_index if rec.identity.frame_index is not None else (
            rec.frame.frame_index if rec.frame is not None else 0)
        m = frames.setdefault(f, np.zeros((h, w), dtype=bool))
        _paste(rec, m)
    return frames
