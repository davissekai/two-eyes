"""Web UI (Gradio) in the Field Evidence look: graphite, bone, silt; machine lime accents.

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

# The bundled bridge/hero imagery is the Goldenwabbit photo, not the old Pra/Beposo clip.
HERO_CREDIT = "Photo: Goldenwabbit, Wikimedia Commons, CC BY-SA 4.0"

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Field Evidence tokens (atelier brand kit, direction A)
BASE = "#15130F"     # graphite
PANEL = "#1c1914"
PANEL2 = "#221e18"
BONE = "#F2EDE4"
SILT = "#C9A27E"
LIME = "#D4FF3A"     # machine accent: chips, badges, emphasis only
WA = "#25D366"       # WhatsApp share button only

RULER = "rgba(242,237,228,.18)"

_EYES_MARK = (
    '<svg viewBox="0 0 220 110" width="150" height="75" xmlns="http://www.w3.org/2000/svg" '
    'aria-label="Two Eyes mark">'
    '<circle cx="55" cy="55" r="44" fill="none" stroke="#F2EDE4" stroke-width="5"/>'
    '<circle cx="55" cy="55" r="11" fill="#C9A27E"/>'
    '<circle cx="165" cy="55" r="44" fill="none" stroke="#D4FF3A" stroke-width="5"/>'
    '<g stroke="#D4FF3A" stroke-width="4">'
    '<line x1="165" y1="3" x2="165" y2="17"/><line x1="165" y1="93" x2="165" y2="107"/>'
    '<line x1="113" y1="55" x2="127" y2="55"/><line x1="203" y1="55" x2="217" y2="55"/></g>'
    '<circle cx="165" cy="55" r="11" fill="#D4FF3A"/>'
    '<path d="M66 55 C 90 30, 110 80, 154 55" fill="none" stroke="#D4FF3A" stroke-width="3" '
    'stroke-dasharray="6 6"/></svg>'
)


def _font_faces(css):
    """Append @font-face rules with the bundled fonts re-encoded as data URIs (loads offline)."""
    faces = [
        ("IS", os.path.join(ASSETS, "fonts", "InstrumentSerif-Regular.ttf"), "normal", ""),
        ("IS", os.path.join(ASSETS, "fonts", "InstrumentSerif-Italic.ttf"), "italic", ""),
        ("G", os.path.join(ASSETS, "fonts", "Geist-VariableFont_wght.ttf"), "normal", ";font-weight:100 900"),
        ("JB", os.path.join(ASSETS, "fonts", "JetBrainsMono-VariableFont_wght.ttf"), "normal", ";font-weight:100 800"),
    ]
    for fam, path, style, weight in faces:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        css += (f"@font-face{{font-family:{fam};font-style:{style}{weight};"
                f"src:url(data:font/ttf;base64,{b64})}}")
    return css


def build_css():
    css = f"""
body {{background:{BASE} !important;}}
.gradio-container {{
  background:{BASE} !important; color:{BONE} !important; max-width:1180px !important;
  font-family:G,'Geist',Arial,sans-serif !important; padding-bottom:0 !important;
}}
.gradio-container h1, .gradio-container h2, .gradio-container h3 {{color:{BONE};}}
.gradio-container label {{color:{SILT} !important; font-weight:600; background:transparent !important;}}
.gradio-container label span {{color:{SILT} !important;}}
.gradio-container .info {{color:{SILT} !important;}}

/* graphite panels, subtle bone rules */
.gradio-container .form, .gradio-container .block {{
  background-color:{PANEL} !important; border-color:{RULER} !important; border-radius:14px !important;
}}
.gradio-container textarea, .gradio-container input, .gradio-container select {{
  background:{PANEL2} !important; color:{BONE} !important; border:1px solid {RULER} !important;
  font-size:15px !important; border-radius:10px !important;
}}
.gradio-container textarea::placeholder, .gradio-container input::placeholder {{
  color:{SILT} !important; opacity:.65;}}
.gradio-container ul.options, .gradio-container ul[class*='option'] {{
  background:{PANEL2} !important; border-color:{RULER} !important;}}
.gradio-container ul.options li, .gradio-container ul[class*='option'] li {{color:{BONE} !important;}}
.gradio-container ul.options li:hover, .gradio-container ul[class*='option'] li:hover {{
  background:{PANEL} !important;}}
.gradio-container .dropdown-arrow {{color:{LIME} !important;}}

