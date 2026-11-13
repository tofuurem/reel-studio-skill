#!/usr/bin/env python3
"""What is wrong with the voice? Numbers that decide the optional voice tools of work/voice_tune.json — before anyone
rebuilds the reel to «try something».

Usage: work/dfvenv/bin/python -I voice_probe.py <project>                       the dialogue stem (+ the raw assembly if kept)
       work/dfvenv/bin/python -I voice_probe.py <project> --takes              every restored take in work/voice/out
       work/dfvenv/bin/python -I voice_probe.py <project> --clip <id> | --file <media> [--at S --dur D]
Per voice: loudness, LRA, spread of the speech level over 3-s windows, spectral centroid (a male voice ≈ 600–700 Hz;
< 500 = dark / boomy «гудит», > 900 = thin), the 1/3-octave deviation from the target speech shape (voicelib.ltas exact),
narrow resonances (1/12 octave over the 1-octave trend) with the cuts notch_plan would make, the floor between words.
Ends with SUGGEST <json> — a draft of work/voice_tune.json (never written by this script) to test with eq_test.py → ab.py.
Thresholds (a podcast edit ep. 1–2): a resonance ≥ notchMinDb under 500 Hz → notches; LRA > 9 LU or a 3-s spread
p90−p10 > 8 dB → leveler; the quiet frames less than 45 dB under the speech → expander (noise / room between words).
"""
import argparse, glob, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N  # noqa: E402
import voicelib as V   # noqa: E402

SR = V.SR
SHOW = [100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500]


def dev(y):
    """1/3-octave deviation (dB) from LTASS + FINISH, normalised over 250 Hz–4 kHz."""
    m = V.ltas(y, exact=True); tgt = {b: V.LTASS[b] + V.FINISH.get(b, 0) for b in V.BANDS}
    ref = [b for b in V.BANDS if 250 <= b <= 4000 and b in m]
    if not ref: return {}
    off = np.mean([m[b] for b in ref]) - np.mean([tgt[b] for b in ref])
    return {b: round(float(m[b] - tgt[b] - off), 1) for b in SHOW if b in m}


def spread(y, win=3.0):
    """Active speech level per 3-s window (windows ≥ 50 % speech): p10, p90 (dB)."""
    sp = V.active_db(y)
    if sp is None: return None
    L = V.db(V.frame_power(y)); k = int(win * 100); out = []
    for i in range(0, len(L) - k, k):
        w = L[i:i + k]; act = w > sp - 15
        if act.mean() >= 0.5: out.append(10 * np.log10(np.mean(10 ** (w[act] / 10))))
    return (round(float(np.percentile(out, 10)), 1), round(float(np.percentile(out, 90)), 1), len(out)) if len(out) >= 4 else None


def floor(y):
    """Speech level, the quiet 10 % of frames, hiss above 6 kHz in the quietest frames (dBFS)."""
    sp = V.active_db(y); L = V.db(V.frame_power(y)); live = L > -100   # digital zeros are not «floor»
    if sp is None or not live.any(): return None
    hp = V.ffilter(y, "highpass=f=6000:poles=2,highpass=f=6000:poles=2"); H = V.db(V.frame_power(hp))[: len(L)]
    q = live & (L < np.percentile(L[live], 15))
    return {"speech": round(sp, 1), "quietP10": round(float(np.percentile(L[live], 10)), 1), "hissOver6k": round(float(np.median(H[q])), 1)}


def report(name, y):
    if len(y) < 5 * SR: print(f"\n== {name}: shorter than 5 s, skipped"); return {}
    I, lra, tp = V.ebur128(y); c = V.centroid(y); res = V.resonances(y); notch, _ = V.notch_plan(y); sp = spread(y); fl = floor(y)
    tone = "dark / boomy" if c < 500 else "thin" if c > 900 else "ok"
    print(f"\n== {name}: {len(y) / SR / 60:.1f} min, {I} LUFS, LRA {lra} LU, true peak {tp} dBTP, centroid {c:.0f} Hz ({tone})")
    print("   spectrum vs target (dB):", dev(y))
    print("   resonances (Hz, dB over the trend):", res, "→ notches:", notch or "none ≥ notchMinDb")
    if sp: print(f"   speech level over 3-s windows: p10 {sp[0]} … p90 {sp[1]} dB (spread {sp[1] - sp[0]:.1f}, n={sp[2]})")
    if fl: print(f"   floor: speech {fl['speech']} dBFS, quiet 10 % {fl['quietP10']} ({fl['speech'] - fl['quietP10']:.0f} dB under), hiss > 6 kHz {fl['hissOver6k']}")
    sug = {}
    if notch: sug["notches"] = "auto"
    if (lra is not None and lra > 9) or (sp and sp[1] - sp[0] > 8): sug["leveler"] = True
    if fl and fl["speech"] - fl["quietP10"] < 45: sug["expander"] = True
    return sug


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project")
    ap.add_argument("--takes", action="store_true"); ap.add_argument("--clip"); ap.add_argument("--file")
    ap.add_argument("--at", type=float); ap.add_argument("--dur", type=float); ap.add_argument("--max-min", type=float, default=10.0)
    a = ap.parse_args(); P = os.path.abspath(a.project)
    if a.file: a.file = os.path.abspath(a.file)   # relative to where the user stands, not to the project
    os.chdir(P)
    def rd(f):   # a long take: its first --max-min minutes (or --at / --dur)
        return V.read(f, ss=a.at, t=a.dur or a.max_min * 60)
    jobs = []
    if a.file: jobs = [(os.path.basename(a.file), a.file)]
    elif a.clip: jobs = [(a.clip, f"work/voice/out/{a.clip}_DeepFilterNet3.wav")]
    elif a.takes: jobs = [(os.path.basename(f).replace("_DeepFilterNet3.wav", ""), f) for f in sorted(glob.glob("work/voice/out/*_DeepFilterNet3.wav"))]
    else:
        jobs = [("dialogue stem (what the reel plays)", "reel/public/audio/dialogue.wav")]
        if os.path.exists("work/voice/dialogue_raw.wav"): jobs.append(("raw assembly (before the chain)", "work/voice/dialogue_raw.wav"))
    tune = {k: v for k, v in (json.load(open("work/voice_tune.json")) if os.path.exists("work/voice_tune.json") else {}).items() if not k.startswith("_")}
    print("work/voice_tune.json:", tune or "none (all optional tools off)")
    sug = {}
    for name, f in jobs:
        if not os.path.exists(f): print(f"\n== {name}: no {f}"); continue
        for k, v in report(name, rd(f)).items(): sug.setdefault(k, v)
    print("\nSUGGEST", json.dumps(sug, ensure_ascii=False), "— a draft: test it on a stretch (eq_test.py → ab.py), the user decides by ear")
    print("PROBE_DONE")


if __name__ == "__main__":
    main()
