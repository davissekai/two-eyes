"""The ground eye: SAM 3.1 finds the river water in the citizen's clip; we read its colour."""
import json
import os
import subprocess
import tempfile

import numpy as np

from . import config as C


def prepare_clip(src, dst=None):
    """Re-encode to H.264 MP4, CLIP_FPS frames/s, CLIP_WIDTH wide, at most CLIP_MAX_S seconds, no audio,
    and no metadata (strips the phone's GPS tags)."""
    dst = dst or os.path.join(tempfile.mkdtemp(), "clip.mp4")
    # A photo becomes a short still clip, so the same SAM 3.1 video path reads it.
    head = ["-loop", "1", "-t", str(C.STILL_CLIP_S)] if is_still_image(src) else []
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *head, "-i", src, "-t", str(C.CLIP_MAX_S),
           "-vf", f"fps={C.CLIP_FPS},scale={C.CLIP_WIDTH}:-2", "-an", "-map_metadata", "-1",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", dst]
    subprocess.run(cmd, check=True)
    return dst


def is_still_image(path):
    """True for a single photo (JPEG, PNG, HEIC, WebP...), False for a video or anything unreadable."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=codec_name,nb_frames:format=format_name", "-of", "json", path],
                             capture_output=True, text=True, timeout=30)
        info = json.loads(out.stdout or "{}")
    except Exception:
        return False
    fmt = (info.get("format") or {}).get("format_name", "")
    return fmt == "image2" or fmt.endswith("_pipe")


def read_frames(mp4):
    import cv2
    cap, frames = cv2.VideoCapture(mp4), []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    cap.release()
    return frames


def lab_b(rgb_pixels):
    """CIELAB b* (blue -, yellow/brown +) of an (N, 3) uint8 RGB array."""
    import cv2
    lab = cv2.cvtColor(rgb_pixels.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    return lab[:, 2].astype(np.float32) - 128.0      # OpenCV stores b* + 128


def lab_l(rgb_pixels):
    import cv2
    lab = cv2.cvtColor(rgb_pixels.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3)
    return lab[:, 0].astype(np.float32) * 100 / 255


def core(mask, min_px=200):
    """The middle of the water: pixels more than half the mask's depth from its edge.

    From a riverbank the edge of the mask is shallows, wet mud and reflections, browner than the
    river itself, so the colour is read away from it. Small masks are used whole.
    """
    from scipy.ndimage import distance_transform_edt
    d = distance_transform_edt(mask)
    inner = d > 0.5 * d.max()
    return inner if inner.sum() >= min_px else mask


def muddiness(frames, masks):
    """Median CIELAB of the middle of the water across frames, a rough colour label (fallback when no
    VLM), and the median RGB of that water, which the page shows as a colour swatch."""
    bs, ls, rgbs = [], [], []
    for i, f in enumerate(frames):
        m = masks.get(i)
        if m is not None and m.shape == f.shape[:2] and m.sum() > 200:
            m = core(m)
            bs.append(np.median(lab_b(f[m])))
            ls.append(np.median(lab_l(f[m])))
            rgbs.append(np.median(f[m], axis=0))
    if not bs:
        return {"water_found": False, "label": "no water found", "b_star": None, "frames_used": 0}
    b, L = float(np.median(bs)), float(np.median(ls))
    if L >= C.GLARE_L:
        label, muddy = "too bright to judge (glare)", None
    elif b >= C.MUDDY_B:
        label, muddy = "muddy brown", True
    elif b <= C.CLEAR_B:
        label, muddy = "clear or green", False
    else:
        label, muddy = "somewhat cloudy", None
    return {"water_found": True, "b_star": round(b, 1), "L_star": round(L, 1), "label": label,
            "frames_used": len(bs), "muddy": muddy, "label_source": "colour rule",
            "rgb": [int(round(v)) for v in np.median(rgbs, axis=0)]}


# Citizens film from bridges, riverbanks, ferry landings and footpaths, not only from above.
COLOUR_QUESTION = (
    'This is a river filmed from a bridge or a riverbank. Looking only at the open river water, not the '
    'shallow edge, wet mud, reflections or sky glare, is it muddy (brown/orange sediment), clear, or '
    'impossible to judge (glare, darkness)? Also say if the camera looks down from above (a bridge) or '
    'across from the bank. Answer only JSON: {"water": "muddy|clear|cannot_tell", '
    '"view": "above|bank|cannot_tell", "reason": "<12 words>"}')


def parse_colour_reply(text):
    """Muse Spark's JSON reply -> label, muddy flag, camera view, reason; None if unusable."""
    import json
    try:
        d = json.loads(text[text.find("{"): text.rfind("}") + 1])
    except ValueError:
        return None
    lab = {"muddy": "muddy brown", "clear": "clear", "cannot_tell": "hard to judge"}.get(d.get("water"))
    if not lab:
        return None
    view = d.get("view") if d.get("view") in ("above", "bank") else "unknown"
    return {"label": lab, "muddy": {"muddy": True, "clear": False}.get(d.get("water")), "view": view,
            "reason": str(d.get("reason", ""))[:120], "label_source": "Muse Spark (image understanding)"}


