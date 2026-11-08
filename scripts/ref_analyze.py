#!/usr/bin/env python3
"""Measure a reference reel («сделай как тут») — rhythm, framing, on-screen text, loudness — so its STYLE can be matched.

Usage: work/venv/bin/python -I ref_analyze.py <project> <video> [--name NAME] [--ocr-every 0.5] [--no-ocr]
→ work/refs/<name>/ref.json, ref.md (numbers + how they map onto this skill's knobs), sheet.jpg (one frame per shot,
  numbered in order, 6 per row). Prints REF_DONE <ref.md>.

What it measures
  cuts      every hard cut AND every short dissolve (≤ 10 frames): a frame-difference spike over the local motion level, plus a
            jump in the 8-frame difference for dissolves; jump cuts inside one take (the speaker shifts) count — they are
            the rhythm of a talking-head reel. Long cross-fades and whip-pans may be missed or doubled: check the sheet.
  rhythm    shot count, median / mean / shortest / longest shot, cuts per 10 s, the hook (cuts in the first 3 s, first cut).
  framing   per shot (middle frame, Apple Vision faces): the largest face's height in the frame → close-up / medium close-up
            / medium / wide / no face (screens, b-roll), as a share of the running time.
  text      Apple Vision OCR (ru + en) every --ocr-every s: share of time with text, where it sits (top / middle / bottom), the
            caption rail (the band where the text changes most often): its y and letter height on a 1080×1920 canvas, words
            and lines per page, page length, ALL CAPS share.
  sound     integrated loudness and loudness range (EBU R128).
Only the style is used — never the reel's footage, music, text, people or logos (inputs/reference-reel.md).
"""
import argparse, difflib, glob, json, os, re, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, ascii_stem, atomic_json, probe

FW = 72   # analysis width for cut detection (px)


def frames_gray(path, fps, w, h):
    hh = max(2, round(FW * h / w / 2) * 2)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-an", "-vf", f"fps={fps},scale={FW}:{hh}:flags=area,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, hh, FW).astype(np.float32)


def detect_cuts(F, fps):
    """Frame indices where a new shot starts."""
    n = len(F)
    if n < 3: return []
    d1 = np.r_[0, np.abs(np.diff(F, axis=0)).mean((1, 2))]
    def base(d, i, r=10, skip=2):
        lo, hi = max(0, i - r), min(len(d), i + r + 1)
        w = np.r_[d[lo:max(lo, i - skip)], d[min(hi, i + skip + 1):hi]]
        return float(np.median(w)) if len(w) else 0.0
    cuts = []
    for i in range(1, n):   # hard cuts: a one-frame spike well over the local motion
        if d1[i] >= 5 and d1[i] >= 3 * base(d1, i) + 2 and d1[i] == d1[max(1, i - 2): i + 3].max(): cuts.append(i)
    k = 8   # short dissolves: the picture 8 frames apart jumps, no single-frame spike inside
    d8 = np.r_[np.zeros(k), np.abs(F[k:] - F[:-k]).mean((1, 2))]
    for i in range(k, n):
        if d8[i] >= 10 and d8[i] >= 2.5 * base(d8, i, 16, 6) + 3 and d8[i] == d8[max(k, i - 4): i + 5].max():
            c = i - k // 2
            if all(abs(c - x) > k for x in cuts): cuts.append(c)
    cuts.sort(); out = []
    for c in cuts:   # shots shorter than 4 frames are flashes, not shots
        if not out or c - out[-1] >= 4: out.append(c)
    return out


def grab(path, t, out, w=360):
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", f"scale={w}:-2", "-q:v", "3", out])
    return os.path.exists(out)


def vision(img_path, faces=True, text=False):
    import Vision, Quartz
    from Foundation import NSURL
    src = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(img_path), None)
    if src is None: return [], []
    img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None); reqs = []
    if faces: fr = Vision.VNDetectFaceRectanglesRequest.alloc().init(); reqs.append(fr)
    if text:
        tr = Vision.VNRecognizeTextRequest.alloc().init(); tr.setRecognitionLevel_(0); tr.setUsesLanguageCorrection_(False)
        tr.setRecognitionLanguages_(["ru-RU", "en-US"]); reqs.append(tr)
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_(reqs, None)
    fs = [r.boundingBox().size.height for r in (fr.results() or [])] if faces else []
    ts = []
    if text:
        for r in (tr.results() or []):
            c = r.topCandidates_(1)
            if not c or c[0].confidence() < 0.4: continue
            b = r.boundingBox(); s = str(c[0].string()).strip()
            if len(re.sub(r"\W", "", s)) < 2: continue
            ts.append({"text": s, "cy": 1 - (b.origin.y + b.size.height / 2), "h": b.size.height, "x": b.origin.x, "w": b.size.width})
    return fs, ts


