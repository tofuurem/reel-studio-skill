#!/usr/bin/env python3
"""Where is the face in each shot? (macOS Vision) → tells you where graphics may go.

Usage: work/venv/bin/python -I face_zones.py [--cutlist work/cutlist.json] [--public reel/public] [--out work/face_zones.json] [--zoom work/timeline_zoom.json]

For every main-track segment it grabs frames at 20/50/80 % of the segment (source time, so speed-changed CapCut segments
sample the right seconds) from the 1080 proxy, runs VNDetectFaceRectanglesRequest and reports the face box plus the free
vertical bands. All numbers in face_zones.json are FINAL SCREEN coordinates (1080x1920): each box is mapped the way Clip.tsx
places the clip — fitted to the canvas (cover, or contain / the CapCut crop region), the user's CapCut framing (scale, flip,
rotation, then the x / y offset in half-canvas units, y up), then the punch zoom + drift around the zoom origin (punchCenterY)
— all read from work/timeline_zoom.json (gen_timeline.py). A 1.2–1.3 punch moves a face ~100 px, and cards placed from
unzoomed boxes landed on chins (birthday reel).
Bands start at numbers.json cardTop (y 300, below the chapter tag) and end at bandBottom (y 1350, above the captions).
Muted b-roll / no-face segments get the full band. Cards must not cover the face; this replaces eyeballing contact sheets.
A landscape canvas (cut list "canvas" 16:9, 1920×1080) — hermes-worker reel, 2026-11-06, where the 9:16 math reported faces
at y 1636 of 1080 and no x at all: boxes are mapped onto 1920×1080, every segment is sampled each --every s (default 0.5,
handheld shots wander), faces smaller than 60 px (a video call on a laptop screen) are ignored, and each row also carries
faceLeft / faceRight, freeLeft / freeRight (x ranges inside wideMargin) and `side` — the wider free side for cards
("left" / "right", "none" when neither is 420 px wide). reelgen: R.free_side(a, b). Bands use wideBandTop / wideBandBottom.
"""
import argparse, json, math, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, need_vision, clip_id, load_json, load_offsets, proxy_file, src_dur

W, H = 1080, 1920

def seg_for(zoom, from_frame):
    """The timeline_zoom.json row of the clip that contains this frame ({} when unknown)."""
    for z in (zoom or {}).get("segments", []):
        if z["fromFrame"] <= from_frame < z["fromFrame"] + max(1, z["durFrames"]): return z
    return {}

def to_canvas(nx, ny, z, pw, ph, drift_default):
    """A point of the proxy frame (0–1 of its width/height) → the canvas point the viewer sees (Clip.tsx, in the same order)."""
    crop = z.get("crop")
    if crop and z.get("srcW") and z.get("srcH"):   # the crop region fitted inside the canvas (cropGeometry in Clip.tsx)
        sw, sh = z["srcW"], z["srcH"]; cw, ch = (crop["x1"] - crop["x0"]) * sw, (crop["y1"] - crop["y0"]) * sh
        k = min(W / cw, H / ch); x = (W - cw * k) / 2 + (nx - crop["x0"]) * sw * k; y = (H - ch * k) / 2 + (ny - crop["y0"]) * sh * k
    else:
        k = (min if z.get("fit") == "contain" else max)(W / pw, H / ph)
        x = (W - pw * k) / 2 + nx * pw * k; y = (H - ph * k) / 2 + ny * ph * k
    f = z.get("framing") or {}
    if f:   # CSS translate → rotate → scale about the centre: scale first, then rotate, then move
        sx = (f.get("scale") or 1) * (-1 if f.get("flipH") else 1); sy = f.get("scaleY") or f.get("scale") or 1
        dx, dy = (x - W / 2) * sx, (y - H / 2) * sy; r = math.radians(f.get("rotation") or 0)
        dx, dy = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
        x, y = W / 2 + dx + (f.get("x") or 0) * W / 2, H / 2 + dy - (f.get("y") or 0) * H / 2
    zz = float(z.get("zoom", 1)) + float(z.get("drift", drift_default)); cy = N["punchCenterY"]
    return W / 2 + (x - W / 2) * zz, cy + (y - cy) * zz

def to_screen(box, z, pw, ph, drift_default=N["punchDrift"]):
    """A face box (0–1 of the proxy frame) → its bounding box on the canvas, through every corner."""
    pts = [to_canvas(box["x"] + u * box["w"], box["y"] + v * box["h"], z, pw, ph, drift_default) for u in (0, 1) for v in (0, 1)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"x": round(min(xs)), "y": round(min(ys)), "w": round(max(xs) - min(xs)), "h": round(max(ys) - min(ys))}

def proxy_size(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True)
    try: w, h = (int(v) for v in r.stdout.strip().split(",")[:2]); return w, h
    except ValueError: return W, H

def detect(img_path):
    need_vision("face_zones.py")
    import Vision, Quartz
    from Foundation import NSURL
    src = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(img_path), None); img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    req = Vision.VNDetectFaceRectanglesRequest.alloc().init()
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([req], None)
    out = []
    for r in (req.results() or []):
        b = r.boundingBox(); out.append({"x": b.origin.x, "y": 1 - b.origin.y - b.size.height, "w": b.size.width, "h": b.size.height})   # 0–1 of the frame
    return out

