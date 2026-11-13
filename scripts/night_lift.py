#!/usr/bin/env python3
"""Lift the shadows of dark (night) proxies in place, after make_proxies.py: an ffmpeg curve on the picture, sound copied.

Usage: work/venv/bin/python -I night_lift.py <project> [--dry-run]       (any python with numpy: work/venv/bin/python)
Why (Halloween vlog, 2026-11-03): night street and bar clips came out of the D-Log LUT almost black on a phone — faces
lost in the mud, while the day clips were fine. A global grade would wash out the day; a per-clip curve by brightness does not.
Per clip: duration-weighted mean luma of its segments (3 frames each from the 1080 proxy, 0–255) picks a curve — below
nightStrong «strong», below nightMedium «medium», below nightMild «mild», else untouched. Both footage/ and footage2k/ are
graded the same; each graded proxy carries comment=night_lift:<level>, so a re-run skips it and measures nothing twice (a
graded proxy would measure brighter), and a proxy that make_proxies re-encoded (no tag) is graded again — re-run this after
every make_proxies run (doctor.py warns about an ungraded one). work/night_lift.json keeps the decisions.
Prints NIGHT_LIFT_DONE.
"""
import argparse, collections, json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, atomic_json, clip_id, load_json, proxy_file, src_dur

CURVES = {"strong": "0/0 0.04/0.12 0.2/0.36 0.6/0.74 1/1", "medium": "0/0 0.06/0.13 0.25/0.38 0.6/0.72 1/1", "mild": "0/0 0.08/0.12 0.3/0.37 0.7/0.76 1/1"}


def tag(p):
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip()


def luma(proxy, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{max(0, t):.2f}", "-i", proxy, "-frames:v", "1", "-vf", "scale=192:-2,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8) if raw else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    P = os.path.abspath(a.project); os.chdir(P)
    cl = load_json("work/cutlist.json"); offs = load_json("work/proxy_offsets.json", {}) or {}
    if not cl: sys.exit("no work/cutlist.json")
    state = load_json("work/night_lift.json", {}) or {}
    acc = collections.defaultdict(lambda: [0.0, 0])
    for s in cl["main"]:
        if s.get("materialType", "video") != "video": continue
        cid = clip_id(s["path"]); prox = proxy_file("reel/public", cid)
        if not os.path.exists(prox) or tag(prox).startswith("night_lift:"): continue
        ys = [y for q in (0.2, 0.5, 0.8) if (y := luma(prox, float(s["srcStart"]) + src_dur(s) * q - float(offs.get(cid, 0)))) is not None]
        if ys: acc[cid][0] += float(np.concatenate(ys).mean()) * s["durFrames"]; acc[cid][1] += s["durFrames"]
    done = 0
    for cid, (tot, n) in sorted(acc.items()):
        mean = tot / n
        level = "strong" if mean < N["nightStrong"] else "medium" if mean < N["nightMedium"] else "mild" if mean < N["nightMild"] else None
        state[cid] = {"mean": round(mean, 1), "level": level}
        if not level: continue
        print(f"{cid}: mean luma {mean:.0f} → {level}" + (" (dry run)" if a.dry_run else ""), flush=True)
        if a.dry_run: continue
        for folder in ("footage", "footage2k"):
            p = f"reel/public/{folder}/{cid}.mp4"
            if not os.path.exists(p) or tag(p).startswith("night_lift:"): continue
            tmp = f"reel/public/{folder}/.{cid}.grade.tmp.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", p, "-map", "0:v:0", "-map", "0:a?", "-vf", f"curves=all='{CURVES[level]}'",
                            "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                            "-color_trc", "bt709", "-c:a", "copy", "-metadata", f"comment=night_lift:{level}", "-movflags", "+faststart", tmp], check=True)
            os.replace(tmp, p); done += 1
    if not a.dry_run: atomic_json(state, "work/night_lift.json")
    print("NIGHT_LIFT_DONE", f"{done} proxy file(s) graded;", sum(1 for s in state.values() if s.get("level")), "dark clip(s) in work/night_lift.json")


if __name__ == "__main__":
    main()
