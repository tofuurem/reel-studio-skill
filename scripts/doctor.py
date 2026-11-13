#!/usr/bin/env python3
"""Where is this project, what is broken, what is the next step — and the gate render.sh runs before every render.

Usage: python3 -I doctor.py <project> [--pre-render] [--comp Reel|Reel2K|Action|ActionTrack|Action2K] [--json]
Checks (OK / WARN / ERR per line):
  env       ffmpeg, ffprobe, node, uv; the shared venvs (setup_env.sh); numpy for glitch_scan; fonts in reel/public/fonts
  cutlist   work/cutlist.json parses, every segment has frames and a sane source range; sources reachable; a LUT hint for DJI clips
  crop      a portrait canvas with landscape camera segments: work/people_zones.json (people_zones.py) covers every one of them,
            and each proxy was cropped from those zones (manifest «crop») — else the 9:16 crop is a guess at the centre
  timeline  reel/ scaffolded, Timeline.tsx newer than the cut list and the proxy offsets, TOTAL_FRAMES = the cut list
  proxies   per folder (footage = Reel, footage2k = Reel2K): every source has a proxy whose manifest matches the cut list —
            window start = proxy_offsets.json, every segment inside the window, duration = window, LUT on camera clips, the
            isolated voice on speaking sources; both folders cut from the same windows; no temp files in public/
  assets    every staticFile("…") / "footage/…" path in reel/src exists in reel/public (missing screenshots, sfx, bed, fonts)
  captions  transcript newer than the cut list and Timeline.tsx, captions and tl_words newer than the transcript (ERR: a re-cut
            not carried through would ship out-of-sync captions); skipped for a silent cut list or a Reel without <Captions>
  reel      Reel.tsx newer than work/gen_reel.py, tl_words.txt and the cut list (graphics follow the words)
  covers    images referenced by src/Cover*.tsx exist in covers/public (or ../covers/public for a series)
  swears    every swear in the transcript is masked in the captions and covered by work/bleeps.json (dialogue.py bleeps the stem)
  audio     the dialogue stem (dialogue.py) exists, is newer than the cut list / restored voice / bleeps, and Reel.tsx plays it
  lint      lint_reel.py on reel/src (backdrop-filter / mix-blend-mode are errors)
  action    (--comp Action* or a project with work/shots.json and no cut list) every piece, matte and voice of work/shots.json
            exists, shotsData.ts is newer than shots.json and gen_action.py, ActionTrack has its preview track
  night     dark clips listed in work/night_lift.json whose proxy was re-encoded without the lift (re-run night_lift.py)
Prints a table and NEXT: <the next pipeline step>. --pre-render exits 1 on any ERR (render.sh refuses; FORCE=1 overrides);
--comp limits the proxy errors to that composition's folder (the other one is a warning). Without --pre-render it always exits 0.
"""
import argparse, glob, json, os, platform, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FONTS, clip_id, crop_keys, crop_sig, duration, in_ranges, is_camera, load_json, looks_log, load_lut_map, lut_for, needs_crop, probe, silent_ranges, src_dur, zone_covers
from swear import is_swear

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--pre-render", action="store_true")
ap.add_argument("--comp", choices=["Reel", "Reel2K", "Action", "ActionTrack", "Action2K"]); ap.add_argument("--json", action="store_true")
a = ap.parse_args()
P = os.path.abspath(a.project); HERE = os.path.dirname(os.path.abspath(__file__))
# a per-project LUT map (work/lut_map.json, the file make_proxies --lut-map got): an explicit "none" is a decision, not a grey clip
LUT_MAP = load_lut_map(os.path.join(P, "work/lut_map.json")) if os.path.exists(os.path.join(P, "work/lut_map.json")) else {}
def pj(*x): return os.path.join(P, *x)
def mt(p): return os.path.getmtime(p) if os.path.exists(p) else 0
rows, nexts = [], []
def add(level, area, msg): rows.append((level, area, msg))
def nxt(step): nexts.append(step)