SIZES = [(0.28, "close-up"), (0.14, "medium close-up"), (0.07, "medium"), (0.025, "wide")]


def shot_size(face_h):
    if not face_h: return "no face"
    return next((n for t, n in SIZES if face_h >= t), "wide")


def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0?", "-af", "ebur128=framelog=quiet", "-f", "null", "-"], capture_output=True, text=True).stderr
    g = lambda k: (lambda m: float(m[-1]) if m else None)(re.findall(k + r":\s+(-?[\d.]+)", r))
    return g("I"), g("LRA")


def same_text(a, b):
    """OCR reads the same caption a little differently from frame to frame: ≥ 70 % alike is the same page."""
    return bool(a) and bool(b) and difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.7


def text_stats(samples, step, W, H):
    """samples: [(t, [lines])] → where the text lives and how the caption rail behaves."""
    if not samples: return {}
    with_text = [s for s in samples if s[1]]
    rep = {"textShare": round(len(with_text) / len(samples), 2)}
    if not with_text: return rep
    lines = [l for _, ls in with_text for l in ls]
    third = lambda cy: "top" if cy < 1 / 3 else "middle" if cy < 2 / 3 else "bottom"
    rep["where"] = {k: round(sum(third(l["cy"]) == k for l in lines) / len(lines), 2) for k in ("top", "middle", "bottom")}
    # the rail: 5 %-bands; the one whose text changes most often between samples
    band = lambda cy: int(cy * 20)
    changes, seen = {}, {}
    for t, ls in samples:
        by = {}
        for l in ls: by.setdefault(band(l["cy"]), []).append(l["text"])
        for b, txt in by.items():
            key = " ".join(txt)
            if not same_text(seen.get(b), key): changes[b] = changes.get(b, 0) + 1
            seen[b] = key
        for b in list(seen):
            if b not in by: seen[b] = None
    if not changes: return rep
    rail = max(changes, key=changes.get)
    rl = [(t, [l for l in ls if abs(band(l["cy"]) - rail) <= 1]) for t, ls in samples]
    rl_lines = [l for _, ls in rl for l in ls]
    scale = H * 1080 / W   # the reel's height in px on a 1080-wide canvas (1920 for 9:16): y and letter height in canvas px
    pages, cur, start = [], None, None
    for t, ls in rl:
        txt = " ".join(l["text"] for l in sorted(ls, key=lambda l: (round(l["cy"], 2), l["x"]))) or None
        if not (txt == cur or same_text(txt, cur)):
            if cur: pages.append((cur, t - start))
            cur, start = txt, t
    if cur: pages.append((cur, samples[-1][0] + step - start))
    words = [len(p.split()) for p, _ in pages]
    nlines = [len({round(l["cy"], 2) for l in ls}) for _, ls in rl if ls]
    letters = "".join(l["text"] for l in rl_lines); alpha = [c for c in letters if c.isalpha()]
    rep["rail"] = {"y": round(float(np.median([l["cy"] for l in rl_lines])) * scale), "yPct": round(float(np.median([l["cy"] for l in rl_lines])) * 100), "textHeightPx": round(float(np.median([l["h"] for l in rl_lines])) * scale),
                   "pages": len(pages), "wordsPerPage": float(np.median(words)) if words else None, "linesPerPage": float(np.median(nlines)) if nlines else None,
                   "pageSec": round(float(np.median([d for _, d in pages])), 2) if pages else None,
                   "allCaps": round(sum(c.isupper() for c in alpha) / len(alpha), 2) if alpha else None,
                   "examples": [p for p, _ in pages[:6]]}
    return rep


