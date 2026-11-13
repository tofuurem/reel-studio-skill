#!/usr/bin/env python3
"""Transcode the source clips used by the cut list (from a CapCut draft or work/plan.json) plus chosen b-roll into Remotion-friendly proxies.

Usage:
  make_proxies.py --res both|1080|2k [--trim-to-cutlist 2] [--voice-dir work/voice/out] [--lut path.cube] [--lut-map map.json]
                  [--extra PATH[@start-end] ...] [--cutlist work/cutlist.json] [--public reel/public] [--allow-missing] [--force]
                  [--people work/people_zones.json] [--centre-crop]

- `--res both` decodes each source ONCE and writes public/footage (1080x1920) and public/footage2k (1440x2560) — use it;
  two parallel passes are refused (a lock), they used to clobber each other's temp files.
- H.264 yuv420p, 30 fps, lanczos scale to the canvas (camera clips fill 9:16 — a horizontal camera clip is cropped, not
  squashed; screen recordings keep their aspect at canvas width). Scale runs BEFORE the LUT (half the work).
- The crop of a landscape camera clip follows the people: work/people_zones.json (people_zones.py, Apple Vision) gives every
  segment a centre or a pan, written into the proxy as one piecewise-linear ffmpeg crop over the window. Without zones for
  every such segment the run stops before encoding (a centre crop loses whoever stands at the edge); --centre-crop accepts
  the old centre crop on purpose. The keyframes are in the manifest («crop»), so a changed crop re-encodes that clip.
- LUT (log → Rec.709) is burned into camera clips only, and only when one is known: per clip via common.lut_for — --lut-map glob, then
  the DJI colour profile recorded in the file (djmd: Normal → none, D-Log / D-Log M → that camera's cube if installed), then --lut
  or the draft's LUT; otherwise none (Rec.709 assumed). Chrome cannot colour-manage log footage.
  An HDR source (HLG / PQ — iPhone «HDR video», Android HDR10, a camera in HLG mode; any kind) gets the HDR → Rec.709 LUT from
  hdr_lut.py instead (fitted to Apple's own conversion): tagged bt709 without it, HLG looks grey, flat and pale.
- `-map 0:v:0` because DJI files carry a second (preview) video stream that breaks muxing.
- With --voice-dir the isolated-voice WAV replaces the camera track (same length, so sync is kept).
- --trim-to-cutlist PAD encodes only the used part of each source (± PAD s; speed-changed CapCut segments use their source
  duration). Offsets go to work/proxy_offsets.json; gen_timeline / transcribe / face_zones subtract them. --extra b-roll can be
  windowed too: `clip.MP4@12.5-30` (then BRoll trimBefore = (source s − offset) × 30, offsets are in proxy_offsets.json too).
  --extra files are muted; 29.97/59.94 fps b-roll is retimed to 30 without duplicate frames.
- Each folder keeps `.manifest.json` {clipId: {src, start, end, voice, voice_mtime, lut, crf, res, kind, speed, crop}}: a proxy is
  re-encoded when ANY of it changed (a window that grew or moved, voice file, LUT, CRF) or its duration does not match — not only
  when the window start moved (audit 2026-10-22: a longer window, a new --voice-dir, a 1080-only re-run all used to be skipped).
  When ONLY the voice changed (a dualmic / voice_clean re-run), the video stream is copied and the new voice remuxed (REMUX).
  A window that only SHRANK inside the old one keeps the proxies (and the old offset) in both folders.
- Writes go to work/tmp first and are verified (ffprobe duration) before they replace the proxy: no half files in public/.
- Missing sources (volume not mounted) end the run with exit 1 after the rest is done (--allow-missing to accept).
≈ 1.1 s of encode per second of 1080 footage, 2.5 s per second at 2k (M-series); `both` ≈ the 2k time alone.
"""
import argparse, fcntl, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HWACCEL, N, atomic_json, check_unique, clip_id, commit, crop_expr, crop_keys, crop_sig, ffmpeg, is_camera, looks_log, load_json, load_lut_map, lut_for, needs_crop, nfc, probe, src_dur, tmp_for, duration, _rm, zone_covers

