#!/usr/bin/env python3
"""Build work/cutlist.json (schema of capcut_export.py) + work/bleeps.json from a hand-written plan — for shoots
that never went through CapCut: you read the transcript, choose ranges, this turns them into a timeline.

Usage: cut_from_transcript.py plan.json [--out work/] [--lut path.cube] [--fps 30]
plan.json:
  {"files": {"0001": "/abs/DJI_..._0001_D.MP4"},           # clip id → source
   "words": {"0001": "work/new/c0001.json"},               # transcript with word timestamps (Whisper or pk2whisper.py)
   "voice": {"0001": "work/voice/out/c0001_DeepFilterNet3.wav"},   # optional: isolated voice, used to snap bleeps to real speech
   "exact": false,                                         # false: ranges snap to words (lead / tail around them)
                                                           # true: ranges are exact source seconds you measured with pauses.py
   "plan": [["0001", 266.5, 302.1, "hook"],                # [clip, start, end, note, {opts}]
            ["0002", 36.58, 54.10, "squats", {"transition": "whip", "audioFadeIn": 4, "exact": true}]],
   "broll": ["/abs/extra.MP4"]}
Plan-level keys (all optional):
  "canvas"        "9:16" (default; or work/intake.json "canvas") | "16:9" | "4:5" | "1:1" | {"w": 1920, "h": 1080}
  "lead", "tail"  seconds kept before the first / after the last word of a word-snapped range (default 0.12 / 0.25;
                  an event vlog breathes better with 0.2 / 0.45)
  "snap"          true (default): a word-snapped range that starts or ends inside a sentence grows to the sentence edge — a
                  word ending in .?!… or a pause ≥ snapJoin s, at most snapBack s back / snapFwd s forward, never into another
                  range of the same clip (Halloween vlog v2: «фразы обрезанные посередине»). Every growth is printed.
  "splitPauses"   seconds (default off): a word-snapped range is split at pauses longer than this, the pause shrinking to
                  lead + tail — whole scenes keep their laughs and reactions, dead air goes. A piece of one lone word between
                  two long pauses is dropped («Я.» reads as a glitch).
  "splitWindows"  seconds (default numbers.json splitWindowSec; 0 = off): ranges of one take further apart than this go to
                  alias clips <id>x<k> (symlinks in work/alias/, the cleaned voice linked too), so make_proxies encodes one
                  short window per group instead of one window over the whole take (c0080: 509 s of 4K for 70 s used).
Opts per range: exact, snap (false: no growth), gaps (true: no pause split), transition ("whip"; default dissolve in
  gen_timeline), cropX (9:16 crop centre 0–1 or [from, to]: overrides people_zones.py), audioFadeIn (frames, when a cut lands
  inside a word), mute (the segment plays silent — always exact seconds, needs no words), amb (a picture beat: dialogue.py
  lays the camera's own sound under it), raw (camera sound instead of the cleaned voice), speed (e.g. 1.5 — a picture beat
  played faster; slow motion belongs to the action-reel pieces, the browser only repeats frames), punch, title/chapter/…
  (anything else is kept on the segment for gen_reel.py).
Frames are cumulative (no 1-frame gaps between segments); adjacent swears (<350 ms) merge into one bleep. After the cut
every speech segment that still starts or ends inside a sentence is listed as MID-SENTENCE (exact ranges included) — fix the
seconds or accept it knowingly.
A range that finds no words (non-exact), ends before it starts or rounds to 0 frames stops the run with exit 1 — nothing is
written, so a typo never silently shortens the reel. cutlist.sources lists only the files the plan actually uses
(unused takes are not encoded by make_proxies).
"""
import argparse, json, os, re, sys
ap = argparse.ArgumentParser(); ap.add_argument("plan"); ap.add_argument("--out", default="work"); ap.add_argument("--lut"); ap.add_argument("--fps", type=int, default=30)
a = ap.parse_args(); P = json.load(open(a.plan)); fps = a.fps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from swear import is_swear  # one matcher for cut + captions
from common import N, canvas_size, clip_id, speech_run