def wide_zone(faces):
    """16:9 canvas: the head box (face ±, hair) over all samples and the free strips left / right of it and above / below it."""
    m, top0, bot0 = N["wideMargin"], N["wideBandTop"], N["wideBandBottom"]
    if not faces:
        return {"faceTop": None, "faceBottom": None, "faceLeft": None, "faceRight": None, "faceSize": 0, "shot": "no-face",
                "freeTop": [top0, bot0], "freeBottom": [top0, bot0], "freeLeft": [m, W - m], "freeRight": [m, W - m], "side": "any"}
    size = max(f["h"] for f in faces)
    l = max(0, int(min(f["x"] for f in faces) - size * 0.3)); r = min(W, int(max(f["x"] + f["w"] for f in faces) + size * 0.3))
    t = max(0, int(min(f["y"] for f in faces) - size * 0.45)); b = min(H, int(max(f["y"] + f["h"] for f in faces) + size * 0.25))
    fl = [m, max(m, l - 40)]; fr = [min(W - m, r + 40), W - m]
    wl, wr = fl[1] - fl[0], fr[1] - fr[0]
    side = ("left" if wl >= wr else "right") if max(wl, wr) >= 420 else "none"
    return {"faceTop": t, "faceBottom": b, "faceLeft": l, "faceRight": r, "faceSize": size, "shot": "close" if size > 300 else "medium" if size > 180 else "wide",
            "freeTop": [top0, max(top0, t - 40)], "freeBottom": [min(bot0, b + 40), bot0], "freeLeft": fl, "freeRight": fr, "side": side}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cutlist", default="work/cutlist.json"); ap.add_argument("--public", default="reel/public"); ap.add_argument("--out", default="work/face_zones.json")
    ap.add_argument("--zoom", default=None, help="default: timeline_zoom.json next to the cut list")
    ap.add_argument("--every", type=float, default=None, help="sample every N source seconds (default: 20/50/80 %% of a segment on 9:16, every 0.5 s on 16:9)")
    a = ap.parse_args()
    global W, H
    cl = json.load(open(a.cutlist)); OFFSETS = load_offsets(a.cutlist)
    cv = cl.get("canvas") or {}; W, H = int(cv.get("w", 1080)), int(cv.get("h", 1920)); wide = W > H
    every = a.every if a.every is not None else (0.5 if wide else 0)
    if cl.get("silent"): json.dump([], open(a.out, "w")); print("silent cut list: no faces"); print("FACE_ZONES_DONE", a.out); return
    zoom = load_json(a.zoom or os.path.join(os.path.dirname(a.cutlist) or ".", "timeline_zoom.json"), {})
    if not zoom: print("WARNING: no timeline_zoom.json (run gen_timeline.py first) — boxes are unzoomed")
    os.makedirs("work/faces", exist_ok=True); rows = []
    for i, s in enumerate(cl["main"]):
        if s.get("materialType", "video") != "video": continue
        z = seg_for(zoom, s["fromFrame"]); faces_all = []; proxy = proxy_file(a.public, clip_id(s['path'])); pw, ph = proxy_size(proxy)
        drift_default = float((zoom or {}).get("drift", N["punchDrift"]))
        d = src_dur(s)
        fracs = [(k + 0.5) * every / d for k in range(max(1, min(24, int(d / every))))] if every > 0 and d > 0 else [0.2, 0.5, 0.8]
        for frac in fracs:
            t = s["srcStart"] - OFFSETS.get(clip_id(s["path"]), 0) + d * frac; img_path = f"work/faces/seg{i:02d}_{int(frac*1000):04d}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", str(t), "-i", proxy, "-frames:v", "1", "-vf", "scale=540:-1", img_path], check=True)
            boxes = [to_screen(b, z, pw, ph, drift_default) for b in detect(img_path)]
            faces_all += [f for f in boxes if f["h"] >= 60] if wide else boxes   # 16:9: a video call on a laptop screen is not the speaker
        if wide:
            zone = wide_zone(faces_all)
        elif faces_all:
            top = min(f["y"] for f in faces_all); bottom = max(f["y"] + f["h"] for f in faces_all); size = max(f["h"] for f in faces_all)
            # head incl. hair ≈ 1.6× the face box; keep 40 px margin
            head_top = max(0, int(top - size * 0.45)); head_bottom = int(bottom + size * 0.25)
            zone = {"faceTop": head_top, "faceBottom": head_bottom, "faceSize": size, "shot": "close" if size > 300 else "medium" if size > 180 else "wide",
                    "freeTop": [N["cardTop"], max(N["cardTop"], head_top - 40)], "freeBottom": [min(N["bandBottom"], head_bottom + 40), N["bandBottom"]]}
        else:
            zone = {"faceTop": None, "faceBottom": None, "faceSize": 0, "shot": "no-face", "freeTop": [N["cardTop"], N["bandBottom"]], "freeBottom": [N["cardTop"], N["bandBottom"]]}
        zone.update({"seg": i, "clip": clip_id(s["path"]), "fromFrame": s["fromFrame"], "durFrames": s["durFrames"], "zoom": round(float(z.get("zoom", 1)) + float(z.get("drift", drift_default)), 3)}); rows.append(zone)
        if wide: print(f"{i:2d} {zone['clip']} from={s['fromFrame']:5d} {zone['shot']:7s} face x {zone['faceLeft']}–{zone['faceRight']} y {zone['faceTop']}–{zone['faceBottom']} | free left {zone['freeLeft']} right {zone['freeRight']} → {zone['side']}")
        else: print(f"{i:2d} {zone['clip']} from={s['fromFrame']:5d} zoom {zone['zoom']:.2f} {zone['shot']:7s} face y {zone['faceTop']}–{zone['faceBottom']} | free top {zone['freeTop']} bottom {zone['freeBottom']}")
    json.dump(rows, open(a.out, "w"), indent=1); print("FACE_ZONES_DONE", a.out)

if __name__ == "__main__":
    main()
