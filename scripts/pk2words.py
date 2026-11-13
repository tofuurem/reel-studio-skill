#!/usr/bin/env python3
"""GigaAM map (work/pk/c<id>.json, from transcribe_gigaam.py) → word JSON (work/new/c<id>.json) for cut_from_transcript.py.

Usage: pk2words.py work/pk/c0028.json [more…]
Output: {text, segments: [{start, end, text, words: [{word, start, end, probability}]}], language}. The map's `w` entries are whole
words with a leading space (and punctuation); a piece without a leading space is glued to the word before it, so the swear matcher
and `exact: false` snapping see whole words. Saves a second pass over a long raw take: the map's word times are good enough for the
plan (word ends are ±0.1–0.26 s: cut on pauses.py / speech_run, not on a word end); the final captions still come from
transcribe.py on the cut timeline.
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
