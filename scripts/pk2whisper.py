#!/usr/bin/env python3
"""Parakeet map (work/pk/c<id>.json) → whisper-shaped word JSON (work/new/c<id>.json) for cut_from_transcript.py.

Usage: pk2whisper.py work/pk/c0028.json [more…]
Parakeet tokens are sentencepiece pieces (a leading space starts a word); they are merged into words so the swear
matcher and `exact: false` snapping see whole words. Saves a whisper pass over a long raw take: Parakeet's word
times are good enough for the plan; the final captions still come from whisper on the cut timeline.
"""
import json, os, sys

for src in sys.argv[1:]:
    segs = []
    for s in json.load(open(src)):
        words, cur = [], None
        for t in s["words"]:
            txt = t["w"]
            if cur is None or txt.startswith(" "):
                if cur and cur["word"].strip(): words.append(cur)
                cur = {"word": txt.rstrip("\n"), "start": t["s"], "end": t["e"], "probability": 1.0}
            else:
                cur["word"] += txt; cur["end"] = t["e"]
        if cur and cur["word"].strip(): words.append(cur)
        segs.append({"start": s["start"], "end": s["end"], "text": s["text"], "words": words})
    out = os.path.join("work/new", os.path.basename(src)); os.makedirs("work/new", exist_ok=True)
    json.dump({"text": " ".join(s["text"] for s in segs), "segments": segs, "language": "ru"}, open(out, "w"), ensure_ascii=False, indent=1)
    print(out, sum(len(s["words"]) for s in segs), "words")
