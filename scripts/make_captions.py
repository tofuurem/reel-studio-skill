#!/usr/bin/env python3
"""Turn whisper words into Remotion Caption[] pages (calm phrase subtitles), profanity masked.

Usage: make_captions.py [--words work/audio/timeline.json] [--out reel/public/captions/timeline.json] [--brands assets/brands.json]
                        [--max-words 8 --max-sec 3.4 --max-chars 54] [--cutlist work/cutlist.json] [--patches work/caption_patches.json] [--no-mask]

Rules (learned the hard way):
- whisper splits one spoken word into tokens without a leading space ("Яндекс" + ".Облаке"); glue them.
- break on sentence punctuation, on a comma once ≥3 words, at --max-words / --max-sec / --max-chars, or on a >0.9 s pause
  (defaults from references/craft/numbers.json: 8 words, 3.4 s, 54 characters = two lines at 50 px; a third line climbs into the card band);
- never leave a preposition/conjunction dangling at the end of a line, never strand the last word of a sentence alone;
- brand names get their canonical spelling (brands.json: {"дот": "Dot", "гермес": "Hermes"});
- tokens inside silent ranges of the cut list (muted segments, the silent carrier, after the speech end) are dropped: whisper
  hallucinates there («Продолжение следует…»); voiceovers placed over a muted shot are kept;
- swears (swear.py) become first letter + asterisks here — a re-run can no longer bring them back (--no-mask to keep them).
Pages are expressed with pageBreakAfter flags; Captions.tsx uses a huge combine window so only these flags cut pages.
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, apply_patches, brand, glue, in_ranges, load_json, silent_ranges
from swear import is_swear

ap = argparse.ArgumentParser(); ap.add_argument("--words", default="work/audio/timeline.json"); ap.add_argument("--out", default="reel/public/captions/timeline.json")
ap.add_argument("--brands", default="assets/brands.json")
ap.add_argument("--max-words", type=int, default=N["capMaxWords"]); ap.add_argument("--max-sec", type=float, default=N["capMaxSec"])
ap.add_argument("--max-chars", type=int, default=N["capMaxChars"], help="characters per page incl. spaces (two lines)")
ap.add_argument("--patches", default="work/caption_patches.json", help='hand fixes that survive re-runs: {"drop": ["двумя", "водными,"], "replace": {"не...": "не делать,"}, "replace_at": [[112.4, "не...", "не делать,"]], "drop_at": [[104.2, "и"]]} (RAW token text as whisper wrote it, before gluing — «Уи-хи» arrives as « Уи» + «-хи.», drop both with drop_at; *_at = seconds ±1.5; an empty replacement leaves a double space — use drop_at instead)')
ap.add_argument("--cutlist", default="work/cutlist.json", help="silent ranges and the speech end come from here")
ap.add_argument("--no-mask", action="store_true", help="keep swears unmasked in the captions")
a = ap.parse_args()
r = json.load(open(a.words)); raw = [w for s in r["segments"] for w in s.get("words", [])]
cl = load_json(a.cutlist)
if cl:
    quiet = silent_ranges(cl); end = cl.get("durationSec")
    if end: quiet = quiet + [(end - 0.25, 1e9)]
    gone = [w for w in raw if in_ranges((w["start"] + w["end"]) / 2, quiet)]
    if gone: print("dropped in silent ranges:", " ".join(f"{w['word'].strip()}@{w['start']:.1f}" for w in gone))
    raw = [w for w in raw if not in_ranges((w["start"] + w["end"]) / 2, quiet)]
brands = load_json(a.brands, {}) or {}
raw, nd = apply_patches(raw, load_json(a.patches, {}))
if nd: print(f"caption patches: {nd} dropped")
words = glue(raw)
FUNC = set("и а но в на с к по за из у о об от до для при что как не же ли то или под над со ко во это уже еще ещё вот все всё бы чтобы если когда где так там тут он она они мы я ты вы мне мой его её их нам вам ваш наш тот та те этот эта эти кроме более менее либо очень самое просто".split())
HARD = (".", "?", "!", "…")
caps, grp = [], []
def flush():
    global grp
    if grp: grp[-1]["pageBreakAfter"] = True
    grp = []
def chars(g): return len("".join(c["text"] for c in g).strip())
masked = 0
for i, w in enumerate(words):
    t = brand(w["word"].strip(), brands); core = t.strip(".,!?…"); low = core.lower()
    if not a.no_mask:
        m = re.match(r"^([^\wа-яё]*)([\wа-яё-]+)(.*)$", t, re.I)
        if m and is_swear(m.group(2)): t = m.group(1) + m.group(2)[0] + "*" * (len(m.group(2)) - 1) + m.group(3); masked += 1
    c = {"text": " " + t, "startMs": round(w["start"] * 1000), "endMs": round(w["end"] * 1000), "timestampMs": round((w["start"] + w["end"]) / 2 * 1000), "confidence": w.get("probability")}
    if grp and chars(grp + [c]) > a.max_chars:   # a third line: break before this word, but never after a function word
        if len(grp) > 1 and grp[-1]["text"].strip().lower().strip(".,!?…") in FUNC:
            carry = grp[-1]; grp[-2]["pageBreakAfter"] = True; grp = [carry]
        else: flush()
    caps.append(c); grp.append(c)
    nxt = words[i + 1] if i + 1 < len(words) else None
    dur = c["endMs"] - grp[0]["startMs"]; gap = (nxt["start"] * 1000 - c["endMs"]) if nxt else 9999
    hard = t.endswith(HARD); soft = t.endswith(",") and len(grp) >= 3; full = len(grp) >= a.max_words or dur >= a.max_sec * 1000
    want = hard or soft or full or gap > 900
    room = nxt is not None and chars(grp) + 1 + len(nxt["word"].strip()) <= a.max_chars
    if want and not hard and gap <= 900 and len(grp) < a.max_words + 3 and room:
        if low in FUNC: continue
        if nxt and nxt["word"].strip().endswith(HARD): continue
    if want and len(grp) <= 2 and nxt and gap <= 1400 and len(grp) < a.max_words + 3 and not hard and room:
        continue  # a one-or-two-word page flickers; glue it to the next phrase
    if want: flush()
flush()
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
json.dump(caps, open(a.out, "w"), ensure_ascii=False)
pages, cur = [], []
for c in caps:
    cur.append(c["text"])
    if c.get("pageBreakAfter"): pages.append("".join(cur).strip()); cur = []
long = [p for p in pages if len(p) > a.max_chars]
print(len(pages), "pages", f"(masked {masked})" if masked else ""); print("\n".join(pages))
if long: print(f"WARNING: {len(long)} page(s) over {a.max_chars} characters (one long word?):", *long, sep="\n  ")
print("CAPTIONS_DONE", a.out)
