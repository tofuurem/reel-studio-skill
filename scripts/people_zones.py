#!/usr/bin/env python3
"""Where are the people in each shot? (macOS Vision) → the crop of every landscape camera segment, decided BEFORE the proxies.

Usage: work/venv/bin/python -I people_zones.py [--cutlist work/cutlist.json] [--out work/people_zones.json] [--fps 4] [--sheet] [--force]

A 16:9 camera clip cut to a 9:16 canvas keeps under a third of its width; a centre crop loses whoever stands at the edge
(Halloween reel, 2026-11-04: the kick, «стоит фоткает», a girl in the shop — all half out of frame until placed by hand).
For every main segment that needs a crop (common.needs_crop: a camera clip wider than a portrait canvas, no CapCut framing)
this samples the SOURCE at --fps (default numbers.json peopleFps), runs VNDetectHumanRectanglesRequest + face rectangles,
and picks the crop centre per frame: the biggest person plus every other big one (≥ peopleNearArea of its area) that still
fits the crop; when the main person alone is wider than the crop, their face. The per-frame centres are smoothed
(peopleSmoothSec), limited in speed (peoplePanSpeed of the frame width per second) and written as keyframes every
peopleKeyEvery s — or ONE centre when the subject moves less than peoplePanMin (a still shot must not wobble).
Overrides: a segment's "cropX" (plan.json opts → cut list): 0.3 = fixed centre, [0.6, 0.3] = pan from → to. Nobody found →
the frame centre, listed as WARNING (set cropX for it). Costumes (a banana suit) are often not «people»; faces then decide.
Output work/people_zones.json {"segments": [{seg, clip, src, srcStart, srcEnd, srcW, srcH, mode auto|manual|centre, keys
[[source s, centre 0–1]], found, frames}]}; make_proxies.py crops from it (and refuses to centre-crop without it).
Detections are cached per clip in work/people/<clip>.json, so a re-cut only scans new seconds. --sheet writes
work/people/sheet_NN.jpg: the frame of every segment (start and end too when it pans) with the crop drawn in red — look at it
before the proxies are encoded.
"""
import argparse, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HWACCEL, N, atomic_json, need_vision, clip_id, load_json, needs_crop, probe, src_dur


def vision(img_path):
    """People (full body) and faces in one image: boxes 0–1 of the frame, top-left origin."""
    need_vision("people_zones.py")
    import Vision, Quartz
    from Foundation import NSURL
    s = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(img_path), None); img = Quartz.CGImageSourceCreateImageAtIndex(s, 0, None)
    body = Vision.VNDetectHumanRectanglesRequest.alloc().init(); body.setUpperBodyOnly_(False)
    face = Vision.VNDetectFaceRectanglesRequest.alloc().init()
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([body, face], None)
    box = lambda r: {"x": round(r.boundingBox().origin.x, 4), "y": round(1 - r.boundingBox().origin.y - r.boundingBox().size.height, 4),
                     "w": round(r.boundingBox().size.width, 4), "h": round(r.boundingBox().size.height, 4), "c": round(float(r.confidence()), 2)}
    return [box(r) for r in body.results() or [] if r.confidence() >= N["peopleMinConf"]], [box(r) for r in face.results() or []]


def scan(src, a, b, fps, cache):
    """Detections for [a, b] of one source, from the cache or a fresh decode (videotoolbox, 640 px wide)."""
    frames = cache.setdefault("frames", [])
    have = [f for f in frames if a - 0.2 <= f["t"] <= b + 0.2]
    if len(have) >= max(1, int((b - a) * fps * 0.8) - 1): return have
    with tempfile.TemporaryDirectory(dir="work") as tmp:
        t0 = max(0.0, a - 0.25)
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", *HWACCEL, "-ss", f"{t0:.3f}", "-t", f"{b - t0 + 0.25:.3f}", "-i", src,
                        "-an", "-vf", f"fps={fps},scale=640:-2", "-q:v", "4", os.path.join(tmp, "%05d.jpg")], check=True)
        new = []
        for i, name in enumerate(sorted(n for n in os.listdir(tmp) if n.endswith(".jpg") and not n.startswith("."))):   # ._*.jpg on exFAT
            people, faces = vision(os.path.join(tmp, name))
            new.append({"t": round(t0 + (i + 0.5) / fps, 3), "people": people, "faces": faces})
    keep = [f for f in frames if not (new and new[0]["t"] - 0.01 <= f["t"] <= new[-1]["t"] + 0.01)]
    cache["frames"] = sorted(keep + new, key=lambda f: f["t"])
    return [f for f in cache["frames"] if a - 0.2 <= f["t"] <= b + 0.2]


