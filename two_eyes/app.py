"""Web UI (Gradio), in the campaign poster look: forest green, cream, gold, orange.

Local:   DEMO_MODE=1 python -m two_eyes.app        (offline demo, no API keys needed)
Colab:   from two_eyes.app import launch; launch(share=True)
"""
import base64
import os

from . import card, demo, pipeline

DEMO_BRIDGES = {
    "Birim, N4 bridge (6.28442, -0.46118)": (6.28442, -0.46118),
    "Birim, N6 bridge (6.38624, -0.55278)": (6.38624, -0.55278),
    "Densu, Akwadum bridge (6.111737, -0.343074)": (6.111737, -0.343074),
}

STANDIN_CREDIT = "Stand-in clip: Pra River from Beposo bridge, 2014. Wikimedia Commons, CC BY-SA 3.0"

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

CSS = """
body {background:#0f2a1a !important;}
.gradio-container {
  background:#0f2a1a !important; color:#fff8ea !important; max-width:1180px !important;
  font-family:'DejaVu Sans', Arial, sans-serif !important; padding-bottom:0 !important;
}
.gradio-container h1, .gradio-container h2, .gradio-container h3 {color:#fff8ea;}
.gradio-container label {color:#fff8ea !important; font-weight:700; background:transparent !important;}
.gradio-container label span, .gradio-container label {color:#fff8ea !important;}
.gradio-container .info {color:#cfe0d2 !important;}

/* panels and inputs on card green */
.gradio-container .form, .gradio-container .block {
  background-color:#163d26 !important; border-color:#275b39 !important;
}
.gradio-container textarea, .gradio-container input, .gradio-container select {
  background:#0c2416 !important; color:#fff8ea !important; border:1px solid #2c5c3f !important;
  font-size:15px !important;
}
.gradio-container textarea::placeholder, .gradio-container input::placeholder {color:#7fa28c !important;}
.gradio-container ul.options, .gradio-container ul[class*='option'] {
  background:#163d26 !important; border-color:#2c5c3f !important;}
.gradio-container ul.options li, .gradio-container ul[class*='option'] li {color:#fff8ea !important;}
.gradio-container ul.options li:hover, .gradio-container ul[class*='option'] li:hover {background:#1e4f31 !important;}
.gradio-container .dropdown-arrow {color:#ffd600 !important;}

/* big orange primary button, large tap target */
.gradio-container button.primary {
  background:#ff7a00 !important; color:#0f2a1a !important; border:none !important;
  border-radius:16px !important; font-weight:800 !important; min-height:52px !important;
  font-size:1.08rem !important; box-shadow:0 4px 0 rgba(0,0,0,.3) !important; letter-spacing:.3px;
}
.gradio-container button.primary:hover {background:#ff8f24 !important;}
.gradio-container button.secondary, .gradio-container button:not(.primary) {
  background:#163d26 !important; color:#fff8ea !important; border:1px solid #2c5c3f !important;
  border-radius:12px !important; min-height:40px;
}

/* outputs */
.gradio-container pre, .gradio-container [class*='json'] ,
.gradio-container [class*='json'] * {
  background:#0c2416 !important; color:#dbeadd !important;
}
.gradio-container img, .gradio-container video {border-radius:14px;}
.gradio-container .status {color:#ffd600 !important;}

/* textareas read back on green */
.gradio-container textarea {min-height:88px;}

/* hero */
.hero {display:grid; grid-template-columns:1.2fr .8fr; gap:30px; align-items:center;
       padding:36px 6px 22px;}
.hero h1 {font-size:clamp(54px,9vw,104px); font-weight:900; line-height:.95;
          letter-spacing:-2px; margin:14px 0 10px; color:#fff8ea;}
.hero h1 .eyes {color:#ff7a00;}
.tag {display:inline-block; background:#ffd600; color:#0f2a1a; font-weight:900;
      padding:7px 16px; border-radius:40px; font-size:clamp(11px,1.6vw,14px); letter-spacing:2px;}
.sub {font-size:clamp(17px,2.3vw,25px); font-weight:700; line-height:1.3; color:#fff8ea;}
.small {opacity:.82; font-size:clamp(13px,1.7vw,15px); line-height:1.55; margin-top:10px; color:#dceada;}
.hero-img {width:100%; border-radius:22px; border:5px solid #ffd600;
           box-shadow:0 10px 30px rgba(0,0,0,.35); display:block;}
.hero-cap {font-size:12.5px; opacity:.75; color:#dbeadd; margin-top:8px; text-align:center;}

/* demo banner */
#demo-banner {background:#ffd600; color:#0f2a1a; font-weight:800; border-radius:14px;
              padding:12px 18px; font-size:15px; line-height:1.4; box-shadow:0 3px 0 rgba(0,0,0,.28);}

/* footer note */
#footnote {border-top:2px solid #1f5233; margin-top:30px; padding:18px 4px 26px;
           font-size:13px; opacity:.72; line-height:1.55; color:#fff8ea;}

/* mobile-first: stack the two columns on small screens */
@media (max-width:760px) {
  .hero {grid-template-columns:1fr; gap:18px; padding:22px 4px 14px;}
  #row-main {display:flex !important; flex-wrap:wrap !important; row-gap:16px;}
  #col-controls, #col-outputs {min-width:100% !important; width:100% !important; max-width:100% !important;}
  .gradio-container button.primary {min-height:56px;}
}

/* hide the "Built with Gradio" attribution / footer */
footer, .gradio-footer, .footer, .gradio-container footer {display:none !important;
  visibility:hidden !important; height:0 !important; overflow:hidden !important;}
"""