/* primary button: bone on graphite, large tap target */
.gradio-container button.primary {{
  background:{BONE} !important; color:{BASE} !important; border:none !important;
  border-radius:12px !important; font-weight:700 !important; min-height:54px !important;
  font-size:1.06rem !important; letter-spacing:.02em;
}}
.gradio-container button.primary:hover {{background:#ffffff !important;}}
.gradio-container button.secondary, .gradio-container button:not(.primary) {{
  background:{PANEL} !important; color:{BONE} !important; border:1px solid {RULER} !important;
  border-radius:10px !important; min-height:42px;
}}

/* outputs */
.gradio-container pre, .gradio-container [class*='json'], .gradio-container [class*='json'] * {{
  background:{PANEL2} !important; color:{BONE} !important;
}}
.gradio-container img, .gradio-container video {{
  border-radius:14px; border:1px solid {RULER};}}
.gradio-container .status {{color:{LIME} !important;}}
.gradio-container textarea {{min-height:88px;}}

/* hero */
.hero {{display:grid; grid-template-columns:1.15fr .85fr; gap:34px; align-items:center;
       padding:40px 6px 26px;}}
.hero-mark {{margin-bottom:6px;}}
.hero h1 {{font-family:IS,'Instrument Serif',serif; font-weight:400;
          font-size:clamp(58px,9vw,108px); line-height:.92; letter-spacing:-.02em;
          margin:10px 0 14px; color:{BONE};}}
.hero .tagline {{font-family:IS,'Instrument Serif',serif; font-size:clamp(19px,2.6vw,28px);
                font-weight:400; color:{BONE};}}
.hero .tagline i {{color:{LIME}; font-style:italic;}}
.sub {{font-size:clamp(15px,2vw,19px); font-weight:500; line-height:1.45; color:{BONE}; margin-top:14px;}}
.small {{font-size:clamp(13px,1.7vw,15px); line-height:1.55; margin-top:10px; color:{SILT};}}
.hero-img {{width:100%; border-radius:16px; border:1px solid {RULER}; display:block;}}
.hero-cap {{font-family:JB,'JetBrains Mono',monospace; letter-spacing:.04em; font-size:11px;
           color:{SILT}; margin-top:8px; text-align:center; opacity:.85;}}

/* machine-lime meta chips (mono, uppercase, tracking) */
.chip-row {{margin-top:10px;}}
.chip {{display:inline-block;border:1.5px solid {LIME};color:{LIME};
       font-family:JB,'JetBrains Mono',monospace;font-weight:500;
       text-transform:uppercase;letter-spacing:.08em;
       border-radius:99px;padding:6px 13px;font-size:12px;margin:0 10px 10px 0;
       background:rgba(21,19,15,.55);}}

/* demo banner: graphite panel with lime rule */
#demo-banner {{border:1.5px solid {LIME}; color:{BONE}; border-radius:12px;
              padding:12px 16px; font-size:14px; line-height:1.5; background:{PANEL};}}
#demo-banner .mono {{font-family:JB,'JetBrains Mono',monospace; letter-spacing:.08em;
                    text-transform:uppercase; color:{LIME};}}

/* footer note */
#footnote {{border-top:1px solid {RULER}; margin-top:30px; padding:18px 4px 26px;
           font-size:12.5px; line-height:1.55; color:{SILT};}}

/* mobile-first: stack the columns on small screens (e.g. 390px phones) */
@media (max-width:760px) {{
  .hero {{grid-template-columns:1fr; gap:18px; padding:24px 4px 14px;}}
  #row-main {{display:flex !important; flex-wrap:wrap !important; row-gap:16px;}}
  #col-controls, #col-outputs {{
    min-width:100% !important; width:100% !important; max-width:100% !important;}}
  .gradio-container button.primary {{min-height:58px;}}
}}

/* hide the "Built with Gradio" attribution / footer */
footer, .gradio-footer, .footer, .gradio-container footer {{display:none !important;
  visibility:hidden !important; height:0 !important; overflow:hidden !important;}}
