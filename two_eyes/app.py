"""Minimal web UI (Gradio). In Colab: from two_eyes.app import launch; launch()"""
from . import pipeline

DEMO_BRIDGES = {
    "Birim, N4 bridge (6.28442, -0.46118)": (6.28442, -0.46118),
    "Birim, N6 bridge (6.38624, -0.55278)": (6.38624, -0.55278),
    "Densu, Akwadum bridge (6.111737, -0.343074)": (6.111737, -0.343074),
}


STANDIN_CREDIT = "Stand-in clip: Pra River from Beposo bridge, 2014. Wikimedia Commons, CC BY-SA 3.0"


def _run(bridge, lat, lon, clip):
    if bridge in DEMO_BRIDGES:
        lat, lon = DEMO_BRIDGES[bridge]
        name = bridge.split(" (")[0]
    else:
        name = "Custom point"
    logs = []
    credit = STANDIN_CREDIT if clip and "pra_beposo" in str(clip) else None
    r = pipeline.run(float(lat), float(lon), name=name, clip=clip, clip_credit=credit, log=lambda *a: logs.append(" ".join(map(str, a))))
    return r["card_png"], r["share_text"], "\n".join(logs), pipeline.public(r)


def launch(share=True, warm=True):
    import threading
    import gradio as gr
    if warm:   # pre-compute the satellite part for the demo bridges in the background
        threading.Thread(target=pipeline.warm, args=(list(DEMO_BRIDGES.values()),), daemon=True).start()
    with gr.Blocks(title="Two Eyes") as ui:
        gr.Markdown("# Two Eyes\nFilm a muddy river from a bridge. We look upstream from space.")
        with gr.Row():
            with gr.Column():
                bridge = gr.Dropdown(list(DEMO_BRIDGES) + ["Custom point"], value=list(DEMO_BRIDGES)[0], label="Bridge")
                lat = gr.Number(label="Latitude (custom)", value=6.28442)
                lon = gr.Number(label="Longitude (custom)", value=-0.46118)
                clip = gr.Video(label="Clip of the river (optional, ~10 s)")
                go = gr.Button("Check upstream", variant="primary")
            with gr.Column():
                img = gr.Image(label="Evidence card", type="filepath")
                txt = gr.Textbox(label="WhatsApp message", lines=4)
                log = gr.Textbox(label="What the checks did", lines=8)
                js = gr.JSON(label="Full report")
        go.click(_run, [bridge, lat, lon, clip], [img, txt, log, js])
    ui.launch(share=share, debug=False)