def advice(r):
    """Map the measurements onto this skill's knobs (plain sentences for ref.md)."""
    out = []; s = r["rhythm"]
    if s["medianShot"] is not None:
        if s["medianShot"] < 1.6: out.append(f"median shot {s['medianShot']} s: the **action** tempo (motion-design.md «Two tempos»: cuts on the beat, 1–2 beats per shot) — or a very tight talking-head cut: in plan.json keep clauses short and cut the breaths.")
        elif s["medianShot"] < 3.5: out.append(f"median shot {s['medianShot']} s: a brisk talking-head cut — one clause per segment in plan.json, punch-ins on the jump cuts, cutaways every 2–3 clauses.")
        else: out.append(f"median shot {s['medianShot']} s: the calm profile (this skill's default, 2–8 s per clause).")
    h = r["hook"]
    out.append(f"hook: {h['cutsFirst3s']} cut(s) in the first 3 s, the first at {h['firstCut']} s" + (", text on screen from the first second" if h.get("textAtStart") else "") + " — match it in the cold open (storyboard.md).")
    fr = r["framing"]
    if fr:
        top = max(fr, key=fr.get); out.append(f"framing: mostly {top} ({round(fr[top] * 100)} % of the time)" + ("; the punch zoom (gen_timeline --punch) gives the closer shots" if fr.get("close-up", 0) > 0.3 else ""))
    t = r.get("text") or {}
    rail = t.get("rail")
    if rail:
        out.append(f"captions: a rail at y ≈ {rail['y']} px, {rail['yPct']} % of the height (ours on 9:16: bottom ≈ 1520 px = 79 %), letters ≈ {rail['textHeightPx']} px tall (ours: 50 px Montserrat ≈ 36 px capitals), "
                   f"{rail['wordsPerPage']} words / {rail['linesPerPage']} line(s) per page, {rail['pageSec']} s a page (ours: ≤ 8 words, ≤ 3.4 s)"
                   + (", ALL CAPS" if (rail.get("allCaps") or 0) > 0.8 else "") + ". Per-word highlighting is not used here (non-negotiable) even if the reference does it.")
    if r["sound"]["lufs"] is not None: out.append(f"loudness {r['sound']['lufs']} LUFS, LRA {r['sound']['lra']} LU (ours: {N['targetLufs']} LUFS, LRA {N['lraMin']}–{N['lraMax']}).")
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("video"); ap.add_argument("--name")
    ap.add_argument("--ocr-every", type=float, default=0.5); ap.add_argument("--no-ocr", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.video): sys.exit(f"no such file: {a.video}")
    mac = sys.platform == "darwin"
    info = probe(a.video); W, H, dur = info["w"], info["h"], info["dur"]
    if not (W and H and dur): sys.exit("not a video (no picture or no duration)")
    name = ascii_stem(a.name or os.path.splitext(os.path.basename(a.video))[0])[:60]
    out = os.path.join(os.path.abspath(a.project), "work/refs", name); os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "_*.jpg")): os.remove(f)   # leftovers of an earlier run
    fps = min(30.0, info["fps"] or 30.0)
    F = frames_gray(a.video, fps, W, H)
    cuts = detect_cuts(F, fps); n = len(F)
    bounds = [0] + cuts + [n]; shots = [(bounds[i] / fps, bounds[i + 1] / fps) for i in range(len(bounds) - 1)]
    lens = np.array([b - s for s, b in shots])
    print(f"{len(shots)} shots, {len(cuts)} cuts over {dur:.1f} s")
    # per shot: a middle frame → the sheet and the framing
    framing, shot_rows = {}, []
    for i, (s, e) in enumerate(shots):
        img = os.path.join(out, f"_s{i:03d}.jpg"); grab(a.video, (s + e) / 2, img)
        fh = max(vision(img)[0] or [0]) if mac and os.path.exists(img) else None
        size = shot_size(fh) if fh is not None else "unknown"
        framing[size] = framing.get(size, 0) + (e - s)
        shot_rows.append({"n": i + 1, "start": round(s, 2), "len": round(e - s, 2), "faceH": round(fh, 3) if fh else None, "size": size})
    framing = {k: round(v / max(dur, 1e-6), 2) for k, v in sorted(framing.items(), key=lambda kv: -kv[1])}
    jpgs = sorted(glob.glob(os.path.join(out, "_s*.jpg")))
    if jpgs:
        cols = 6; rows = -(-len(jpgs) // cols)
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-framerate", "1", "-i", os.path.join(out, "_s%03d.jpg"),
                        "-vf", f"scale=180:-2,tile={cols}x{rows}:padding=4:color=0x222222", "-frames:v", "1", "-q:v", "3", os.path.join(out, "sheet.jpg")])
    # on-screen text
    text, start_text = {}, None
    if mac and not a.no_ocr:
        step = max(a.ocr_every, dur / 240)   # ≤ 240 OCR frames, decoded in ONE ffmpeg pass (a seek per frame took minutes)
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", a.video, "-an", "-vf", f"fps=1/{step},scale=720:-2", "-q:v", "3", os.path.join(out, "_o%04d.jpg")])
        ocr = sorted(glob.glob(os.path.join(out, "_o*.jpg")))
        samples = [(round(i * step, 2), vision(f, faces=False, text=True)[1]) for i, f in enumerate(ocr)]
        text = text_stats(samples, step, W, H); start_text = any(ls for t, ls in samples if t < 1.0)
        for f in ocr: os.remove(f)
    lufs, lra = loudness(a.video) if info["has_audio"] else (None, None)
    rep = {"video": os.path.abspath(a.video), "size": f"{W}x{H}", "fps": info["fps"], "duration": round(dur, 2),
           "rhythm": {"shots": len(shots), "cuts": len(cuts), "medianShot": round(float(np.median(lens)), 2), "meanShot": round(float(lens.mean()), 2),
                      "shortest": round(float(lens.min()), 2), "longest": round(float(lens.max()), 2), "cutsPer10s": round(len(cuts) / dur * 10, 1)},
           "hook": {"cutsFirst3s": sum(1 for c in cuts if c / fps < 3), "firstCut": round(cuts[0] / fps, 2) if cuts else None,
                    "textAtStart": start_text},
           "framing": framing, "text": text, "sound": {"lufs": lufs, "lra": lra},
           "cutTimes": [round(c / fps, 2) for c in cuts], "shots": shot_rows}
    src = a.video + ".source.json"
    if os.path.exists(src): rep["source"] = json.load(open(src))
    rep["advice"] = advice(rep)
    atomic_json(rep, os.path.join(out, "ref.json"))
    r = rep["rhythm"]
    md = [f"# Reference: {name}", "", f"`{rep['video']}` — {rep['size']}, {rep['fps']} fps, {rep['duration']} s" + (f" — {rep['source'].get('title')!r} by {rep['source'].get('uploader')}, {rep['source'].get('url')}" if rep.get("source") else ""), "",
          "| | |", "|---|---|",
          f"| shots | {r['shots']} ({r['cutsPer10s']} cuts per 10 s) |", f"| shot length | median {r['medianShot']} s, mean {r['meanShot']} s, {r['shortest']}–{r['longest']} s |",
          f"| hook | {rep['hook']['cutsFirst3s']} cut(s) in the first 3 s, first cut at {rep['hook']['firstCut']} s |",
          "| framing | " + ", ".join(f"{k} {round(v * 100)} %" for k, v in framing.items()) + " |"]
    if text:
        md.append(f"| text on screen | {round(text.get('textShare', 0) * 100)} % of the time" + (", " + ", ".join(f"{k} {round(v * 100)} %" for k, v in text.get("where", {}).items()) if text.get("where") else "") + " |")
        if text.get("rail"):
            rl = text["rail"]
            md.append(f"| caption rail | y ≈ {rl['y']} px ({rl['yPct']} % of the height), letters ≈ {rl['textHeightPx']} px, {rl['wordsPerPage']} words / {rl['linesPerPage']} line(s) a page, {rl['pageSec']} s a page, ALL CAPS {round((rl['allCaps'] or 0) * 100)} % |")
    md.append(f"| sound | {lufs} LUFS, LRA {lra} LU |")
    md += ["", "## How it maps onto this skill", ""] + [f"- {x}" for x in rep["advice"]] + ["", "Sheet: `sheet.jpg` (shots in order, 6 per row). Shots:", "",
          "| # | start | length | framing |", "|---|---|---|---|"] + [f"| {s['n']} | {s['start']} | {s['len']} | {s['size']} |" for s in shot_rows]
    if text.get("rail", {}).get("examples"): md += ["", "Caption pages (OCR, first six): " + " / ".join(f"«{x}»" for x in text["rail"]["examples"])]
    open(os.path.join(out, "ref.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md[:12]))
    print("REF_DONE", os.path.join(out, "ref.md"))


if __name__ == "__main__":
    main()
