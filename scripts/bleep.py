#!/usr/bin/env python3
"""Censor profanity in a rendered video: mute the speech and lay a short beep over each range.

Usage: bleep.py <in.mp4> <bleeps.json> <out.mp4> [--style soft|sine] [--freq 1000] [--gain -18]   (gain default: numbers.json bleepGain)
bleeps.json: [{"startMs":…, "endMs":…}, …] on the final timeline (cut_from_transcript.py for planned cuts, bleeps_from_timeline.py for CapCut drafts).
Runs after render.sh (video stream copied), so it does not touch the Remotion project — only for a reel WITHOUT a dialogue stem:
dialogue.py bleeps the stem itself (no extra AAC encode); then this script just copies the file.
"""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from common import N
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("bleeps"); ap.add_argument("out")
ap.add_argument("--freq", type=int, default=1000); ap.add_argument("--gain", type=float, default=N["bleepGain"], help="beep peak level dBFS")
SINE_LEVEL = -21.0  # ffmpeg's sine source has a fixed peak of about −21 dBFS; compensate so --gain is the real peak
ap.add_argument("--pad", type=float, default=0.04)
ap.add_argument("--style", choices=["sine", "soft"], default="soft", help="sine = classic 1 kHz censor beep; soft = two-tone decaying 'boop', low-passed (reads as a device sound, not as censorship)")
a = ap.parse_args()
bl = json.load(open(a.bleeps))
dj = os.path.join(os.path.dirname(os.path.abspath(a.bleeps)), "voice", "dialogue.json")
if bl and os.path.exists(dj) and json.load(open(dj)).get("bleeps"):
    if os.path.abspath(a.inp) != os.path.abspath(a.out): subprocess.run(["cp", a.inp, a.out], check=True)
    print("already bleeped inside the dialogue stem (dialogue.py) — copied as is"); print("BLEEP_DONE", a.out); raise SystemExit
if not bl:
    subprocess.run(["cp", a.inp, a.out], check=True); print("no bleeps"); print("BLEEP_DONE", a.out); raise SystemExit
ranges = [(max(0, b["startMs"] / 1000 - a.pad), b["endMs"] / 1000 + a.pad) for b in bl]
mute = ",".join(f"volume=enable='between(t,{s:.3f},{e:.3f})':volume=0" for s, e in ranges)
beeps = []
for i, (s, e) in enumerate(ranges):
    d = max(0.12, e - s)
    if a.style == "sine":
        src = f"sine=frequency={a.freq}:duration={d:.3f}:sample_rate=48000,afade=t=in:d=0.01,afade=t=out:st={max(0,d-0.02):.3f}:d=0.02,volume={a.gain - SINE_LEVEL:.1f}dB"
    else:  # two partials, gentle decay, no harsh edge; peak ≈ 0.9 FS before volume
        src = (f"aevalsrc=exprs='(0.55*sin(2*PI*740*t)+0.35*sin(2*PI*1110*t))*(0.35+0.65*exp(-2.2*t))':s=48000:d={d:.3f},"
               f"lowpass=f=2400,afade=t=in:d=0.012,afade=t=out:st={max(0,d-0.06):.3f}:d=0.06,volume={a.gain - 1:.1f}dB")
    beeps.append(f"{src},aformat=channel_layouts=stereo,adelay={int(s*1000)}|{int(s*1000)}[b{i}]")
AAC = "aac_at" if " aac_at " in subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout else "aac"
mix_in = "".join(f"[b{i}]" for i in range(len(ranges)))
fc = f"[0:a]{mute}[v];" + ";".join(beeps) + f";[v]{mix_in}amix=inputs={len(ranges)+1}:normalize=0:duration=first[a]"
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", a.inp, "-filter_complex", fc, "-map", "0:v?", "-map", "[a]", "-c:v", "copy", "-c:a", AAC, "-b:a", N["aacBitrate"], a.out], check=True)
print(f"bleeped {len(ranges)} ranges → {a.out}"); print("BLEEP_DONE", a.out)
