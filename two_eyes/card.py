"""Evidence card: badges (never percentages), honest headline, PNG for WhatsApp.

Field Evidence look (atelier brand kit, direction A): graphite card, bone type,
silt labels, laterite accents, machine-lime scar outlines only; WhatsApp share lives in the UI, not the PNG.
"""
import datetime as dt
import os
import textwrap

import numpy as np

from . import config as C

BADGES = [("A", "New forest scar"), ("B", "Drains to this bridge"), ("C", "Alerts agree"),
          ("D", "Looks like mining"), ("E", "River muddier below"), ("F", "Inside a protected area")]

# --- Field Evidence palette ---
GRAPHITE = "#15130F"
BONE = "#F2EDE4"
SILT = "#C9A27E"
LATERITE = "#9C5A34"
LIME = "#D4FF3A"          # machine accent: masks, boxes, badges, finding
WA = "#25D366"            # WhatsApp share pill only
CONTOUR_COLOR = LIME      # mask contours / scar boxes are machine vision -> lime
RULE_EDGE = "rgba(242,237,228,.18)"
RULE_EDGE_HEX = "#4a443b"   # matplotlib spines need an opaque colour

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

# badge styles: value -> (facecolour, symbol colour, label colour)
_BADGES_STYLE = {
    True: (LIME, GRAPHITE, BONE),                    # pass: lime chip, bone label
    False: ("none", SILT, SILT),                     # fail: silt, muted
    None: ("none", SILT, SILT),                      # unknown: silt dash
}


def _period(p):
    s, e = (dt.date.fromisoformat(x) for x in p)
    return f"{s:%b}–{e:%b %Y}" if s.year == e.year else f"{s:%b %Y}–{e:%b %Y}"


def headline(r):
    """Card text from the checks that agree (the table in DOCS.md section 4). r = report dict."""
    k = r["checks"]
    A, B, Cc, D, E, F = (k.get(x, {}).get("pass") for x in "ABCDEF")
    lines = []
    if r.get("status") == "CLOUDY":
        return ["Clouds blocked the view upstream. We'll check again when it clears."]
    if not A:
        return [f"No new forest clearing upstream between {_period(C.BEFORE)} and {_period(C.AFTER)}.",
                "This doesn't mean the water is safe."]
    s = r["scar"]
    where = f"{s['area_ha']:.1f} ha, about {s['distance_km']:.0f} km upstream"
    if not B:
        return [f"A new forest clearing ({s['area_ha']:.1f} ha) was found nearby, but it drains elsewhere,",
                "not to this bridge."]
    if not Cc:
        # Lead + silt subline (Field Evidence card layout)
        lines.append(f"Possible forest clearing, {s['distance_km']:.0f} km upstream.")
        lines.append(
            f"since early {C.BEFORE[0][:4]} · {s['area_ha']:.1f} ha · our check only, not yet confirmed")
    else:
        first = k["C"].get("radd_first")
        conf = f"radar alerts from {first}" if first else "Global Forest Watch loss data"
        lines.append(f"Forest cleared upstream since {C.BEFORE[0][:4]} ({where}), confirmed by {conf}. "
                     "Cause not confirmed.")
    if Cc and D and E:
        lines.append("The clearing shows signs of mining and the river turns muddier just below it. "
                     "Likely source of this mud, not proven.")
    elif Cc and D:
        lines.append("The clearing shows signs of mining (open-water pits). Cause not proven.")
    elif E:
        lines.append("The river is muddier just below the clearing.")
    if F:
        names = ", ".join(p["name"] for p in k["F"]["protected_areas"] if p.get("name"))
        lines.append(f"It lies inside {names or 'a protected area'}. Only the authorities can confirm whether it's illegal.")
    g = r.get("ground")
    if g and g.get("water_found"):
        if g.get("muddy") is None and "judge" in g.get("label", ""):
            lines.append("Your clip: river water found, but its colour is hard to judge (glare).")
        else:
            lines.append(f"Your clip: the water looks {g['label']}.")
    return lines


