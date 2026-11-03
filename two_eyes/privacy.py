"""Privacy blur: SAM 3.1 concept prompts for face / license plate on sampled frames.

Fail closed: if detection errors out, the clip must not ship unblurred.
"""
import os
import subprocess
import tempfile

import cv2
import numpy as np

from . import config as C
from . import sam


PRIVACY_PROMPTS = ("face", "license plate")


class PrivacyBlurError(RuntimeError):
    """Raised when privacy detection fails — caller must not share the clip."""


def _blur_box(frame, box, ksize=51):
    l, t, r, b = [int(x) for x in box]
    H, W = frame.shape[:2]
    l, t = max(l, 0), max(t, 0)
    r, b = min(r, W), min(b, H)
    if r <= l or b <= t:
        return frame
    roi = frame[t:b, l:r]
    k = ksize if ksize % 2 == 1 else ksize + 1
    # scale kernel to box size
    k = max(11, min(k, (r - l) | 1, (b - t) | 1))
    if k % 2 == 0:
        k += 1
    frame[t:b, l:r] = cv2.GaussianBlur(roi, (k, k), 0)
    return frame


def _one_prompt(rgb, prompt):
    try:
        return sam.concept_boxes(rgb, prompt)[0], None
    except Exception as ex:
        return [], f"{prompt}:{type(ex).__name__}"


def detect_privacy_boxes(rgb):
    """Run the face and license-plate concept prompts (one call each, side by side). Returns boxes."""
    from concurrent.futures import ThreadPoolExecutor
    boxes = []
    errors = []
    with ThreadPoolExecutor(max_workers=len(PRIVACY_PROMPTS)) as ex:
        for b, err in ex.map(lambda p: _one_prompt(rgb, p), PRIVACY_PROMPTS):
            boxes.extend(b)
            if err:
                errors.append(err)
    if errors and not boxes:
        raise PrivacyBlurError("privacy detection failed: " + ", ".join(errors))
    if errors:
        # Partial failure with some boxes: still fail closed — must not ship if any prompt errored
        raise PrivacyBlurError("privacy detection partial failure: " + ", ".join(errors))
    return boxes


def blur_frames(frames):
    """Blur faces/plates in each frame. Fail closed on detection errors."""
    out = []
    for fr in frames:
        boxes = detect_privacy_boxes(fr)
        img = fr.copy()
        for box in boxes:
            _blur_box(img, box)
        out.append(img)
    return out


def blur_clip(src_mp4, dst_mp4=None, sample_every=1, prepared=False):
    """Read clip, blur sampled frames' privacy regions, write a new mp4. Fail closed."""
    from .ground import read_frames, prepare_clip
    clean = src_mp4 if prepared else prepare_clip(src_mp4)   # prepare_clip also strips metadata
    frames = read_frames(clean)
    if not frames:
        raise PrivacyBlurError("could not read frames for privacy blur")
    # Sample: every sample_every frame (default all prepared frames — already 1 fps)
    sampled_idx = list(range(0, len(frames), max(1, sample_every)))
    blurred = frames[:]
    from concurrent.futures import ThreadPoolExecutor
    try:
        # Frames are independent, so their Meta calls run side by side (was ~20 calls in a row).
        with ThreadPoolExecutor(max_workers=C.PRIVACY_WORKERS) as ex:
            found = list(ex.map(lambda i: detect_privacy_boxes(frames[i]), sampled_idx))
        for i, boxes in zip(sampled_idx, found):
            img = frames[i].copy()
            for box in boxes:
                _blur_box(img, box)
            blurred[i] = img
    except PrivacyBlurError:
        raise
    except Exception as ex:
        raise PrivacyBlurError(f"privacy blur failed: {type(ex).__name__}") from ex

    dst_mp4 = dst_mp4 or os.path.join(tempfile.mkdtemp(), "private.mp4")
    h, w = blurred[0].shape[:2]
    # write via cv2 then remux
    tmp = dst_mp4 + ".raw.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp, fourcc, float(C.CLIP_FPS), (w, h))
    for fr in blurred:
        writer.write(cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
    writer.release()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-an", "-map_metadata", "-1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", dst_mp4], check=True)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return dst_mp4
