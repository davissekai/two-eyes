// Two Eyes phone app: one screen at a time, driven by the browser history so the phone's back works.
"use strict";

const MAX_CLIP_MB = 80;
const STEPS = ["where", "film", "checking"];
const state = {place: null, clip: null, jobId: null, result: null, polling: false};
const $ = (id) => document.getElementById(id);

// --- screens -------------------------------------------------------------------------------------

// Show one screen. push adds a history entry (forward); replace swaps the current one (no way back to it).
function show(name, {push = true, replace = false, back = false} = {}) {
  if (!document.querySelector(`[data-screen="${name}"]`)) name = "start";
  if (["film", "checking"].includes(name) && !state.place) name = "where";
  if (["result", "share"].includes(name) && !state.result) name = state.jobId ? "checking" : "start";
  document.querySelectorAll(".screen").forEach((s) => {
    const on = s.dataset.screen === name;
    s.hidden = !on;
    s.classList.toggle("back-in", on && back);
  });
  const at = ["result", "share"].includes(name) ? STEPS.length - 1 : STEPS.indexOf(name);
  $("progress").hidden = at < 0;
  $("progress").querySelectorAll("li").forEach((li, i) => li.classList.toggle("on", i <= at));
  $("back").hidden = name === "start";
  if (replace) history.replaceState({screen: name}, "", `#${name}`);
  else if (push) history.pushState({screen: name}, "", `#${name}`);
  window.scrollTo(0, 0);
  const h = document.querySelector(`[data-screen="${name}"] h1, [data-screen="${name}"] h2`);
  if (h) { h.tabIndex = -1; h.focus({preventScroll: true}); }
}

window.addEventListener("popstate", (e) => show((e.state && e.state.screen) || "start", {push: false, back: true}));
$("back").addEventListener("click", () => history.back());
document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => show(b.dataset.go)));
window.addEventListener("scroll", () => document.querySelector(".topbar").classList.toggle("scrolled", scrollY > 4),
  {passive: true});

// --- where ---------------------------------------------------------------------------------------

function setPlace(place, how) {
  state.place = place;
  $("to-film").disabled = !place;
  $("chosen").hidden = !place;
  if (place) $("chosen").innerHTML = `Checking from <b></b>`;
  if (place) $("chosen").querySelector("b").textContent = how;
  document.querySelectorAll(".spot").forEach((b) =>
    b.setAttribute("aria-checked", String(!!place && b.dataset.name === place.name)));
}

const GPS_IDLE = ["Use my location", "Your phone's GPS finds the river you're at"];
const ROUGH_FIX_M = 1000;

// Puts the GPS button in one of its states: idle, busy (looking) or ok (found, showing where and how close).
function gpsState(kind, [title, sub] = GPS_IDLE) {
  const btn = $("gps");
  btn.classList.toggle("busy", kind === "busy");
  btn.classList.toggle("ok", kind === "ok");
  btn.querySelector("b").textContent = title;
  btn.querySelector("small").textContent = sub;
}

// Accuracy in words a person reads at a glance: metres when close, km when rough.
function distance(m) {
  return m < ROUGH_FIX_M ? `${Math.round(m)} m` : `${Math.round(m / 100) / 10} km`;
}

function message(el, text, bad) {
  el.hidden = !text;
  el.textContent = text || "";
  el.classList.toggle("bad", !!bad);
}

// Asks the phone for its position and says plainly what happened. Needs https (or localhost).
$("gps").addEventListener("click", () => {
  const msg = $("gps-msg");
  if (!navigator.geolocation || !window.isSecureContext) {
    return message(msg, "This page can't use your location (it needs a secure https link). Pick a spot below.", true);
  }
  gpsState("busy", ["Finding you…", "Hold on, this can take a few seconds"]);
  message(msg, "");
  navigator.geolocation.getCurrentPosition((p) => {
    const c = p.coords;
    setPlace({lat: c.latitude, lon: c.longitude, name: "Your spot"}, "your GPS position");
    gpsState("ok", ["Location found",
      `${c.latitude.toFixed(4)}, ${c.longitude.toFixed(4)} · within ${distance(c.accuracy)}`]);
    message(msg, c.accuracy >= ROUGH_FIX_M
      ? "That's a rough fix. If you can, step into the open and tap again, or pick a spot below." : "");
  }, (e) => {
    gpsState("idle");
    message(msg, e.code === 1
      ? "Location is blocked. Allow location for this site in your browser settings, or pick a spot below."
      : "Couldn't get a GPS fix. Try again in the open, away from buildings, or pick a spot below.", true);
  }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 60000});
});

