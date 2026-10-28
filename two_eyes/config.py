"""Frozen settings for Two Eyes.

The scar cut-offs below were fixed on Day 1 (26 Oct 2026) and passed the kill gate on
27 Oct 2026 under amendment A1 (Cloud Score+ added to the SCL mask). Do not tune them
after seeing results: change them only through a written amendment and a rerun of the gate.
"""

# --- Sentinel-2 ---
S2 = "COPERNICUS/S2_SR_HARMONIZED"
CS_PLUS = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
CS_CLEAR = 0.60              # amendment A1: keep pixels with cs_cdf >= 0.60
MAX_CLOUD_PCT = 40           # scene-level filter
BEFORE = ("2023-01-01", "2023-03-31")   # dry season, "before"
AFTER = ("2026-01-01", "2026-04-30")    # dry season, "now"

SCALE_M = 10
CRS = "EPSG:32630"           # UTM 30N, Ghana
PIXEL_HA = SCALE_M * SCALE_M / 10_000
BOX_HALF_M = 1000            # 2 km x 2 km box around each candidate scar
UPSCALE = 4                  # SAM sees the box at 4x (nearest neighbour)

# --- Frozen cut-offs (kill gate, 26-27 Oct 2026) ---
NDVI_FOREST = 0.6            # pixel was forest in the before image
NDVI_DROP = 0.20             # before minus now NDVI that counts as clearing
MIN_SCAR_HA = 0.5            # smallest scar reported (~50 pixels)
MAX_CLOUDY = 0.30            # masked share above this -> "Cloudy"
AREA_TOL = 0.5               # validation only: +/-50% area at the reference site
SEARCH_RADIUS_M = 150        # validation only

# --- Upstream search ---
HYBAS = "WWF/HydroSHEDS/v1/Basins/hybas_12"
MAX_CANDIDATES = 8           # scars refined with SAM per report (largest first)
MAX_SEARCH_KM2 = 600         # cap on the upstream area searched (keeps EE calls bounded)

# --- Check C: outside confirmation ---
RADD = "projects/radar-wur/raddalert/v1"
RADD_SINCE_YYDOY = 23001     # alerts on/after 1 Jan 2023 (start of "before")
HANSEN = "UMD/hansen/global_forest_change_2025_v1_13"
HANSEN_SINCE = 23            # lossyear >= 2023
CONFIRM_BUFFER_M = 100       # look for alerts within 100 m of the scar outline
CONFIRM_MIN_SHARE = 0.10     # alerts must cover >=10% of the scar area (and >=0.1 ha)

# --- Check D: does it look like mining? ---
DRIVERS = "projects/landandcarbon/assets/wri_gdm_drivers_forest_loss_1km/v1_3_2001_2025"
DRIVER_HARD_COMMODITIES = 2  # class 2 = mining or energy infrastructure
MNDWI_WATER = 0.0            # (green - SWIR1)/(green + SWIR1) > 0 -> open water
POND_MIN_SHARE = 0.03        # >=3% of the scar is open water (pits/ponds)
BARE_NDVI = 0.25             # now-NDVI below this inside the scar = bare ground

# --- Check E: is the river muddier below the scar? ---
JRC_WATER = "JRC/GSW1_4/GlobalSurfaceWater"
WATER_OCCURRENCE = 50        # JRC occurrence % that counts as river water
MUDDIER_DELTA = 0.05         # NDTI below minus above that counts as "muddier"
MIN_WATER_PX = 20            # fewer water pixels than this -> "not measurable"

# --- Check F: protected area / licences ---
WDPA = "WCMC/WDPA/current/polygons"
LICENCE_MAP_URL = "https://miningrepository.mincom.gov.gh/map"

# --- Ground eye (citizen clip) ---
SAM_MODEL = "sam-3.1"
TEXT_MODEL = "muse-spark-1.3"
META_BASE_URL = "https://api.meta.ai/v1"
WATER_PROMPT = "river water"
CLIP_FPS = 1                 # frames per second sent to SAM 3.1 (1 is plenty for water colour; halves latency)
CLIP_MAX_S = 10
CLIP_WIDTH = 480
# Muddiness of the water pixels in the clip, from CIELAB b* (blue -, yellow/brown +).
# Uncalibrated v1 thresholds, stated on the card as a rough reading.
MUDDY_B = 18.0
CLEAR_B = 8.0
GLARE_L = 85.0               # median L* above this: overexposed, colour not judged

SHARE_LLM = False            # WhatsApp text from the fixed template (fast, no wording drift); True = Muse Spark rewrite