THEME = None  # set in launch(); gradio import stays lazy so tests can import this module cheaply


def _resolve(bridge, lat, lon):
    """Coordinates to check. Typed lat/lon that disagree with the chosen bridge win (custom point)."""
    if bridge in DEMO_BRIDGES:
        blat, blon = DEMO_BRIDGES[bridge]
        if lat is not None and lon is not None and abs(lat - blat) < 1e-4 and abs(lon - blon) < 1e-4:
            return float(lat), float(lon), bridge.split(" (")[0]
    if lat is None or lon is None:
        return None
    return float(lat), float(lon), "Custom point"


def _run(bridge, lat, lon, clip):
    logs = []
    def log(*a):
        logs.append(" ".join(map(str, a)))
    try:
        point = _resolve(bridge, lat, lon)
        if point is None:
            raise ValueError("Type both coordinates for a custom point, or pick a bridge from the list.")
        lat_f, lon_f, name = point
        credit = STANDIN_CREDIT if clip and "pra_beposo" in str(clip) else None
        r = pipeline.run(lat_f, lon_f, name=name, clip=clip, clip_credit=credit, log=log)
        wa = card.whatsapp_url(r["share_text"])
        return r["card_png"], r["share_text"], "\n".join(logs), pipeline.public(r), _share_html(wa), r["card_png"]
    except Exception as ex:
        log(f"Something failed: {type(ex).__name__}: {ex}")
        log("Offline? Set DEMO_MODE=1 (or just unset MODEL_API_KEY) to see the demo result.")
        return None, "", "\n".join(logs), {}, "", None


def _share_html(wa_url):
    """Two big tap targets: WhatsApp share + card download (mobile-friendly, orange/gold)."""
    if not wa_url:
        return ""
    style = ("display:inline-flex;align-items:center;gap:8px;padding:13px 22px;border-radius:14px;"
             "font-weight:800;font-size:1.02rem;margin:6px 10px 6px 0;color:#0f2a1a;"
             "text-decoration:none;box-shadow:0 3px 0 rgba(0,0,0,.3);")
    return (f'<div class="share-row">'
            f'<a href="{wa_url}" target="_blank" rel="noopener" '
            f'style="{style}background:#ff7a00;">🟢&nbsp;Share on WhatsApp</a>'
            f'<span style="{style}background:#ffd600;">⬇&nbsp;Download the card above</span>'
            f'</div>')


def _chip_html():
    """Gold Meta-visibility chips: what SAM 3.1 did + the Muse Spark line when present."""
    try:
        r = demo.demo_report()
    except Exception:
        return ""
    meta = r.get("meta") or {}
    chips = []
    chip_css = ("display:inline-block;background:#ffd600;color:#0f2a1a;font-weight:800;"
                "border-radius:40px;padding:6px 14px;font-size:13.5px;margin:0 10px 10px 0;")
    apple_css = chip_css + "background:#ffe27a;opacity:.95;"
    if meta.get("sam_refined"):
        chips.append(f'<span class="chip" style="{chip_css}">SAM 3.1 refined {meta["sam_refined"]} scars</span>')
    muse = meta.get("muse_quote") or (r.get("ground") or {}).get("label")
    if muse:
        chips.append(f'<span class="chip" style="{apple_css}">Muse Spark: &ldquo;{muse}&rdquo;</span>')
    if not chips:
        return ""
    return '<div style="margin-top:6px">' + "".join(chips) + "</div>"