# ---------------------------------------------------------------- env
for tool in ("ffmpeg", "ffprobe", "node", "zsh", "uv"):
    if not shutil.which(tool): add("ERR" if tool != "uv" else "WARN", "env", f"{tool} not found — python3 -I {os.path.dirname(os.path.abspath(__file__))}/deps.py --install")
APPLE_SILICON = sys.platform == "darwin" and platform.machine() == "arm64"
for v in ("venv", "dfvenv", "gigvenv"):   # gigvenv = GigaAM, Russian speech (transcribe.py --lang ru, transcribe_gigaam.py); Whisper lives in venv
    if not os.path.exists(pj("work", v, "bin", "python")): add("WARN", "env", f"work/{v} missing — setup_env.sh {P}")
py = pj("work/venv/bin/python") if os.path.exists(pj("work/venv/bin/python")) else "python3"
if subprocess.run([py, "-I", "-c", "import numpy"], capture_output=True).returncode: add("ERR", "env", "numpy missing (glitch_scan.py) — setup_env.sh")

# ---------------------------------------------------------------- cut list
cl_path = pj("work/cutlist.json"); cl = load_json(cl_path)
# an action reel (inputs/action-reel.md) has no cut list: work/shots.json from actiongen.py instead
ACTION = (a.comp or "").startswith("Action") or (not cl and os.path.exists(pj("work/shots.json")))
if ACTION: cl = None
silent = bool(cl and cl.get("silent"))
if ACTION: pass
elif not cl:
    add("ERR", "cutlist", "work/cutlist.json missing"); nxt("make the cut list: capcut_export.py (draft) · cut_from_transcript.py work/plan.json (raw takes / voiceover) · silent_timeline.py (images only)")
else:
    segs = [s for s in cl["main"] if s.get("materialType", "video") == "video"]
    bad = [s for s in segs if int(s.get("durFrames", 0)) <= 0 or float(s.get("dur", 0)) <= 0 or float(s.get("srcStart", 0)) < 0]
    if bad: add("ERR", "cutlist", f"{len(bad)} segment(s) without frames or with a negative source start: " + ", ".join(f"@{s['tlStart']}s" for s in bad[:5]))
    if int(cl.get("totalFrames", 0)) <= 0: add("ERR", "cutlist", "totalFrames is 0")
    if not bad: add("OK", "cutlist", f"{len(segs)} segments, {cl['totalFrames']} frames ({cl['totalFrames'] / cl['fps']:.1f} s)" + (" — SILENT (images only)" if silent else ""))
    missing = [s for s in cl["sources"] if not os.path.exists(s)]
    if missing: add("WARN", "cutlist", f"{len(missing)} source(s) not reachable (volume not mounted?) — fine while the proxies are complete: " + ", ".join(os.path.basename(m) for m in missing[:3]))
    for s in cl["sources"]:
        if is_camera(s) and os.path.exists(s):
            lut, why = lut_for(s, next((p for p in cl.get("luts", {}).values() if p), None))
            if not lut and why.startswith("NO LUT FOUND"): add("ERR", "cutlist", f"{os.path.basename(s)}: {why}")
            elif not lut and looks_log(s) and not why.startswith("djmd"): add("WARN", "cutlist", f"no LUT for {os.path.basename(s)} — fine for Normal / Rec.709 footage; D-Log needs make_proxies --lut / --lut-map")

# ---------------------------------------------------------------- crop (people-aware 9:16 crop of landscape camera clips)
zones = load_json(pj("work/people_zones.json"), {}) or {}; crop_srcs = set()
if cl:
    infos = {s: probe(s) for s in cl["sources"] if is_camera(s) and os.path.exists(s)}
    need = [s for s in cl["main"] if s.get("materialType", "video") == "video" and s["path"] in infos and needs_crop(cl, s, infos[s["path"]])]
    crop_srcs = {s["path"] for s in need}
    if need:
        miss = [s for s in need if not zone_covers(zones, s)]
        if not zones: add("ERR", "crop", f"{len(need)} landscape camera segment(s) for a 9:16 canvas, no work/people_zones.json — the crop would be a guess at the centre"); nxt("work/venv/bin/python -I people_zones.py --sheet (then look at work/people/sheet_*.jpg)")
        elif miss: add("ERR", "crop", f"{len(miss)} segment(s) not in work/people_zones.json (re-cut?): " + ", ".join(f"{clip_id(s['path'])}@{s['srcStart']:.1f}" for s in miss[:4])); nxt("work/venv/bin/python -I people_zones.py --sheet")
        else:
            nobody = [r for r in zones["segments"] if r.get("mode") == "centre"]
            add("WARN" if nobody else "OK", "crop", f"people zones cover {len(need)} segment(s)" + (f"; nobody found in {len(nobody)} (centre crop — cropX in plan.json if wrong)" if nobody else ""))