ap = argparse.ArgumentParser()
ap.add_argument("--res", choices=["1080", "2k", "both"], required=True)
ap.add_argument("--lut"); ap.add_argument("--lut-map", help='JSON {"<glob on file name>": "<cube path or none>"} for mixed cameras')
ap.add_argument("--voice-dir"); ap.add_argument("--extra", nargs="*", default=[], help="b-roll files, optionally windowed: path@start-end (source seconds)")
ap.add_argument("--cutlist", default="work/cutlist.json"); ap.add_argument("--public", default="reel/public")
ap.add_argument("--crf", type=int, default=N["proxyCrf"])
ap.add_argument("--trim-to-cutlist", type=float, default=None, metavar="PAD_SEC", help=f"encode only the used part of each source (+PAD s each side, usually {N['proxyPadSec']}); offsets → work/proxy_offsets.json")
ap.add_argument("--no-lut", action="store_true", help="no LUT at all (a frame grab proved the footage is already Rec.709)")
ap.add_argument("--allow-missing", action="store_true", help="exit 0 even when a source is missing (volume not mounted)")
ap.add_argument("--force", action="store_true", help="re-encode everything")
ap.add_argument("--people", default="work/people_zones.json", help="crop centres from people_zones.py (Apple Vision)")
ap.add_argument("--centre-crop", action="store_true", help="crop landscape camera clips at the centre without people zones")
a = ap.parse_args()
cl = json.load(open(a.cutlist)); work = os.path.dirname(a.cutlist) or "."
RES = {"1080": ("footage", 1080, 1920), "2k": ("footage2k", 1440, 2560)}
targets = ["2k", "1080"] if a.res == "both" else [a.res]
landscape = bool(cl["canvas"].get("w") and cl["canvas"].get("h") and cl["canvas"]["w"] > cl["canvas"]["h"])

# one run at a time: the temp folder is shared, and two passes used to race on proxy_offsets.json
os.makedirs(os.path.join(work, "tmp"), exist_ok=True); TMP = os.path.join(work, "tmp")
lock = open(os.path.join(TMP, "make_proxies.lock"), "w")
try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError: sys.exit("another make_proxies.py is running in this project — wait for it (use --res both instead of two parallel passes)")
for f in glob.glob(os.path.join(TMP, ".footage*.tmp.mp4")): _rm(f)                       # leftovers of a crashed run
for d, _, _ in RES.values():
    for f in glob.glob(os.path.join(a.public, d, "*.tmp.mp4")): _rm(f); print("removed stale", f)   # the old in-place temp files

def parse_extra(x):
    m = re.match(r"^(.*)@(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$", x)
    return (m.group(1), float(m.group(2)), float(m.group(3))) if m else (x, None, None)
extras = [parse_extra(x) for x in a.extra]
srcs = list(cl["sources"]) + [p for p, _, _ in extras]; check_unique(srcs)
ex_win = {p: (s, e) for p, s, e in extras}; ex_set = set(ex_win)
lut_map = load_lut_map(a.lut_map); draft_lut = a.lut or next((p for p in cl.get("luts", {}).values() if p), None)
main_segs = [s for s in cl["main"] if s.get("materialType", "video") == "video"]

def same(o, n):
    if not o: return ["no manifest entry"]
    diff = []
    for k in ("src", "start", "end", "voice", "voice_mtime", "lut", "crf", "res", "kind", "crop"):
        x, y = o.get(k), n.get(k)
        if k in ("src", "voice") and x and y and x != y and os.path.basename(x) == os.path.basename(y) and not os.path.exists(x):
            continue   # the project (or the volume) moved: same file name, the old path is gone — not a new source (Halloween v4: an archived project re-encoded everything)
        if isinstance(x, float) or isinstance(y, float):
            if x is None or y is None or abs(float(x) - float(y)) > 0.01: diff.append(f"{k} {x}→{y}")
        elif x != y:
            short = lambda v: "/".join(str(v).split("/")[-2:]) if v else v
            diff.append("crop " + ("centre→people" if not x else "people→centre" if not y else "people zones changed") if k == "crop" else
                        f"{k} {short(x)}→{short(y)}" if k in ("voice", "lut", "src") else f"{k} {x}→{y}")
    return diff

manifests, man_paths = {}, {}
for r in RES:
    d = os.path.join(a.public, RES[r][0]); man_paths[r] = os.path.join(d, ".manifest.json")
    manifests[r] = json.load(open(man_paths[r])) if os.path.exists(man_paths[r]) else {}
    if not manifests[r] and os.path.exists(os.path.join(d, ".windows.json")) and r in targets: print(f"{RES[r][0]}: old .windows.json, no manifest → existing proxies are re-encoded once")
offsets_path = os.path.join(work, "proxy_offsets.json")
offsets = json.load(open(offsets_path)) if os.path.exists(offsets_path) else {}

