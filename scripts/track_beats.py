#!/usr/bin/env python3
"""The beat grid of a music track → where the reel starts in it, where the drop lands, which frames the cuts go on.

Usage: work/venv/bin/python -I track_beats.py <project> <track.mp3> [--start S] [--len SEC] [--fps 30] [--drop S]
  without --start: tempo, phase, a bar-by-bar energy map, the drop candidates and suggested windows of --len seconds
  with --start:    the same + the reel grid from that second: beat / bar / phrase frames and the drop frame, and the track
                   cut for the preview → reel/public/audio/track_cut.m4a (the published reel has NO music: the user adds the
                   same track in Instagram from the same second — the licence comes with Instagram's library)
→ work/track_beats.json {bpm, period, phase, beats [s], bars [{t, db, kick}], drops [s], start, len, fps, grid {beats, bars,
  phrases, drop}} — actiongen.py reads it (shots measured in beats land exactly on the grid).
Why (Halloween reel, 2026-11-04): the first beat tracker said 76.86 BPM for a 115.4 BPM track — every «cut on the beat» was
off. Here: spectral-flux onsets, autocorrelation for the period (70–180 BPM), then period and phase refined together over the
whole track; drops = the bars where the energy and the low end (kick) jump most over the two bars before. Listen to the
suggested drop before building on it; --drop S overrides it.
Also (2026-11-09, from video-shotcraft's beat-sync notes): drums split into bands — kick 40–160 Hz, snare 150–500 Hz +
1–3 kHz, hats 6–14 kHz; every bar carries its hat density (busy hats = room for small moves, sparse = hold still); the
strongest kick / snare transients become grid "hits" (frames) — pin accents (a flash, a crash) to a real hit, not a grid
point; and a tempo check: when as many strong hits fall between the beats as on them, the tempo is probably half (or the
phase is off) — the script says so with the ×2 value to try by ear.
Prints TRACK_BEATS_DONE.
"""
import argparse, json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, atomic_json

SR = 22050; NFFT = 1024; HOP = 256