"""
    return _font_faces(css)


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
        credit = HERO_CREDIT if clip else None
        r = pipeline.run(lat_f, lon_f, name=name, clip=clip, clip_credit=credit, log=log)
        wa = card.whatsapp_url(r["share_text"])
        return r["card_png"], r["share_text"], "\n".join(logs), pipeline.public(r), _share_html(wa), r["card_png"]
    except Exception as ex:
        log(f"Something failed: {type(ex).__name__}: {ex}")
        log("Offline? Set DEMO_MODE=1 (or just unset MODEL_API_KEY) to see the demo result.")
        return None, "", "\n".join(logs), {}, "", None


def _share_html(wa_url):
    """Two big tap targets: WhatsApp green share, lime-outline download (mobile-first)."""
    if not wa_url:
        return ""
    style = ("display:inline-flex;align-items:center;gap:8px;padding:14px 22px;border-radius:12px;"
             "font-weight:700;font-size:1.02rem;margin:8px 10px 8px 0;")
    wa_style = f"{style}background:{WA};color:#0b2e17;border:none;text-decoration:none;"
    dl_style = f"{style}background:transparent;color:{LIME};border:1.5px solid {LIME};"
    return (f'<div class="share-row">'
            f'<a href="{wa_url}" target="_blank" rel="noopener" '
            f'style="{wa_style}">Share on WhatsApp</a>'
            f'<span style="{dl_style}">Download the card</span>'
            f'</div>')


def _chip_html():
    """Machine-lime mono chips: what SAM 3.1 did + the Muse Spark line when present."""
    try:
        r = demo.demo_report()
    except Exception:
        return ""
    meta = r.get("meta") or {}
    chips = []
    if meta.get("sam_refined"):
        chips.append(f'<span class="chip">SAM 3.1 refined {meta["sam_refined"]} scars</span>')
    muse = meta.get("muse_quote") or (r.get("ground") or {}).get("label")
    if muse:
        chips.append(f'<span class="chip">Muse Spark: &ldquo;{muse}&rdquo;</span>')
    if not chips:
        return ""
    return '<div class="chip-row">' + "".join(chips) + "</div>"


def _hero_html():
    with open(os.path.join(ASSETS, "bridge_brand.jpg"), "rb") as f:
        hero_b64 = base64.b64encode(f.read()).decode()
    return (
        '<div class="hero">'
        '<div>'
        f'<div class="hero-mark">{_EYES_MARK}</div>'
        '<h1>Two Eyes</h1>'
        '<div class="tagline">Film the river. <i>Find the source.</i></div>'
        '<div class="sub">Your phone sees the muddy river. The satellite sees the scar upstream.</div>'
        '<div class="small">Film a muddy river from a public bridge. We trace the river upstream for new '
        'forest clearings in Sentinel-2 imagery — often galamsey — cross-check them against independent '
        'datasets, and return a dated, anonymous evidence card you can share on WhatsApp. '
        'SAM 3.1 (Meta Model API) + Sentinel-2 (Earth Engine).</div>'
        '</div>'
        '<div>'
        f'<img class="hero-img" src="data:image/jpeg;base64,{hero_b64}" alt="Bridge over a brown river">'
        f'<div class="hero-cap">{HERO_CREDIT}</div>'
        '</div>'
        '</div>'
    )


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

    banner = ''
    if demo.is_demo_mode():
        banner = ('<div id="demo-banner"><span class="mono">Demo mode</span><br>'
                  'Cached Birim N4 bridge result from the recorded run of 28 Oct 2026. '
                  'No Earth Engine and no Meta API calls are made.</div><div style="height:16px"></div>')
    banner += _chip_html()

    theme = gr.themes.Base(primary_hue="neutral", neutral_hue="neutral")   # page look is set by CSS below
    with gr.Blocks(title="Two Eyes — check upstream") as ui:
        gr.HTML(_hero_html() + banner)
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
                  'about 1 km; no personal data is kept.<br>'
                  'Imagery: bridge photo — Photo: Goldenwabbit, Wikimedia Commons, CC BY-SA 4.0. '
                  'Satellite: Contains modified Copernicus Sentinel data 2023, 2026. '
                  'Sources: Sentinel-2 (ESA/Copernicus), HydroBASINS (WWF), RADD (WUR/GFW), '
                  'Hansen GFC (UMD), WDPA (UNEP-WCMC), JRC water.</div>')
        gr.HTML(footer)
        go.click(_run, [bridge, lat, lon, clip], [img, txt, log, js, share, card_file])
        bridge.change(_fill, [bridge, lat, lon], [lat, lon])
    # Gradio 6: css and theme live in launch(), not Blocks
    ui.launch(share=share, debug=False, css=build_css(), theme=theme)


if __name__ == "__main__":
    launch()
