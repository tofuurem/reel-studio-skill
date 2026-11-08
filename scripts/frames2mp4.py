#!/usr/bin/env python3
"""Screencast frames with their own timestamps → a constant 30 fps H.264 clip (site_capture.mjs uses it).

Usage: python3 -I frames2mp4.py <frames_dir> <out.mp4> [--skip SEC] [--size WxH] [--crf 14]
<frames_dir>/frames.json = [{"f": "/abs/f00000.jpg", "t": <seconds>}, …] (CDP Page.screencastFrame metadata.timestamp).
Each frame is held until the next one arrives (ffmpeg concat demuxer with per-frame durations), so a page that only
repaints on change still plays in real time; the last frame is held 0.5 s. --skip drops the first SEC seconds.
"""
import argparse, json, os, subprocess, sys

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("frames_dir"); ap.add_argument("out"); ap.add_argument("--skip", type=float, default=0.0)
ap.add_argument("--size", default=None, help="output WxH (even numbers); default: the frames' own size")
ap.add_argument("--crf", type=int, default=14)
a = ap.parse_args()
fr = json.load(open(os.path.join(a.frames_dir, "frames.json")))
if not fr: sys.exit("no frames")
t0 = fr[0]["t"] + a.skip
fr = [f for f in fr if f["t"] >= t0 - 1e-6] or fr[-1:]
lst = os.path.join(a.frames_dir, "concat.txt")
with open(lst, "w") as fh:
    for x, y in zip(fr, fr[1:]):
        fh.write(f"file '{x['f']}'\nduration {max(0.001, y['t'] - x['t']):.4f}\n")
    fh.write(f"file '{fr[-1]['f']}'\nduration 0.5\nfile '{fr[-1]['f']}'\n")
vf = "fps=30" + (f",scale={a.size.replace('x', ':')}:flags=lanczos" if a.size else ",scale=trunc(iw/2)*2:trunc(ih/2)*2") + ",format=yuv420p"
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-vf", vf, "-c:v", "libx264", "-preset", "slow",
                "-crf", str(a.crf), "-movflags", "+faststart", a.out], check=True)
print("FRAMES2MP4_DONE", a.out)