def onsets(x):
    win = np.hanning(NFFT); n = 1 + (len(x) - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    M = np.log1p(100 * np.abs(np.fft.rfft(x[idx] * win, axis=1)))          # frames × bins
    f = np.fft.rfftfreq(NFFT, 1 / SR)
    d = np.maximum(0, np.diff(M, axis=0)); flux = np.concatenate([[0], d.sum(1)]); low = np.concatenate([[0], d[:, f < 150].sum(1)])
    fr = SR / HOP; k = int(fr)
    o = np.maximum(0, flux - np.convolve(flux, np.ones(k) / k, mode="same"))
    band = lambda m: np.concatenate([[0], d[:, m].sum(1)])
    bands = {"kick": band((f >= 40) & (f < 160)), "snare": band(((f >= 150) & (f < 500)) | ((f >= 1000) & (f < 3000))), "hat": band((f >= 6000) & (f < 11000))}
    return o, low, fr, bands


def peaks(env, fr, min_gap=0.25, q=92):
    """Strong transients of one band: local maxima over the q-th percentile of its rise, at least min_gap s apart."""
    e = np.maximum(0, env - np.convolve(env, np.ones(int(fr)) / int(fr), mode="same")); thr = np.percentile(e, q); g = int(min_gap * fr); out = []
    for i in np.flatnonzero(e > thr):
        if e[i] == e[max(0, i - g): i + g + 1].max() and (not out or i - out[-1] > g): out.append(i)
    return np.array(out) / fr, e


def grid(o, fr, dur):
    seg = o[: int(min(len(o), 120 * fr))]
    ac = np.correlate(seg, seg, mode="full")[len(seg) - 1:]
    lags = np.arange(len(ac)) / fr; ok = (lags > 60 / 180) & (lags < 60 / 70)
    period = lags[ok][np.argmax(ac[ok])]
    best = None
    for p in np.linspace(period * 0.99, period * 1.01, 41):
        for ph in np.linspace(0, p, 64, endpoint=False):
            idx = (np.arange(ph, len(o) / fr, p) * fr).astype(int); idx = idx[idx < len(o)]
            sc = o[idx].sum()
            if best is None or sc > best[0]: best = (sc, p, ph)
    _, p, ph = best
    # the downbeat: of the 4 beat phases, the one whose beats carry the most low-end onset energy starts the bars
    return float(p), float(ph), np.arange(ph, dur, p)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("track")
    ap.add_argument("--start", type=float); ap.add_argument("--len", type=float, default=45.0); ap.add_argument("--fps", type=int, default=30); ap.add_argument("--drop", type=float)
    a = ap.parse_args(); P = os.path.abspath(a.project)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", a.track, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64); dur = len(x) / SR
    if dur < 5: sys.exit(f"cannot read {a.track}")
    o, low, fr, bands = onsets(x); p, ph, beats = grid(o, fr, dur)
    hit_t = np.sort(np.concatenate([peaks(bands["kick"], fr, 0.3, 97)[0], peaks(bands["snare"], fr, 0.3, 97)[0]]))
    if len(hit_t): hit_t = hit_t[np.concatenate([[True], np.diff(hit_t) > 0.12])]   # a kick and a snare on the same hit count once
    # tempo check: strong hits on the beats vs halfway between them
    if len(hit_t) >= 8:
        rel = ((hit_t - ph) / p) % 1.0; on = np.mean((rel < 0.12) | (rel > 0.88)); mid = np.mean(np.abs(rel - 0.5) < 0.12)
        print(f"hits: {len(hit_t)} strong kick/snare transients, {on:.0%} on the beats, {mid:.0%} halfway between")
        if mid > 0.6 * on and mid > 0.2: print(f"TEMPO WARNING: as many hits fall between the beats as on them — try {120 / p:.1f} BPM (×2) by ear, or the phase is off")
    hat = bands["hat"]
    # downbeat phase: which of every 4th beat has the strongest kick
    kick_at = lambda t: low[int(t * fr)] if int(t * fr) < len(low) else 0
    down = max(range(4), key=lambda k: sum(kick_at(t) for t in beats[k::4]))
    bars_t = beats[down::4]
    bars = []
    for t0, t1 in zip(bars_t, bars_t[1:]):
        seg = x[int(t0 * SR): int(t1 * SR)]
        bars.append({"t": round(float(t0), 3), "db": round(float(10 * np.log10((seg ** 2).mean() + 1e-12)), 1), "kick": round(float(low[int(t0 * fr): int(t1 * fr)].mean()), 2),
                     "hat": round(float(hat[int(t0 * fr): int(t1 * fr)].mean()), 2)})
    score = []
    for i in range(2, len(bars)):
        prev_db = max(bars[i - 1]["db"], bars[i - 2]["db"]); prev_k = max(bars[i - 1]["kick"], bars[i - 2]["kick"], 1e-6)
        score.append((bars[i]["db"] - prev_db + 6 * np.log2(max(bars[i]["kick"], 1e-6) / prev_k), bars[i]["t"]))
    drops = [t for _, t in sorted(score, reverse=True)[:4]]
    phrase = N["actionPhraseBars"]
    out = {"track": os.path.abspath(a.track), "bpm": round(60 / p, 2), "period": round(p, 5), "phase": round(ph, 4), "downbeat": int(down),
           "beats": [round(float(b), 3) for b in beats], "bars": bars, "drops": drops}
    print(f"BPM {60 / p:.2f}  beat {p:.5f} s = {p * a.fps:.3f} frames at {a.fps} fps  first beat {ph:.3f} s  bar = {4 * p:.3f} s  phrase ({phrase} bars) = {phrase * 4 * p:.2f} s")
    for i, b in enumerate(bars):
        mark = "  ← drop?" if b["t"] in drops[:2] else ""
        if i % 2 == 0 or mark: print(f"  bar {i:3d}  {int(b['t'] // 60)}:{b['t'] % 60:05.2f}  {b['db']:6.1f} dB  kick {b['kick']:6.2f}  hat {b['hat']:5.2f}  " + "#" * int(max(0, b["db"] + 32)) + mark)
    print("drop candidates (listen!):", ", ".join(f"{int(t // 60)}:{t % 60:05.2f} ({t:.2f} s)" for t in drops))
    if a.start is None:
        d = drops[0]
        for lead_bars in (2, 3, 4):
            s = max(0.0, d - lead_bars * 4 * p)
            print(f"  window: --start {s:.3f} --len {a.len:g}  → the drop lands at {d - s:.2f} s (frame {round((d - s) * a.fps)}), {lead_bars} bars of build-up first")
    else:
        drop = a.drop if a.drop is not None else next((t for t in drops if a.start < t < a.start + a.len), None)
        f = lambda t: round((t - a.start) * a.fps)
        inwin = lambda t: a.start - 1e-6 <= t < a.start + a.len
        bt = [t for t in beats if inwin(t)]; br = [b["t"] for b in bars if inwin(b["t"])]
        anchor = drop if drop is not None else (br[0] if br else a.start)
        ph_t = [t for t in np.arange(anchor - 64 * phrase * 4 * p, a.start + a.len, phrase * 4 * p) if inwin(t)]
        out.update({"start": a.start, "len": a.len, "fps": a.fps, "drop": drop,
                    "grid": {"beats": [f(t) for t in bt], "bars": [f(t) for t in br], "phrases": [f(t) for t in ph_t], "drop": f(drop) if drop is not None else None,
                             "hits": [f(t) for t in hit_t if inwin(t)],
                             "frames": round(a.len * a.fps), "beatFrames": round(p * a.fps, 4)}})
        os.makedirs(os.path.join(P, "reel/public/audio"), exist_ok=True); cut = os.path.join(P, "reel/public/audio/track_cut.m4a")
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{a.start:.4f}", "-t", f"{a.len:.3f}", "-i", a.track, "-vn", "-c:a", "aac", "-b:a", "192k", cut], check=True)
        print(f"reel grid from {a.start:.3f} s ({int(a.start // 60)}:{a.start % 60:05.2f}): {len(bt)} beats, drop at frame {out['grid']['drop']}, phrases at frames {out['grid']['phrases']}")
        print(f"preview track → {cut}  (tell the user: in Instagram start the track at {int(a.start // 60)}:{a.start % 60:04.1f})")
    os.makedirs(os.path.join(P, "work"), exist_ok=True); atomic_json(out, os.path.join(P, "work/track_beats.json"))
    print("TRACK_BEATS_DONE", os.path.join(P, "work/track_beats.json"))


if __name__ == "__main__":
    main()