async function loadSpots() {
  try {
    const spots = await (await fetch("/api/spots")).json();
    $("spots").replaceChildren(...spots.map((s) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "spot"; b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", "false"); b.dataset.name = s.name;
      b.innerHTML = "<span><b></b><small></small></span><i aria-hidden=\"true\"></i>";
      b.querySelector("b").textContent = s.name;
      b.querySelector("small").textContent = `${s.lat.toFixed(4)}, ${s.lon.toFixed(4)}`;
      b.addEventListener("click", () => { message($("gps-msg"), ""); gpsState("idle"); setPlace(s, s.name); });
      return b;
    }));
  } catch (e) {
    $("spots").textContent = "Couldn't load the spots. Use your location or type coordinates.";
  }
}

$("use-coords").addEventListener("click", () => {
  const lat = parseFloat($("lat").value.replace(",", ".")), lon = parseFloat($("lon").value.replace(",", "."));
  if (!(Math.abs(lat) <= 90 && Math.abs(lon) <= 180)) {
    return message($("coords-msg"), "Type both numbers, like 6.2844 and -0.4612.", true);
  }
  message($("coords-msg"), "");
  message($("gps-msg"), "");
  gpsState("idle");
  setPlace({lat, lon, name: "Your spot"}, `${lat.toFixed(4)}, ${lon.toFixed(4)}`);
});

// --- film ----------------------------------------------------------------------------------------

// A desktop has no camera button to press: say "choose" instead of "film".
const DESKTOP = window.matchMedia && matchMedia("(hover: hover) and (pointer: fine)").matches;
const PICK_LABEL = DESKTOP ? "Choose a video or photo" : "Open camera";
const AGAIN_LABEL = DESKTOP ? "Choose another" : "Film again";
$("record-label").textContent = PICK_LABEL;

const VIDEO_EXT = /\.(mp4|mov|m4v|3gp|webm|mkv|avi)$/i, PHOTO_EXT = /\.(jpe?g|png|webp|heic|heif)$/i;
function kindOf(f) {
  if (f.type.startsWith("video/") || (!f.type && VIDEO_EXT.test(f.name))) return "video";
  if (f.type.startsWith("image/") || (!f.type && PHOTO_EXT.test(f.name))) return "photo";
  return null;
}

function resetClip() {
  state.clip = null;
  $("clip").value = "";
  const v = $("clip-preview"), im = $("photo-preview");
  if (v.src) { URL.revokeObjectURL(v.src); v.removeAttribute("src"); }
  if (im.src) { URL.revokeObjectURL(im.src); im.removeAttribute("src"); }
  v.hidden = true; im.hidden = true;
  $("film-box").classList.remove("has-clip");
  $("record").classList.add("primary"); $("record").classList.remove("quiet");
  $("record-label").textContent = PICK_LABEL;
  $("check-with-clip").hidden = true;
  $("need-clip").hidden = false;
  message($("clip-msg"), "");
}

$("clip").addEventListener("change", () => {
  const f = $("clip").files[0];
  if (!f) return;
  const kind = kindOf(f);
  if (!kind) { resetClip(); return message($("clip-msg"), "That isn't a video or a photo. Film the water and try again.", true); }
  if (f.size === 0) { resetClip(); return message($("clip-msg"), "That file is empty. Film the water again.", true); }
  if (f.size > MAX_CLIP_MB * 1024 * 1024) {
    resetClip();
    return message($("clip-msg"), "That clip is too long. Ten seconds of video is enough.", true);
  }
  message($("clip-msg"), "");
  state.clip = f;
  const v = $("clip-preview"), im = $("photo-preview");
  if (v.src) { URL.revokeObjectURL(v.src); v.removeAttribute("src"); }
  if (im.src) { URL.revokeObjectURL(im.src); im.removeAttribute("src"); }
  if (kind === "video") {
    im.hidden = true; v.src = URL.createObjectURL(f); v.hidden = false; v.play().catch(() => {});
  } else {
    v.hidden = true; im.src = URL.createObjectURL(f); im.hidden = false;
  }
  $("film-box").classList.add("has-clip");
  $("record").classList.remove("primary"); $("record").classList.add("quiet");
  $("record-label").textContent = AGAIN_LABEL;
  $("check-with-clip").hidden = false;
  $("need-clip").hidden = true;
});
$("check-with-clip").addEventListener("click", () => startCheck(state.clip));

