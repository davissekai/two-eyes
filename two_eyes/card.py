"""Evidence card: badges (never percentages), honest headline, PNG for WhatsApp.

Poster look (see the campaign poster): cream card, gold border, forest-green type,
orange accents, scar contour in alert red.
"""
import datetime as dt
import textwrap

import numpy as np

from . import config as C

BADGES = [("A", "New forest scar"), ("B", "Drains to this bridge"), ("C", "Alerts agree"),
          ("D", "Looks like mining"), ("E", "River muddier below"), ("F", "Inside a protected area")]

# --- poster palette ---
CREAM = "#fff8ea"
GOLD = "#ffd600"
ORANGE = "#ff7a00"
FOREST = "#0f2a1a"
PANEL_GREEN = "#163d26"
ALERT = CONTOUR_COLOR = "#e8432e"
MUTED_FOOT = "#8b8474"
RULE_EDGE = "#d5cbba"

# badge styles: value -> (facecolor, symbol colour, label colour)
_BADGES_STYLE = {
    True: (GOLD, "#1e1e00", FOREST),          # pass: gold filled, dark text
    False: ("#f2ecdb", "#a89d89", "#857d6c"),  # fail: muted on cream
    None: ("#f6f3e9", "#a49d8e", "#8a8474"),   # none: grey dash on cream
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
        lines.append(f"Possible forest clearing upstream since early {C.BEFORE[0][:4]} ({where}). "
                     "Our check only, not yet confirmed.")
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


def render(r, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib.patches import Rectangle

    fig = plt.figure(figsize=(7.2, 9.6), dpi=150, facecolor=CREAM)
    gs = GridSpec(4, 3, figure=fig, height_ratios=[0.5, 2.2, 1.6, 1.9], hspace=0.28, wspace=0.05,
                  left=0.05, right=0.95, top=0.97, bottom=0.035)
    ax = fig.add_subplot(gs[0, :]); ax.axis("off")
    ax.text(0, 0.78, "TWO EYES · EVIDENCE CARD", fontsize=15.5, weight="bold", va="center", color=FOREST)
    if r.get("demo"):
        ax.text(1, 0.78, "DEMO", fontsize=11, weight="bold", va="center", ha="right", color=GOLD)
    lat, lon = r["bridge"]["lat"], r["bridge"]["lon"]
    ax.text(0, 0.15, f"{r['bridge'].get('name') or 'Bridge'} (~{round(lat, 2)}, {round(lon, 2)}) · "
            f"checked {r['date']}", fontsize=8.5, color="#6b6355", va="center")
    s = r.get("scar") or {}
    if r.get("status") == "SCAR" and s.get("area_ha"):
        ax.text(1, 0.15, f"{s['area_ha']:.1f} ha · {s['distance_km']:.0f} km upstream",
                fontsize=10, weight="bold", va="center", ha="right", color=ORANGE)
    ax.add_patch(Rectangle((0, 0.42), 1, 0.022, transform=ax.transAxes, facecolor=GOLD,
                           edgecolor="none", clip_on=False))
    n_refined, muse_quote = _meta_info(r)
    strip = [f"SAM 3.1 refined {n_refined} scars"] if n_refined else []
    if muse_quote:
        strip.append(muse_quote)
    if strip:
        ax.text(0, 0.58, "   ·   ".join(strip), fontsize=8.5, weight="bold", color=ORANGE, va="center")

    panels = [("Your clip", r.get("ground", {}).get("still") if r.get("ground") else None, None)]
    out_method = str(s.get("outline_method", ""))
    now_title = f"Now ({_period(C.AFTER)})"
    if "sam" in out_method.lower() or s.get("sam_boxes"):
        now_title = f"Now · SAM 3.1 ({_period(C.AFTER)})"
    panels += [(f"Before ({_period(C.BEFORE)})", s.get("rgb_before"), None),
               (now_title, s.get("rgb_after"), s.get("mask"))]
    for i, (title, img, mask) in enumerate(panels):
        a = fig.add_subplot(gs[1, i]); a.set_xticks([]); a.set_yticks([])
        for sp in a.spines.values():
            sp.set_color(RULE_EDGE)
        a.set_title(title, fontsize=8.5, color=FOREST, weight="bold", loc="left")
        if img is None:
            a.text(0.5, 0.5, "no clip" if i == 0 else "no image", ha="center", va="center",
                   color="#b0a892", fontsize=8, transform=a.transAxes)
            continue
        a.imshow(img)
        if i == 0 and (r.get("ground") or {}).get("credit"):
            a.set_xlabel(textwrap.fill(r["ground"]["credit"], 34), fontsize=5.5, color="#8d8574")
        if mask is not None and mask.any():
            a.contour(mask.astype(float), levels=[0.5], colors=[CONTOUR_COLOR], linewidths=1.2)
        if i == 2:
            for box in (s.get("sam_boxes") or []):
                l, t, rr, b = box
                a.add_patch(Rectangle((l, t), rr - l, b - t, fill=False,
                                      edgecolor="#ff7a00", linewidth=1.5))

    ax = fig.add_subplot(gs[2, :]); ax.axis("off")
    for i, (key, name) in enumerate(BADGES):
        v = r["checks"].get(key, {}).get("pass")
        face, sym_col, label_col = _BADGES_STYLE.get(v, _BADGES_STYLE[None])
        x, y = (i % 3) / 3, 0.75 - (i // 3) * 0.5
        ax.add_patch(plt.Rectangle((x + 0.005, y - 0.2), 0.32, 0.38, transform=ax.transAxes,
                                   facecolor=face, edgecolor=GOLD if v else RULE_EDGE, lw=1.4))
        ax.text(x + 0.03, y, f"{_badge_symbol(v)}  {key}  {name}", fontsize=8.5,
                color=label_col, weight="bold" if v else "normal",
                va="center", transform=ax.transAxes)

    ax = fig.add_subplot(gs[3, :]); ax.axis("off")
    body = "\n\n".join(textwrap.fill(t, 78) for t in headline(r))
    ax.text(0, 1, body, fontsize=9.5, va="top", linespacing=1.4, color=FOREST)
    ax.text(0, 0.0, textwrap.fill(
        "Badges show which independent checks agree; they are not a probability. Sources: Sentinel-2 (ESA/Copernicus), "
        "SAM 3.1 (Meta), HydroBASINS, RADD (WUR/GFW), Hansen GFC, WRI/Google DeepMind drivers, WDPA, JRC water. "
        "Location shown to ~1 km. No personal data kept.", 100), fontsize=6, color=MUTED_FOOT, va="bottom")
    if r.get("scar") or r.get("ground") or r.get("meta"):
        ax.text(1, 0.155, "Powered by Meta SAM 3.1 + Muse Spark", fontsize=8.5, weight="bold",
                color=ORANGE, va="bottom", ha="right")
    fig.add_artist(Rectangle((0, 0), 1, 1, transform=fig.transFigure, fill=False,
                             edgecolor=GOLD, linewidth=8, clip_on=False))
    fig.savefig(path, facecolor=CREAM)
    plt.close(fig)
    return path
