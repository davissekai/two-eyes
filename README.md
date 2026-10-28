# Two Eyes

**Your phone sees the muddy river. The satellite sees the scar upstream.**

Film a muddy river from a public bridge. Two Eyes traces the river upstream, looks for new forest
clearings in Sentinel-2 imagery (often galamsey, illegal gold mining, in Ghana), cross-checks them
against independent datasets, and returns a dated, anonymous evidence card you can share on WhatsApp.

Built for the Meta Global AI Developer Hackathon (Oct 26 – Nov 5, 2026). Uses **SAM 3.1** (box prompts on
satellite tiles, concept prompt on the citizen's video) and **Muse Spark** (image understanding: judges the
water colour in the clip; optional plain-English rewrite of the share text) on Meta Model API.

## How it works

| Check | Question | Method / data |
|---|---|---|
| A | Is there a new scar upstream? | Sentinel-2 SR, SCL + Cloud Score+ mask; NDVI-first candidates; SAM 3.1 box prompts refine outlines |
| B | Does it drain to this bridge? | HydroBASINS level 12, `NEXT_DOWN` walk |
| C | Do outside alerts agree? | RADD radar alerts (WUR / Global Forest Watch), Hansen GFC v1.13 |
| D | Does it look like mining? | Open-water pits inside the scar (MNDWI), WRI/Google DeepMind drivers v1.3 |
| E | Is the river muddier below? | Sentinel-2 NDTI on JRC surface-water pixels, below vs above (or now vs before) |
| F | Inside a protected area? | WDPA. Licence register: manual check on the Minerals Commission map |
| Ground | What does the clip show? | SAM 3.1 video segmentation of the river water; Muse Spark colour judgement (CIELAB rule as fallback) |

The card shows **badges**, never a probability, and its wording only goes as far as the agreeing checks
allow (e.g. "Likely source of this mud, not proven"). Proving illegality takes the authorities.

## Validation (kill gate, 27 Oct 2026)

Cut-offs were frozen before testing: NDVI forest > 0.6, drop > 0.20, min scar 0.5 ha, max cloudy 30%.
Amendment A1 (written before the rerun) added Google Cloud Score+ (`cs_cdf >= 0.60`) on top of the SCL
cloud mask after the first run showed an unmasked cloud in the intact-forest control; no cut-off changed.

| Site | Result | Pass |
|---|---|---|
| CERSGIS-measured clearing, Atewa (ref 5.49 ha) | 4.34 ha | ✓ (±50%) |
| Intact forest control | 0.00 ha | ✓ |
| Cocoa farm control | 0.00 ha | ✓ |

SAM 3.1 with the concept prompt "forest" found nothing at 10 m, so the shipped design is
NDVI-first with SAM 3.1 box refinement. The packaged pipeline reruns this gate (`two_eyes.validate`):
4.44 ha / 0.00 / 0.00, still a pass. Only three sites so far: treat it as a smoke test, not accuracy.

## End-to-end demo (27–28 Oct 2026)

Filming point: N4 trunk-road bridge over the Birim (6.28442, -0.46118), 307 km² of catchment searched.

- 24 NDVI candidates, 8 refined with SAM 3.1. Lead scar: **17.0 ha, about 19 km upstream**, NDVI 0.71 → 0.17.
- Checks: A ✓, B ✓, C – (outside the RADD forest baseline; Hansen ends 2025), D ✓ (open-water pits,
  WRI driver = hard commodities), E – (river too narrow for the JRC water mask), F ✗ (no protected area;
  licence status is a manual check).
- Ground eye: SAM 3.1 tracked the water in every frame; Muse Spark: "muddy brown".
- Speed: about 80 s for a new place; satellite results are cached per place (fixed dates), so a repeat
  or pre-warmed bridge takes about 16 s, all of it the clip.

**The demo clip is a stand-in.** It is a slow pan made from the photograph
["Pra River Ghana.jpg"](https://commons.wikimedia.org/wiki/File:Pra_River_Ghana.jpg) (Pra River from the
Beposo bridge, 2014), Wikimedia Commons, licensed **CC BY-SA 3.0**. It was not filmed at the N4 Birim bridge,
and it is credited on every evidence card it appears on. The clip file itself is not included in this repo.

## Run it (Google Colab)

```python
!pip -q install "two-eyes[app] @ git+https://github.com/davissekai/two-eyes"
import os, ee
from google.colab import userdata
os.environ["MODEL_API_KEY"] = userdata.get("MODEL_API_KEY")   # Colab Secrets
ee.Authenticate(); ee.Initialize(project="YOUR-EE-PROJECT")

from two_eyes import pipeline
r = pipeline.run(6.28442, -0.46118, name="Birim, N4 bridge", clip="river.mp4")
print(r["share_text"])          # card: two_eyes_out/evidence_card.png

from two_eyes.app import launch; launch()   # simple web UI with a public link
```

Tests: `pytest tests` (pure-Python parts; no Earth Engine needed).

## Safety

Film only from public places, never at mining sites. Clips are re-encoded with metadata (GPS) stripped,
locations on the card are rounded to about 1 km, and nothing personal is stored.

## Data and licences

Sentinel-2 (Copernicus), Cloud Score+ (Google), HydroBASINS (WWF), RADD (Wageningen University, CC BY 4.0),
Hansen GFC (UMD, CC BY 4.0), WRI/Google DeepMind drivers (CC BY 4.0), WDPA (UNEP-WCMC, non-commercial),
JRC Global Surface Water. Validation reference: CERSGIS (June 2026).
Demo stand-in image: "Pra River Ghana.jpg", Wikimedia Commons, CC BY-SA 3.0 (see above).

Code: MIT licence (see `LICENSE`).
