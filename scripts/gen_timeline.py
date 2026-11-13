#!/usr/bin/env python3
"""Generate reel/src/Timeline.tsx from work/cutlist.json (hardcoded JSX so Studio can edit it).

Usage: gen_timeline.py [--cutlist work/cutlist.json] [--out reel/src/Timeline.tsx] [--xfade 7] [--punch 1.2]

- Segments contiguous in the source that differ only by a mute are merged into one <Clip> with a volume
  callback (CapCut users mute clicks with 0.3 s slivers).
- Punch-in alternates on jump cuts inside the same source file so each cut lands on a new framing — for plans cut from raw
  takes. A CapCut draft keeps the user's framing: no punch and no alternation unless --punch is given (the cut is final).
- Every media Sequence gets premountFor (numbers.json premount): the video mounts before it shows (no black first frame).
- work/timeline_zoom.json {"segments": [{fromFrame, durFrames, zoom, drift, framing, crop, srcW, srcH, fit}]} records how each
  clip is placed on the canvas; face_zones.py maps the faces through it, so card bands are measured on the frame the viewer sees.
- A CapCut draft also gets drift={0}: the user's framing is final, no slow push-in on top.
- Every cut is softened: the outgoing clip is held (muted) for --xfade frames while the incoming one fades in
  on top (the sound: dialogue.py's stem crossfades every cut; without a stem the proxy's sound switches exactly on the cut). A segment with "transition": "whip" gets a whip-pan
  (blur + slide) instead of the dissolve; "audioFadeIn": N ramps its sound over N frames (cut inside a word).
  Hard cuts read as jerky in reels; 6–8 frames is invisible as a dissolve but removes the snap.
- Other seams (references/craft/transitions.md): "transition" "cut" | "push" | "blur" | "leak" | "wipe" | "bodywipe" | "match"
  (ui/Seam.tsx). "match" and "bodywipe" need work/seams.json from seams.py (run it after this script, then run this again);
  without it they fall back to a dissolve / a plain wipe. Each seam sets its own overlap (push / cut 1 frame, wipe
  seamWipeFrames, bodywipe the person's crossing).
- The seam budget (the user, 2026-11-09: «вжух на каждое действие» is a terrible video): most cuts stay plain; WARNINGs when
  effect seams exceed seamFxPerMin, come closer than seamFxGapCuts plain cuts, repeat a kind within seamRepeatSec, use more
  than transitionKindsMax kinds, or a leak appears more than once.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, clip_id, check_unique, load_json, load_offsets
KINDS = {"dissolve", "cut", "whip", "push", "blur", "leak", "wipe", "bodywipe", "match"}
PLAIN = {"dissolve", "cut"}
ap = argparse.ArgumentParser(); ap.add_argument("--cutlist", default="work/cutlist.json"); ap.add_argument("--out", default="reel/src/Timeline.tsx")
ap.add_argument("--xfade", type=int, default=N["xfade"], help="overlap frames on every cut (0 = hard cuts)")
ap.add_argument("--punch", type=float, default=None, help="(default: 1.0 with alternation for plans, none for CapCut drafts) "
                "base framing scale for talking-head clips (1.0 = full frame; 1.2 brings a small figure in a wide pool/couch shot closer). Jump cuts inside one source alternate base / base+0.1; a cut-list segment may carry its own \"punch\".")
a = ap.parse_args()
cl = json.load(open(a.cutlist)); fps = cl["fps"]; segs = [s for s in cl["main"] if s["materialType"] == "video"]
for s in cl["main"]:
    if s["materialType"] != "video": print(f"WARNING: main-track {s['materialType']} segment at {s['tlStart']}s ({s.get('name')}) is not a video — place it by hand in Reel.tsx (e.g. <Img> in a Sequence)")
OFFSETS = load_offsets(a.cutlist)  # proxies trimmed with make_proxies --trim-to-cutlist
bad = [f"{s.get('name') or os.path.basename(s['path'])} @ {s['tlStart']}s: durFrames {s['durFrames']}" for s in segs if int(s["durFrames"]) <= 0]
if bad: sys.exit("segments without frames (fix the cut list / plan):\n  " + "\n  ".join(bad))
DRAFT = cl.get("draft") not in ("transcript-cut", "silent")
ALTERNATE = a.punch is not None or not DRAFT; BASE = 1.0 if a.punch is None else a.punch
KEEP_FRAMING = DRAFT and a.punch is None   # CapCut draft without an explicit --punch: no punch, no drift
# merge mute slivers
merged = []
for s in segs:
    if merged:
        p = merged[-1]
        same = p["path"] == s["path"] and abs((p["trimBeforeFrames"] + p["durFrames"]) - s["trimBeforeFrames"]) <= 1
        if same and p.get("speed", 1) == s.get("speed", 1) and (p["volume"] < 0.01) != (s["volume"] < 0.01) and min(p["durFrames"], s["durFrames"]) <= 15:
            mute_first = p["volume"] < 0.01
            p.setdefault("muteRanges", []).append((0, p["durFrames"]) if mute_first else (p["durFrames"], p["durFrames"] + s["durFrames"]))
            p["durFrames"] += s["durFrames"]; p["dur"] += s["dur"]; p["volume"] = 1.0
            continue
    merged.append(dict(s))
X = a.xfade
SEAMS = (load_json(os.path.join(os.path.dirname(a.cutlist) or ".", "seams.json"), {}) or {}).get("cuts", {})


def kind_of(seg):
    """The seam INTO this segment: the cut list's "transition" (a CapCut transition dict → a dissolve)."""
    t = seg.get("transition")
    if isinstance(t, str):
        if t not in KINDS: sys.exit(f"segment at {seg['tlStart']}s: unknown transition {t!r} — one of {sorted(KINDS)}")
        if t == "match" and "match" not in SEAMS.get(str(seg["fromFrame"]), {}): print(f"WARNING: match cut at {seg['tlStart']:.1f}s has no seams.json entry (run seams.py, then this again) — dissolve for now"); return "dissolve"
        if t == "bodywipe" and "wipe" not in SEAMS.get(str(seg["fromFrame"]), {}): print(f"WARNING: bodywipe at {seg['tlStart']:.1f}s has no seams.json entry (run seams.py, then this again) — a plain wipe for now"); return "wipe"
        return t
    return "dissolve" if X > 0 else "cut"


