"""Words for the full captions of a censored cut (subtitles on ALL speech, both versions) → work/audio/timeline.json (uncensored)
and work/audio/timeline_censored.json, for the skill's make_captions.py.

Usage: python3 -I work/scripts/caption_words.py      (after stem_bleeps.py; then make_captions.py --words <file> --out <captions file> --no-mask)
Base: GigaAM on the uncensored dialogue stem (work/new/cstemu.json, the same transcript the bleeps are timed from — never swap
single words between two recognizers by time, that put swears on the wrong words). The censored file masks every word whose
middle is inside a bleep (first letter + asterisks) and nothing else: a masked word is always bleeped and a bleeped one always
masked (craft/censor.md). Page-level fixes read against the audio go to work/caption_fixes.json: [[from_s, to_s, "text"]] —
the text replaces the words inside the span, "" deletes them.
"""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")); os.chdir(ROOT)
d = json.load(open("work/new/cstemu.json"))
fixes = json.load(open("work/caption_fixes.json")) if os.path.exists("work/caption_fixes.json") else []
bleeps = [(b["startMs"] / 1000, b["endMs"] / 1000) for b in json.load(open("work/bleeps_censored.json"))]
def fix(seg):
    ws = []
    for w in seg["words"]:
        mid = (w["start"] + w["end"]) / 2; hit = next((f for f in fixes if f[0] <= mid <= f[1]), None)
        if hit is None: ws.append(w)
        elif hit[2] and not any(x.get("fixed") == tuple(hit[:2]) for x in ws):
            ws.append({**w, "word": " " + hit[2], "start": hit[0], "end": hit[1], "fixed": tuple(hit[:2])})
    return {**seg, "words": [{k: v for k, v in w.items() if k != "fixed"} for w in ws]}
def mask(w):
    t = w["word"].strip(); core = "".join(c for c in t if c.isalnum() or c == "-")
    if not core: return w
    i = t.index(core[0]); return {**w, "word": " " + t[:i + 1] + "*" * (len(core) - 1) + t[i + len(core):]}
base = [fix(s) for s in d["segments"]]
for name, segs in (("timeline", base), ("timeline_censored", [{**s, "words": [mask(w) if any(a <= (w["start"] + w["end"]) / 2 <= b for a, b in bleeps) else w for w in s["words"]]} for s in base])):
    json.dump({**d, "segments": segs}, open(f"work/audio/{name}.json", "w"), ensure_ascii=False, indent=1)
print("CAPTION_WORDS_DONE work/audio/timeline.json, work/audio/timeline_censored.json")