def share_text(r, use_llm=True):
    """WhatsApp message. Muse Spark rewrites the facts plainly; falls back to the template."""
    base = " ".join(headline(r))
    if not (use_llm and C.SHARE_LLM):
        return base
    try:
        from .sam import client
        prompt = ("Rewrite this evidence summary as a short WhatsApp message in plain English for Ghanaian "
                  "readers (max 60 words). Keep every number and every caution exactly. Add no new facts, "
                  "no greeting, no percentages, no accusations against people.\n\n" + base)
        out = client().responses.create(model=C.TEXT_MODEL, input=prompt).output_text.strip()
        return out if 20 < len(out) < 500 and "%" not in out else base
    except Exception:
        return base


def _meta_info(r):
    """(n_refined, muse_quote) for the Meta strip: prefers r['meta'], else derives from the report."""
    meta = r.get("meta") or {}
    n = meta.get("sam_refined")
    if n is None:
        n = len([c for c in r.get("candidates", []) if c.get("status") == "SCAR"]) or 1
    quote = meta.get("muse_quote")
    if quote is None:
        g = r.get("ground") or {}
        if g.get("water_found") and g.get("label"):
            quote = g["label"]
    return (n, f"Muse Spark: \u201c{quote}\u201d" if quote else None)


def whatsapp_url(share_text):
    """One-tap WhatsApp share link (no network needed to build it)."""
    from urllib.parse import quote
    return "https://wa.me/?text=" + quote(share_text)


def _badge_symbol(v):
    return {True: "✓", False: "✗", None: "–"}[v]


def _register_fonts():
    """(serif, body, mono) family names, registered from the bundled TTFs."""
    from matplotlib import font_manager as fm
    names = []
    for f in ("InstrumentSerif-Regular.ttf", "InstrumentSerif-Italic.ttf",
              "Geist-VariableFont_wght.ttf", "JetBrainsMono-VariableFont_wght.ttf"):
        p = os.path.join(FONTS_DIR, f)
        if os.path.isfile(p):
            fm.fontManager.addfont(p)
    def fam(fname):
        return fm.FontProperties(fname=os.path.join(FONTS_DIR, fname)).get_name()
    return fam("InstrumentSerif-Regular.ttf"), fam("Geist-VariableFont_wght.ttf"), \
        fam("JetBrainsMono-VariableFont_wght.ttf")


def _emphasis_phrase(r):
    """Short italic lime phrase for the headline, from the checks (demo run: mining digs)."""
    k = r["checks"]
    if k.get("D", {}).get("pass"):
        return "Signs of mining upstream."
    if k.get("E", {}).get("pass"):
        return "The river runs brown."
    if k.get("A", {}).get("pass") is False:
        return "No new scar found."
    return "Bare earth by the river."


def _sat_tile(rgb, mask, darken=0.85):
    """Satellite lead for the card: strip painted scar fills, darken ~15%, ground shows through."""
    out = np.asarray(rgb, dtype=np.float32).copy()
    if mask is not None and np.any(mask):
        # Replace orange/yellow paint with a muted bare-earth tone from luminance
        # so only the lime contour (drawn by render) marks the scar — no fill, no orange cores.
        pix = out[mask]
        lum = 0.30 * pix[:, 0] + 0.59 * pix[:, 1] + 0.11 * pix[:, 2]
        scale = np.clip(lum / 190.0, 0.45, 1.15)
        out[mask, 0] = 118.0 * scale
        out[mask, 1] = 104.0 * scale
        out[mask, 2] = 46.0 * scale
    out *= darken
    return np.clip(out, 0, 255).astype(np.uint8)