def subject(fr, span, prev=None):
    """Crop centre for one frame (None = nobody): the main person and the big ones next to them that still fit. The main
    person is sticky: among everyone at least peopleStickyArea as big as the biggest, the one nearest the previous centre —
    two people who do not fit together (one standing, one crouching) otherwise swap «biggest» and the crop swings between."""
    area = lambda q: q["w"] * q["h"]; mid = lambda q: q["x"] + q["w"] / 2
    boxes = sorted(fr["people"], key=area, reverse=True)
    if not boxes and fr["faces"]:   # no body found (close-up, costume): the face
        fs = fr["faces"] if prev is None else sorted(fr["faces"], key=lambda f: abs(mid(f) - prev))
        return mid(max(fs, key=area) if prev is None else fs[0])
    if not boxes: return None
    fit = span * N["peopleFitMargin"]
    big = [q for q in boxes if area(q) >= N["peopleStickyArea"] * area(boxes[0])]
    main = boxes[0] if prev is None else min(big, key=lambda q: abs(mid(q) - prev))
    lo, hi = main["x"], main["x"] + main["w"]
    if hi - lo > fit:   # the main person alone is wider than the crop: keep their face in
        fs = [f for f in fr["faces"] if lo - 0.02 <= f["x"] + f["w"] / 2 <= hi + 0.02]
        return (max(fs, key=area)["x"] + max(fs, key=area)["w"] / 2) if fs else (lo + hi) / 2
    for q in boxes[1:]:
        if area(q) < N["peopleNearArea"] * area(main): break   # background crowd does not pull the crop
        nlo, nhi = min(lo, q["x"]), max(hi, q["x"] + q["w"])
        if nhi - nlo <= fit: lo, hi = nlo, nhi
    return (lo + hi) / 2


def path(frames, a, b, span):
    """Smoothed, speed-limited keyframes [[t, c]] over [a, b]; one key pair when the subject barely moves; None if nobody."""
    pts, prev = [], None
    for f in frames:
        c = subject(f, span, prev)
        if c is not None: pts.append((f["t"], c)); prev = c
    if not pts: return None, 0
    lim = lambda c: max(span / 2, min(1 - span / 2, c))
    ts = [t for t, _ in pts]; cs = [c for _, c in pts]
    def at(t):   # linear between detections, held at the ends
        if t <= ts[0]: return cs[0]
        if t >= ts[-1]: return cs[-1]
        k = next(i for i in range(1, len(ts)) if ts[i] >= t)
        return cs[k - 1] + (cs[k] - cs[k - 1]) * (t - ts[k - 1]) / max(1e-6, ts[k] - ts[k - 1])
    step = N["peopleKeyEvery"]; n = max(1, round((b - a) / step)); grid = [a + (b - a) * i / n for i in range(n + 1)]
    half = N["peopleSmoothSec"] / 2
    sm = [sum(at(t + d) for d in (-half, -half / 2, 0, half / 2, half)) / 5 for t in grid]
    if max(sm) - min(sm) < N["peoplePanMin"]:
        c = lim(sorted(cs)[len(cs) // 2]); return [[round(a, 3), round(c, 4)], [round(b, 3), round(c, 4)]], len(pts)
    out = [sm[0]]
    for i in range(1, len(sm)):   # a fast whip of the subject becomes a pan the eye can follow
        d = N["peoplePanSpeed"] * (grid[i] - grid[i - 1])
        out.append(out[-1] + max(-d, min(d, sm[i] - out[-1])))
    return [[round(t, 3), round(lim(c), 4)] for t, c in zip(grid, out)], len(pts)


def sheet(rows, cl):
    """Frames with the crop in red, 6 × 4 per page → work/people/sheet_NN.jpg."""
    for old in [f for f in os.listdir("work/people") if f.startswith("sheet_")]: os.remove(os.path.join("work/people", old))
    tiles = []
    for r in rows:
        ks = r["keys"]; picks = [(ks[0][0] + ks[-1][0]) / 2] if len({c for _, c in ks}) == 1 else [ks[0][0] + 0.1, ks[-1][0] - 0.1]
        for t in picks:
            c = next((c for tt, c in reversed(ks) if tt <= t), ks[0][1]); tiles.append((r["src"], t, c, r["srcW"], r["srcH"]))
    with tempfile.TemporaryDirectory(dir="work") as tmp:
        for i, (src, t, c, w, h) in enumerate(tiles):
            W = 320; H = round(W * h / w / 2) * 2; cw = round(H * cl["canvas"]["w"] / cl["canvas"]["h"]); x = max(0, min(W - cw, round(c * W - cw / 2)))
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{max(0, t):.3f}", "-i", src, "-frames:v", "1",
                            "-vf", f"scale={W}:{H},drawbox=x={x}:y=0:w={cw}:h={H}:color=red@0.9:t=3", os.path.join(tmp, f"{i:04d}.jpg")], check=True)
        per = 24
        for p in range(0, len(tiles), per):
            lst = os.path.join(tmp, f"list{p}.txt")
            open(lst, "w").write("".join(f"file '{os.path.join(tmp, f'{i:04d}.jpg')}'\n" for i in range(p, min(len(tiles), p + per))))
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-vf", "tile=6x4:padding=4", "-frames:v", "1",
                            f"work/people/sheet_{p // per + 1:02d}.jpg"], check=True)
    print("sheets:", *sorted(f"work/people/{f}" for f in os.listdir("work/people") if f.startswith("sheet_")))


