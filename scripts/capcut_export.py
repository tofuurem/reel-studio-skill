#!/usr/bin/env python3
"""Read a CapCut (macOS) draft and export everything the Remotion edit needs.

Usage:
  capcut_export.py [--draft NAME_OR_PATH] [--fps 30] [--out work/] [--list]

Writes:
  <out>/cutlist.json      main video track as frame-accurate segments + other tracks
  <out>/draft_summary.md  human-readable summary (read this first)

Why a script: draft_info.json is ~150 KB of nested JSON; the timeline, speeds,
LUTs, mutes, overlay tracks and voiceovers are scattered across materials/tracks and
are easy to miss by eye. This normalises them once.
Per segment the user's framing is exported too: "transform" {scale, scaleY, x, y, rotation, flipH} (CapCut units: x/y are
offsets of the clip centre in half-canvas units, y points UP — checked on real drafts: a 3×3 grid of tiles sits at ±0.667
with scale 0.335, subtitles at y −0.56 sit low), "srcW"/"srcH" (source size), "crop" {x0, y0, x1, y1} (0–1 of the source)
and "keyframes": true (+ "keyframeGroups") — gen_timeline.py turns transform/crop into Clip `framing`/`crop` props (the cut
is final, so the framing is kept); keyframed moves are only warned about.
Main-track photos and text tracks are listed in the warnings: they are placed by hand in Reel.tsx.
"""
import argparse, json, os, subprocess, sys, time, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import LUT_DIR, SKILL

ROOT = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
LUT_DIRS = [os.path.expanduser("~/Movies/CapCut/User Data/Resources/Lut"), LUT_DIR, os.path.join(SKILL, "assets", "luts"), os.path.expanduser("~/Downloads")]

def us(x): return round((x or 0) / 1e6, 4)

def list_drafts():
    """(modified, name, folder, seconds) newest first. Without CapCut's root_meta_info.json the draft folders are scanned."""
    mp = os.path.join(ROOT, "root_meta_info.json")
    if not os.path.exists(mp):
        rows = [(os.path.getmtime(os.path.join(d, "draft_info.json")) * 1e6, os.path.basename(d), d, 0.0) for d in glob.glob(os.path.join(ROOT, "*")) if os.path.exists(os.path.join(d, "draft_info.json"))]
        return sorted(rows, reverse=True)
    meta = json.load(open(mp))
    rows = []
    for d in meta.get("all_draft_store", []):
        rows.append((d.get("tm_draft_modified", 0), d.get("draft_name"), d.get("draft_fold_path"), (d.get("tm_duration") or 0) / 1e6))
    rows.sort(reverse=True)
    return rows

def find_lut(name):
    base = name.replace(".cube", "")
    for d in LUT_DIRS:
        for cand in [os.path.join(d, base, name), os.path.join(d, name)]:
            if os.path.exists(cand): return cand
        hits = glob.glob(os.path.join(d, "**", name), recursive=True)
        if hits: return hits[0]
    return None