// --- checking ------------------------------------------------------------------------------------

async function startCheck(clip) {
  if (!clip) {
    const msg = $("clip-msg");
    if (msg) { msg.hidden = false; msg.textContent = "Film the water first, or take a photo of it."; }
    show("film");
    return;
  }
  const fd = new FormData();
  fd.append("lat", state.place.lat); fd.append("lon", state.place.lon); fd.append("name", state.place.name);
  fd.append("clip", clip);
  state.result = null;
  $("checking-where").textContent = `From ${state.place.name === "Your spot" ? "your spot" : state.place.name}, with your ` +
    (kindOf(clip) === "photo" ? "photo." : "clip.");
  $("readout").innerHTML = '<div class="readout"><p class="fine">Sending your clip…</p></div>';
  $("checking-actions").hidden = true;
  show("checking");
  try {
    const r = await fetch("/api/checks", {method: "POST", body: fd});
    let body = {};
    try { body = await r.json(); } catch (e) { /* a proxy error page, not our JSON */ }
    if (!r.ok) {
      const plain = {413: "That clip is too big. Ten seconds of video is enough.",
        429: "Two Eyes is busy with other checks. Try again in a minute."}[r.status];
      throw new Error(typeof body.detail === "string" ? body.detail
        : plain || "Two Eyes couldn't start the check. Try again in a minute.");
    }
    state.jobId = body.id;
    sessionStorage.setItem("twoEyesJob", JSON.stringify({id: body.id, place: state.place}));
    poll();
  } catch (e) {
    failed(e.message && !e.message.includes("fetch") ? e.message : "Couldn't reach Two Eyes. Check your connection.");
  }
}

function failed(text) {
  $("readout").innerHTML = '<div class="readout"><p class="fail"></p></div>';
  $("readout").querySelector(".fail").textContent = text;
  $("checking-actions").hidden = false;
}
$("retry").addEventListener("click", () => startCheck(state.clip));
$("change-spot").addEventListener("click", () => {
  sessionStorage.removeItem("twoEyesJob");
  Object.assign(state, {jobId: null, result: null});
  show("where");
});

// Poll the check; a dropped connection just waits and tries again, the check keeps running on the server.
async function poll() {
  if (state.polling) return;
  state.polling = true;
  let wait = 1200;
  while (state.jobId) {
    try {
      const r = await fetch(`/api/checks/${state.jobId}`);
      if (r.status === 404) { failed("This check has expired. Start a new one."); break; }
      const body = await r.json();
      $("readout").innerHTML = body.readout_html;
      if (body.state === "done") { showResult(body.result); break; }
      if (body.state === "failed") { $("checking-actions").hidden = false; break; }
      wait = 1200;
    } catch (e) {
      wait = Math.min(wait * 2, 10000);
    }
    await new Promise((ok) => setTimeout(ok, wait));
  }
  state.polling = false;
}

// --- result + share ------------------------------------------------------------------------------

function showResult(res) {
  state.result = res;
  for (const k of ["verdict", "trace", "eyes", "links", "preview"]) $(k).innerHTML = res[k] || "";
  $("next-steps").innerHTML = res.next_steps || "";
  $("share-buttons").innerHTML = res.share_html || "";
  $("save-card").href = res.card_url;
  $("native-share").hidden = !navigator.share;
  if (location.hash === "#checking" || !history.state || history.state.screen === "checking") {
    show("result", {replace: true});
  }
}

$("native-share").addEventListener("click", async () => {
  const res = state.result;
  try {
    const blob = await (await fetch(res.card_url)).blob();
    const file = new File([blob], "two-eyes-evidence-card.png", {type: "image/png"});
    const data = navigator.canShare && navigator.canShare({files: [file]})
      ? {files: [file], text: res.share_text} : {text: res.share_text};
    await navigator.share(data);
  } catch (e) { /* the person closed the share sheet */ }
});

$("again").addEventListener("click", () => {
  sessionStorage.removeItem("twoEyesJob");
  Object.assign(state, {jobId: null, result: null});
  resetClip();
  show("where");
});

// --- start-up ------------------------------------------------------------------------------------

loadSpots();
try {
  const saved = JSON.parse(sessionStorage.getItem("twoEyesJob") || "null");
  if (saved && ["#checking", "#result", "#share"].includes(location.hash)) {
    state.place = saved.place; state.jobId = saved.id;
    show("checking", {replace: true});
    poll();
  } else {
    show("start", {replace: true});
  }
} catch (e) {
  show("start", {replace: true});
}
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