def capped(w):
    """Parakeet sometimes stretches a sentence's last word over the following silence (c0080 «жопа»: 22 s) — cap it."""
    return {**w, "end": min(w["end"], w["start"] + max(0.7, 0.11 * len(w["word"].strip())))}


words = {k: [capped(w) for s in json.load(open(v))["segments"] for w in s.get("words", [])] for k, v in P["words"].items()}
VOICE = dict(P.get("voice", {})); EXACT = bool(P.get("exact", False))
lead, tail = float(P.get("lead", 0.12)), float(P.get("tail", 0.25))
SNAP = P.get("snap", True); SPLIT = P.get("splitPauses"); WIN = float(P.get("splitWindows", N["splitWindowSec"]) or 0)
OUT = os.path.abspath(a.out)
cw, ch = canvas_size(P.get("canvas"), os.path.dirname(OUT))
ENDS = re.compile(r"[.?!…]$")
ends = lambda w: bool(ENDS.search(w["word"].strip()))

SPANS = {}
for item in P["plan"]: SPANS.setdefault(item[0], []).append((item[1], item[2]))
grown, mid = [], []


def snap(clip, s_a, s_b, ws):
    """Grow ws (the words of one range) to the sentence edges, within snapBack / snapFwd, never into another range of the clip."""
    al = words[clip]; i0 = al.index(ws[0]); i1 = al.index(ws[-1])
    lo = max([e for x, e in SPANS[clip] if e <= s_a + 0.01 and (x, e) != (s_a, s_b)], default=-1)
    hi = min([x for x, e in SPANS[clip] if x >= s_b - 0.01 and (x, e) != (s_a, s_b)], default=1e9)
    j = i0
    while j > 0 and not ends(al[j - 1]) and al[j]["start"] - al[j - 1]["end"] < N["snapJoin"] and ws[0]["start"] - al[j - 1]["start"] <= N["snapBack"] and al[j - 1]["start"] > lo: j -= 1
    k = i1
    while k < len(al) - 1 and not ends(al[k]) and al[k + 1]["start"] - al[k]["end"] < N["snapJoin"] and al[k + 1]["end"] - ws[-1]["end"] <= N["snapFwd"] and al[k + 1]["end"] < hi: k += 1
    if j < i0 or k > i1:
        parts = []
        if j < i0: parts.append(f"+{ws[0]['start'] - al[j]['start']:.1f} s before «{' '.join(w['word'].strip() for w in al[j:i0])}»")
        if k > i1: parts.append(f"+{al[k]['end'] - ws[-1]['end']:.1f} s after «{' '.join(w['word'].strip() for w in al[i1 + 1:k + 1])}»")
        grown.append(f"{clip} {s_a}–{s_b}: " + " ".join(parts))
    return al[j:k + 1]


def check_mid(clip, s0, s1, note):
    """A speech segment that starts after a word with no sentence end (gap < 1 s) or ends before one → MID-SENTENCE."""
    al = words.get(clip) or []
    idx = [i for i, w in enumerate(al) if w["end"] > s0 + 0.05 and w["start"] < s1 - 0.05]
    if not idx: return
    i0, i1 = idx[0], idx[-1]
    if i0 > 0 and not ends(al[i0 - 1]) and al[i0]["start"] - al[i0 - 1]["end"] < 1.0:
        mid.append(f"{clip} {s0:.2f}: «{note}» starts after «…{' '.join(w['word'].strip() for w in al[max(0, i0 - 4):i0])}»")
    if i1 < len(al) - 1 and not ends(al[i1]) and al[i1 + 1]["start"] - al[i1]["end"] < 1.0:
        mid.append(f"{clip} {s1:.2f}: «{note}» ends before «{' '.join(w['word'].strip() for w in al[i1 + 1:i1 + 5])}…»")