def overlap(kind, seg):
    if kind == "bodywipe": return len(SEAMS[str(seg["fromFrame"])]["wipe"]["xs"])
    if kind == "wipe": return N["seamWipeFrames"]
    if kind in ("cut", "push"): return 1
    return max(1, X)


def budget(merged, kinds):
    """The seam budget: effect seams are rare, never back to back, a kind does not repeat soon, a leak once."""
    fx = [(i, k, merged[i]["fromFrame"] / fps) for i, k in enumerate(kinds) if i > 0 and k not in PLAIN]
    if not fx: return
    minutes = max(cl["totalFrames"] / fps / 60, 0.25); cap = max(1, round(N["seamFxPerMin"] * minutes))
    if len(fx) > cap: print(f"SEAM BUDGET: {len(fx)} effect seams in {minutes * 60:.0f} s (at most {cap}: seamFxPerMin {N['seamFxPerMin']}) — make the rest plain dissolves")
    for (i, k, t), (j, e, u) in zip(fx, fx[1:]):
        if j - i - 1 < N["seamFxGapCuts"]: print(f"SEAM BUDGET: {k} at {t:.1f}s and {e} at {u:.1f}s have {j - i - 1} plain cut(s) between them (≥ {N['seamFxGapCuts']}) — alternate")
        if k == e and u - t < N["seamRepeatSec"]: print(f"SEAM BUDGET: {k} again after {u - t:.1f}s (≥ {N['seamRepeatSec']} s between two of a kind)")
    used = sorted({k for k in kinds[1:]})
    if len(used) > N["transitionKindsMax"]: print(f"SEAM BUDGET: {len(used)} seam kinds {used} (at most {N['transitionKindsMax']} per reel, repeated)")
    if sum(k == "leak" for _, k, _ in fx) > 1: print("SEAM BUDGET: more than one light leak — once per reel")