def launch(share=False, warm=True):
    import threading
    import gradio as gr

    def _fill(bridge, lat, lon):
        """Bridge picks fill the coordinate boxes; picking 'Custom point' leaves them as typed."""
        if bridge in DEMO_BRIDGES:
            return DEMO_BRIDGES[bridge]
        if hasattr(gr, "skip"):
            return gr.skip(), gr.skip()
        return gr.update(), gr.update()

    def _warm_safe(bridges):
        try:
            pipeline.warm(bridges, log=lambda *a: None)
        except Exception as ex:
            print(f"[two_eyes] warm skipped: {type(ex).__name__}: {ex}")

    if warm:
        threading.Thread(target=_warm_safe, args=(list(DEMO_BRIDGES.values()),), daemon=True).start()

    with open(os.path.join(ASSETS, "hero_mask.jpg"), "rb") as f:
        hero_b64 = base64.b64encode(f.read()).decode()

    hero = (
        '<div class="hero">'
        '<div>'
        '<span class="tag">META AI HACKATHON · GHANA</span>'
        '<h1>TWO <span class="eyes">EYES</span></h1>'
        '<div class="sub">Your phone sees the muddy river. The satellite sees the scar upstream.</div>'
        '<div class="small">Film a muddy river from a public bridge. We trace the river upstream for new '
        'forest clearings in Sentinel-2 imagery — often galamsey — cross-check them against independent '
        'datasets, and return a dated, anonymous evidence card you can share on WhatsApp. '
        'SAM 3.1 (Meta Model API) + Sentinel-2 (Earth Engine).</div>'
        '</div>'
        '<div>'
        f'<img class="hero-img" src="data:image/jpeg;base64,{hero_b64}" alt="Muddy river seen from a bridge, '
        'river water outlined by SAM 3.1">'
        '<div class="hero-cap">SAM 3.1 finds the river water in your clip.</div>'
        '</div>'
        '</div>'
    )
    banner = ('<div id="demo-banner">Demo mode — showing a cached Atewa / Birim result. '
              'No Earth Engine or Meta API calls.</div><div style="height:16px"></div>'
              if demo.is_demo_mode() else '')
    banner += _chip_html()

    theme = gr.themes.Base(primary_hue="orange", neutral_hue="stone")   # page look is set by CSS below
    with gr.Blocks(title="Two Eyes — check upstream") as ui:
        gr.HTML(hero + banner)
        with gr.Row(elem_id="row-main"):
            with gr.Column(elem_id="col-controls"):
                bridge = gr.Dropdown(list(DEMO_BRIDGES) + ["Custom point"],
                                     value=list(DEMO_BRIDGES)[0], label="Bridge")
                lat = gr.Number(label="Latitude (custom)", value=6.28442)
                lon = gr.Number(label="Longitude (custom)", value=-0.46118)
                clip = gr.Video(label="Clip of the river (optional, ~10 s)")
                go = gr.Button("Check upstream", variant="primary")
            with gr.Column(elem_id="col-outputs"):
                img = gr.Image(label="Evidence card", type="filepath")
                txt = gr.Textbox(label="WhatsApp message", lines=4)
                share = gr.HTML(label="Share")
                card_file = gr.File(label="Download evidence card")
                log = gr.Textbox(label="What the checks did", lines=8)
                js = gr.JSON(label="Full report")
        footer = ('<div id="footnote">Safety: film only from public places, never at mining sites. '
                  'Clips are re-encoded with GPS metadata stripped; locations on the card are rounded to '
                  'about 1 km; no personal data is kept.<br>Sources: Sentinel-2 (ESA/Copernicus), '
                  'HydroBASINS (WWF), RADD (WUR/GFW), Hansen GFC (UMD), WDPA (UNEP-WCMC), JRC water. '
                  'Demo imagery: Pra River, Wikimedia Commons, CC BY-SA 3.0.</div>')
        gr.HTML(footer)
        go.click(_run, [bridge, lat, lon, clip], [img, txt, log, js, share, card_file])
        bridge.change(_fill, [bridge, lat, lon], [lat, lon])
    # Gradio 6: css and theme live in launch(), not Blocks
    ui.launch(share=share, debug=False, css=CSS, theme=theme)


if __name__ == "__main__":
    launch()
