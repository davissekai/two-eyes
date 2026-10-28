"""The ground eye: SAM 3.1 finds the river water in the citizen's clip; we read its colour."""
import os
import subprocess
import tempfile

import numpy as np

from . import config as C


def prepare_clip(src, dst=None):
    """Re-encode to H.264 MP4, CLIP_FPS frames/s, CLIP_WIDTH wide, at most CLIP_MAX_S seconds, no audio,
    and no metadata (strips the phone's GPS tags)."""
    dst = dst or os.path.join(tempfile.mkdtemp(), "clip.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-t", str(C.CLIP_MAX_S),
           "-vf", f"fps={C.CLIP_FPS},scale={C.CLIP_WIDTH}:-2", "-an", "-map_metadata", "-1",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", dst]
    subprocess.run(cmd, check=True)
    return dst


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


def muddiness(frames, masks):
    """Median CIELAB of water pixels across frames, and a rough colour label (fallback when no VLM)."""
    bs, ls = [], []
    for i, f in enumerate(frames):
        m = masks.get(i)
        if m is not None and m.shape == f.shape[:2] and m.sum() > 200:
            bs.append(np.median(lab_b(f[m])))
            ls.append(np.median(lab_l(f[m])))
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
            "frames_used": len(bs), "muddy": muddy, "label_source": "colour rule"}


def judge_colour(frame, mask=None):
    """Ask Muse Spark (image understanding) what the river water looks like. Returns dict or None.
    Cached via muse.respond — never re-calls Meta on a cache hit.
    With a mask, only the water crop is sent; without one, the whole frame."""
    from . import muse
    if mask is not None and mask.sum() > 200:
        rr, cc = np.nonzero(mask)
        crop = frame[rr.min():rr.max() + 1, cc.min():cc.max() + 1]
    else:
        crop = frame
    q = ('This is a river seen from a bridge. Looking only at the river water, is it muddy (brown/orange sediment), clear, or '
         'impossible to judge (glare, darkness)? Answer only JSON: {"water": "muddy|clear|cannot_tell", '
         '"reason": "<12 words>"}')
    text = muse.respond(q, images=[crop], schema_name="water_colour", cache_tag="water_colour_v1")
    d = muse.parse_json(text)
    lab = {"muddy": "muddy brown", "clear": "clear", "cannot_tell": "hard to judge"}.get(d.get("water"))
    if not lab:
        return None
    return {"label": lab, "muddy": {"muddy": True, "clear": False}.get(d.get("water")),
            "reason": str(d.get("reason", ""))[:120], "label_source": "Muse Spark (image understanding)"}


def overlay(frame, mask, color=(255, 120, 0), alpha=0.45):
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
        mp4 = privacy.blur_clip(mp4)
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
    res.update(method=method, n_frames=len(frames), privacy_blurred=bool(privacy_blur),
               still=overlay(frames[best], masks[best]) if best in masks else frames[best])
    return res
