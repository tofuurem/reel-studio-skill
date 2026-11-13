#!/usr/bin/env python3
"""Measure the two seams that depend on the picture → work/seams.json, read by gen_timeline.py.

Usage: work/venv/bin/python -I seams.py <project> [--cutlist work/cutlist.json] [--public reel/public]
Run after gen_timeline.py (it needs work/timeline_zoom.json and the proxies), then run gen_timeline.py again.

- "match" (a match cut on the person): the face in the last frame of the outgoing clip and in the first frame of the
  incoming one (macOS Vision), both mapped to the canvas the way Clip.tsx places them (face_zones.to_canvas: fit, CapCut
  framing, punch + drift). The incoming clip then starts moved and zoomed so its head lands where the previous head was
  and eases to its own framing over seamMatchFrames. The zoom also has to keep the canvas covered after the move; beyond
  seamMatchMaxScale the cut stays a dissolve (WARNING) — pick another moment or another take.
- "bodywipe" (someone walks across the outgoing shot): the outgoing clip keeps playing over the cut while the passing
  person's trailing edge reveals the next shot behind them. The person is the biggest box that moves sideways in the 2.5 s
  after the cut (Vision human rectangles at the full frame rate); the path is their trailing edge in canvas px per frame
  until they leave the frame. Put the cut on the frame they ENTER the shot (a WARNING says when they start mid-frame).
Linux (no Vision): nothing is measured; the cuts fall back to a dissolve / a plain wipe.
Prints SEAMS_DONE.
"""
import argparse, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, atomic_json, load_json, proxy_file
import face_zones as fz


def grab(proxy, t, out, w=640):
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{max(0.0, t):.3f}", "-i", proxy, "-frames:v", "1", "-vf", f"scale={w}:-2", out], check=True)


def biggest(faces):
    return max(faces, key=lambda b: b["w"] * b["h"]) if faces else None


def centre(box, z, pw, ph):
    s = fz.to_screen(box, z, pw, ph)
    return s["x"] + s["w"] / 2, s["y"] + s["h"] / 2, s["h"]


def match(p, q, public, fps, tmp):
    pp, qp = proxy_file(public, p["clip"]), proxy_file(public, q["clip"])
    (pw, ph), (qw, qh) = fz.proxy_size(pp), fz.proxy_size(qp)
    if "contain" in (p.get("fit"), q.get("fit")): return None, "a letterboxed (contain) clip — a match cut needs full-frame clips"
    a_img, b_img = os.path.join(tmp, "a.jpg"), os.path.join(tmp, "b.jpg")
    grab(pp, (p["tb"] + (p["durFrames"] - 1) * p.get("speed", 1)) / fps, a_img); grab(qp, q["tb"] / fps, b_img)
    fa, fb = biggest(fz.detect(a_img)), biggest(fz.detect(b_img))
    if not fa or not fb: return None, "no face on one side of the cut"
    ax, ay, ah = centre(fa, p, pw, ph)                     # the outgoing clip at its end: punch + drift
    bx, by, bh = centre(fb, dict(q, drift=0), qw, qh)      # the incoming clip at its first frame: punch only
    W, H = fz.W, fz.H
    need = [ah / bh]
    for A, B, S in ((ax, bx, W), (ay, by, H)):            # the moved, zoomed picture still covers the canvas
        if B > 1: need.append(A / B)
        if S - B > 1: need.append((S - A) / (S - B))
    k = max(1.0, *need)
    if k > N["seamMatchMaxScale"]: return None, f"needs a {k:.2f}× zoom to line the heads up (max {N['seamMatchMaxScale']})"
    return {"x": round(bx, 1), "y": round(by, 1), "dx": round(ax - bx, 1), "dy": round(ay - by, 1), "k": round(k, 3)}, f"head moves {ax - bx:+.0f}, {ay - by:+.0f} px, zoom {k:.2f}"