def render(r, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib.patches import Rectangle
    
    SERIF, BODY, MONO = _register_fonts()
    fig = plt.figure(figsize=(7.2, 9.6), dpi=150, facecolor=GRAPHITE)
    fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
    gs = GridSpec(5, 1, figure=fig, height_ratios=[2.65, 2.75, 1.95, 1.35, 0.9], hspace=0.06)
    # No lime border around the whole card (chrome lives in the UI, not the PNG).

    # --- 1. lead satellite panel: darkened ground + thin 2px lime scar outlines only ---
    ax = fig.add_subplot(gs[0]); ax.axis("off")
    s = r.get("scar") or {}
    img = s.get("rgb_after")
    mask = s.get("mask")
    if img is not None:
        ax.imshow(_sat_tile(img, mask, darken=0.85), aspect="auto")
    else:
        ax.text(0.5, 0.5, "no image", ha="center", va="center", color=SILT,
                fontsize=9, transform=ax.transAxes)
    if mask is not None and mask.any():
        # ~2px at 150 dpi: linewidth_pt = 2 * 72 / 150 ≈ 0.96
        ax.contour(mask.astype(float), levels=[0.5], colors=[LIME], linewidths=1.0)
    illustrative = bool(r.get("demo") or s.get("boxes_illustrative"))
    if illustrative and mask is not None and mask.any():
        ax.text(0.03, 0.06, "Illustrative outlines, not live SAM", transform=ax.transAxes,
                fontsize=7.5, color=LIME, family=MONO, va="bottom",
                bbox=dict(boxstyle="round,pad=0.45", fc=GRAPHITE, ec=LIME, alpha=0.55))
    # chip: EVIDENCE CARD
    ax.text(0.02, 0.97, "EVIDENCE CARD", transform=ax.transAxes, fontsize=9, family=MONO,
            color=GRAPHITE, va="top", ha="left",
            bbox=dict(boxstyle="square,pad=0.55", fc=LIME, ec="none"))
    # demo chip, tucked under the EVIDENCE CARD chip
    if r.get("demo"):
        ax.text(0.02, 0.86, "DEMO · ILLUSTRATIVE", transform=ax.transAxes, fontsize=8,
                family=MONO, color=LIME, va="top", ha="left",
                bbox=dict(boxstyle="square,pad=0.45", fc="none", ec=LIME, lw=1.2))
    # Two Eyes mark (left silt pupil, right lime crosshair), from the brand logo lockup
    mk_ax = ax.inset_axes([0.87, 0.045, 0.115, 0.10])
    mk_ax.axis("off")
    mk_ax.set_aspect("equal")
    mk_ax.set_xlim(0, 3.1); mk_ax.set_ylim(0, 1)
    from matplotlib.patches import Circle
    mk_ax.add_patch(Circle((0.45, 0.5), 0.36, fill=False, ec=BONE, lw=2))
    mk_ax.add_patch(Circle((0.45, 0.5), 0.09, fc=SILT, ec="none"))
    mk_ax.add_patch(Circle((2.65, 0.5), 0.36, fill=False, ec=LIME, lw=2))
    mk_ax.add_patch(Circle((2.65, 0.5), 0.09, fc=LIME, ec="none"))
    for xy1, xy2 in (((2.65, 0.9), (2.65, 1.1)), ((2.15, 0.5), (2.3, 0.5)),
                     ((2.65, -0.1), (2.65, 0.1)), ((3.0, 0.5), (3.15, 0.5))):
        mk_ax.plot(*zip(xy1, xy2), color=LIME, lw=1.6, clip_on=False)
    mk_ax.plot([0.85, 2.25], [0.5, 0.62], color=LIME, lw=1.4)

    # --- 2. headline (Instrument Serif ~1.05 lh) + one small Geist silt subline ---
    ax = fig.add_subplot(gs[1]); ax.axis("off")
    h_lines = headline(r)
    lead = h_lines[0] if h_lines else ""
    lead_lines = textwrap.wrap(lead, 42)
    y = 0.98
    for line in lead_lines:
        ax.text(0.02, y, line, fontsize=22, va="top", family=SERIF, color=BONE,
                linespacing=1.05)
        y -= 0.22 * 1.05
    sub = h_lines[1] if len(h_lines) > 1 else ""
    # Prefer the silt meta line when present (demo: since early 2023 · 17.0 ha · …)
    if sub and ("·" in sub or "our check only" in sub.lower() or sub.startswith("since ")):
        ax.text(0.02, y - 0.02, sub, fontsize=10, va="top", family=BODY, color=SILT)
        y -= 0.16
        rest = " ".join(h_lines[2:])
    else:
        rest = " ".join(h_lines[1:])
    if rest:
        ax.text(0.02, y - 0.04, textwrap.fill(rest, 92), fontsize=10, va="top", family=BODY,
                color=BONE, linespacing=1.45)

    # --- 3. mono rows: RIVER | LOCATION | COMPARED | FINDING ---
    ax = fig.add_subplot(gs[2]); ax.axis("off")
    lat, lon = r["bridge"]["lat"], r["bridge"]["lon"]
    comp = f"Sentinel-2 · {_period(C.BEFORE)} vs {_period(C.AFTER)}"
    finding = f"{s['area_ha']:.1f} ha, {s['distance_km']:.0f} km upstream" if s.get("area_ha") else "—"
    rows = [("RIVER", r["bridge"].get("name") or "Bridge", BONE),
            ("LOCATION", f"{lat:.4f}, {lon:.4f}", BONE),
            ("COMPARED", comp, BONE),
            ("FINDING", finding, LIME)]
    n_refined, muse_quote = _meta_info(r)
    rows.append(("CHECKS BY", f"SAM 3.1 refined {n_refined} scars" + (f" · {muse_quote}" if muse_quote else ""), SILT))
    for i, (k, v, col) in enumerate(rows):
        y = 0.88 - i * 0.185
        ax.plot([0.02, 0.98], [y - 0.125, y - 0.125], color=RULE_EDGE_HEX, lw=0.8)
        ax.text(0.02, y, k, fontsize=8.5, family=MONO, color=SILT, va="center")
        ax.text(0.30, y, v, fontsize=9.5, family=MONO if col != BONE else BODY, color=col,
                va="center")

    # --- 4. A–F checks: lime/silt mono chips ---
    ax = fig.add_subplot(gs[3]); ax.axis("off")
    for i, (key, name) in enumerate(BADGES):
        v = r["checks"].get(key, {}).get("pass")
        face, sym_col, label_col = _BADGES_STYLE.get(v, _BADGES_STYLE[None])
        x, y = (i % 2) * 0.5, 0.78 - (i // 2) * 0.42
        ax.text(x + 0.02, y, f"{_badge_symbol(v)} {key}", fontsize=10,
                family=[MONO, "DejaVu Sans"],    # fallback: JBMono lacks the ballot glyphs
                color=sym_col, weight="bold", va="center",
                bbox=dict(boxstyle="square,pad=0.4", fc=face if face != "none" else "none",
                          ec=LIME if v else RULE_EDGE_HEX, lw=1.1))
        ax.text(x + 0.085, y, name, fontsize=9, family=BODY, color=label_col,
                va="center", alpha=0.85 if v else 0.7)

    # --- 5. footer (Share on WhatsApp stays in the Gradio UI only — not on the PNG) ---
    ax = fig.add_subplot(gs[4]); ax.axis("off")
    cop_years = f"{C.BEFORE[0][:4]}, {C.AFTER[0][:4]}"
    ax.text(0.02, 0.18, textwrap.fill(
        f"Contains modified Copernicus Sentinel data {cop_years} · checked {r['date']}", 76),
        fontsize=6.5, family=MONO, color=SILT, va="bottom")
    ax.text(0.02, 0.55, "Powered by", fontsize=6.5, family=MONO, color=SILT, va="bottom")
    ax.text(0.13, 0.55, "Meta SAM 3.1 + Muse Spark", fontsize=6.5, family=MONO, color=BONE,
            va="bottom")
    fig.savefig(path, facecolor=GRAPHITE)
    plt.close(fig)
    return path