def probe_duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out) if out else None
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", help="draft name (folder under CapCut drafts) or full path; default = most recently modified")
    ap.add_argument("--fps", type=int, default=30, choices=[30], help="only 30: the template, the proxies and reelgen are 30 fps")
    ap.add_argument("--out", default="work")
    ap.add_argument("--list", action="store_true", help="only list drafts")
    a = ap.parse_args()

    drafts = [] if (a.draft and os.path.isdir(a.draft)) else list_drafts()
    if not drafts and not (a.draft and os.path.isdir(a.draft)):
        sys.exit(f"no CapCut drafts found in {ROOT} — is CapCut installed and the draft saved? Or pass --draft <draft folder path>")
    if a.list:
        for tm, name, path, dur in drafts:
            print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(tm/1e6))}  {dur:7.1f}s  {name}")
        return
    if a.draft and os.path.isdir(a.draft):
        folder = a.draft
    elif a.draft:
        folder = os.path.join(ROOT, a.draft)
    else:
        folder = drafts[0][2]
    info_path = os.path.join(folder, "draft_info.json")
    if not os.path.exists(info_path):
        sys.exit(f"draft_info.json not found in {folder}")
    d = json.load(open(info_path))
    fps = a.fps
    m = d["materials"]
    by_id = {}
    for kind, items in m.items():
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict) and "id" in it:
                    by_id[it["id"]] = (kind, it)

    def resolve_path(p):
        if not p: return p
        if "##_draftpath_placeholder_" in p:
            return os.path.join(folder, p.split("_##/", 1)[1])
        return p

    luts, warnings = {}, []
    tracks_out = []
    for ti, t in enumerate(d.get("tracks", [])):
        segs = []
        for s in t.get("segments", []):
            kind, mat = by_id.get(s["material_id"], ("?", {}))
            tr, sr = s.get("target_timerange", {}), s.get("source_timerange") or {}
            seg = {
                "track": ti, "trackType": t.get("type"), "materialType": mat.get("type", kind),
                "name": mat.get("material_name") or mat.get("name") or "",
                "path": resolve_path(mat.get("path", "")),
                "tlStart": us(tr.get("start")), "dur": us(tr.get("duration")),
                "srcStart": us(sr.get("start")), "srcDur": us(sr.get("duration")),
                "speed": s.get("speed", 1.0), "volume": s.get("volume", 1.0),
                "fromFrame": round(us(tr.get("start")) * fps), "durFrames": round(us(tr.get("duration")) * fps),
                "trimBeforeFrames": round(us(sr.get("start")) * fps),
            }
            if mat.get("type") == "text" or kind == "texts":
                try: seg["text"] = json.loads(mat.get("content", "{}")).get("text", "")
                except Exception: seg["text"] = mat.get("content", "")
            clip = s.get("clip") or {}
            sc, trf = clip.get("scale") or {}, clip.get("transform") or {}
            if mat.get("width") and mat.get("height"): seg["srcW"], seg["srcH"] = mat["width"], mat["height"]
            eps = 1e-3   # drafts carry float noise (x = -2.2e-16, scale = 0.9999999999999999)
            if abs(sc.get("x", 1) - 1) > eps or abs(sc.get("y", 1) - 1) > eps or abs(trf.get("x", 0)) > eps or abs(trf.get("y", 0)) > eps or abs(clip.get("rotation", 0) or 0) > eps or (clip.get("flip") or {}).get("horizontal"):
                seg["clipTransform"] = clip
                seg["transform"] = {"scale": sc.get("x", 1), "scaleY": sc.get("y", sc.get("x", 1)), "x": trf.get("x", 0), "y": trf.get("y", 0),
                                    "rotation": clip.get("rotation", 0), "flipH": bool((clip.get("flip") or {}).get("horizontal"))}
            cr = mat.get("crop") or {}
            if cr and any(abs(v - dflt) > 1e-6 for v, dflt in [(cr.get("upper_left_x", 0), 0), (cr.get("upper_left_y", 0), 0), (cr.get("lower_right_x", 1), 1), (cr.get("lower_right_y", 1), 1)]):
                seg["crop"] = {"x0": cr.get("upper_left_x", 0), "y0": cr.get("upper_left_y", 0), "x1": cr.get("lower_right_x", 1), "y1": cr.get("lower_right_y", 1)}
            if s.get("common_keyframes"):
                seg["keyframes"] = True; seg["keyframeGroups"] = len(s["common_keyframes"])
                warnings.append(f"track {ti} seg @{seg['tlStart']}s has {len(s['common_keyframes'])} keyframe groups (zoom/position animation) — reproduce by hand")
            extras = []
            for ref in s.get("extra_material_refs", []):
                k2, m2 = by_id.get(ref, (None, None))
                if not m2: continue
                if k2 == "speeds" and m2.get("speed", 1) != 1: seg["speed"] = m2["speed"]
                elif k2 == "transitions": seg["transition"] = {"name": m2.get("name"), "dur": us(m2.get("duration"))}
                elif k2 == "effects" and m2.get("type") == "lut":
                    seg["lut"] = m2.get("name"); luts[m2.get("name")] = find_lut(m2.get("name", ""))
                elif k2 == "effects": extras.append({"effect": m2.get("name"), "type": m2.get("type")})
                elif k2 == "material_animations" and m2.get("animations"):
                    seg["animations"] = [(x.get("name"), x.get("type"), us(x.get("duration"))) for x in m2["animations"]]
                elif k2 == "audio_fades": seg["audioFade"] = {"in": us(m2.get("fade_in_duration")), "out": us(m2.get("fade_out_duration"))}
            if extras: seg["effects"] = extras
            segs.append(seg)
        tracks_out.append({"index": ti, "type": t.get("type"), "segments": segs})

    video_tracks = [t for t in tracks_out if t["type"] == "video" and t["segments"]]
    main = video_tracks[0]["segments"] if video_tracks else []
    for s in main:
        if s["materialType"] != "video":
            warnings.append(f"main track @{s['tlStart']}s is a {s['materialType']} ({os.path.basename(s['path'] or '') or s.get('name')}) for {s['dur']}s — place it by hand in Reel.tsx (<Img> in a Sequence)")
    for t in tracks_out:
        if t["type"] == "text" and t["segments"]:
            warnings.append(f"text track {t['index']}: {len(t['segments'])} titles (" + "; ".join((x.get('text') or '')[:30] for x in t['segments'][:4]) + ") — the user's on-screen text: rebuild as Pill/Card, do not drop")
    sources = sorted({s["path"] for s in main if s["materialType"] == "video"})
    src_dirs = sorted({os.path.dirname(p) for p in sources})
    # b-roll candidates: untouched files next to the used ones
    candidates = []
    for sd in src_dirs:
        if not os.path.isdir(sd):
            warnings.append(f"source folder not mounted: {sd}"); continue
        for f in sorted(os.listdir(sd)):
            p = os.path.join(sd, f)
            if f.startswith("._") or not f.lower().endswith((".mp4", ".mov", ".mxf")): continue
            if p not in sources:
                candidates.append({"path": p, "dur": probe_duration(p)})

    canvas = d.get("canvas_config", {})
    out = {
        "draft": os.path.basename(folder), "draftFolder": folder, "fps": fps,
        "canvas": {"w": canvas.get("width"), "h": canvas.get("height")},
        "durationSec": us(d.get("duration")), "totalFrames": round(us(d.get("duration")) * fps),
        "main": main, "tracks": tracks_out, "sources": sources, "luts": luts,
        "voiceovers": sorted(glob.glob(os.path.join(folder, "audio_record", "*"))),
        "brollCandidates": candidates, "warnings": warnings,
    }
    os.makedirs(a.out, exist_ok=True)
    json.dump(out, open(os.path.join(a.out, "cutlist.json"), "w"), ensure_ascii=False, indent=1)

    L = [f"# CapCut draft `{out['draft']}`", "", f"- canvas {canvas.get('width')}x{canvas.get('height')}, {out['durationSec']} s = {out['totalFrames']} frames @ {fps} fps", f"- main track: {len(main)} segments, {len(sources)} source files", f"- LUTs: {luts or 'none'}", f"- voiceovers: {len(out['voiceovers'])}", ""]
    L.append("## Main video track (timeline → source)")
    for i, s in enumerate(main):
        flags = []
        if s["volume"] < 0.01: flags.append("MUTED")
        if s["speed"] != 1: flags.append(f"speed {s['speed']}")
        if s.get("clipTransform"): flags.append("transform")
        if s.get("crop"): flags.append("crop")
        if s["materialType"] != "video": flags.append(s["materialType"].upper())
        if s.get("transition"): flags.append(f"transition {s['transition']['name']}")
        if s.get("keyframes"): flags.append("KEYFRAMES")
        L.append(f"{i:2d}. tl {s['tlStart']:7.2f}-{s['tlStart']+s['dur']:7.2f} ({s['dur']:5.2f}s) | src {s['srcStart']:7.2f}+{s['srcDur']:5.2f} | from={s['fromFrame']} dur={s['durFrames']} trim={s['trimBeforeFrames']} | {os.path.basename(s['path'])} {' '.join(flags)}")
    for t in tracks_out:
        if t is (video_tracks[0] if video_tracks else None) or not t["segments"]: continue
        L.append(f"\n## Track {t['index']} ({t['type']})")
        for s in t["segments"]:
            L.append(f"- tl {s['tlStart']:.2f}-{s['tlStart']+s['dur']:.2f} {s['materialType']} {s.get('text') or os.path.basename(s['path'] or '')} vol={s['volume']}")
    if candidates:
        L.append("\n## Unused files next to the sources (b-roll candidates)")
        for c in candidates: L.append(f"- {os.path.basename(c['path'])} {c['dur'] and round(c['dur'],1)}s")
    if warnings:
        L.append("\n## Warnings"); L += [f"- {w}" for w in warnings]
    open(os.path.join(a.out, "draft_summary.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print("EXPORT_DONE", os.path.join(a.out, "cutlist.json"))

if __name__ == "__main__":
    main()
