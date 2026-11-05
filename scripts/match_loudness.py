#!/usr/bin/env python3
"""Bring every speech source of a cut list to the same loudness (camera takes + voiceovers recorded on another mic).

Usage: match_loudness.py [--cutlist work/cutlist.json] [--voice-dir work/voice/out] [--out work/voice/matched] [--target -24] [--max-gain 18]
                         [--voiceovers-out reel/public/audio]
CapCut drafts: voiceovers recorded in CapCut sit on the draft's audio tracks (cutlist "tracks", type audio). They are measured over
their used ranges too (isolated voice from --voice-dir when voice_isolate.sh ran on them, else the file itself) and written as
<voiceovers-out>/<name>.m4a at the same gain — place that file in Reel.tsx where the draft put it.
For each source it measures the integrated loudness (EBU R128) of ONLY the ranges the cut list uses, on the DeepFilterNet
wav, and writes <out>/<clipId>_DeepFilterNet3.wav with a static gain to the target (soft limiter at -1 dBFS for the rare peak).
The originals in --voice-dir stay untouched: pauses.py / bleep snapping keep working on them with their thresholds.
Then: make_proxies.py --voice-dir work/voice/matched (both passes). A source used for < 1.5 s keeps the median gain of the rest.
render.sh still sets the final programme loudness; this step only removes the jump between a quiet voiceover and a loud take.
"""
import argparse, json, os, re, statistics, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from common import N, clip_id, speech_tracks, src_dur
ap = argparse.ArgumentParser(); ap.add_argument("--cutlist", default="work/cutlist.json"); ap.add_argument("--voice-dir", default="work/voice/out")
ap.add_argument("--out", default="work/voice/matched"); ap.add_argument("--voiceovers-out", default="reel/public/audio"); ap.add_argument("--target", type=float, default=N["sourceLufs"], help="keeps ~4 dB of peak headroom on typical speech; render.sh lifts the programme to -16 later"); ap.add_argument("--max-gain", type=float, default=18.0)
a = ap.parse_args(); cl = json.load(open(a.cutlist)); os.makedirs(a.out, exist_ok=True)
ranges = {}
for s in cl["main"]:
    if s.get("volume", 1) < 0.01: continue
    ranges.setdefault(s["path"], []).append((s["srcStart"], s["srcStart"] + src_dur(s)))   # source seconds: a 2× CapCut segment uses twice its timeline length
vo_paths = set(cl.get("voiceovers", []))
for s in speech_tracks(cl): ranges.setdefault(s["path"], []).append((s["srcStart"], s["srcStart"] + src_dur(s)))
def measure(wav, rs):
    sel = "+".join(f"between(t,{x:.3f},{y:.3f})" for x, y in rs)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af", f"aselect='{sel}',asetpts=N/SR/TB,ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r); p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    return (float(i[-1]) if i else None), (float(p[-1]) if p else None)
rows, skipped = [], []
for path, rs in ranges.items():
    cid = clip_id(path); wav = os.path.join(a.voice_dir, f"{cid}_DeepFilterNet3.wav")
    if not os.path.exists(wav):
        if path in vo_paths: wav = path   # a CapCut voiceover that was not isolated: measure the file itself
        else: skipped.append(cid); print("WARNING: no isolated voice for", cid, f"in {a.voice_dir} - skipped (its proxy keeps the camera sound). Series episode? the voice pool lives in ../work/voice — new_project.sh links it"); continue
    used = sum(y - x for x, y in rs); I, pk = measure(wav, rs)
    rows.append([cid, wav, used, I, pk, path])
gains = {r[0]: a.target - r[3] for r in rows if r[3] is not None and r[3] > -60 and r[2] >= 1.5}
med = statistics.median(gains.values()) if gains else 0.0
for cid, wav, used, I, pk, path in rows:
    g = max(-a.max_gain, min(a.max_gain, gains.get(cid, med))); out = os.path.join(a.out, os.path.basename(wav))
    if path in vo_paths:   # draft voiceover → a ready m4a for <Audio>
        os.makedirs(a.voiceovers_out, exist_ok=True); out = os.path.join(a.voiceovers_out, os.path.splitext(os.path.basename(path))[0] + ".m4a")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-af", f"volume={g:.2f}dB,alimiter=limit=0.89:level=false:attack=3:release=60", "-ar", "48000", "-ac", "1", "-c:a", "aac", "-b:a", "192k", out], check=True)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-af", f"volume={g:.2f}dB,alimiter=limit=0.89:level=false:attack=3:release=60", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", out], check=True)
    print(f"{cid:22s} used {used:6.1f}s  I {I if I is not None else float('nan'):6.1f} LUFS  peak {pk if pk is not None else float('nan'):6.1f}  gain {g:+5.1f} dB{'' if cid in gains else '  (median gain: too short/quiet to measure)'}")
print("MATCH_DONE", a.out, f"target {a.target} LUFS" + (f" — {len(skipped)} source(s) skipped: {', '.join(skipped)}" if skipped else ""))
