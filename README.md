# Two Eyes

**Your phone sees the muddy river. The satellite sees the scar upstream.**

Film a muddy river from a public spot: a bridge, a riverbank, a ferry landing. Two Eyes traces the river upstream, looks for new forest
clearings in Sentinel-2 imagery (often galamsey, illegal gold mining, in Ghana), cross-checks them
against independent datasets, and returns a dated, anonymous evidence card you can share on WhatsApp.

Built for the Meta Global AI Developer Hackathon (Oct 26 – Nov 5, 2026). Uses **SAM 3.1** (box prompts on
satellite tiles, concept prompt on the citizen's video) and **Muse Spark** (image understanding: judges the
water colour in the clip; check-grounded evidence-card text; scar-cause second opinion) on Meta Model API.

## How it works

| Check | Question | Method / data |
|---|---|---|
| A | Is there a new scar upstream? | Sentinel-2 SR, SCL + Cloud Score+ mask; NDVI-first candidates; SAM 3.1 box prompts refine outlines |
| B | Does it drain to this spot? | Spot snapped onto HydroRIVERS (flags confluences), then HydroBASINS level 12, `NEXT_DOWN` walk |
| C | Do outside alerts agree? | RADD radar alerts (WUR / Global Forest Watch), Hansen GFC v1.13 |
| D | Does it look like mining? | Open-water pits inside the scar (MNDWI), WRI/Google DeepMind drivers v1.3 |
| E | Is the river muddier below? | Sentinel-2 NDTI on JRC surface-water pixels, below vs above (or now vs before) |
| F | Inside a protected area? | WDPA. Licence register: manual check on the Minerals Commission map |
| Ground | What does the clip show? | SAM 3.1 video segmentation of the river water; colour read from the middle of the water (bank shots have muddy edges); Muse Spark colour judgement (CIELAB rule as fallback) |

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

- 24 NDVI candidates, **9 refined with SAM 3.1** (recorded Meta Model API run, 28 Oct 2026; was 8 in the
  earlier illustrative demo). Lead scar: **17.0 ha, about 19 km upstream** (Earth Engine catchment
  numbers; visual-tile px are not hectares), NDVI 0.71 → 0.17.
- Checks: A ✓, B ✓, C – (outside the RADD forest baseline; Hansen ends 2025), D ✓ (open-water pits,
  WRI driver = hard commodities), E – (river too narrow for the JRC water mask), F ✗ (no protected area;
  licence status is a manual check).
- Ground eye: Muse Spark (recorded Meta run): **"muddy brown"** — "Water is brown with sediment throughout".
- Muse scar judge (frozen prompt v1): exact-match hit rate **50% (4/8)** on **real Atewa** Earth Engine
  Sentinel-2 true-colour chips (CERSGIS-measured clearing components + nearby galamsey-belt scars as
  mining positives; intact-forest / no-scar windows as `unclear` controls). Replaces the earlier Birim
  stand-in **5/8 (62.5%)**. Muse preferred `unclear` on the mining positives when open-water pits were
  not resolvable at 10 m — honest, not over-called. Verdicts cached for a deterministic demo.
  Lead scar figures (**17.0 ha, ~19 km upstream**) are unchanged (Birim EE catchment).
- Card text: Muse Spark writes under check-grounded rules (every sentence names a check; code drops
  sentences whose check failed). A minimum card (location, NDVI change, "Likely source, not proven")
  always survives.
- Privacy: uploaded clips are SAM 3.1 concept-prompted for `face` then `license plate` and blurred
  before storage/share; detection errors fail closed (clip does not ship unblurred).
- Meta API calls for the recorded Birim SAM + Muse colour + scar-judge score: see `birim_meta.json`
  and the local disk cache under `~/.two_eyes_cache/meta` (never re-called on a cache hit).
- Speed: about 80 s for a new place; satellite results are cached per place (fixed dates), so a repeat
  or pre-warmed spot takes about 16 s, all of it the clip.

**The demo clip is a stand-in.** It is a slow pan made from the photograph
["Pra River Ghana.jpg"](https://commons.wikimedia.org/wiki/File:Pra_River_Ghana.jpg) (Pra River from the
Beposo bridge, 2014), Wikimedia Commons, licensed **CC BY-SA 3.0**. It was not filmed at the N4 Birim bridge,
and it is credited on every evidence card it appears on. The clip file itself is not included in this repo.

### Meta Model API

Base URL `https://api.meta.ai/v1` (OpenAI-SDK compatible). Models: `sam-3.1`, `muse-spark-1.3`.
Load `MODEL_API_KEY` from `~/.secrets/MODEL_API_KEY` at runtime (never print, log, or commit). Every
response is cached to disk; a cache hit never re-calls Meta. Demo mode (`DEMO_MODE=1`) serves the
recorded Birim Meta run with no live API calls.

## Run it (Google Colab)

```python
!pip -q install "two-eyes[app] @ git+https://github.com/davissekai/two-eyes"
import os, ee
from google.colab import userdata
os.environ["MODEL_API_KEY"] = userdata.get("MODEL_API_KEY")   # Colab Secrets
os.environ["EE_PROJECT"] = userdata.get("EE_PROJECT")         # never hard-code
ee.Authenticate(); ee.Initialize(project=os.environ["EE_PROJECT"])

from two_eyes import pipeline
r = pipeline.run(6.28442, -0.46118, name="Birim, N4 bridge", clip="river.mp4")
print(r["share_text"])          # card: two_eyes_out/evidence_card.png

from two_eyes.app import launch; launch()   # simple web UI with a public link
```

Tests: `pytest tests` (pure-Python parts; no Earth Engine needed).

## Run the phone app

An installable web app: one screen at a time (where you are, film the water, the live check, the result,
share). Phones add it to the home screen and open it full-screen.

```bash
pip install -e ".[web]"
python -m two_eyes.web                     # demo result, no keys needed
EE_PROJECT=<your-ee-project> MODEL_API_KEY=... python -m two_eyes.web   # live
```

It serves on http://127.0.0.1:8000. Phones only allow GPS and the camera over https, so to use it on a
phone, put it behind an https tunnel or host.

## Safety

Film only from public places, never at mining sites. Clips are re-encoded with metadata (GPS) stripped,
faces and license plates are blurred with SAM 3.1 before anything is stored or shared (fail closed on
detection errors), the filming spot is rounded to about 1 km on the card and in the shared report (the
clearing itself stays precise, so officials can find it), and nothing personal is stored.

## Data and licences

Sentinel-2 (Copernicus), Cloud Score+ (Google), HydroBASINS (WWF), RADD (Wageningen University, CC BY 4.0),
Hansen GFC (UMD, CC BY 4.0), WRI/Google DeepMind drivers (CC BY 4.0), WDPA (UNEP-WCMC, non-commercial),
JRC Global Surface Water. Validation reference: CERSGIS (June 2026).
Demo stand-in image: "Pra River Ghana.jpg", Wikimedia Commons, CC BY-SA 3.0 (see above).

Code: MIT licence (see `LICENSE`).
