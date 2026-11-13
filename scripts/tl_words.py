#!/usr/bin/env python3
"""work/audio/timeline.json → work/tl_words.txt ("<frame> <word>" per line, split tokens glued).
Usage: tl_words.py [--words work/audio/timeline.json] [--out work/tl_words.txt] [--fps 30] [--brands assets/brands.json]
                   [--patches work/caption_patches.json] [--cutlist work/cutlist.json]
This is the sync source for every graphic: a generator (work/gen_reel.py) looks words up and writes absolute frames
into Reel.tsx, so a re-cut only needs a re-run, not a hand edit of numbers. See references/craft/storyboard.md.
The same corrections as the captions apply (caption_patches.json on raw tokens, brands.json spellings), and words in silent
ranges are skipped — so fw("Tripo") finds the word the captions show, not the recognizer's «трипа»."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import apply_patches, brand, glue, in_ranges, load_json, silent_ranges
ap = argparse.ArgumentParser(); ap.add_argument("--words", default="work/audio/timeline.json"); ap.add_argument("--out", default="work/tl_words.txt"); ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--brands", default="assets/brands.json"); ap.add_argument("--patches", default="work/caption_patches.json"); ap.add_argument("--cutlist", default="work/cutlist.json")
a = ap.parse_args()
ws = [w for s in json.load(open(a.words))["segments"] for w in s.get("words", [])]
cl = load_json(a.cutlist)
if cl:
    quiet = silent_ranges(cl) + ([(cl["durationSec"] - 0.25, 1e9)] if cl.get("durationSec") else [])
    ws = [w for w in ws if not in_ranges((w["start"] + w["end"]) / 2, quiet)]
ws, _ = apply_patches(ws, load_json(a.patches, {}))
brands = load_json(a.brands, {}) or {}
out = [dict(w, word=brand(w["word"].strip(), brands)) for w in glue(ws)]
open(a.out, "w").write("".join(f"{int(round(w['start'] * a.fps)):5d} {w['word'].strip()}\n" for w in out))
print(len(out), "words →", a.out); print(" ".join(f"{int(round(w['start'] * a.fps))}:{w['word'].strip()}" for w in out))
print("TL_WORDS_DONE", a.out)
