"""Muse Spark helpers with disk cache. Never re-calls Meta on a cache hit."""
import base64
import hashlib
import io
import json
import os

from PIL import Image

from . import config as C
from . import meta_cache
from .secrets import ensure_model_api_key


def _client():
    from openai import OpenAI
    ensure_model_api_key()
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        raise RuntimeError("MODEL_API_KEY is not set")
    return OpenAI(base_url=C.META_BASE_URL, api_key=key)


def _img_url(rgb, quality=85):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality)
    raw = buf.getvalue()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest()


def respond(prompt, images=None, schema_name=None, cache_tag=""):
    """Cached Muse Spark call. images: list of RGB uint8 arrays. Returns output_text."""
    images = images or []
    digests = []
    content = [{"type": "input_text", "text": prompt}]
    for im in images:
        url, dig = _img_url(im)
        digests.append(dig)
        content.append({"type": "input_image", "image_url": url})
    key = meta_cache.make_key("muse", C.TEXT_MODEL, cache_tag or schema_name or "free", prompt, *digests)
    hit = meta_cache.get(key)
    if hit is not None and "output_text" in hit:
        return hit["output_text"] or ""
    resp = _client().responses.create(
        model=C.TEXT_MODEL,
        input=[{"type": "message", "role": "user", "content": content}],
    )
    text = resp.output_text or ""
    meta_cache.put(key, {"output_text": text, "model": C.TEXT_MODEL, "tag": cache_tag or schema_name})
    meta_cache.bump_calls(1)
    return text


def parse_json(text):
    t = (text or "").strip()
    if "{" not in t:
        raise ValueError("no JSON object in Muse response")
    t = t[t.find("{"): t.rfind("}") + 1]
    return json.loads(t)
