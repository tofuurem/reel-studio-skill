#!/usr/bin/env python3
"""Find single-frame render dropouts (a card's text or panel missing for one frame = "the cards blink").

Usage: glitch_scan.py <video.mp4> [--expect N] [y0 h]...   default bands for a 2560-high frame: 200 800 (face), 1000 700 (cards), 1700 700 (captions)
A frame is bad when its band differs strongly from BOTH neighbours while the neighbours match each other.
Exit codes: 0 = GLITCH_SCAN CLEAN; 1 = dropouts found (look, then re-render); 2 = the file itself is broken — missing, empty,
or fewer frames decoded than it holds / than --expect (render.sh passes the raw render's frame count): a truncated file is
never "clean" (audit 2026-10-22: a missing file used to print CLEAN).
False positives: a laptop or phone screen inside the footage can refresh for one frame, a hard flash cut can too — look at a
flagged frame before re-rendering.
"""
import os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import count_frames

argv = sys.argv[1:]
if not argv: sys.exit(__doc__)
expect = None
if "--expect" in argv:
    k = argv.index("--expect"); expect = int(argv[k + 1]); del argv[k:k + 2]
v = argv[0]; args = [int(x) for x in argv[1:]]
if not os.path.exists(v) or os.path.getsize(v) == 0: print(f"GLITCH_SCAN BROKEN: {v} is missing or empty"); sys.exit(2)
packets = count_frames(v)
if packets == 0: print(f"GLITCH_SCAN BROKEN: no video frames in {v}"); sys.exit(2)
if expect is not None and abs(packets - expect) > 1: print(f"GLITCH_SCAN BROKEN: {packets} frames in the file, {expect} expected (truncated or wrong file)"); sys.exit(2)
H = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "csv=p=0", v], capture_output=True, text=True).stdout.strip().strip(",") or 2560)
k = H / 2560
bands = list(zip(args[::2], args[1::2])) if args else [(int(200 * k), int(800 * k)), (int(1000 * k), int(700 * k)), (int(1700 * k), int(700 * k))]
total = 0
for y0, h in bands:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", v, "-vf", f"crop=iw:{h}:0:{y0},scale=180:90", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    n = len(raw) // (180 * 90)
    if n == 0 or abs(n - packets) > 1: print(f"GLITCH_SCAN BROKEN: decoded {n} of {packets} frames in band y={y0} (damaged file)"); sys.exit(2)
    a = np.frombuffer(raw[:n * 180 * 90], dtype=np.uint8).reshape(n, 90, 180).astype(np.int16)
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    bad = []
    for i in range(1, n - 1):
        p, q = d[i - 1], d[i]
        if p > 8 and q > 8 and np.abs(a[i - 1] - a[i + 1]).mean() < max(3.0, 0.25 * min(p, q)): bad.append((i, round(float(p), 1), round(float(q), 1)))
    total += len(bad)
    print(f"band y={y0}..{y0+h}: {n} frames, single-frame dropouts: {len(bad)}")
    for b in bad[:30]: print(f"  frame {b[0]} ({b[0]/30:.2f}s) diffs {b[1]} {b[2]}")
print("GLITCH_SCAN", "CLEAN" if total == 0 else f"BAD {total}", f"({packets} frames)")
sys.exit(1 if total else 0)
