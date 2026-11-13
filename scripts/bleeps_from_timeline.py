#!/usr/bin/env python3
"""work/bleeps.json from the timeline transcript — for cuts that did not come from plan.json (CapCut drafts).

Usage: python3 -I bleeps_from_timeline.py [--words work/audio/timeline.json] [--wav work/audio/timeline.wav] [--out work/bleeps.json] [--fps 30]
Run after transcribe.py (it writes both inputs). Every word swear.py matches becomes a bleep, snapped to the voice-activity run
around it on the timeline audio (GigaAM word ends drift ±0.1–0.26 s), clamped to the word −0.2/+0.28 s; swears closer than 350 ms
merge into one bleep. Same format as cut_from_transcript.py, so bleep.py and mask_captions.py work the same way.
Words inside silent ranges of the cut list (muted segments, the silent carrier) are recognizer hallucinations and are skipped.
Read the printed list against the audio: a swear GigaAM did not hear is not bleeped.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from swear import is_swear
from common import in_ranges, load_json, silent_ranges, speech_run
ap = argparse.ArgumentParser(); ap.add_argument("--words", default="work/audio/timeline.json"); ap.add_argument("--wav", default="work/audio/timeline.wav")
ap.add_argument("--out", default="work/bleeps.json"); ap.add_argument("--fps", type=int, default=30); ap.add_argument("--cutlist", default="work/cutlist.json")
a = ap.parse_args()
words = [w for s in json.load(open(a.words))["segments"] for w in s.get("words", [])]
cl = load_json(a.cutlist); quiet = silent_ranges(cl) if cl else []

bleeps = []
for w in words:
    if not is_swear(w["word"]) or in_ranges((w["start"] + w["end"]) / 2, quiet): continue
    b0, b1 = w["start"] - 0.2, w["end"] + 0.28   # GigaAM word ends are ±0.1–0.26 s
    if os.path.exists(a.wav):
        r0, r1 = speech_run(a.wav, (w["start"] + w["end"]) / 2); b0, b1 = max(r0, b0), min(r1, b1)
    b1 = max(b1, b0 + 0.25)
    bleeps.append({"word": w["word"].strip(), "startMs": round(b0 * 1000), "endMs": round(b1 * 1000)})
merged = []
for b in bleeps:
    if merged and b["startMs"] - merged[-1]["endMs"] < 350: merged[-1]["endMs"] = b["endMs"]; merged[-1]["word"] += " " + b["word"]
    else: merged.append(b)
for b in merged: b["fromFrame"] = int(b["startMs"] / 1000 * a.fps); b["toFrame"] = int(b["endMs"] / 1000 * a.fps) + 1
json.dump(merged, open(a.out, "w"), ensure_ascii=False, indent=1)
for b in merged: print(f"  bleep {b['word']:20s} {b['startMs']/1000:7.2f}–{b['endMs']/1000:7.2f} s  frames {b['fromFrame']}–{b['toFrame']}")
print(f"BLEEPS_DONE {len(merged)} → {a.out}")