# ---------------------------------------------------------------- ranges → pieces (source seconds)
pieces, errors = [], []
for k, item in enumerate(P["plan"]):
    clip, s_a, s_b, note = item[:4]; opts = dict(item[4]) if len(item) > 4 else {}
    mute = opts.pop("mute", False); exact = opts.pop("exact", EXACT) or mute   # a mute range has no words to snap to
    do_snap = opts.pop("snap", SNAP); gaps = opts.pop("gaps", False); speed = float(opts.pop("speed", 1.0) or 1.0)
    if clip not in P["files"]: errors.append(f"plan[{k}] {note!r}: clip {clip!r} is not in files"); continue
    if s_b <= s_a: errors.append(f"plan[{k}] {note!r}: {clip} {s_a}–{s_b} ends before it starts"); continue
    if speed <= 0: errors.append(f"plan[{k}] {note!r}: speed {speed}"); continue
    cwords = words.get(clip, [])  # a clip without a transcript (silent b-roll, usually "mute": true) has no words
    if exact:
        ws = [] if mute else [w for w in cwords if w["end"] > s_a + 0.05 and w["start"] < s_b - 0.05]
        pieces.append([clip, s_a, s_b, note, opts, mute, speed, ws]); continue
    ws = [w for w in cwords if w["end"] > s_a and w["start"] < s_b]
    if not ws: errors.append(f"plan[{k}] {note!r}: {clip} {s_a}–{s_b} has no words (wrong clip or seconds? use \"exact\": true for a wordless range)"); continue
    if do_snap and not opts.get("amb"): ws = snap(clip, s_a, s_b, ws)
    groups, cur = [], [ws[0]]
    for p, q in zip(ws, ws[1:]):
        if SPLIT and not gaps and q["start"] - p["end"] > float(SPLIT): groups.append(cur); cur = []
        cur.append(q)
    groups.append(cur)
    if len(groups) > 1: groups = [g for g in groups if len(g) > 1] or groups   # a lone word between two long pauses reads as a glitch
    for i, g in enumerate(groups):
        o = opts if i == 0 else {x: v for x, v in opts.items() if x not in ("transition", "audioFadeIn", "title", "chapter")}
        pieces.append([clip, max(0.0, g[0]["start"] - lead), g[-1]["end"] + tail, note if i == 0 else f"{note} ·{i + 1}", o, False, speed, g])

# ---------------------------------------------------------------- alias clips for far-apart ranges of one take
files = dict(P["files"]); words_files = dict(P["words"]); alias_of = {}
if WIN > 0:
    by = {}
    for n, pc in enumerate(pieces): by.setdefault(pc[0], []).append(n)
    for clip, ns in by.items():
        groups = []
        for n in sorted(ns, key=lambda n: pieces[n][1]):
            s0, s1 = pieces[n][1], pieces[n][2]
            g = next((g for g in groups if s0 - g[1] <= WIN and g[0] - s1 <= WIN), None)
            if g: g[0], g[1] = min(g[0], s0), max(g[1], s1); g[2].append(n)
            else: groups.append([s0, s1, [n]])
        for gi, (_, _, gn) in enumerate(sorted(groups, key=lambda g: g[0])):
            if gi == 0: continue
            src = os.path.realpath(files[clip]); stem, ext = os.path.splitext(os.path.basename(files[clip]))   # named after the plan's file (it may itself be a renamed link)
            parts = stem.split("_"); alias = f"{clip}x{gi}"
            name = "_".join(parts[:2] + [parts[2] + f"x{gi}"] + parts[3:]) + ext if stem.startswith("DJI_") and len(parts) > 2 else f"{stem}x{gi}{ext}"
            os.makedirs(os.path.join(OUT, "alias"), exist_ok=True); link = os.path.join(OUT, "alias", name)
            if os.path.lexists(link) and os.path.realpath(link) != src: os.remove(link)
            if not os.path.lexists(link): os.symlink(src, link)
            files[alias] = link; alias_of[clip_id(link)] = clip_id(files[clip])
            if clip in words_files: words_files[alias] = words_files[clip]; words[alias] = words[clip]
            for vd in ("voice/out",):   # the cleaned voice of the take serves the alias too
                d = os.path.join(OUT, vd); bv = f"{clip_id(files[clip])}_DeepFilterNet3.wav"; av = f"{clip_id(link)}_DeepFilterNet3.wav"
                if os.path.isdir(d) and not os.path.lexists(os.path.join(d, av)): os.symlink(bv, os.path.join(d, av))
            if clip in VOICE: VOICE[alias] = VOICE[clip]
            for n in gn: pieces[n][0] = alias

