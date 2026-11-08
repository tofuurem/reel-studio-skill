#!/usr/bin/env python3
"""One look at all the material before planning: a table of every media file and contact sheets you can read.

Usage: python3 -I inventory.py <project> <files|dirs>… [--lut <cube>] [--lut-map map.json] [--name inventory]
→ <project>/work/<name>/inventory.md  table: #, kind, file, duration, size (as displayed, rotation applied), fps (average; VFR
                                       flagged), camera, MB, audio level, silent?, LUT, shot time, notes
  <project>/work/<name>/camera.jpg    one graded frame per camera clip (tiles in table order, 6 per row)
  <project>/work/<name>/screen.jpg    three frames per screen recording / other video (one row each)
  <project>/work/<name>/images.jpg    thumbnails of the images (6 per row)
  More than 36 tiles → camera_1.jpg, camera_2.jpg … (36 per sheet; one giant sheet is unreadable).
Kinds follow ingest.py (camera = any video that is not a screen recording or in assets/video, screen = «Запись экрана»/Screen Recording/rec_*, video, audio, image). The LUT goes on
camera clips only, per clip (common.lut_for: --lut-map, the DJI colour profile in the file, --lut; otherwise none), and on every HDR video (HLG / PQ: iPhone «HDR»,
a camera in HLG mode) as the HDR → Rec.709 LUT — the sheets show what the proxies will look like. "silent" =
no audio stream or mean level under −70 dB over the first 2 min: do not transcribe those (Whisper invents «Продолжение
следует…» on silence). ffmpeg here has no drawtext, so tiles carry no labels — a frame that cannot be grabbed becomes a grey
tile, so the tile order always equals the table order. AppleDouble `._*` files are skipped.
"""
import argparse, json, os, subprocess, sys, unicodedata, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import is_camera, load_lut_map, looks_log, lut_for, nfc, probe

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("paths", nargs="+"); ap.add_argument("--lut"); ap.add_argument("--lut-map"); ap.add_argument("--name", default="inventory")
a = ap.parse_args()
P = os.path.abspath(a.project); OUT = os.path.join(P, "work", a.name); os.makedirs(OUT, exist_ok=True)
LUT_MAP = load_lut_map(a.lut_map)
VIDEO = {".mp4", ".mov", ".m4v"}; IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"}; AUDIO = {".aac", ".m4a", ".wav", ".mp3", ".aif", ".aiff"}
PER_SHEET = 36; LONG_AUDIO = 150

def files(paths):
    for p in paths:
        if os.path.isfile(p): yield os.path.abspath(p); continue
        for root, dirs, fs in os.walk(p):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for f in sorted(fs):
                if not f.startswith("."): yield os.path.abspath(os.path.join(root, f))

def kind(f):
    n = nfc(os.path.basename(f)); stem, ext = os.path.splitext(n); ext = ext.lower(); low = stem.lower()
    if ext in VIDEO: return "screen" if ("запись экрана" in low or "screen recording" in low or low.startswith("rec_")) else "camera" if is_camera(f) else "video"
    return "image" if ext in IMAGE else "audio" if ext in AUDIO else None

def level(f):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-t", "120", "-i", f, "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    for l in r.splitlines():
        if "mean_volume" in l: return float(l.split(":")[1].replace("dB", ""))
    return None

def grab(f, t, vf, out, w, h):
    subprocess.run(["ffmpeg", "-v", "quiet", "-nostdin", "-y", "-ss", f"{t:.2f}", "-i", f, "-frames:v", "1", "-vf", vf, out])
    if not os.path.exists(out):   # keep the tile order = table order: a grey placeholder for a frame that cannot be grabbed
        subprocess.run(["ffmpeg", "-v", "quiet", "-nostdin", "-y", "-f", "lavfi", "-i", f"color=c=0x555555:s={w}x{h}:d=0.04", "-frames:v", "1", out])
    return out

def sheet(tiles, cols, w, h, name):
    """Tiles → name.jpg, or name_1.jpg, name_2.jpg … when there are more than PER_SHEET. Returns the written file names."""
    if not tiles: return []
    pages = [tiles[i:i + PER_SHEET] for i in range(0, len(tiles), PER_SHEET)]; outs = []
    for k, page in enumerate(pages, 1):
        out = os.path.join(OUT, f"{name}.jpg" if len(pages) == 1 else f"{name}_{k}.jpg")
        lay = "|".join(f"{(i % cols) * w}_{(i // cols) * h}" for i in range(len(page)))
        args = sum([["-i", t] for t in page], [])
        flt = "".join(f"[{i}:v]" for i in range(len(page))) + (f"xstack=inputs={len(page)}:layout={lay}:fill=black[o]" if len(page) > 1 else "null[o]")
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *args, "-filter_complex", flt, "-map", "[o]", out], check=True); outs.append(os.path.basename(out))
    for t in tiles: os.remove(t)
    return outs

