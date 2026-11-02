"""The page's look: Field Evidence light mode (bone page, graphite type, lime only for machine sight).

Tokens and CSS for the Gradio app. Gradio's own widgets are restyled to match; the case-file
sections (case_file.py, share.py, readout.py) are plain HTML styled here.
"""
import base64
import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

GRAPHITE = "#15130F"
BONE = "#F2EDE4"          # page background
PANEL = "#FAF7F1"         # lighter bone panels
PANEL2 = "#E8E1D5"        # darker bone wells
SILT = "#C9A27E"          # rules + borders ONLY (fails WCAG AA as text on bone)
LATERITE = "#9C5A34"      # secondary text (AA on bone)
LIME = "#D4FF3A"          # machine accent only: on graphite chips or over imagery
WA = "#25D366"            # WhatsApp share only
RULER = "rgba(21,19,15,.20)"


def _font_faces():
    """@font-face rules with the bundled fonts as data URIs, so the page looks right offline."""
    faces = [
        ("IS", "InstrumentSerif-Regular.ttf", "normal", ""),
        ("IS", "InstrumentSerif-Italic.ttf", "italic", ""),
        ("G", "Geist-VariableFont_wght.ttf", "normal", ";font-weight:100 900"),
        ("JB", "JetBrainsMono-VariableFont_wght.ttf", "normal", ";font-weight:100 800"),
    ]
    css = ""
    for fam, fname, style, weight in faces:
        with open(os.path.join(ASSETS, "fonts", fname), "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        css += f"@font-face{{font-family:{fam};font-style:{style}{weight};src:url(data:font/ttf;base64,{b64})}}"
    return css


_GRADIO = """
body {background:BONE !important;}
/* belt and braces for the light-only brand: Gradio's text colours come from these variables */
.gradio-container, .dark .gradio-container, body.dark {--body-text-color:GRAPHITE; --body-text-color-subdued:LATERITE;
  --block-title-text-color:LATERITE; --block-label-text-color:LATERITE; --background-fill-primary:PANEL;
  --background-fill-secondary:BONE; --block-background-fill:PANEL; --input-background-fill:PANEL;
  --border-color-primary:RULER; color-scheme:light;}
.gradio-container .plain, .gradio-container .prose {color:GRAPHITE !important;}
.gradio-container {background:BONE !important; color:GRAPHITE !important; max-width:1120px !important;
  font-family:G,'Geist',Arial,sans-serif !important; padding-bottom:0 !important;}
.gradio-container h1, .gradio-container h2, .gradio-container h3 {color:GRAPHITE;}
.gradio-container label {color:LATERITE !important; font-weight:600; background:transparent !important;}
.gradio-container label span, .gradio-container .info {color:LATERITE !important;}
/* dropdown labels use block-info, which the label rule above misses (Gradio default is near-white) */
.gradio-container [data-testid="block-info"] {color:LATERITE !important; font-weight:600;}
.gradio-container .form, .gradio-container .block {background-color:PANEL !important;
  border-color:RULER !important; border-radius:14px !important;}
.gradio-container textarea, .gradio-container input, .gradio-container select,
.gradio-container .wrap input, .gradio-container .wrap .secondary-wrap,
.gradio-container [data-testid="dropdown"], .gradio-container [data-testid="dropdown"] input,
.gradio-container .container > .wrap, .gradio-container .input-container,
.gradio-container .dropdown-container, .gradio-container .wrap.full {
  background:PANEL !important; color:GRAPHITE !important; border:1px solid RULER !important;
  font-size:15px !important; border-radius:10px !important; box-shadow:none !important;}
.gradio-container .scrub input, .gradio-container .clip input {border:none !important; background:transparent !important;}
.gradio-container textarea::placeholder, .gradio-container input::placeholder {color:LATERITE !important; opacity:.75;}
.gradio-container ul.options, .gradio-container [role="listbox"] {background:PANEL !important;
  border:1px solid RULER !important; color:GRAPHITE !important;}
.gradio-container ul.options li, .gradio-container [role="option"] {color:GRAPHITE !important; background:PANEL !important;}
.gradio-container ul.options li:hover, .gradio-container [role="option"]:hover {background:PANEL2 !important;}
.gradio-container .dropdown-arrow, .gradio-container .icon-wrap {color:GRAPHITE !important;}
.gradio-container button.primary {background:GRAPHITE !important; color:BONE !important; border:none !important;
  border-radius:12px !important; font-weight:700 !important; min-height:56px !important; font-size:1.06rem !important;}
.gradio-container button.primary:hover {background:#000 !important;}
.gradio-container button.secondary, .gradio-container button:not(.primary) {background:PANEL !important;
  color:GRAPHITE !important; border:1px solid RULER !important; border-radius:10px !important; min-height:44px;}
#locate {border-style:dashed !important; font-weight:600 !important;}
.gradio-container pre, .gradio-container [class*='json'], .gradio-container [class*='json'] * {
  background:PANEL2 !important; color:GRAPHITE !important;}
.gradio-container video {border-radius:14px;}
.gradio-container .plain {background:transparent !important; border:none !important; box-shadow:none !important;
  padding:0 !important;}
#custom-fields {border:1px solid RULER !important; background:PANEL !important; box-shadow:none !important;
  border-radius:14px !important;}
footer, .gradio-footer, .footer, .gradio-container footer {display:none !important;}
"""

_PAGE = """
.mono {font-family:JB,'JetBrains Mono',monospace; font-size:12px; letter-spacing:.06em; text-transform:uppercase;}
.label {font-weight:600; color:GRAPHITE;}
.hint {font-size:13.5px; color:LATERITE; margin:0;}
.panel {background:PANEL; border:1px solid RULER; border-radius:16px; padding:20px; min-width:0;}
.section-head {display:flex; justify-content:space-between; align-items:end; gap:12px; flex-wrap:wrap;
  border-bottom:1px solid RULER; padding:0 2px 10px; margin-top:28px;}
.section-head h2 {font-family:IS,'Instrument Serif',serif; font-weight:400; font-size:clamp(30px,4.4vw,40px);
  line-height:1.05; margin:0; color:GRAPHITE;}
.section-head .mono {color:LATERITE;}
.tag {position:absolute; font:700 11px/1 JB,monospace; letter-spacing:.08em; background:LIME; color:GRAPHITE;
  padding:6px 8px; text-transform:uppercase;}

/* hero */
.hero {display:grid; grid-template-columns:1fr 1.05fr; gap:32px; align-items:center; padding:28px 4px 8px;}
.hero h1 {font-family:IS,'Instrument Serif',serif; font-weight:400; font-size:clamp(52px,8vw,96px);
  line-height:.92; letter-spacing:-.025em; margin:10px 0 0; color:GRAPHITE;}
.hero h1 em {display:block; color:LATERITE;}
.lede {font-size:19px; line-height:1.45; margin-top:16px; max-width:34ch;}
.steps {list-style:none; margin:22px 0 0; padding:0; display:grid; gap:10px; counter-reset:s;}
.steps li {display:grid; grid-template-columns:34px 1fr; gap:12px; counter-increment:s;}
.steps li::before {content:counter(s); font:400 24px/1 IS,serif; border:1.5px solid GRAPHITE; border-radius:99px;
  width:34px; height:34px; display:grid; place-items:center; padding-top:3px;}
.steps b {display:block;} .steps small {font-size:14px; color:LATERITE;}
.safe {margin-top:16px; display:flex; flex-wrap:wrap; gap:8px;}
.safe span {font-size:13px; border:1px solid RULER; border-radius:99px; padding:5px 11px;}
.photo {position:relative; border-radius:18px; overflow:hidden; border:1px solid RULER; aspect-ratio:900/505;}
.photo img {width:100%; height:100%; object-fit:cover; display:block; border:none !important; border-radius:0 !important;}
.photo .reticle {position:absolute; left:62%; top:50%; width:30%; aspect-ratio:1; transform:translate(-50%,-50%);}
.photo .reticle circle {stroke-dasharray:320; animation:draw 1.6s ease-out .3s both;}
@keyframes draw {from {stroke-dashoffset:320;} to {stroke-dashoffset:0;}}
.photo .tag {left:70%; top:76%;}
.photo .cap {position:absolute; left:10px; bottom:8px; font:10px JB,monospace; color:BONE; text-shadow:0 1px 2px #000;}
.chip-row {margin-top:6px;}
.chip {display:inline-block; color:LIME; background:GRAPHITE; font:500 12px JB,monospace; text-transform:uppercase;
  letter-spacing:.08em; border-radius:99px; padding:6px 13px; margin:0 10px 10px 0;}
#demo-banner {border:1.5px solid RULER; border-radius:12px; padding:12px 16px; font-size:14px; background:PANEL;}
#demo-banner .mono {display:inline-block; color:LIME; background:GRAPHITE; padding:4px 10px; border-radius:6px; margin-bottom:6px;}

/* filming guide */
.field-label {display:flex; align-items:baseline; gap:10px; font-weight:600; color:GRAPHITE; margin:2px 0 6px;}
.field-label .num {font:400 24px/1 IS,serif; color:LATERITE;}
.guide {display:grid; grid-template-columns:72px 1fr; gap:14px; align-items:center;}
.phone {width:72px; aspect-ratio:9/16; border:2px solid GRAPHITE; border-radius:12px; position:relative; background:PANEL2;}
.phone i {position:absolute; inset:34% 9% 30% 9%; border:2px dashed LATERITE; border-radius:5px;}
.guide ul {list-style:none; margin:0; padding:0; display:grid; gap:3px; font-size:14px;}
.guide li::before {content:"\\2192  "; color:LATERITE;}

/* readout */
.readout {background:GRAPHITE; color:BONE; border-radius:16px; padding:18px 20px; display:grid; gap:14px;}
.readout .mono {color:LIME;}
.gradio-container .readout .run li > span {color:BONE !important;}
.bar {height:4px; background:rgba(242,237,228,.14); border-radius:99px; overflow:hidden;}
.bar i {display:block; height:100%; background:LIME; transition:width .4s ease;}
.run {list-style:none; margin:0; padding:0; display:grid; gap:10px;}
.run li {display:grid; grid-template-columns:22px 1fr; gap:12px; align-items:baseline; transition:opacity .3s;}
.run .dot {width:12px; height:12px; border-radius:99px; border:1.5px solid rgba(242,237,228,.4); align-self:center;}
.run li.done .dot {background:LIME; border-color:LIME;}
.run li.live .dot {border-color:LIME; animation:pulse 1s infinite;}
.run li.wait {opacity:.38;}
.run small {display:block; font:11px JB,monospace; color:SILT; margin-top:2px;}
.readout .fail {margin:0; color:SILT; font-size:14px;}
@keyframes pulse {50% {box-shadow:0 0 0 5px rgba(212,255,58,.18);}}
.sample-tag {display:inline-block; font:12px JB,monospace; color:LATERITE; border:1px dashed RULER;
  border-radius:99px; padding:4px 12px;}

/* verdict + ladder */
.verdict {display:grid; grid-template-columns:1.2fr 1fr; gap:16px;}
.verdict h3 {font-family:IS,serif; font-weight:400; font-size:clamp(28px,3.6vw,38px); line-height:1.06; margin:0;
  color:GRAPHITE; text-wrap:balance;}
.numbers {display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:20px;}
.numbers div {border-top:1.5px solid GRAPHITE; padding-top:8px; min-width:0;}
.numbers b {display:block; font:400 clamp(34px,4.6vw,50px)/1 IS,serif; font-variant-numeric:tabular-nums;}
.numbers span {font-size:13px; color:LATERITE;}
.ladder {display:grid; gap:12px;}
.rungs {display:grid; grid-template-columns:repeat(4,1fr); gap:6px;}
.rung {border:1px solid RULER; border-radius:10px; padding:9px; font-size:13.5px; min-height:64px; display:grid;
  align-content:space-between; min-width:0;}
.rung .mono {font-size:9.5px; color:LATERITE; min-height:1em;}
.rung.on {background:GRAPHITE; color:BONE; border-color:GRAPHITE;} .rung.on .mono {color:LIME;}
.rung.off {color:LATERITE; border-style:dashed;}
.ladder p {margin:0; font-size:14px;}
.ladder .next {border-left:2px solid GRAPHITE; background:PANEL2; border-radius:0 8px 8px 0; padding:8px 10px;}

/* river trace */
.trace-wrap {background:PANEL; border:1px solid RULER; border-radius:16px; padding:18px;}
.trace-head {display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; align-items:center;}
.legend {display:flex; gap:14px; flex-wrap:wrap; font-size:13px; color:LATERITE;}
.legend span {display:inline-flex; gap:6px; align-items:center;}
.legend .mark {margin:0; width:20px; height:20px; font-size:10px;}
.trace {display:grid; grid-template-columns:auto 1fr auto; align-items:start; padding-top:22px;}
.trace .eye {display:grid; justify-items:center; gap:6px; width:92px; text-align:center; font-size:13px;}
.trace .eye svg {width:52px; height:52px;} .trace .eye b {display:block;}
.stations {list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(7,1fr); position:relative;}
.stations::before {content:""; position:absolute; left:0; right:0; top:25px; border-top:2.5px dashed GRAPHITE; opacity:.5;}
.stations li {position:relative; display:grid; justify-items:center; gap:6px; text-align:center; padding:0 4px;
  font-size:13px; line-height:1.3; min-width:0;}
.mark {width:28px; height:28px; border-radius:99px; display:grid; place-items:center; font:700 13px/1 JB,monospace;
  margin-top:11px; background:BONE; border:1.5px solid RULER; color:LATERITE; font-style:normal;}
li.yes .mark, .legend .mark.yes {background:GRAPHITE; border-color:GRAPHITE; color:LIME;}
li.skip {opacity:.6;}
.stations small {display:block; color:LATERITE; font-size:12px;}
.km {position:absolute; top:-16px; left:50%; transform:translateX(-50%); font:11px JB,monospace; background:PANEL;
  padding:0 8px; color:LATERITE; white-space:nowrap;}

/* two eyes */
.eyes {display:grid; grid-template-columns:1fr 1fr; gap:16px;}
.eye-card {display:grid; gap:12px; align-content:start;}
.eye-head {display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;} .eye-head .mono {color:LATERITE;}
.scrub {position:relative; aspect-ratio:1; border-radius:14px; overflow:hidden; user-select:none; touch-action:pan-y;}
.scrub img, .clip img {position:absolute; inset:0; width:100%; height:100%; object-fit:cover; display:block;
  border:none !important; border-radius:0 !important;}
.scrub .after {clip-path:inset(0 0 0 var(--x));}
.scrub .line {position:absolute; top:0; bottom:0; left:var(--x); width:2px; background:LIME; transform:translateX(-1px);}
.scrub .knob {position:absolute; top:50%; left:var(--x); width:44px; height:44px; transform:translate(-50%,-50%);
  border-radius:99px; background:LIME; color:GRAPHITE; display:grid; place-items:center; font-size:20px;
  box-shadow:0 2px 10px rgba(0,0,0,.35); pointer-events:none;}
.scrub .tag.l {left:10px; top:10px;} .scrub .tag.r {right:10px; top:10px;}
.scrub input[type=range] {position:absolute; inset:0; width:100%; height:100%; opacity:0; cursor:ew-resize; margin:0;}
.clip {position:relative; display:block; aspect-ratio:720/404; border-radius:14px; overflow:hidden; cursor:pointer;}
.clip input {position:absolute; opacity:0;}
.clip .mask {opacity:0; transition:opacity .35s;}
.clip input:checked ~ .mask {opacity:1;}
.clip input:focus-visible ~ .toggle {outline:3px solid LIME;}
.clip .tag {left:12px; bottom:12px;}
.clip .toggle {position:absolute; right:10px; top:10px; font:12px G,sans-serif; background:rgba(21,19,15,.78);
  color:BONE; padding:6px 10px; border-radius:99px;}
.clip .toggle:empty {display:none;}
.quote {font-family:IS,serif; font-size:24px; line-height:1.2; margin:0;}
.swatches {display:grid; grid-template-columns:1fr 1fr; gap:10px;}
.sw {display:grid; grid-template-columns:40px 1fr; gap:10px; align-items:center; font-size:13px;}
.sw i {width:40px; height:40px; border-radius:10px; border:1px solid RULER;}
.sw small {display:block; color:LATERITE;}

/* share */
.chat {background:#E6DDCF; border-radius:22px; padding:16px 14px; border:1px solid RULER; max-width:380px; margin:0 auto;}
.chat-top {display:flex; gap:10px; align-items:center; font-weight:600; margin-bottom:12px;}
.chat-top i {width:30px; height:30px; border-radius:99px; background:LATERITE;}
.bubble {background:#DCF8C6; border-radius:12px 2px 12px 12px; padding:6px; margin-left:28px;}
.bubble .thumb {display:block; width:100%; border-radius:8px; border:none !important;}
.bubble p {font-size:14px; line-height:1.4; padding:8px 6px 2px; margin:0; white-space:pre-line; color:GRAPHITE;}
.bubble .ts {text-align:right; font-size:10px; color:#5E6B5A; padding:0 6px 2px;}
a.wa {display:inline-flex; align-items:center; justify-content:center; min-height:52px; padding:0 22px;
  border-radius:12px; background:WA; color:#10230F !important; font-weight:700; text-decoration:none; width:100%;}
.next-steps ul {list-style:none; margin:8px 0 0; padding:0; display:grid; gap:8px;}
.next-steps li {padding:12px 14px; border:1px solid RULER; border-radius:12px; background:PANEL;}
.next-steps small {display:block; color:LATERITE; font-size:13px;}
#footnote {border-top:1px solid RULER; margin-top:30px; padding:18px 4px 26px; font-size:12.5px; line-height:1.55; color:LATERITE;}

:focus-visible {outline:3px solid GRAPHITE; outline-offset:2px;}
@media (max-width:820px) {
  .hero, .verdict, .eyes {grid-template-columns:1fr;}
  .hero .photo-col {order:-1;}
  .trace {grid-template-columns:1fr;}
  .trace .eye {grid-template-columns:52px 1fr; justify-items:start; text-align:left; width:auto; align-items:center;}
  .stations {grid-template-columns:1fr; padding:10px 0 10px 12px;}
  .stations::before {top:0; bottom:0; left:25px; right:auto; border-top:0; border-left:2.5px dashed GRAPHITE;}
  .stations li {grid-template-columns:28px 1fr; justify-items:start; text-align:left; gap:2px 14px; padding:6px 0;}
  .stations li .mark {margin:0; grid-row:span 2;}
  .km {position:static; transform:none; grid-column:2; padding:0; background:none;}
  .rungs {grid-template-columns:repeat(2,1fr);}
  #row-input, #row-share {flex-wrap:wrap !important;}
  #row-input > div, #row-share > div {min-width:100% !important;}
}
@media (prefers-reduced-motion: reduce) {*, *::before, *::after {animation:none !important; transition:none !important;}}
"""


def build_css():
    """Full page CSS: Gradio restyle + case-file components, with the brand tokens filled in."""
    css = _GRADIO + _PAGE
    for name, value in [("GRAPHITE", GRAPHITE), ("BONE", BONE), ("PANEL2", PANEL2), ("PANEL", PANEL),
                        ("SILT", SILT), ("LATERITE", LATERITE), ("LIME", LIME), ("RULER", RULER), ("WA", WA)]:
        css = css.replace(name, value)
    return css + _font_faces()