# ---------------------------------------------------------------- action reel
if ACTION:
    sj = load_json(pj("work/shots.json"))
    if not sj: add("ERR", "action", "work/shots.json missing"); nxt("work/venv/bin/python -I work/gen_action.py (from assets/examples/gen_action.example.py)")
    else:
        lost = [p["file"] for s in sj["shots"] for p in s["pieces"] if not os.path.exists(pj("reel/public", p["file"]))]
        lost += [p["matte"] for s in sj["shots"] for p in s["pieces"] if p.get("matte") and not os.path.exists(pj("reel/public", p["matte"]))]
        lost += [s["voice"] for s in sj["shots"] if s.get("voice") and not os.path.exists(pj("reel/public", s["voice"]))]
        if lost: add("ERR", "action", f"{len(lost)} piece/voice/matte file(s) missing: {', '.join(lost[:4])}"); nxt("work/venv/bin/python -I work/gen_action.py")
        ts = pj("reel/src/shotsData.ts")
        if not os.path.exists(ts) or mt(ts) < mt(pj("work/shots.json")): add("ERR", "action", "reel/src/shotsData.ts older than work/shots.json"); nxt("work/venv/bin/python -I work/gen_action.py")
        elif os.path.exists(pj("work/gen_action.py")) and mt(ts) < mt(pj("work/gen_action.py")): add("ERR", "action", "shotsData.ts is older than work/gen_action.py — re-run it"); nxt("work/venv/bin/python -I work/gen_action.py")
        elif not lost: add("OK", "action", f"{len(sj['shots'])} shots, {sum(s['frames'] for s in sj['shots'])} frames, every piece present")
        tb = load_json(pj("work/track_beats.json"))
        if a.comp == "ActionTrack" and not os.path.exists(pj("reel/public/audio/track_cut.m4a")): add("ERR", "action", "ActionTrack needs reel/public/audio/track_cut.m4a — track_beats.py <project> <track> --start S")
        if tb and tb.get("start") is not None: add("OK", "action", f"track grid from {tb['start']:.3f} s ({tb['bpm']} BPM, drop at frame {(tb.get('grid') or {}).get('drop')}) — the user starts the track there in Instagram")

# ---------------------------------------------------------------- night lift (dark proxies graded after make_proxies)
nl = load_json(pj("work/night_lift.json"), {}) or {}
if cl and nl:
    for folder, comp in (("footage", "Reel"), ("footage2k", "Reel2K")):
        if a.comp not in (None, comp): continue
        ungraded = []
        for cid, st in nl.items():
            f = pj("reel/public", folder, cid + ".mp4")
            if st.get("level") and os.path.exists(f) and "night_lift:" not in subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "csv=p=0", f], capture_output=True, text=True).stdout:
                ungraded.append(cid)
        if ungraded: add("WARN", "proxies", f"{folder}: dark clip(s) re-encoded without the night lift: {', '.join(ungraded[:5])}"); nxt(f"night_lift.py {P}")

# ---------------------------------------------------------------- timeline / scaffold
if not os.path.exists(pj("reel/package.json")) or not os.path.isdir(pj("reel/node_modules")):
    add("ERR", "timeline", "reel/ not scaffolded (package.json / node_modules)"); nxt(f"scaffold.sh {P} (background, wait for SCAFFOLD_OK)")
