"""Disk cache for Meta Model API responses. Cache hits never re-call the API."""
import hashlib
import json
import os
import time

CACHE_DIR = os.environ.get(
    "TWO_EYES_META_CACHE",
    os.path.join(os.path.expanduser("~"), ".two_eyes_cache", "meta"),
)


def _path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, key + ".json")


def make_key(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, (bytes, bytearray)):
            h.update(p)
        else:
            h.update(str(p).encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:32]


def get(key: str):
    path = _path(key)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def put(key: str, payload: dict):
    path = _path(key)
    payload = dict(payload)
    payload.setdefault("cached_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, path)
    return payload


def call_count_path():
    return os.path.join(CACHE_DIR, "_call_count.json")


def bump_calls(n=1):
    path = call_count_path()
    os.makedirs(CACHE_DIR, exist_ok=True)
    data = {"calls": 0}
    if os.path.isfile(path):
        try:
            data = json.load(open(path))
        except Exception:
            pass
    data["calls"] = int(data.get("calls", 0)) + n
    json.dump(data, open(path, "w"))
    return data["calls"]


def get_calls():
    path = call_count_path()
    if not os.path.isfile(path):
        return 0
    try:
        return int(json.load(open(path)).get("calls", 0))
    except Exception:
        return 0


# At most this many Meta API calls in flight across every check on the server, so several checks at once
# queue politely instead of tripping the API's rate limit. Calls past the cap wait their turn.
import threading as _threading
SLOTS = _threading.BoundedSemaphore(int(os.environ.get("TWO_EYES_META_CONCURRENCY", "12")))