zones = load_json(a.people, {}) or {}
plan, missing, nolut, camaudio, need_people, KEYS = [], [], [], [], [], {}
for src in srcs:
    if not os.path.exists(src): missing.append(src); print("MISSING (volume not mounted?):", src); continue
    info = probe(src); cid = clip_id(src); broll = src in ex_set
    segs = [s for s in main_segs if s["path"] == src]
    if broll and ex_win[src][0] is not None: rng = (max(0.0, ex_win[src][0]), min(info["dur"] or 1e9, ex_win[src][1]))
    elif a.trim_to_cutlist is not None and segs:
        rng = (max(0.0, min(s["srcStart"] for s in segs) - a.trim_to_cutlist), min(info["dur"] or 1e9, max(s["srcStart"] + src_dur(s) for s in segs) + a.trim_to_cutlist))
    else: rng = None
    lut, why = (None, "--no-lut") if a.no_lut else lut_for(src, draft_lut, lut_map, info)
    if looks_log(src) and not lut and not a.no_lut and not why.startswith(("lut-map", "djmd: ")): nolut.append(src)  # an explicit "none" in --lut-map or a Normal profile in the file is a decision, not a miss
    voice = os.path.join(a.voice_dir, f"{cid}_DeepFilterNet3.wav") if a.voice_dir and not broll else None
    if voice and not os.path.exists(voice): voice = None
    if not a.centre_crop and not broll and any(needs_crop(cl, s, info) for s in segs):
        uncovered = [s for s in segs if needs_crop(cl, s, info) and not zone_covers(zones, s)]
        if uncovered: need_people += [f"{cid} {s['srcStart']:.2f}–{s['srcStart'] + src_dur(s):.2f} s" for s in uncovered]
        else: KEYS[cid] = crop_keys(zones, src)
    speaks = any(s.get("volume", 1) >= 0.01 for s in segs)
    if speaks and not voice and not broll and not cl.get("silent"): camaudio.append(cid)
    entry = {"src": nfc(os.path.abspath(src)), "start": round(rng[0], 3) if rng else 0.0, "end": round(rng[1], 3) if rng else round(info["dur"], 3),
             "voice": nfc(os.path.abspath(voice)) if voice else None, "voice_mtime": int(os.path.getmtime(voice)) if voice else None,
             "lut": lut, "crf": a.crf, "kind": "broll" if broll else ("camera" if is_camera(src) else "screen"),
             "speed": max([float(s.get("speed", 1) or 1) for s in segs] or [1.0]), "crop": crop_sig(KEYS.get(cid))}
    plan.append((src, cid, info, rng, entry, why))

if nolut:
    import glob as _g
    print("note: DJI clips without a LUT — fine if shot in Normal / Rec.709; if they look grey (D-Log), re-run with --lut '<cube>' (--lut-map for mixed cameras):", *nolut, sep="\n  ")
    print("known LUTs:", *sorted(set(_g.glob(os.path.expanduser("~/.cache/reel-studio/luts/*.cube")))) or ["(none in ~/.cache/reel-studio/luts)"], sep="\n  ")
if need_people:
    print("landscape camera segments without people zones (the crop would be guessed at the centre):", *need_people[:12], *(["…"] if len(need_people) > 12 else []), sep="\n  ")
    sys.exit(f"run people_zones.py first (work/venv/bin/python -I $S/people_zones.py --sheet, look at work/people/sheet_*.jpg), or --centre-crop to accept the centre crop")
free_gb = __import__("shutil").disk_usage(a.public if os.path.isdir(a.public) else ".").free / 1e9
need = sum(e["end"] - e["start"] for _, _, _, _, e, _ in plan) * sum(2.5 if t == "2k" else 1.2 for t in targets) / 1e3
if free_gb < need + 2: print(f"WARNING: {free_gb:.1f} GB free, proxies need ≈{need:.1f} GB (+2 GB for renders). Free space or use --trim-to-cutlist.")

def ntsc_rate(fps): return abs(fps - 30000 / 1001) < 0.01 or abs(fps - 60000 / 1001) < 0.02

def vchain(W, H, cam, ntsc, lut, keys=None, start=0.0, info=None):
    pre = "setpts=PTS/1.001," if ntsc else ""
    if cam and keys and info and info["w"] > info["h"]:   # people-aware: scale to the canvas height, crop where the people are
        sw = round(info["w"] * H / info["h"] / 2) * 2
        size = f"scale={sw}:{H}:flags=lanczos,crop={W}:{H}:{crop_expr(keys, start, sw, W)}:0"
    else: size = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}" if cam else f"scale={W}:-2:flags=lanczos"
    # setparams: the LUT's output is Rec.709 — say so, or an HDR source's HLG / BT.2020 tags ride through to the proxy and
    # Chrome tone-maps the converted picture a second time
    return pre + size + (f",lut3d=file='{lut}':interp=tetrahedral,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709" if lut else "")

