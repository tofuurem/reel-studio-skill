#!/usr/bin/env python3
"""Replace the synthesized sound effects with designed ones from earshot's bank (optional; make_sfx.sh calls it).

Usage: <earshot's python> sfx_bank.py <project> [--set whoosh=whoosh_big/cape …] [--synth]
       (make_sfx.sh finds that python itself; deps.py --with sound installs earshot)
earshot (github.com/Leonxlnx/earshot, MIT) ships 252 sound effects stored as code — whooshes, swishes, pops, ticks, dings,
hits, risers, shutters — rendered by id in seconds, with no models and no network. Our ffmpeg synthesis (pink noise through
a filter) is the fallback; the bank sounds like designed sound. Each kind below gets one bank id; the level of the new file
is matched to the synthesized one it replaces (integrated loudness, pyloudnorm), so every numbers.json level (sfxPop,
sfxWhoosh …) keeps meaning the same thing, and the peak stays ≤ −1 dBFS. The synthesized originals move to
audio/sfx/synth/ for an A/B; `--synth` puts them back. `--set kind=id` picks another bank sound (`earshot sfx list`).
rewind and beep stay synthesized (the bank has no tape rewind or plain electronic beep).
→ reel/public/audio/sfx/<kind>.wav, work/sfx_bank.json (kind → id, gain). Prints SFX_BANK_DONE.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

BANK = {   # kind: (earshot id, render options) — chosen by ear on 2026-11-09 for calm reels and action reels
    "tick": ("pro_hover_tick/detent", {}),
    "pop": ("pro_pop_in/round", {}), "pop2": ("pro_pop_in/airy", {}), "pop3": ("ui_pop/soft", {}),
    "done": ("pro_notify/ding_2045", {}),
    "whoosh": ("whoosh_fast/crisp", {}), "whoosh2": ("whoosh_fast/tight", {}), "whoosh3": ("swipe/glide", {}),
    "softwhoosh": ("swish/soft", {}), "softwhoosh2": ("swipe/velvet", {}), "softwhoosh3": ("swipe/cloth", {}),
    "hit": ("pro_impact/short", {}), "hit2": ("cut_hit/punch", {}), "hit3": ("pro_impact/air", {}),
    "shutter": ("shutter/dslr", {}),
    "riser": ("pro_riser/air_gate", {"dur": 0.9}),   # like the synth one: 0.9 s, loudest at its end (placed at target − 27 f)
    "powerdown": ("downlifter/tape", {"dur": 1.0}),
}


def loudness(path):
    import numpy as np, soundfile as sf, pyloudnorm as pyln
    x, sr = sf.read(path, always_2d=True)
    pad = np.zeros((int(sr * 0.6), x.shape[1]))   # BS.1770 needs ≥ 0.4 s; silence is gated out
    return pyln.Meter(sr).integrated_loudness(np.vstack([pad, x, pad])), float(np.abs(x).max())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--set", action="append", default=[], help="kind=earshot id")
    ap.add_argument("--synth", action="store_true", help="put the synthesized sounds back")
    a = ap.parse_args(); P = os.path.abspath(a.project)
    D = os.path.join(P, "reel/public/audio/sfx"); S = os.path.join(D, "synth"); rep_p = os.path.join(P, "work/sfx_bank.json")
    if a.synth:
        for f in os.listdir(S) if os.path.isdir(S) else []:
            if f.endswith(".wav"): shutil.copy2(os.path.join(S, f), os.path.join(D, f))
        if os.path.exists(rep_p): os.remove(rep_p)
        print("SFX_BANK_DONE synthesized sounds restored"); return
    if not shutil.which("earshot"): sys.exit("earshot is not installed (python3 -I deps.py --install --with sound)")
    bank = dict(BANK)
    for kv in a.set:
        k, _, v = kv.partition("=")
        if not v: sys.exit(f"--set {kv}: use kind=earshot/id")
        bank[k] = (v, {})
    os.makedirs(S, exist_ok=True); rep = {}
    import numpy as np, soundfile as sf
    with tempfile.TemporaryDirectory() as tmp:
        for kind, (sid, opt) in bank.items():
            ref = os.path.join(S, kind + ".wav")
            if not os.path.exists(ref):
                if not os.path.exists(os.path.join(D, kind + ".wav")): print(f"skip {kind}: no synthesized reference (run make_sfx.sh)"); continue
                shutil.copy2(os.path.join(D, kind + ".wav"), ref)
            out = os.path.join(tmp, kind + ".wav")
            cmd = ["earshot", "sfx", "render", sid, "-o", out, "--sr", "48000", "--peak", "-1"] + sum([[f"--{k}", str(v)] for k, v in opt.items()], [])
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode or not os.path.exists(out): print(f"WARNING: {kind}: earshot {sid} failed — keeping the synthesized one ({(r.stderr or r.stdout).strip()[-160:]})"); continue
            l_ref, _ = loudness(ref); l_new, pk = loudness(out)
            g = l_ref - l_new; g = min(g, -1 - 20 * np.log10(max(pk, 1e-9)))   # same loudness as before, peak ≤ −1 dBFS
            x, sr = sf.read(out, always_2d=True); x = x * 10 ** (g / 20)
            if x.shape[1] == 1: x = np.repeat(x, 2, axis=1)   # the synthesized set is stereo
            sf.write(os.path.join(D, kind + ".wav"), x, sr, subtype="PCM_24")
            short = (l_ref - l_new) - g   # > 0: the peak ceiling stopped it short of the old loudness (a sharp click, a soft swish)
            rep[kind] = {"id": sid, "opt": opt, "gainDb": round(float(g), 1), "matchedLufs": round(float(l_ref), 1), "underDb": round(float(max(0, short)), 1)}
            print(f"{kind:12s} ← {sid:24s} {g:+5.1f} dB" + (f"  ({short:.1f} dB under the synthesized one: peak-limited)" if short > 0.5 else ""))
    try:
        import importlib.metadata as md; ver = md.version("earshot")
    except Exception: ver = "?"
    os.makedirs(os.path.dirname(rep_p), exist_ok=True)
    json.dump({"earshot": ver, "sounds": rep}, open(rep_p, "w"), indent=1)
    print(f"SFX_BANK_DONE {len(rep)} sounds from the earshot bank; synthesized originals in {os.path.relpath(S, P)}/ (--synth restores them)")


if __name__ == "__main__":
    main()
