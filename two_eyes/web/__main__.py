"""Run the phone app.

    python -m two_eyes.web                     (demo result unless the live pipeline can run)
    EE_PROJECT=<id> MODEL_API_KEY=... python -m two_eyes.web    (live: Earth Engine + Meta models)

Phones only allow GPS and the camera on https; for a phone, put it behind an https tunnel.
"""
import os

import uvicorn


def main():
    project = os.environ.get("EE_PROJECT")
    if project:
        import ee
        ee.Initialize(project=project)
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("two_eyes.web.server:app", host=os.environ.get("HOST", "127.0.0.1"), port=port)


if __name__ == "__main__":
    main()
