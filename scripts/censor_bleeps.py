"""Bleeps of a censored cut → work/bleeps_censored.json (cut_from_transcript.py's bleeps format, timeline ms).

Usage: python3 -I censor_bleeps.py <project> [--swears work/bleeps.json] [--no-drugs]
Run after cut_from_transcript.py (keep a copy of its work/bleeps.json — the uncensored cut empties it). Bleeps = every
swear that list has + the rude words swear.py does not count (CENSOR_WORDS: «сука», «наркоман») + the weed and mushroom
talk (DRUG_WORDS: «курим», «накуривается», «косяки», «грибов» …), found in the cut's own words (work/new/c<id>.json).
Neighbours closer than 350 ms merge. Then: dialogue.py <project> --bleeps work/bleeps_censored.json
--out reel/public/audio/dialogue_censored.wav (the uncensored stem stays), and captions through censor_text().
Why: Halloween vlog censored (2026-11-09, YouTube + family) — «накуривается, грибов объешься — запикать».
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clipid import clip_id  # noqa: E402

CENSOR_WORDS = re.compile(r"^(сук[аиуое]?|сучк\w*|наркоман\w*|долбо[её]б\w*)$", re.I)
DRUG_WORDS = re.compile(r"(косяк|кисяк|косяч|накур|раскур|^курим$|^курит|покур|^трав[аук]|шишк|ганж|каннабис|гриб|^дунуть|^дунем|затяж|бошк)", re.I)
core = lambda w: re.sub(r"[^\wа-яё-]", "", w.lower().replace("ё", "е"))


def is_extra(word):
    c = core(word); return bool(CENSOR_WORDS.match(c) or DRUG_WORDS.search(c))


def censor_text(t):
    """Caption text with every swear and censored word masked as «к*****» (first letter kept)."""
    import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from swear import is_swear
    return re.sub(r"[А-Яа-яЁёA-Za-z-]+", lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1) if (is_swear(m.group(0)) or is_extra(m.group(0))) else m.group(0), t)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--swears", default="work/bleeps.json"); ap.add_argument("--no-drugs", action="store_true")
    a = ap.parse_args(); os.chdir(a.project)
    if a.no_drugs: DRUG_WORDS = re.compile(r"(?!)")
    cl = json.load(open("work/cutlist.json")); fps = cl["fps"]
    out = list(json.load(open(a.swears)) if os.path.exists(a.swears) else [])
    for s in cl["main"]:
        if float(s.get("volume", 1)) < 0.01: continue
        if not s.get("path"): continue
        cid = clip_id(s["path"])[1:].split("x")[0]   # the id every other script uses (IMG_1234.MOV, Cyrillic names, drone files)
        p = f"work/new/c{cid}.json"
        if not os.path.exists(p): continue
        a, d, sp = s["srcStart"], s["srcDur"], float(s.get("speed", 1) or 1)
        for sg in json.load(open(p))["segments"]:
            for w in sg["words"]:
                if not (a <= w["start"] < a + d) or not is_extra(w["word"]): continue
                b0, b1 = max(w["start"] - 0.1, a), min(w["end"] + 0.2, w["start"] + max(0.7, 0.11 * len(w["word"].strip())), a + d)   # GigaAM word ends are ±0.1–0.26 s
                t0 = s["fromFrame"] / fps + (b0 - a) / sp; t1 = s["fromFrame"] / fps + (b1 - a) / sp
                out.append({"word": w["word"].strip(), "src": [round(b0, 2), round(b1, 2)], "startMs": round(t0 * 1000), "endMs": round(t1 * 1000),
                            "fromFrame": round(t0 * fps), "toFrame": round(t1 * fps), "why": "censored"})
    out.sort(key=lambda b: b["startMs"]); merged = []
    for b in out:
        if merged and b["startMs"] - merged[-1]["endMs"] < 350:
            m = merged[-1]; m["endMs"] = max(m["endMs"], b["endMs"]); m["toFrame"] = max(m["toFrame"], b["toFrame"]); m["word"] += " " + b["word"]
        else: merged.append(dict(b))
    json.dump(merged, open("work/bleeps_censored.json", "w"), ensure_ascii=False, indent=1)
    extra = [b for b in merged if b.get("why")]
    print(f"{len(merged)} bleeps ({len(extra)} with the censored words):", ", ".join(b["word"] for b in extra))
    print("CENSOR_BLEEPS_DONE")
