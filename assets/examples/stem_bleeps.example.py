"""Bleeps of the censored cut, timed from GigaAM on the uncensored dialogue stem → work/bleeps_censored.json.

Usage: python3 -I work/scripts/stem_bleeps.py
Before: work/gigvenv/bin/python -I $S/transcribe.py --sources work/audit/stemu.wav   → work/new/cstemu.json (words on the timeline)
Why the stem and not the source clips: a source clip carries the far mic and background voices (v4 bleeped «Сейчас нет, ему
больно»); the stem is only what the viewer hears. GigaAM word ends are ±0.1–0.26 s (40 ms token grid), so each bleep spans
the word −0.2 / +0.28 s, at least 0.38 s; neighbours closer than 0.15 s merge (one long bleep over three words reads as a
broken track). Hand decisions live in work/bleep_patches.json: {"add": [[t, "word"], …], "drop": [t, …]} (seconds ±0.5).
Listen to every bleep once: GigaAM can miss a swear said over wind or music; an `add` fixes that by time.
"""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")); os.chdir(ROOT)
sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts"))
from swear import is_swear
from censor_bleeps import is_extra
FPS = 30
words = [w for s in json.load(open("work/new/cstemu.json"))["segments"] for w in s["words"]]
patch = json.load(open("work/bleep_patches.json")) if os.path.exists("work/bleep_patches.json") else {"add": [], "drop": []}
spans = [[w["start"] - 0.2, w["end"] + 0.28, w["word"].strip()] for w in words if is_swear(w["word"]) or is_extra(w["word"])]
for t, word in patch["add"]: spans.append([t - 0.2, t + 0.5, word])
spans = [s for s in spans if not any(abs(s[0] + 0.2 - t) < 0.5 for t in patch["drop"])]
out = []
for s, e, w in sorted(spans):
    if e - s < 0.38: m = (s + e) / 2; s, e = m - 0.19, m + 0.19
    if out and s - out[-1]["e"] < 0.15: out[-1]["e"] = max(out[-1]["e"], e); out[-1]["word"] += " " + w
    else: out.append({"s": max(0, s), "e": e, "word": w})
res = [{"word": b["word"], "startMs": round(b["s"] * 1000), "endMs": round(b["e"] * 1000), "fromFrame": round(b["s"] * FPS), "toFrame": round(b["e"] * FPS)} for b in out]
json.dump(res, open("work/bleeps_censored.json", "w"), ensure_ascii=False, indent=1)
for b in res: print(f'  {b["startMs"] / 1000:8.2f}–{b["endMs"] / 1000:8.2f}  {b["word"]}')
print(f"STEM_BLEEPS_DONE {len(res)} bleeps")
