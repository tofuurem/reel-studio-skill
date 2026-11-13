#!/usr/bin/env python3
"""A timeline for a reel without any voice — screenshots, images, renders over music (references/inputs/screens-and-images.md).

Usage: python3 -I silent_timeline.py <project> --seconds S [--preset warm|night|bright|dusk] [--fps 30]
→ work/vo/silence.mp4 (vo_carriers.sh --silence, ≥ S s), work/cutlist.json with top-level "silent": true and one muted
  segment of that carrier, work/beats.json {"bpm", "frames": [beat frames], "bars": [bar frames]} from the lo-fi preset's BPM.
Offer the user lines to record first (inputs/voiceover.md) — a reel with a voice carries more. Without one:
  make_proxies.py --res both → gen_timeline.py → make_bed.sh <project> <preset> (same preset: the beats match) →
  gen_reel.py places the pictures on work/beats.json (a cut on a bar, a push-in over 2 bars) → render.
transcribe / captions / tl_words / bleeps / face_zones are skipped (they see "silent": true); Reel.tsx has no <Captions>.
"""
import argparse, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--seconds", type=float, required=True)
ap.add_argument("--preset", default="warm", choices=["warm", "night", "bright", "dusk"]); ap.add_argument("--fps", type=int, default=30, choices=[30], help="only 30: the template, the proxies and reelgen are 30 fps")
a = ap.parse_args()
P = os.path.abspath(a.project); fps = a.fps; S = a.seconds; F = int(round(S * fps))
subprocess.run([os.path.join(HERE, "vo_carriers.sh"), P, "--silence", str(int(S) + 2)], check=True)
carrier = os.path.join(P, "work/vo/silence.mp4")
seg = {"track": 0, "trackType": "video", "materialType": "video", "name": "silence.mp4", "path": carrier, "tlStart": 0.0, "dur": round(S, 4),
       "srcStart": 0.0, "srcDur": round(S, 4), "speed": 1.0, "volume": 0.0, "fromFrame": 0, "durFrames": F, "trimBeforeFrames": 0,
       "note": "silent carrier (images-only reel)", "text": ""}
cl = {"draft": "silent", "silent": True, "draftFolder": None, "fps": fps, "canvas": {"w": 1080, "h": 1920}, "durationSec": round(S, 3), "totalFrames": F,
      "main": [seg], "tracks": [{"index": 0, "type": "video", "segments": [seg]}], "sources": [carrier], "luts": {}, "voiceovers": [],
      "brollCandidates": [], "warnings": []}
os.makedirs(os.path.join(P, "work"), exist_ok=True)
json.dump(cl, open(os.path.join(P, "work/cutlist.json"), "w"), ensure_ascii=False, indent=1)
src = open(os.path.join(HERE, "lofi.py")).read()   # lofi.py synthesises on import: read its preset table as text
m = re.search(rf"'{a.preset}':\s*dict\(bpm=(\d+)", src); bpm = int(m.group(1)) if m else 76
beat = 60 / bpm
frames = [int(round(k * beat * fps)) for k in range(int(S / beat) + 1) if k * beat < S]
json.dump({"bpm": bpm, "preset": a.preset, "frames": frames, "bars": frames[::4]}, open(os.path.join(P, "work/beats.json"), "w"))
print(f"silent timeline {S:.1f} s = {F} frames, {a.preset} {bpm} BPM: {len(frames)} beats, {len(frames[::4])} bars (every {4 * beat:.2f} s)")
print(f"next: make_proxies.py --res both · gen_timeline.py · make_bed.sh {P} {a.preset} · make_sfx.sh {P}")
print("SILENT_TIMELINE_DONE", os.path.join(P, "work/cutlist.json"))