def main():
    ap = argparse.ArgumentParser(description="people-aware crop centres for landscape camera segments (Apple Vision)")
    ap.add_argument("--cutlist", default="work/cutlist.json"); ap.add_argument("--out", default="work/people_zones.json")
    ap.add_argument("--fps", type=float, default=N["peopleFps"]); ap.add_argument("--sheet", action="store_true", help="write work/people/sheet_NN.jpg with the crops drawn")
    ap.add_argument("--force", action="store_true", help="ignore the detection cache")
    a = ap.parse_args()
    cl = json.load(open(a.cutlist)); os.makedirs("work/people", exist_ok=True)
    cw, ch = cl["canvas"].get("w") or 1080, cl["canvas"].get("h") or 1920
    infos, caches, rows, warn = {}, {}, [], []
    for i, s in enumerate(cl["main"]):
        if s.get("materialType", "video") != "video" or not os.path.exists(s["path"]): continue
        src = s["path"]; info = infos.get(src) or infos.setdefault(src, probe(src))
        if not needs_crop(cl, s, info): continue
        cid = clip_id(src); span = info["h"] * cw / ch / info["w"]
        a0, b0 = float(s["srcStart"]), float(s["srcStart"]) + src_dur(s)
        row = {"seg": i, "clip": cid, "src": src, "srcStart": round(a0, 3), "srcEnd": round(b0, 3), "srcW": info["w"], "srcH": info["h"], "frames": 0, "found": 0}
        lim = lambda c: max(span / 2, min(1 - span / 2, float(c)))
        if s.get("cropX") is not None:
            x = s["cropX"]; c0, c1 = (x, x) if not isinstance(x, (list, tuple)) else (x[0], x[-1])
            row.update(mode="manual", keys=[[round(a0, 3), round(lim(c0), 4)], [round(b0, 3), round(lim(c1), 4)]])
        else:
            cp = f"work/people/{cid}.json"
            cache = caches.get(cid) or caches.setdefault(cid, {} if a.force else load_json(cp, {}) or {})
            frames = scan(src, a0, b0, a.fps, cache); atomic_json(cache, cp)
            keys, found = path(frames, a0, b0, span)
            row.update(frames=len(frames), found=found)
            if keys: row.update(mode="auto", keys=keys)
            else: row.update(mode="centre", keys=[[round(a0, 3), 0.5], [round(b0, 3), 0.5]]); warn.append(f"seg {i} {cid} {a0:.1f}–{b0:.1f} s: nobody found — centre crop (set cropX in plan.json if wrong)")
        rows.append(row)
        ks = row["keys"]; move = "" if len({c for _, c in ks}) == 1 else f" → {ks[-1][1]:.2f} (pan, {len(ks)} keys)"
        print(f"{i:3d} {cid:10s} {a0:8.2f}–{b0:8.2f} {row['mode']:6s} centre {ks[0][1]:.2f}{move}  people in {row['found']}/{row['frames']} frames", flush=True)
    atomic_json({"canvas": {"w": cw, "h": ch}, "fps": a.fps, "segments": rows}, a.out)
    for w in warn: print("WARNING:", w)
    if a.sheet and rows: sheet(rows, cl)
    print("PEOPLE_ZONES_DONE", a.out, f"{len(rows)} segment(s) cropped" + ("" if rows else " — nothing to crop (landscape canvas, vertical sources or CapCut framing)"))


if __name__ == "__main__":
    main()
