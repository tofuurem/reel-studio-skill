#!/usr/bin/env python3
"""Loudness-matched audio A/B for the user: 1, 2, 3 … short beeps announce each version, then the clip — one MP3 to listen
to on the phone instead of a whole reel per idea. Reads any media (wav, mp3, mp4, mov: the first audio track).

Usage: work/dfvenv/bin/python -I ab.py <out.mp3> <file>[@start:dur] <file>[@start:dur] … [--names "как сейчас,экспандер"]
                                       [--lufs -16] [--after <file>@start:dur]
  start / dur in seconds of that file; --after plays this clip after EVERY version (the next words, the music drop) —
  compare in context, not in isolation. Prints the legend (1 = …, 2 = …) and AB_DONE.
Why: a podcast edit ep. 2 (2026-11-13) — the user decided voices, stingers and the guest's mic by ear from such files; a
variant that won as a 30-s A/B still failed inside the episode, so keep --after (or a stretch with a cut) for decisions
that live at a transition. Craft: references/craft/ab.md. Video versions: ab_video.py.
"""
import argparse, os, subprocess, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voicelib as V   # noqa: E402

SR = V.SR


def beeps(k, freq=740.0):
    """k short beeps (160 ms, 120 ms apart) at −20 dBFS: «version k» without words."""
    n = int(0.16 * SR); one = 0.1 * np.sin(2 * np.pi * freq * np.arange(n) / SR) * np.hanning(n)
    return np.concatenate([np.concatenate([one, np.zeros(int(0.12 * SR))]) for _ in range(k)])


def clip(spec):
    """'file[@start:dur]' → mono float at SR."""
    path, _, rng = spec.partition("@")
    if not os.path.exists(path): sys.exit(f"no file {path}")
    if rng:
        s, d = (float(v) for v in rng.split(":")); return V.read(path, ss=s, t=d)
    return V.read(path)


def match(x, lufs):
    I, _, _ = V.ebur128(x)
    return x if I is None or I < -70 else x * 10 ** ((lufs - I) / 20)


def write_ab(out, versions, after=None, lufs=-16.0, names=None):
    """versions: list of mono arrays → MP3 (stereo 256k) with k beeps before version k."""
    if after is not None: after = match(after, lufs)
    parts = []
    for k, x in enumerate(versions, 1):
        parts += [beeps(k), np.zeros(int(0.7 * SR)), match(x, lufs)]
        if after is not None: parts += [np.zeros(int(0.4 * SR)), after]
        parts.append(np.zeros(int(1.2 * SR)))
    y = np.concatenate(parts); y = y / max(1.0, np.abs(y).max() / 0.89)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        w = os.path.join(tmp, "ab.wav"); V.write(w, y)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", w, "-ac", "2", "-c:a", "libmp3lame", "-b:a", "256k", out], check=True)
    for k in range(1, len(versions) + 1):
        print(f"  {k} {'бип' if k == 1 else 'бипа' if k < 5 else 'бипов'} = {names[k - 1] if names and k <= len(names) else f'версия {k}'}")
    print(f"AB_DONE {out} ({len(y) / SR:.0f} s, {len(versions)} versions)")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("clips", nargs="+")
    ap.add_argument("--names", default=""); ap.add_argument("--lufs", type=float, default=-16.0); ap.add_argument("--after")
    a = ap.parse_args()
    write_ab(a.out, [clip(c) for c in a.clips], clip(a.after) if a.after else None, a.lufs, [s.strip() for s in a.names.split(",")] if a.names else None)


if __name__ == "__main__":
    main()
