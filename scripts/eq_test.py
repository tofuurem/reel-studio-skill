#!/usr/bin/env python3
"""Try voice_tune candidates on a 20–60 s stretch through the SAME chain dialogue.py uses — and hand the user one A/B MP3,
instead of rebuilding the dialogue and rendering the whole reel per idea.

Usage: work/dfvenv/bin/python -I eq_test.py <project> --at <timeline s> --dur 30
           --try "экспандер" '{"expander": true}' --try "резонансы" '{"notches": "auto"}' [--try NAME @file.json …]
           [--clip <id> (the restored take, --at = source seconds)] [--no-current] [--ab out/ab/voice.mp3] [--wav-dir DIR]
Source: work/voice/dialogue_raw.wav (dialogue.py --keep-raw: the assembly before the chain, un-leveled) at timeline time —
cuts, room tone and camera sound as in the reel; or --clip: one restored take at voiceTargetDb.
Version 1 is the project as it is now (work/voice_tune.json or nothing) unless --no-current; each --try is a whole tune
(the same keys as voice_tune.json: leveler, expander, notches, extraEq, hpf). Prints per version: centroid, the largest
deviation from the target speech shape, LRA, what the expander / notches did; --ab writes the loudness-matched A/B
(1, 2, 3 … beeps) via ab.py. The leveler here runs over the whole stretch (in dialogue.py: speech only, before room tone)
— close enough to judge by ear. Craft: references/craft/ab.md.
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N        # noqa: E402
import voicelib as V         # noqa: E402
from ab import write_ab      # noqa: E402
from voice_probe import dev  # noqa: E402

SR = V.SR


def load_tune(s):
    t = json.load(open(s[1:])) if s.startswith("@") else json.loads(s)
    return {k: v for k, v in t.items() if not k.startswith("_")}


def run(x, tune):
    rep = {}
    if tune.get("leveler"):
        lv = tune["leveler"] if isinstance(tune["leveler"], dict) else {}
        x, rep["leveler"] = V.leveler(x, N["voiceTargetDb"], lv.get("amount", N["levelerAmount"]), lv.get("max_db", N["levelerMaxDb"]))
    y, ch = V.voice_chain(x, tune=tune); ch.update(rep); return y, ch


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project")
    ap.add_argument("--at", type=float, required=True); ap.add_argument("--dur", type=float, default=30.0); ap.add_argument("--clip")
    ap.add_argument("--try", dest="tries", nargs=2, action="append", metavar=("NAME", "TUNE_JSON"), default=[])
    ap.add_argument("--no-current", action="store_true"); ap.add_argument("--ab", default="out/ab/voice_ab.mp3"); ap.add_argument("--wav-dir")
    a = ap.parse_args(); P = os.path.abspath(a.project); os.chdir(P)
    if a.clip:
        f = f"work/voice/out/{a.clip}_DeepFilterNet3.wav"
        if not os.path.exists(f): sys.exit(f"no {f} — voice_clean.py first")
        x = V.read(f, ss=a.at, t=a.dur); lv = V.active_db(x)
        if lv is not None: x = x * 10 ** ((N["voiceTargetDb"] - lv) / 20)
    else:
        f = "work/voice/dialogue_raw.wav"
        if not os.path.exists(f): sys.exit("no work/voice/dialogue_raw.wav — run dialogue.py <project> --keep-raw once (or use --clip <id>)")
        x = V.read(f, ss=a.at, t=a.dur)
    if len(x) < 5 * SR: sys.exit("the stretch is shorter than 5 s")
    cur = {}
    if os.path.exists("work/voice_tune.json"): cur = load_tune("@work/voice_tune.json")
    versions = ([] if a.no_current else [("как сейчас" + (f" {sorted(cur)}" if cur else ""), cur)]) + [(n, load_tune(t)) for n, t in a.tries]
    if not versions: sys.exit("nothing to compare: add --try NAME '<json>'")
    outs = []
    for k, (name, tune) in enumerate(versions, 1):
        y, ch = run(x, tune); d = dev(y); I, lra, _ = V.ebur128(y)
        extra = "; ".join(f"{key} {ch[key]}" for key in ("leveler", "expander", "notches", "extraEq") if ch.get(key))
        print(f"{k}. {name}: centroid {V.centroid(y):.0f} Hz, max |dev| {max(abs(v) for v in d.values()):.1f} dB, LRA {lra} LU{'; ' + extra if extra else ''}")
        print(f"   spectrum vs target: {d}")
        outs.append(y)
        if a.wav_dir: V.write(os.path.join(a.wav_dir, f"{k}_{name.split()[0]}.wav"), y)
    write_ab(a.ab, outs, names=[n for n, _ in versions])
    print("EQ_TEST_DONE")


if __name__ == "__main__":
    main()
