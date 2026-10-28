"""One-call Colab helpers: two_eyes.colab.smoke(globals())."""
import json
import os
import time


def setup(g=None, project=None):
    import ee
    g = g or {}
    if not os.environ.get("MODEL_API_KEY"):
        try:
            from google.colab import userdata
            os.environ["MODEL_API_KEY"] = userdata.get("MODEL_API_KEY")
        except Exception as ex:
            print("MODEL_API_KEY not loaded:", type(ex).__name__)
    try:
        ee.Number(1).getInfo()
    except Exception:
        ee.Initialize(project=project or g.get("EE_PROJECT"))
    print("Earth Engine OK; Meta key loaded:", bool(os.environ.get("MODEL_API_KEY")))


def smoke(g=None, bridge=(6.28442, -0.46118), name="Birim, N4 bridge", clip=None, validate_first=True,
          clip_credit=None, focus=None):
    from . import pipeline, validate
    setup(g)
    t = time.time()
    if validate_first and g and "SITES" in g:
        S = g["SITES"]
        validate.run({k: (S[k]["lat"], S[k]["lon"]) for k in ("intact_forest", "cocoa_farm") if S.get(k, {}).get("lat")})
        print(f"[validation took {time.time() - t:.0f}s]")
    t = time.time()
    r = pipeline.run(bridge[0], bridge[1], name=name, clip=clip, clip_credit=clip_credit, focus=focus)
    print(f"[pipeline took {time.time() - t:.0f}s]")
    print("CHECK C:", json.dumps(r["checks"].get("C"), default=str))
    print(json.dumps(pipeline.public(r), indent=1, default=str)[:6000])
    try:
        from IPython.display import Image, display
        display(Image(r["card_png"]))
    except Exception:
        pass
    return r


def radd_info(lat=6.16305, lon=-0.58102):
    """Diagnostic: what the RADD collection holds near a point."""
    import ee
    from . import config as C
    col = ee.ImageCollection(C.RADD)
    print("RADD images:", col.size().getInfo())
    print("geography values:", col.aggregate_array("geography").distinct().getInfo())
    print("layer values:", col.aggregate_array("layer").distinct().getInfo())
    pt = ee.Geometry.Point([lon, lat]).buffer(500)
    near = col.filterBounds(pt)
    print("images over the scar:", near.size().getInfo())
    for f in near.limit(6).getInfo()["features"]:
        print(" ", f["properties"].get("layer"), f["properties"].get("geography"), [b["id"] for b in f["bands"]])