tl = pj("reel/src/Timeline.tsx")
if cl and not ACTION:
    txt = open(tl).read() if os.path.exists(tl) else ""
    m = re.search(r"TOTAL_FRAMES\s*=\s*(\d+)", txt)
    if not txt or "Clip" not in txt: add("ERR", "timeline", "Timeline.tsx missing or still the stub"); nxt("gen_timeline.py")
    elif mt(tl) < mt(pj("work/cutlist.json")) or mt(tl) < mt(pj("work/proxy_offsets.json")):
        add("ERR", "timeline", "Timeline.tsx is older than the cut list / proxy offsets"); nxt("gen_timeline.py")
    elif not m or int(m.group(1)) != int(cl["totalFrames"]): add("ERR", "timeline", f"TOTAL_FRAMES {m.group(1) if m else '?'} ≠ cut list {cl['totalFrames']}"); nxt("gen_timeline.py")
    else: add("OK", "timeline", f"Timeline.tsx matches the cut list ({cl['totalFrames']} frames)")

# ---------------------------------------------------------------- proxies
offsets = load_json(pj("work/proxy_offsets.json"), {}) or {}
folders = [("footage", "Reel"), ("footage2k", "Reel2K")]
mans = {f: load_json(pj("reel/public", f, ".manifest.json"), {}) or {} for f, _ in folders}
need_proxies = False
if cl:
    speaking = {s["path"] for s in cl["main"] if s.get("materialType", "video") == "video" and float(s.get("volume", 1)) >= 0.01}
    for folder, comp in folders:
        level = "ERR" if (a.comp in (None, comp)) else "WARN"
        man = mans[folder]; probs = []
        if not man and glob.glob(pj("reel/public", folder, "*.mp4")): probs.append("no .manifest.json (proxies from an older make_proxies) — re-run make_proxies once")
        for src in cl["sources"]:
            cid = clip_id(src); out = pj("reel/public", folder, cid + ".mp4"); e = man.get(cid)
            if not os.path.exists(out): probs.append(f"{cid}: no proxy"); continue
            if not e: continue
            if abs(float(e.get("start", 0)) - float(offsets.get(cid, 0))) > 0.01: probs.append(f"{cid}: cut from {e.get('start')} s, proxy_offsets says {offsets.get(cid, 0)} s (other windows than the other resolution)")
            for s in cl["main"]:
                if s["path"] != src: continue
                a0, a1 = float(s["srcStart"]), float(s["srcStart"]) + src_dur(s)
                if a0 < float(e["start"]) - 0.01 or a1 > float(e["end"]) + 0.01: probs.append(f"{cid}: segment {a0:.2f}–{a1:.2f} s is outside the proxy window {e['start']}–{e['end']}"); break
            d = duration(out); want = float(e["end"]) - float(e["start"])
            if abs(d - want) > max(0.6, want * 0.002) and e.get("kind") != "broll": probs.append(f"{cid}: proxy {d:.2f} s, window {want:.2f} s")
            if not e.get("lut") and os.path.exists(src) and probe(src).get("hdr") and not lut_for(src, None, LUT_MAP)[1].startswith("lut-map"): probs.append(f"{cid}: HDR source encoded without the HDR → Rec.709 LUT (grey, pale) — re-run make_proxies")
            if src in crop_srcs and zones and e.get("crop") != crop_sig(crop_keys(zones, src)): probs.append(f"{cid}: cropped {'at the centre' if not e.get('crop') else 'from older people zones'} — re-run make_proxies")
            if src in speaking and not e.get("voice") and not silent: add("WARN", "proxies", f"{folder}/{cid}: camera sound, no isolated voice")
        if probs:
            need_proxies = True
            for x in probs: add(level, "proxies", f"{folder}: {x}")
        elif man: add("OK", "proxies", f"{folder}: {len(cl['sources'])} source(s) match the cut list")
    f1, f2 = mans["footage"], mans["footage2k"]
    for cid in set(f1) & set(f2):
        if f1[cid].get("voice") != f2[cid].get("voice") or f1[cid].get("lut") != f2[cid].get("lut"): add("WARN", "proxies", f"{cid}: footage and footage2k differ in voice/LUT — re-run make_proxies --res both")
    if need_proxies: nxt("make_proxies.py --res both --trim-to-cutlist 2 --voice-dir work/voice/out [--extra …]")