def inside(cid, entry):
    """A shorter cut keeps the proxies: the new window lies inside the old one in every target folder (same source, voice,
    LUT, CRF) — re-encoding a minute of 2K to drop a few seconds was the slowest part of a re-cut. The old window then stays
    the offset, so trimBefore and both resolutions keep agreeing."""
    olds = [manifests[r].get(cid) for r in targets]
    if a.force or not all(olds) or any(not os.path.exists(os.path.join(a.public, RES[r][0], cid + ".mp4")) for r in targets): return None
    for o in olds:
        if [d for d in same(o, dict(entry, res=o.get("res"))) if not d.startswith(("start ", "end ", "voice ", "voice_mtime "))]: return None   # a new voice alone is remuxed below
        if o["start"] > entry["start"] + 0.01 or o["end"] < entry["end"] - 0.01: return None
    if len({(o["start"], o["end"]) for o in olds}) > 1: return None
    return olds[0]["start"], olds[0]["end"]

failed = []; not_made = set()
for src, cid, info, rng, entry, why in plan:
    keep = inside(cid, entry)
    if keep and (abs(keep[0] - entry["start"]) > 0.01 or abs(keep[1] - entry["end"]) > 0.01):
        print(f"ok {cid}: new window {entry['start']:.2f}–{entry['end']:.2f} s is inside the proxy {keep[0]:.2f}–{keep[1]:.2f} s — kept")
        entry["start"], entry["end"] = keep
    todo = []
    for r in targets:
        d, W, H = RES[r]; W, H = (H, W) if landscape else (W, H)
        e = dict(entry, res=f"{W}x{H}"); out = os.path.join(a.public, d, cid + ".mp4")
        diff = ["--force"] if a.force else same(manifests[r].get(cid), e)
        if not diff and os.path.exists(out):
            got, want = duration(out), (e["end"] - e["start"]) / (1.001 if entry["kind"] == "broll" and ntsc_rate(info["fps"]) else 1)
            if abs(got - want) > max(0.6, want * 0.002): diff = [f"duration {got:.2f} s ≠ window {want:.2f} s"]
        if not diff and os.path.exists(out): print(f"ok {cid} {r} (manifest matches)"); continue
        if diff and e["voice"] and os.path.exists(out) and all(d.startswith(("voice ", "voice_mtime ")) for d in diff):
            # only the restored voice changed (dualmic / voice_clean re-run): copy the video stream, remux the new voice —
            # Halloween v4: a new voice chain would otherwise re-encode 40 min of 4K (≈ 2 h) for a picture that did not change
            tmp = tmp_for(out, TMP); want = e["end"] - e["start"]
            rc = ffmpeg(["-loglevel", "error", "-i", out, "-ss", f"{e['start']:.3f}", "-to", f"{e['end']:.3f}", "-i", e["voice"], "-map", "0:v:0", "-c:v", "copy",
                         "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", tmp])
            ok, msg = commit(tmp, out, want, max(0.6, want * 0.002)) if rc == 0 else (False, f"{cid} {r}: remux exit {rc}")
            if ok:
                print(f"REMUX {cid} {r}: new voice, video copied"); manifests[r][cid] = e; atomic_json(manifests[r], man_paths[r]); continue
            _rm(tmp); print(f"remux failed ({msg}) — re-encoding")
        if os.path.exists(out): print(f"RE-ENCODE {cid} {r}: {', '.join(diff)}")
        todo.append((r, W, H, out, e))
    if not todo: continue
    broll = entry["kind"] == "broll"; cam = entry["kind"] == "camera" or (broll and is_camera(src))   # a DJI clip used as b-roll is cropped to 9:16 too
    ntsc = broll and ntsc_rate(info["fps"])
    seek = ["-ss", f"{rng[0]:.3f}", "-to", f"{rng[1]:.3f}"] if rng else []
    args = ["-loglevel", "error", "-stats", *HWACCEL, *seek, "-i", src]
    if entry["voice"]: args += [*seek, "-i", entry["voice"]]
    # one decode: the largest size is scaled (+ LUT) once, the smaller one is scaled down from it
    todo.sort(key=lambda t: -t[1])
    r0, W0, H0, _, _ = todo[0]
    fc = f"[0:v:0]{vchain(W0, H0, cam, ntsc, entry['lut'], KEYS.get(cid), rng[0] if rng else 0.0, info)},format=yuv420p" + (f",split={len(todo)}" + "".join(f"[s{k}]" for k in range(len(todo))) if len(todo) > 1 else "[s0]")
    for k, (r, W, H, out, e) in enumerate(todo):
        if k > 0: fc += f";[s{k}]scale={W}:{H if cam else -2}:flags=lanczos[v{k}]"
    fc = fc.replace("[s0]", "[v0]", 1) if len(todo) == 1 else fc + f";[s0]null[v0]"
    args += ["-filter_complex", fc]
    tmps = []
    for k, (r, W, H, out, e) in enumerate(todo):
        tmp = tmp_for(out, TMP); tmps.append(tmp)
        args += ["-map", f"[v{k}]"]
        if broll: args += ["-an"]
        elif entry["voice"]: args += ["-map", "1:a", "-shortest"]
        else: args += ["-map", "0:a?"]
        args += ["-r", "30", *(["-fps_mode", "cfr"] if broll else []), "-c:v", "libx264", "-preset", "fast", "-crf", str(a.crf), "-pix_fmt", "yuv420p",
                 "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", tmp]
    if KEYS.get(cid) and entry["crop"]: print(f"   crop follows people: {len(KEYS[cid])} keys, centre {min(c for _, c in KEYS[cid]):.2f}–{max(c for _, c in KEYS[cid]):.2f}")
    print("==", cid, "b-roll (muted" + (", retimed 30" if ntsc else "") + ")" if broll else "voice" if entry["voice"] else "camera-audio",
          f"range {rng[0]:.1f}-{rng[1]:.1f}s" if rng else "full", f"LUT {os.path.basename(entry['lut'])} ({why})" if entry["lut"] else "no LUT", "→", "+".join(t[0] for t in todo))
    rc = ffmpeg(args, quiet=False)
    want = (entry["end"] - entry["start"]) / (1.001 if ntsc else 1)
    for (r, W, H, out, e), tmp in zip(todo, tmps):
        if rc != 0: _rm(tmp); failed.append(f"{cid} {r}: ffmpeg exit {rc}"); not_made.add(cid); continue
        ok, msg = commit(tmp, out, want, max(0.6, want * 0.002))
        if not ok: failed.append(msg); not_made.add(cid); continue
        manifests[r][cid] = e; atomic_json(manifests[r], man_paths[r])   # after every file: a crash leaves a true manifest
