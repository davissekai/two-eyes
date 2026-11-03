"""Load Meta Model API key from the local secrets file into the environment.

Never prints or logs the key. ~/.secrets/MODEL_API_KEY is the source of truth;
.env is gitignored and may also set MODEL_API_KEY for local runs.
"""
import os

_SECRET_PATHS = (
    os.path.expanduser("~/.secrets/MODEL_API_KEY"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
)


def ensure_model_api_key():
    """Put MODEL_API_KEY in the environment if a local secrets file has it. No-op if already set."""
    if os.environ.get("MODEL_API_KEY"):
        return bool(os.environ["MODEL_API_KEY"].strip())
    for path in _SECRET_PATHS:
        if not os.path.isfile(path):
            continue
        raw = open(path, "r", encoding="utf-8").read().strip()
        if not raw:
            continue
        # .env style: MODEL_API_KEY=...
        if "=" in raw and not raw.startswith("LL") and "MODEL_API_KEY" in raw.split("=", 1)[0]:
            raw = raw.split("=", 1)[1].strip().strip('"').strip("'")
        if raw:
            os.environ["MODEL_API_KEY"] = raw
            return True
    return False