tmps = [p for p in glob.glob(pj("reel/public/**/*"), recursive=True) if re.search(r"\.tmp(\.|$)|\.part$", os.path.basename(p))]
if tmps: add("ERR", "proxies", f"temp files in reel/public (the bundler dies on them): {', '.join(os.path.relpath(t, P) for t in tmps[:3])}")

# ---------------------------------------------------------------- assets referenced by the source
src_dir = pj("reel/src")
if os.path.isdir(src_dir):
    refs, cover_refs = set(), set()
    TALK = {"Reel.tsx", "Timeline.tsx", "Captions.tsx", "Sfx.tsx"}; ACT = {"Action.tsx", "shotsData.ts"}   # check only the files the comp renders
    reel_src = open(os.path.join(src_dir, "Reel.tsx"), encoding="utf-8").read() if os.path.exists(os.path.join(src_dir, "Reel.tsx")) else ""
    for f in glob.glob(os.path.join(src_dir, "**/*.ts*"), recursive=True):
        if os.path.basename(f) in (TALK if ACTION else ACT): continue
        t = open(f, encoding="utf-8").read()
        # comments are no references: blocks/BeforeAfter.tsx documents «"screens/old.png"» and stopped every render (Halloween v4)
        t = re.sub(r"(?m)^\s*//[^\n]*|\s//\s[^\n]*", "", re.sub(r"/\*.*?\*/", "", t, flags=re.S))
        found = set(re.findall(r"""staticFile\(\s*["'`]([^"'`$]+)["'`]\s*\)""", t))
        found |= {r for r in re.findall(r"""["'`]((?:footage|screens|audio|captions|covers|fonts)/[^"'`$\s]+\.\w{2,5})["'`]""", t)}
        if os.path.basename(f) == "Sfx.tsx" and "<MusicBed" not in reel_src:   # the bed's default path is no reference when the reel has no MusicBed (music: none)
            found = {r for r in found if not r.startswith("audio/lofi_bed")}
        # covers render from their own public dir (cover.sh --public-dir <covers>/public), not from reel/public
        (cover_refs if os.path.basename(f).startswith("Cover") else refs).update(found)
    pubs = [d for d in (pj("covers/public"), pj("../covers/public")) if os.path.isdir(d)]
    lost = [r for r in sorted(cover_refs) if r.startswith("covers/") and not any(os.path.exists(os.path.join(d, r)) for d in pubs)]
    if lost: add("WARN", "covers", f"{len(lost)} cover image(s) not in covers/public: {', '.join(lost[:4])}")
    missing = []
    for r in sorted(refs):
        if r.startswith("footage/"):
            for folder, comp in folders:
                if a.comp in (None, comp) and not os.path.exists(pj("reel/public", folder, r[len("footage/"):])): missing.append(f"{folder}/{r[len('footage/'):]}")
        elif not os.path.exists(pj("reel/public", r)): missing.append(r)
    if missing: add("ERR", "assets", f"{len(missing)} file(s) used in reel/src are not in reel/public: " + ", ".join(missing[:6]) + (" …" if len(missing) > 6 else ""))
    else: add("OK", "assets", f"{len(refs)} referenced files present")
    fonts_ts = os.path.join(src_dir, "fonts.ts")
    if os.path.exists(fonts_ts) and "fonts/" in open(fonts_ts).read():
        lack = [f for f in FONTS if not os.path.exists(pj("reel/public/fonts", f))]
        if lack: add("ERR", "env", f"fonts missing in reel/public/fonts: {', '.join(lack)} — setup_env.sh, then scaffold.sh copies them")
    reel_txt = open(os.path.join(src_dir, "Reel.tsx")).read() if os.path.exists(os.path.join(src_dir, "Reel.tsx")) else ""
else: reel_txt = ""