lines = ['import React from "react";', 'import { AbsoluteFill, Sequence } from "remotion";', 'import { Clip } from "./Clip";', 'import { colors } from "./theme";', '',
         (f'/** Cut list from work/plan.json ({fps} fps). Keep numbers hardcoded: Studio edits them.' if cl["draft"] == "transcript-cut" else f'/** Cut list imported 1:1 from CapCut draft "{cl["draft"]}" ({fps} fps). Keep numbers hardcoded: Studio edits them.'),
         f' *  Each clip overlaps the next by {X} frames (dissolve / whip); audio switches on the cut. */',
         'export const Timeline: React.FC = () => {', '  return (', '    <AbsoluteFill style={{ backgroundColor: colors.bg }}>']
prev_src = None; punch = 1.0; zoom, framing = [], []
kinds = [kind_of(s) if i else None for i, s in enumerate(merged)]
budget(merged, kinds)
for i, s in enumerate(merged):
    cid = clip_id(s["path"])
    base = float(s.get("punch", BASE))
    if s["path"] == prev_src and ALTERNATE: punch = base + 0.1 if abs(punch - base) < 0.01 else base
    else: punch = base
    prev_src = s["path"]
    tb = s["trimBeforeFrames"] - round(OFFSETS.get(cid, 0) * fps)
    last = i == len(merged) - 1
    nxt = merged[i + 1] if not last else None
    props = [f'src="footage/{cid}.mp4"', f'trimBefore={{{tb}}}', f'punch={{{punch}}}']
    drift = 0 if KEEP_FRAMING else N["punchDrift"]
    if KEEP_FRAMING: props.append("drift={0}")   # a draft keeps the user's framing: no slow push-in either
    if s.get("drift") is not None:   # a plan range may set its own push-in: 0 for a framed composite (a window baked into the
        drift = float(s["drift"]); props.append(f"drift={{{drift}}}")   # picture must not grow — «Покупать байк» 2026-11-10)
    if s.get("speed", 1) != 1: props.append(f'playbackRate={{{s["speed"]}}}')
    if s["volume"] < 0.01: props.append("volume={0}")
    elif s.get("muteRanges"):
        cond = " || ".join(f"(f >= {a0} && f < {a1})" for a0, a1 in s["muteRanges"]); props.append(f"volume={{(f) => ({cond} ? 0 : 1)}}")
    dur = s["durFrames"]
    k_in = kinds[i]; k_out = kinds[i + 1] if nxt is not None else None
    ov_in = overlap(k_in, s) if i > 0 else 0; ov_out = overlap(k_out, nxt) if nxt is not None else 0
    if ov_out or ov_in: props.append(f"hold={{{dur}}}")
    if i > 0 and k_in != "cut":
        props.append(f'enter="{k_in}" enterFrames={{{ov_in}}}')
        sm = SEAMS.get(str(s["fromFrame"]), {})
        if k_in == "match": props.append("match={" + json.dumps(sm["match"]) + "}")
        if k_in == "bodywipe": props.append("wipe={" + json.dumps(sm["wipe"]) + "}")
    if k_out in ("whip", "push", "blur", "leak"): props.append(f'exit="{k_out}" exitFrames={{{ov_out}}}')
    if s.get("audioFadeIn"): props.append(f'audioFadeIn={{{s["audioFadeIn"]}}}')
    name = f"{i:02d} {cid} {s['tlStart']:.1f}s"
    frm = f' from={{{s["fromFrame"]}}}' if s["fromFrame"] else ""  # from={0} is the default (lint rule)
    total = dur + ov_out
    lines.append(f'      <Sequence name="{name}"{frm} durationInFrames={{{total}}} premountFor={{{N["premount"]}}}>')
    tf = s.get("transform") or {}; crop = s.get("crop"); fr = None
    if tf:   # the user's CapCut framing (the cut is final): Clip reproduces scale / position / rotation / flip
        fr = {k: round(v, 4) if isinstance(v, float) else v for k, v in tf.items() if v not in (None, 0, False) and not (k in ("scale", "scaleY") and abs(v - 1) < 1e-3)}
        props.append("framing={{" + ", ".join(f"{k}: {json.dumps(v)}" for k, v in fr.items()) + "}}"); framing.append(name)
    if crop:
        if s.get("srcW") and s.get("srcH"):
            props.append("crop={{" + ", ".join(f"{k}: {round(crop[k], 4)}" for k in ("x0", "y0", "x1", "y1")) + "}}" + f" srcW={{{s['srcW']}}} srcH={{{s['srcH']}}}"); framing.append(name)
        else: print(f"WARNING: {name}: CapCut crop without the source size (re-export the draft) — not applied")
    fit = None
    if DRAFT and not tf and not crop and s.get("srcW") and s.get("srcH") and abs(s["srcW"] / s["srcH"] - 9 / 16) > 0.02:
        props.append('fit="contain"'); fit = "contain"   # CapCut letterboxes a non-9:16 main-track clip at scale 1
    if s.get("keyframes"): lines.append(f'        {{/* CapCut keyframes ({s.get("keyframeGroups")} groups: zoom/position animation) — only the base framing is reproduced */}}')
    lines.append(f'        <Clip {" ".join(props)} />')
    zoom.append({"fromFrame": s["fromFrame"], "durFrames": dur, "zoom": punch, "drift": drift, "clip": cid, "framing": fr, "tb": tb, "speed": s.get("speed", 1),
                 "transition": k_in, "tl": s["tlStart"],
                 "crop": crop if crop and s.get("srcW") and s.get("srcH") else None, "srcW": s.get("srcW"), "srcH": s.get("srcH"),
                 "fit": fit or ("contain" if fr or crop else "cover")})   # face_zones.py maps faces through all of it
    lines.append('      </Sequence>')