# ---------------------------------------------------------------- pieces → timeline
segs, bleeps, tl, frame = [], [], 0.0, 0
for clip, s0, s1, note, opts, mute, speed, ws in pieces:
    path = files[clip]; src_d = s1 - s0; dur = src_d / speed; end_frame = round((tl + dur) * fps)
    if end_frame - frame <= 0: errors.append(f"{note!r}: {clip} {s0:.2f}–{s1:.2f} is shorter than one frame"); continue
    if not mute and ws and not opts.get("amb"): check_mid(clip, s0, s1, note)
    segs.append({"track": 0, "trackType": "video", "materialType": "video", "name": os.path.basename(path), "path": path, "clip": clip,
                 "tlStart": round(tl, 4), "dur": round(dur, 4), "srcStart": round(s0, 4), "srcDur": round(src_d, 4), "speed": speed, "volume": 0.0 if mute else 1.0,
                 "fromFrame": frame, "durFrames": end_frame - frame, "trimBeforeFrames": round(s0 * fps), "note": note,
                 "text": " ".join(w["word"].strip() for w in ws), **opts})
    for w in ws:
        if is_swear(w["word"]) and not mute:
            b0, b1 = w["start"] - 0.2, w["end"] + 0.15
            if clip in VOICE and os.path.exists(VOICE[clip]):
                r0, r1 = speech_run(VOICE[clip], (w["start"] + w["end"]) / 2); b0, b1 = max(r0, b0), min(r1, b1)
            b0 = max(b0, s0); b1 = min(max(b1, b0 + 0.25), s1)
            bleeps.append({"word": w["word"].strip(), "src": [round(b0, 2), round(b1, 2)], "startMs": round((tl + (b0 - s0) / speed) * 1000), "endMs": round((tl + (b1 - s0) / speed) * 1000)})
    tl += dur; frame = end_frame
if errors: print("PLAN ERRORS — nothing written:", *errors, sep="\n  "); sys.exit(1)
merged = []
for b in bleeps:
    if merged and b["startMs"] - merged[-1]["endMs"] < 350: merged[-1]["endMs"] = b["endMs"]; merged[-1]["word"] += " " + b["word"]
    else: merged.append(b)
for b in merged: b["fromFrame"] = int(b["startMs"] / 1000 * fps); b["toFrame"] = int(b["endMs"] / 1000 * fps) + 1
out = {"draft": "transcript-cut", "draftFolder": None, "fps": fps, "canvas": {"w": cw, "h": ch}, "durationSec": round(tl, 3), "totalFrames": frame,
       "main": segs, "tracks": [{"index": 0, "type": "video", "segments": segs}], "sources": sorted({s["path"] for s in segs}),
       "words": words_files, "aliases": alias_of,   # alias clip id → the take's clip id (voice, transcript)
       "luts": ({"lut": a.lut} if a.lut else {}), "voiceovers": [], "brollCandidates": [{"path": p, "dur": None} for p in P.get("broll", [])], "warnings": []}
os.makedirs(OUT, exist_ok=True)
json.dump(out, open(f"{OUT}/cutlist.json", "w"), ensure_ascii=False, indent=1); json.dump(merged, open(f"{OUT}/bleeps.json", "w"), ensure_ascii=False, indent=1)
print(f"{len(segs)} segments, {tl:.1f}s = {frame} frames ({tl / 60:.1f} min), {len(merged)} bleeps, canvas {cw}x{ch}" + (f", {len(alias_of)} alias clip(s)" if alias_of else ""))
for s in segs: print(f"  f{s['fromFrame']:5d}+{s['durFrames']:4d}  tl {s['tlStart']:6.1f}  {s['clip']:>8} {s['srcStart']:7.2f}  {s['note']}  | {s['text'][:60]}")
for b in merged: print("  bleep", b["word"], b["src"], b["startMs"], b["endMs"])
if grown: print("GROWN to sentence edges:", *grown, sep="\n  ")
if mid: print("MID-SENTENCE (fix the seconds, or accept knowingly):", *mid, sep="\n  ")