# ---------------------------------------------------------------- transcript, captions, swears
words_p, caps_p = pj("work/audio/timeline.json"), pj("reel/public/captions/timeline.json")
uses_caps = "Captions" in reel_txt
if cl and not silent:
    if not os.path.exists(words_p): add("WARN", "captions", "no transcript (work/audio/timeline.json)"); nxt("transcribe.py --lang ru")
    elif mt(words_p) < max(mt(tl), mt(cl_path)): add("ERR", "captions", "transcript is older than the cut list / Timeline.tsx (re-cut?) — captions and anchors would be out of sync"); nxt("transcribe.py → make_captions.py → tl_words.py → gen_reel.py")
    if uses_caps:
        if not os.path.exists(caps_p): add("ERR", "captions", "Reel uses <Captions> but reel/public/captions/timeline.json is missing"); nxt("make_captions.py --brands assets/brands.json")
        elif mt(caps_p) < mt(words_p): add("WARN", "captions", "captions are older than the transcript"); nxt("make_captions.py --brands assets/brands.json")
        else: add("OK", "captions", "captions newer than the transcript")
    if os.path.exists(pj("work/tl_words.txt")) and mt(pj("work/tl_words.txt")) < mt(words_p): add("ERR", "captions", "tl_words.txt older than the transcript — anchors point at old frames"); nxt("tl_words.py (then gen_reel.py)")
    reel_p = pj("reel/src/Reel.tsx")
    if os.path.exists(pj("work/gen_reel.py")) and os.path.exists(reel_p) and mt(reel_p) < max(mt(pj("work/tl_words.txt")), mt(pj("work/gen_reel.py")), mt(cl_path)):
        add("ERR", "reel", "Reel.tsx is older than gen_reel.py / tl_words.txt / the cut list — graphics sit on old frames"); nxt("python3 -I work/gen_reel.py && (cd reel && npx tsc --noEmit -p .)")
    words = [w for s in (load_json(words_p, {}) or {}).get("segments", []) for w in s.get("words", [])]
    quiet = silent_ranges(cl)
    sw = [w for w in words if is_swear(w["word"]) and not in_ranges((w["start"] + w["end"]) / 2, quiet)]
    if sw:
        caps = load_json(caps_p, []) or []
        unmasked = [c["text"].strip() for c in caps if is_swear(c["text"])]
        if unmasked: add("ERR", "swears", f"unmasked in captions: {', '.join(unmasked[:4])} — make_captions.py masks by default (or mask_captions.py)")
        bl = load_json(pj("work/bleeps.json"), None)
        if bl is None: add("ERR", "swears", f"{len(sw)} swear(s) but no work/bleeps.json — bleeps_from_timeline.py (drafts) / cut_from_transcript.py (plans)")
        else:
            miss = [w for w in sw if not any(b["startMs"] / 1000 - 0.05 <= (w["start"] + w["end"]) / 2 <= b["endMs"] / 1000 + 0.05 for b in bl)]
            if miss: add("ERR", "swears", f"not covered by bleeps.json: {', '.join(w['word'].strip() + '@' + format(w['start'], '.1f') for w in miss[:4])} — re-run the bleeps step")
            elif (load_json(pj("work/voice/dialogue.json"), {}) or {}).get("bleeps"): add("OK", "swears", f"{len(sw)} swear(s) masked; bleeped inside the dialogue stem")
            else: add("OK", "swears", f"{len(sw)} swear(s) masked and bleeped — run bleep.py on the render")
if cl and not silent and any(is_camera(s) for s in cl["sources"]):
    fzp = pj("work/face_zones.json")
    if not os.path.exists(fzp): add("WARN", "layout", "no work/face_zones.json — cards are placed blind"); nxt("face_zones.py")
    elif mt(fzp) < max(mt(pj("work/cutlist.json")), mt(pj("work/timeline_zoom.json"))):
        add("ERR", "layout", "work/face_zones.json is older than the cut list / timeline_zoom.json — bands are from the old cut"); nxt("face_zones.py")