for src, cid, info, rng, entry, why in plan:
    if cid not in not_made: offsets[cid] = entry["start"]   # a failed re-encode keeps the old proxy, so it keeps its old offset
atomic_json(offsets, offsets_path)
# the other resolution must have been cut from the same windows, or Reel2K plays other seconds than Studio shows
for r in RES:
    if r in targets or not manifests[r]: continue
    stale = [cid for cid, off in offsets.items() if cid in manifests[r] and abs(manifests[r][cid].get("start", 0) - off) > 0.01]
    if stale: print(f"WARNING: {RES[r][0]} was cut from other windows for {', '.join(stale)} — re-run with --res {r} (or both) before rendering {'Reel2K' if r == '2k' else 'Reel'}")
# voiceovers recorded inside CapCut → public/audio (only for projects without a dialogue stem: dialogue.py places them itself)
au = os.path.join(a.public, "audio"); os.makedirs(au, exist_ok=True)
for v in cl.get("voiceovers", []):
    m4a = os.path.join(au, os.path.splitext(os.path.basename(v))[0] + ".m4a"); dst = os.path.join(au, os.path.basename(v))
    if os.path.exists(m4a): continue
    if not os.path.exists(dst) and os.path.exists(v): __import__("shutil").copy2(v, dst); print("voiceover copied raw (dialogue.py puts it into the dialogue stem):", dst)
if camaudio: print("NOTE: no isolated voice for", ", ".join(camaudio), "— their proxies carry the camera sound" + ("" if a.voice_dir else " (no --voice-dir given)"))
if failed: print("FAILED:", *failed, sep="\n  "); sys.exit(1)
if missing and not a.allow_missing: print(f"PROXIES_INCOMPLETE {len(missing)} missing source(s) — mount the volume and re-run (or --allow-missing)"); sys.exit(1)
print("PROXIES_DONE", " ".join(os.path.join(a.public, RES[r][0]) for r in targets), f"offsets {offsets}")
