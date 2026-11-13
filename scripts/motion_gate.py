#!/usr/bin/env python3
"""Look at the seams of a finished render, not only its frames: a sheet of every cut and a list of dead stretches.

Usage: work/venv/bin/python -I motion_gate.py <project> <render.mp4> [--max 30]
→ work/qa/cuts_NN.jpg: one row per cut — frames cut−2, cut−1, cut, cut+1 (from work/cutlist.json, or work/shots.json for an
  action reel); the console lists each row with its seam kind. Read it as the viewer meets the cut: does the eye land where it was on
  the frame before (match, hand-off), does something move across the cut, does an effect seam come right after another?
→ FROZEN lines: runs of more than 18 frames where the picture does not change (mean difference of 64 px grey frames < 0.25)
  outside the designed holds — a freeze, an end card or a still board you meant are fine; anything else reads as «the video
  is waiting» (motion-design.md «No idle wobble» is about the opposite mistake: do not fill them with fake motion either).
→ the seam count: effect seams vs plain cuts (the seam budget, transitions.md).
Prints MOTION_GATE_DONE.
"""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_json

PLAIN = {None, "dissolve", "cut"}


def cuts_of(P):
    cl = load_json(os.path.join(P, "work/cutlist.json"), {}) or {}
    sh = load_json(os.path.join(P, "work/shots.json"), {}) or {}
    if sh.get("shots") and (not cl or os.path.getmtime(os.path.join(P, "work/shots.json")) > os.path.getmtime(os.path.join(P, "work/cutlist.json"))):
        return [(s["from"], s["fx"].get("whip") and "whip" or next((k for k in ("crashAt", "rgbAt", "stutterUntil", "bump") if s["fx"].get(k) not in (None, False)), None))
                for s in sh["shots"][1:]], sh.get("fps", 30)
    segs = [s for s in cl.get("main", []) if s.get("materialType", "video") == "video"]
    return [(s["fromFrame"], s.get("transition") if isinstance(s.get("transition"), str) else None) for s in segs[1:]], cl.get("fps", 30)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("render"); ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--from", dest="start", type=int, default=0, help="first timeline frame of a part render (render_part.sh --frames=A-B → A)")
    a = ap.parse_args(); P = os.path.abspath(a.project); out = os.path.join(P, "work/qa"); os.makedirs(out, exist_ok=True)
    cuts, fps = cuts_of(P)
    import numpy as np
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", a.render], capture_output=True, text=True)
    vw, vh = (int(x) for x in r.stdout.strip().split(",")[:2]); w = 64; h = max(2, round(w * vh / vw / 2) * 2)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", a.render, "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, dtype=np.uint8)[: len(raw) // (w * h) * w * h].reshape(-1, h, w).astype(np.float32)
    diff = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2)) if len(fr) > 1 else np.zeros(0)
    cuts = [(c - a.start, k) for c, k in cuts if c >= a.start and c - a.start + 1 < len(fr)]   # a part render: its own cuts, in its own frames
    still = diff < 0.25; runs, i = [], 0
    while i < len(still):
        if still[i]:
            j = i
            while j < len(still) and still[j]: j += 1
            if j - i > 18: runs.append((i, j))
            i = j
        else: i += 1
    for i, j in runs: print(f"FROZEN {(i + a.start) / fps:6.2f}–{(j + a.start) / fps:6.2f} s ({j - i} frames) — a designed hold? if not, cut it or give it story")
    # the cut sheet: 4 frames per cut, rows of cuts, pages of a.max rows
    th = 180 if vh > vw else 110; tw = round(th * vw / vh / 2) * 2; pages = 0
    for p0 in range(0, len(cuts), a.max):
        rows = cuts[p0: p0 + a.max]
        # one between() per cut: 120 eq() terms overflowed ffmpeg's expression parser on a 24-min vlog (Halloween, 2026-11-09)
        expr = "+".join(f"between(n\\,{max(0, c - 2)}\\,{max(3, c + 1)})" for c, k in rows)
        name = os.path.join(out, f"cuts_{p0 // a.max + 1:02d}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", a.render, "-vf", f"select='{expr}',scale={tw}:{th},tile=4x{len(rows)}:padding=3",
                        "-frames:v", "1", "-fps_mode", "passthrough", name], check=True)
        pages += 1
        for n, (c, k) in enumerate(rows, p0 + 1): print(f"  cut {n:3d} @ {(c + a.start) / fps:7.2f} s  {k or 'plain'}")
    fx = [k for _, k in cuts if k not in PLAIN]
    print(f"seams: {len(fx)} effect / {len(cuts)} cuts" + (f" ({', '.join(f'{x} ×{fx.count(x)}' for x in sorted(set(fx)))})" if fx else ""))
    print(f"MOTION_GATE_DONE {pages} cut sheet(s) in work/qa/, {len(runs)} frozen stretch(es)")


if __name__ == "__main__":
    main()