# ---------------------------------------------------------------- dialogue stem (dialogue.py)
dts, dwav = pj("reel/src/dialogueSrc.ts"), pj("reel/public/audio/dialogue.wav")
stem_on = bool(os.path.exists(dts) and re.search(r'DIALOGUE[^=]*=\s*"', open(dts).read()))
if cl and not silent and os.path.isdir(src_dir):
    if not os.path.exists(os.path.join(src_dir, "Dialogue.tsx")):
        add("WARN", "audio", "reel/src has no Dialogue.tsx (scaffolded before 2026-11-07): the voice plays from the proxies, cut hard and encoded twice — copy Dialogue.tsx, dialogueSrc.ts and Clip.tsx from the template, then dialogue.py")
    elif not stem_on or not os.path.exists(dwav):
        add("WARN", "audio", "no dialogue stem — the voice plays from the proxies"); nxt("work/dfvenv/bin/python -I $S/dialogue.py <project>")
    else:
        dj = load_json(pj("work/voice/dialogue.json"), {}) or {}
        vfiles = glob.glob(pj("work/voice/out/*_DeepFilterNet3.wav"))
        if mt(dwav) < max([mt(cl_path), mt(pj("work/bleeps.json")), mt(pj("work/voice_tune.json"))] + [mt(v) for v in vfiles]):
            add("ERR", "audio", f"{os.path.basename(dwav)} is older than the cut list / the restored voice / bleeps.json / voice_tune.json — it would play the old cut"); nxt("work/dfvenv/bin/python -I $S/dialogue.py <project>")
        else:
            o = (dj.get("chain") or {}).get("out") or {}
            add("OK", "audio", f"dialogue stem: {len(dj.get('cuts', []))} crossfaded cuts, {dj.get('bleeps', 0)} bleeps, LRA {o.get('lra')} LU" + (f"; voice_tune {sorted(dj['tune'])}" if dj.get("tune") else ""))
        if reel_txt and "<Dialogue" not in reel_txt:
            add("ERR", "audio", "Reel.tsx does not place <Dialogue /> while Clip mutes the proxies — the reel would have no voice"); nxt("python3 -I work/gen_reel.py (reelgen.write adds it)")
if not stem_on:
    for vo in (cl or {}).get("voiceovers", []):
        if not os.path.exists(pj("reel/public/audio", os.path.splitext(os.path.basename(vo))[0] + ".m4a")): add("WARN", "audio", f"CapCut voiceover {os.path.basename(vo)} has no levelled file — dialogue.py puts the voiceovers into the dialogue stem")

# ---------------------------------------------------------------- lint
if os.path.isdir(src_dir):
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "lint_reel.py"), src_dir], capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or ["?"])[-1]
    if r.returncode: add("ERR", "lint", last); [add("ERR", "lint", l) for l in r.stdout.splitlines() if " ERROR " in l][:5]
    elif "warnings=" in last: add("WARN", "lint", last + " — python3 -I $S/lint_reel.py <project>")
    else: add("OK", "lint", "LINT_OK")

if cl and not ACTION and not os.path.exists(pj("work/gen_reel.py")): nxt("write work/gen_reel.py from an example (assets/examples/gen_reel*.example.py) → Reel.tsx")
errs = [r for r in rows if r[0] == "ERR"]
if not nexts: nxt("fix the errors above" if errs else f"render.sh {P} Action2K <abs out>/<name>_2k.mp4 (no music in it; ActionTrack = preview with the track)" if ACTION else f"render.sh {P} Reel2K <abs out>/<name>_2k.mp4 (then bleep.py if bleeps.json is not empty)")
if a.json: print(json.dumps({"rows": rows, "errors": len(errs), "next": nexts[0]}, ensure_ascii=False, indent=1))
else:
    for lv, area, msg in rows: print(f"{lv:4s} {area:9s} {msg}")
    print("NEXT:", nexts[0])
    print("DOCTOR", "OK" if not errs else f"ERRORS {len(errs)}", f"({len([r for r in rows if r[0] == 'WARN'])} warnings)")
sys.exit(1 if (a.pre_render and errs) else 0)