def bodywipe(p, public, fps, tmp):
    import people_zones as pz
    pp = proxy_file(public, p["clip"]); pw, ph = fz.proxy_size(pp)
    sp = float(p.get("speed", 1) or 1); t0 = (p["tb"] + p["durFrames"] * sp) / fps
    # one sample per TIMELINE frame: a sped-up clip shows sp source seconds per second
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{t0:.3f}", "-t", f"{2.5 * sp:.3f}", "-i", pp, "-an", "-vf", f"fps={fps / sp:.4f},scale=640:-2",
                    os.path.join(tmp, "w%04d.jpg")], check=True)
    frames = [pz.vision(os.path.join(tmp, n))[0] for n in sorted(x for x in os.listdir(tmp) if x.startswith("w") and x.endswith(".jpg"))]
    big = [[b for b in people if b["h"] >= 0.35] for people in frames]
    if not any(big): return None, "nobody big enough crosses the shot in the 2.5 s after the cut"
    # follow the box nearest to the previous one, starting from the first frame anyone is there
    i0 = next(i for i, b in enumerate(big) if b); track = []; prev = None
    for i in range(i0, len(big)):
        if not big[i]: break
        b = min(big[i], key=lambda r: abs(r["x"] + r["w"] / 2 - prev) if prev is not None else -r["w"] * r["h"])
        prev = b["x"] + b["w"] / 2; track.append(b)
    if len(track) < 4: return None, "the person is visible for fewer than 4 frames"
    if i0 + len(track) >= len(big): return None, "the person is still in frame 2.5 s after the cut — the wipe would snap open at its end; pick a cut where they walk out"
    move = (track[-1]["x"] + track[-1]["w"] / 2) - (track[0]["x"] + track[0]["w"] / 2)
    if abs(move) < 0.2: return None, f"the person moves only {abs(move):.0%} of the frame width — not a crossing"
    d = "left" if move < 0 else "right"
    edge = [b["x"] + b["w"] if d == "left" else b["x"] for b in track]   # the trailing edge, 0–1 of the proxy frame
    xs = [fz.to_canvas(e, 0.5, p, pw, ph, N["punchDrift"])[0] for e in edge]
    W = fz.W; far = W if d == "left" else 0; gone = -1 if d == "left" else W + 1
    note = ""
    if i0 > 0 or abs(xs[0] - far) > 0.25 * W: note = f" (they start {abs(xs[0] - far) / W:.0%} of the width in — cut {i0} frame(s) later or earlier so they enter on the cut)"
    xs = [far] * i0 + xs   # frame k of the path = frame k after the cut: the edge stays at the far side until they appear
    xs = xs[:73] + [gone] * 2   # always end fully open
    return {"xs": [round(x, 1) for x in xs], "dir": d}, f"{len(xs)} frames, walking {d}{note}"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--cutlist", default="work/cutlist.json"); ap.add_argument("--public", default="reel/public")
    a = ap.parse_args(); os.chdir(os.path.abspath(a.project))
    cl = load_json(a.cutlist); zoom = load_json(os.path.join(os.path.dirname(a.cutlist) or ".", "timeline_zoom.json"), {})
    if not cl or not zoom: sys.exit("run gen_timeline.py first (work/cutlist.json, work/timeline_zoom.json)")
    cv = cl.get("canvas") or {}; fz.W, fz.H = int(cv.get("w", 1080)), int(cv.get("h", 1920)); fps = cl["fps"]
    rows = zoom["segments"]; by_from = {str(s["fromFrame"]): s for s in cl["main"]}
    want = [(i, by_from.get(str(r["fromFrame"]), {}).get("transition")) for i, r in enumerate(rows) if i > 0]
    want = [(i, k) for i, k in want if k in ("match", "bodywipe")]
    if sys.platform != "darwin":
        print("no macOS Vision: match / bodywipe cuts stay a dissolve / a plain wipe"); atomic_json({"cuts": {}}, "work/seams.json"); print("SEAMS_DONE work/seams.json"); return
    out = {}
    for i, k in want:
        p, q = rows[i - 1], rows[i]
        with tempfile.TemporaryDirectory(dir="work") as tmp:
            res, why = match(p, q, a.public, fps, tmp) if k == "match" else bodywipe(p, a.public, fps, tmp)
        tag = f"{k} at {q.get('tl', q['fromFrame'] / fps):.1f}s ({p['clip']} → {q['clip']})"
        if res is None: print(f"WARNING: {tag}: {why} — falls back to {'a dissolve' if k == 'match' else 'a plain wipe'}"); continue
        out[str(q["fromFrame"])] = {"match" if k == "match" else "wipe": res}; print(f"{tag}: {why}")
    atomic_json({"cuts": out}, "work/seams.json")
    print(f"SEAMS_DONE work/seams.json: {len(out)} of {len(want)} measured — run gen_timeline.py again")


if __name__ == "__main__":
    main()
