#!/usr/bin/env python3
"""Two wireless mics recorded as the camera's L/R channels → one clean voice per clip (the voice_isolate.sh step for them).

Usage: work/dfvenv/bin/python -I dualmic.py <project> [--cutlist work/cutlist.json] [--pad 2] <camera files…>
       work/dfvenv/bin/python -I dualmic.py <project> --test START DUR <camera file>   → work/voice/test/<id>_{L,R,mix,downmix}.wav
Why (Halloween vlog, 2026-11-02 … 04): a downmix first mixes both mics' noise and the far mic's late copy of every voice
(comb filtering, a hollow «из толчка» voice); a mic held at the mouth clips in the transmitter, and the flat tops crackle
(«колонки хотят спалить»). So, per channel: adeclip (input halved so rebuilt peaks fit) → DeepFilterNet limited to
dualmicAtten dB (full strength sounded hollow) → a Dugan-style automix per 10 ms: each channel's gain is its share of the
smoothed power ^ (dualmicHard / 2), so whoever speaks into their own mic wins. A dead channel (digital silence) is skipped;
a mono file or two identical channels (one mic on both) go through the same chain once.
--cutlist cleans only the source ranges the cut list uses (± --pad s), zeros elsewhere — a 9-minute take is not read whole.
Output: work/voice/out/<clipId>_DeepFilterNet3.wav (48 kHz mono float, full clip length) — what voice_mix.py and
make_proxies --voice-dir read. Re-runs skip finished clips unless the windows changed (work/voice/out/.dualmic.json).
Prints DUALMIC_DONE.
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, atomic_json, clip_id, load_json, src_dur

SR = 48000; HOP = 480   # 10 ms
DECLIP = "adeclip,volume=0.5"


def channels(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip()
    return int(r or 0)


def duration(src):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True).stdout)


def extract(src, ch, dst, ss=None, t=None):
    """One channel (or the mono track: ch None), declipped, 48 kHz."""
    seek = ["-ss", f"{ss:.3f}", "-t", f"{t:.3f}"] if ss is not None else []
    pan = f"pan=mono|c0=c{ch}," if ch is not None else ""
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *seek, "-i", src, "-map", "0:a:0", "-vn",
                    "-af", f"{pan}{DECLIP}", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", dst], check=True)


def same_channels(src, ss=None):
    """Two channels carrying one mic (a mono mic split to L/R): correlation of a 20 s sample > 0.98."""
    seek = ["-ss", f"{ss:.3f}"] if ss is not None else []
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", *seek, "-t", "20", "-i", src, "-map", "0:a:0", "-ac", "2", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
    if len(x) < 1600 or x.std(0).min() < 1e-5: return False
    return float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]) > 0.98


def env(x):
    n = len(x) // HOP
    if not n: return np.zeros_like(x)
    p = (x[: n * HOP].reshape(n, HOP) ** 2).mean(1) + 1e-10
    out = np.empty_like(p); s = p[0]
    for i, v in enumerate(p):   # fast attack (~20 ms), slower release (~160 ms)
        s += (0.5 if v > s else 0.06) * (v - s); out[i] = s
    e = np.repeat(out, HOP)
    return np.pad(e, (0, len(x) - len(e)), mode="edge")


def automix(l, r):
    n = min(len(l), len(r)); l, r = l[:n], r[:n]
    live = [c for c in (l, r) if len(c) and np.abs(c).max() > 1e-4]
    if len(live) < 2: return live[0] if live else l
    hard = N["dualmicHard"] / 2
    el, er = env(l) ** hard, env(r) ** hard
    gl = el / (el + er + 1e-30)
    return gl * l + (1 - gl) * r


def clean(P, src, ranges, tmp):
    """Clean voice for each (a, b) source range (None = the whole file) → list of float arrays."""
    df = os.path.join(P, "work/dfvenv/bin/deepFilter")
    if not os.path.exists(df): sys.exit(f"DeepFilterNet missing: run setup_env.sh {P} first")
    two = channels(src) >= 2 and not same_channels(src, ranges[0][0] if ranges[0] else None)
    chans = ((0, "L"), (1, "R")) if two else ((None, "M"),)
    ins = []
    for i, rg in enumerate(ranges):
        for ch, name in chans:
            f = os.path.join(tmp, f"w{i:03d}_{name}.wav"); ins.append(f)
            extract(src, ch, f) if rg is None else extract(src, ch, f, rg[0], rg[1] - rg[0])
    subprocess.run([df, *ins, "-a", str(N["dualmicAtten"]), "-o", tmp], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = []
    for i, _ in enumerate(ranges):
        got = [sf.read(os.path.join(tmp, f"w{i:03d}_{name}_DeepFilterNet3.wav"))[0] for _, name in chans]
        out.append(2 * (automix(*got) if two else got[0]))   # ×2 gives back the declip headroom
    return out, two


def windows(cl, src, pad, dur):
    rs = sorted((max(0.0, float(s["srcStart"]) - pad), min(dur, float(s["srcStart"]) + src_dur(s) + pad))
                for s in cl["main"] if os.path.realpath(s["path"]) == os.path.realpath(src) and float(s.get("volume", 1)) >= 0.01)
    merged = []
    for a, b in rs:
        if merged and a <= merged[-1][1] + 1.0: merged[-1][1] = max(merged[-1][1], b)
        else: merged.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in merged]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("sources", nargs="+")
    ap.add_argument("--cutlist"); ap.add_argument("--pad", type=float, default=2.0); ap.add_argument("--test", nargs=2, type=float, metavar=("START", "DUR"))
    a = ap.parse_args(); P = os.path.abspath(a.project)
    os.makedirs(os.path.join(P, "work/tmp"), exist_ok=True)
    if a.test:
        src = a.sources[0]; cid = clip_id(src); outdir = os.path.join(P, "work/voice/test"); os.makedirs(outdir, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.path.join(P, "work/tmp")) as tmp:
            rg = (a.test[0], a.test[0] + a.test[1]); (mix,), two = clean(P, src, [rg], tmp)
            sf.write(os.path.join(outdir, f"{cid}_mix.wav"), mix, SR, subtype="FLOAT")
            if two:
                for name in ("L", "R"): os.replace(os.path.join(tmp, f"w000_{name}_DeepFilterNet3.wav"), os.path.join(outdir, f"{cid}_{name}.wav"))
            dm = os.path.join(tmp, "dm.wav")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", str(rg[0]), "-t", str(a.test[1]), "-i", src, "-map", "0:a:0", "-ac", "1", "-ar", str(SR), dm], check=True)
            subprocess.run([os.path.join(P, "work/dfvenv/bin/deepFilter"), dm, "-o", tmp], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.replace(os.path.join(tmp, "dm_DeepFilterNet3.wav"), os.path.join(outdir, f"{cid}_downmix.wav"))
        print("test files:", outdir, "(" + ("two mics" if two else "one mic") + ")"); print("DUALMIC_DONE"); return
    cl = load_json(os.path.join(P, a.cutlist)) if a.cutlist else None
    if a.cutlist and not cl: sys.exit(f"no cut list at {a.cutlist}")
    outdir = os.path.join(P, "work/voice/out"); os.makedirs(outdir, exist_ok=True)
    state_p = os.path.join(outdir, ".dualmic.json"); state = load_json(state_p, {}) or {}
    for src in a.sources:
        cid = clip_id(src); target = os.path.join(outdir, f"{cid}_DeepFilterNet3.wav"); dur = duration(src)
        rs = windows(cl, src, a.pad, dur) if cl else None
        if cl and not rs: print("skip", cid, "(no speaking segment in the cut list)"); continue
        sig = {"windows": rs, "atten": N["dualmicAtten"], "hard": N["dualmicHard"]}
        if os.path.exists(target) and state.get(cid) == sig: print("skip", cid, "(done)"); continue
        if os.path.exists(target) and cid not in state and not cl: print("skip", cid, "(done)"); continue
        with tempfile.TemporaryDirectory(dir=os.path.join(P, "work/tmp")) as tmp:
            parts, two = clean(P, src, rs or [None], tmp)
            full = np.zeros(int(dur * SR) + SR)
            for rg, m in zip(rs or [(0.0, dur)], parts):
                s0 = int(rg[0] * SR); m = m[: max(0, min(len(m), len(full) - s0))].copy()
                k = min(480, len(m) // 2)   # 10 ms edges; the windows are padded, so the cut points sit well inside
                if k and rs: m[:k] *= np.linspace(0, 1, k); m[-k:] *= np.linspace(1, 0, k)
                full[s0:s0 + len(m)] = m
        sf.write(target + ".part.wav", full, SR, subtype="FLOAT", format="WAV"); os.replace(target + ".part.wav", target)
        state[cid] = sig; atomic_json(state, state_p)
        print("done", cid, "two mics" if two else "one mic", f"{len(rs)} window(s)" if rs else "whole file", flush=True)
    print("DUALMIC_DONE", outdir)


if __name__ == "__main__":
    main()