def lvl(v): return '' if v is None else '%.0f dB' % v
def note(r):
    n = []
    if r["kind"] == "camera" and (r.get("w") or 0) > (r.get("h") or 0): n.append("horizontal: make_proxies centre-crops it to 9:16 — check the framing")
    if r["kind"] in ("screen", "video") and r["silent"]: n.append("no sound: do not transcribe")
    if r.get("vfr"): n.append(f"VFR (avg {r['fps']:.1f}, max {r['r_fps']:.0f} fps): proxies make it constant 30")
    elif r["kind"] in ("screen", "video", "camera") and (r.get("fps") or 0) > 31: n.append(f"{r['fps']:.0f} fps: proxies retime to 30")
    if r.get("rot"): n.append(f"rotated {r['rot']}° (size shown as displayed)")
    why = str(r.get("lut_why", ""))
    if why.startswith("NO LUT FOUND"): n.append(why)   # the file itself says D-Log / D-Log M and its cube is not installed
    elif r["kind"] == "camera" and not r.get("lut") and looks_log(r["file"]) and not why.startswith(("djmd", "lut-map")): n.append("no LUT: fine for Normal / Rec.709, grey if it is D-Log (--lut)")
    if r.get("hdr"): n.append(f"HDR {r['hdr'].upper()}: converted to Rec.709 by {r.get('lut') or 'the HDR LUT'} (hdr_lut.py)")
    if r["kind"] == "audio" and r.get("dur", 0) > LONG_AUDIO: n.append("long audio: voiceover monologue or music?")
    elif r.get("dur", 0) > 240: n.append("long take: --trim-to-cutlist")
    return "; ".join(n)

rows = []; cam, scr, img = [], [], []
for f in files(a.paths):
    k = kind(f)
    if not k: continue
    info = probe(f) if k != "image" else {kk: v for kk, v in probe(f).items() if kk in ("w", "h")}   # images: size only
    lv = level(f) if k in ("camera", "screen", "video", "audio") and info.get("has_audio", k == "audio") else None
    silent = k != "image" and (lv is None or lv < -70)
    lut, why = lut_for(f, a.lut, LUT_MAP, info) if k in ("camera", "screen", "video") else (None, "")
    shot = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
    rows.append({"kind": k, "file": f, **info, "level": lv, "silent": silent, "lut": os.path.basename(lut) if lut else None, "lut_why": why, "shot": shot, "mb": round(os.path.getsize(f) / 1048576, 1)})
    i = len(rows); fit = "scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x333333"
    if k == "camera":
        t = min(4.0, info.get("dur", 0) / 2); vf = (f"lut3d=file='{lut}':interp=tetrahedral," if lut else "") + fit.format(w=216, h=384)
        cam.append(grab(f, t, vf, os.path.join(OUT, f"_c{i:03d}.jpg"), 216, 384))
    elif k in ("screen", "video"):
        pre = f"lut3d=file='{lut}':interp=tetrahedral," if lut else ""   # an HDR phone clip: the sheet shows what the proxy will look like
        for j in (1, 2, 3): scr.append(grab(f, info.get("dur", 0) * j / 4, pre + fit.format(w=480, h=300), os.path.join(OUT, f"_s{i:03d}_{j}.jpg"), 480, 300))
    elif k == "image":
        img.append(grab(f, 0, fit.format(w=300, h=300), os.path.join(OUT, f"_i{i:03d}.jpg"), 300, 300))

made = sheet(cam, 6, 216, 384, "camera") + sheet(scr, 3, 480, 300, "screen") + sheet(img, 6, 300, 300, "images")
luts = sorted({r["lut"] for r in rows if r.get("lut")})
L = ["# Inventory", "", f"{len(rows)} files · LUT on camera clips: {', '.join(luts) if luts else 'none found'}", "",
     "| # | kind | file | dur | size | fps | camera | MB | audio | silent | LUT | shot | note |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    fps = f"{r.get('fps') or ''}" + (" VFR" if r.get("vfr") else "")
    L.append(f"| {i} | {r['kind']} | {unicodedata.normalize('NFC', os.path.basename(r['file']))} | {r.get('dur', 0):.1f}s | {r.get('w') or ''}×{r.get('h') or ''} | {fps} | {r.get('camera') or ''} | {r['mb']} | {lvl(r['level'])} | {'yes' if r['silent'] else ''} | {r['lut'] or ''} | {r['shot']} | {note(r)} |")
talk = [r["file"] for r in rows if r["kind"] in ("camera", "screen", "video", "audio") and not r["silent"]]
L += ["", "Sheets: " + (", ".join(made) or "none") + " (tiles in table order within each kind; grey = frame could not be read).", "",
      "Next: transcribe only the files with sound —", "", "```", "cd " + P, "work/pkvenv/bin/python -I $S/transcribe_parakeet.py \\", *[f"  '{t}' \\" for t in talk], "```"]
open(os.path.join(OUT, "inventory.md"), "w").write("\n".join(L) + "\n")
json.dump(rows, open(os.path.join(OUT, "inventory.json"), "w"), ensure_ascii=False, indent=1)
print("\n".join(L[:len(rows) + 6])); print("INVENTORY_DONE", OUT)