def judge_colour(frame, mask=None):
    """Ask Muse Spark (image understanding) what the river water looks like. Returns dict or None.
    Cached via muse.respond — never re-calls Meta on a cache hit.
    With a mask, only the water crop is sent; without one, the whole frame (lets it run alongside SAM)."""
    from . import muse
    if mask is not None and mask.sum() > 200:
        rr, cc = np.nonzero(mask)
        crop = frame[rr.min():rr.max() + 1, cc.min():cc.max() + 1]
    else:
        crop = frame
    # Cache tag v2: prompt includes bridge-or-bank view (citizen PR), so do not reuse v1 cache.
    text = muse.respond(COLOUR_QUESTION, images=[crop], schema_name="water_colour",
                        cache_tag="water_colour_v2")
    return parse_colour_reply(text)


def overlay(frame, mask, color=(212, 255, 58), alpha=0.55):
    out = frame.astype(np.float32).copy()
    out[mask] = out[mask] * (1 - alpha) + np.array(color, np.float32) * alpha
    return out.astype(np.uint8)


def analyse_clip(src, use_sam=True, use_vlm=True, privacy_blur=True):
    """Prepare clip, privacy-blur faces/plates (fail closed), then SAM water + Muse colour on one still.

    Muse water colour runs on a single still only (no whole-clip Muse) to keep Meta calls minimal.
    """
    mp4 = prepare_clip(src)
    if privacy_blur:
        from . import privacy
        # Fail closed: PrivacyBlurError propagates — caller must not share the unblurred clip.
        mp4 = privacy.blur_clip(mp4, prepared=True)
    frames = read_frames(mp4)
    if not frames:
        raise ValueError("Could not read any frames from the clip.")
    h, w = frames[0].shape[:2]
    masks, method = {}, "SAM 3.1 (video, concept prompt '%s')" % C.WATER_PROMPT
    from concurrent.futures import ThreadPoolExecutor
    mid = frames[len(frames) // 2]
    with ThreadPoolExecutor(max_workers=2) as ex:
        # Single-still Muse colour only (skip whole-clip Muse water colour — extra cost).
        vfut = ex.submit(judge_colour, mid) if use_vlm else None
        if use_sam:
            from . import sam
            masks = sam.segment_video(mp4, C.WATER_PROMPT, (w, h))
        res = muddiness(frames, masks)
        if vfut is not None and res.get("water_found"):
            try:
                v = vfut.result()
                if v:
                    res.update(v)
            except Exception as e:
                res["vlm_error"] = type(e).__name__
    best = max(masks, key=lambda k: masks[k].sum()) if masks else len(frames) // 2
    best = min(best, len(frames) - 1)
    # frame: what the citizen filmed; still: same frame with measured water painted lime.
    res.update(method=method, n_frames=len(frames), frame=frames[best],
               privacy_blurred=bool(privacy_blur),
               still=overlay(frames[best], masks[best]) if best in masks else frames[best])
    return res