lines += ['    </AbsoluteFill>', '  );', '};', '', f'export const TOTAL_FRAMES = {cl["totalFrames"]};', '']
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
open(a.out, "w").write("\n".join(lines))
json.dump({"drift": N["punchDrift"], "centerY": N["punchCenterY"], "segments": zoom}, open(os.path.join(os.path.dirname(a.cutlist) or ".", "timeline_zoom.json"), "w"), indent=1)
if framing: print(f"NOTE: {len(set(framing))} clip(s) keep the user's CapCut framing (scale/position/crop) — compare one still with CapCut")
fxs = [k for k in kinds[1:] if k not in PLAIN]
clip_tsx = os.path.join(os.path.dirname(a.out), "Clip.tsx")
if set(fxs) - {"whip"} and os.path.exists(clip_tsx) and "ui/Seam" not in open(clip_tsx).read():
    print("WARNING: reel/src/Clip.tsx predates the seams (scaffold.sh never overwrites it) — copy Clip.tsx and ui/Seam.tsx from the "
          "skill's assets/remotion-template/src and re-run scaffold.sh (installs @remotion/effects), or tsc fails on the new seam kinds")
if fxs: print("seams:", ", ".join(f"{k} ×{fxs.count(k)}" for k in sorted(set(fxs))), f"of {len(merged) - 1} cuts")
print(f"TIMELINE_DONE {a.out}: {len(merged)} clips, xfade {X}, punch {'off (CapCut draft)' if not ALTERNATE and BASE == 1.0 else BASE}")
