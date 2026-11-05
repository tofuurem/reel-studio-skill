#!/usr/bin/env python3
"""The voice bus of a cut made here (plan.json → cut list): every clip's cleaned voice brought to one level, picture beats
given the camera's own sound, loud moments tamed — written as the voice files make_proxies.py muxes in.

Usage: work/dfvenv/bin/python -I voice_mix.py <project> [--voice-dir work/voice/out] [--out work/voice/mixed] [--force]
Then: make_proxies.py … --voice-dir work/voice/mixed (only clips whose mix changed are re-encoded: the file is rewritten
only when its inputs changed, work/voice/mixed/.manifest.json).
Why (Halloween vlog, 52 clips, two cameras, two lav mics, 2026-11-02 … 04):
- the cleaned voice varies by up to 25 dB between clips → per clip, the active speech (20 ms frames within 30 dB of the
  loudest) goes to voiceTargetDb, at most voiceMaxGain up (more lifts mic hiss and DeepFilterNet artefacts);
- a whispered line inside a loud clip → per segment ±voiceSegMax dB into [voiceSegLo, voiceSegHi], 40 ms ramps;
- DeepFilterNet leaves digital silence where nobody speaks (a dance, a bike ride) and a picture beat with no sound feels
  dead in a vlog without music → a segment with "amb": true (plan opts) gets the camera's own sound at ambDb, kept out
  from under every transcript word (±0.25 s: the camera mic hears the voice late = a hollow echo); "raw": true replaces
  the cleaned voice with the camera sound at rawDb (DeepFilterNet swallowed a line — a voice inside a costume);
- a shout into a close lav sat 7 dB over the speech and render.sh's static gain pushed it into the hard limiter
  («колонки хрипят») → tame(): a 3:1 compressor over voiceTargetDb + tameOverDb on a 10 ms envelope, then a 3 ms look-ahead
  limiter at tameCeilDb, so render.sh's limiter has nothing left to do; then highpass 80 Hz + a gentle 2.5:1 compressor.
Alias clips (cut_from_transcript.py splits far-apart ranges of one take into <id>x<k>) read their base clip's voice.
Prints VOICE_MIX_DONE.
"""
import argparse, hashlib, json, os, subprocess, sys, tempfile
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, atomic_json, clip_id, load_json, src_dur

SR = 48000; FADE = int(0.15 * SR)
VOICE_AF = "highpass=f=80,acompressor=threshold=-24dB:ratio=2.5:attack=15:release=200:makeup=1"


def active_db(x):
    """Level of the speech itself: RMS of the 20 ms frames within 30 dB of the loudest ones (pauses do not count)."""
    n = len(x) // 960
    if n == 0: return None
    f = 10 * np.log10((x[: n * 960].reshape(n, 960) ** 2).mean(1) + 1e-12)
    act = f[f > f.max() - 30]; act = act[act > -60]
    return None if len(act) < 10 else float(10 * np.log10(np.mean(10 ** (act / 10))))


def camera(src, a, dur):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{max(0, a):.3f}", "-t", f"{dur:.3f}", "-i", src, "-map", "0:a:0", "-vn",
                          "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def speech_gate(words, a, n):
    """1 where nobody speaks, 0 under every word (±0.25 s), 0.12 s ramps — n samples from source second a."""
    g = np.ones(n); R = int(0.12 * SR)
    for w in words:
        i0 = int((w["start"] - 0.25 - a) * SR); i1 = int((min(w["end"], w["start"] + 0.9) + 0.25 - a) * SR)
        if i1 < 0 or i0 > n: continue
        g[max(0, i0): min(n, i1)] = 0
    return np.convolve(g, np.ones(R) / R, mode="same")


def tame(x):
    """Compressor on a 10 ms power envelope (≈20 ms attack, ≈160 ms release), then a 3 ms look-ahead peak limiter with an
    80 ms release — gain curves interpolated to samples, no hard clipping anywhere."""
    comp_db = N["voiceTargetDb"] + N["tameOverDb"]; ratio = N["tameRatio"]; ceil = 10 ** (N["tameCeilDb"] / 20)
    H = 480; n = len(x) // H
    if n < 2: return x
    p = (x[: n * H].reshape(n, H) ** 2).mean(1) + 1e-12; e = np.empty(n); v = p[0]
    for i in range(n):
        v += (0.5 if p[i] > v else 0.06) * (p[i] - v); e[i] = v
    over = np.maximum(0, 10 * np.log10(e) - comp_db)
    x = x * np.interp(np.arange(len(x)), np.arange(n) * H + H / 2, 10 ** (-over * (1 - 1 / ratio) / 20))
    B = 48; m = len(x) // B + 1
    pk = np.zeros(m * B); pk[: len(x)] = np.abs(x); pk = pk.reshape(m, B).max(1)
    req = np.minimum(1, ceil / np.maximum(pk, 1e-9)); ahead = req.copy()
    for k in range(1, 4): ahead[:-k] = np.minimum(ahead[:-k], req[k:])
    out = np.empty(m); v = 1.0; up = 1 - np.exp(-1 / 80)
    for i in range(m):
        v = ahead[i] if ahead[i] < v else v + up * (ahead[i] - v); out[i] = v
    return np.clip(x * np.interp(np.arange(len(x)), np.arange(m) * B + B / 2, out), -ceil, ceil)


def ramp(x):
    k = min(FADE, len(x) // 2)
    if k: x[:k] *= np.linspace(0, 1, k); x[-k:] *= np.linspace(1, 0, k)
    return x


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--voice-dir", default="work/voice/out")
    ap.add_argument("--out", default="work/voice/mixed"); ap.add_argument("--cutlist", default="work/cutlist.json"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); P = os.path.abspath(a.project); os.chdir(P)
    cl = load_json(a.cutlist)
    if not cl: sys.exit(f"no cut list at {a.cutlist}")
    os.makedirs(a.out, exist_ok=True); os.makedirs("work/tmp", exist_ok=True)
    man_p = os.path.join(a.out, ".manifest.json"); man = load_json(man_p, {}) or {}
    flag = lambda s, k: bool(s.get(k) or (s.get("meta") or {}).get(k))
    speech = lambda s: float(s.get("volume", 1)) >= 0.01 and not flag(s, "amb") and not flag(s, "raw")
    by = {}
    for s in cl["main"]:
        if s.get("materialType", "video") == "video": by.setdefault(clip_id(s["path"]), []).append(s)
    base = {cid: (cl.get("aliases") or {}).get(cid, cid) for cid in by}   # alias clips read their take's voice
    words_map = cl.get("words") or {}
    def words_of(s):
        f = words_map.get(s.get("clip", "")) or words_map.get(base[clip_id(s["path"])][1:])
        return [w for sg in json.load(open(f))["segments"] for w in sg.get("words", [])] if f and os.path.exists(f) else []
    vpath = lambda b: os.path.join(a.voice_dir, f"{b}_DeepFilterNet3.wav")
    # per base clip: one gain from all the speech it contributes (aliases included)
    gain, cache = {}, {}
    for b in sorted(set(base.values())):
        if not os.path.exists(vpath(b)): continue
        info = sf.info(vpath(b)); parts = []
        for cid, ss in by.items():
            if base[cid] != b: continue
            for s in ss:
                if not speech(s): continue
                i0 = int(float(s["srcStart"]) * SR); parts.append(sf.read(vpath(b), start=i0, stop=min(info.frames, i0 + int(src_dur(s) * SR)))[0])
        lv = active_db(np.concatenate(parts)) if parts else None
        gain[b] = 0.0 if lv is None else float(np.clip(N["voiceTargetDb"] - lv, -12, N["voiceMaxGain"]))
    print("clip gains dB:", {k: round(g, 1) for k, g in gain.items()})
    nums = {k: N[k] for k in ("voiceTargetDb", "voiceMaxGain", "voiceSegLo", "voiceSegHi", "voiceSegMax", "ambDb", "rawDb", "tameOverDb", "tameRatio", "tameCeilDb")}
    wrote = 0
    for cid, ss in sorted(by.items()):
        b = base[cid]; src = ss[0]["path"]; target = os.path.join(a.out, f"{cid}_DeepFilterNet3.wav")
        ambs = [s for s in ss if float(s.get("volume", 1)) >= 0.01 and (flag(s, "amb") or flag(s, "raw"))]
        if not os.path.exists(vpath(b)):
            if not ambs: continue
            print(f"{cid}: no cleaned voice ({vpath(b)}) — camera sound only for its amb/raw segments")
        sig = hashlib.md5(json.dumps([nums, gain.get(b), [[s["srcStart"], src_dur(s), s.get("volume", 1), flag(s, "amb"), flag(s, "raw")] for s in ss],
                                      os.path.getmtime(vpath(b)) if os.path.exists(vpath(b)) else 0, VOICE_AF]).encode()).hexdigest()[:12]
        if not a.force and man.get(cid) == sig and os.path.exists(target): print("ok", cid, "(unchanged)"); continue
        lo = max(0.0, min(float(s["srcStart"]) for s in ss) - 2.0); hi = max(float(s["srcStart"]) + src_dur(s) for s in ss) + 2.0
        n0, n = int(lo * SR), int((hi - lo) * SR)
        track = np.zeros(n)
        if os.path.exists(vpath(b)):
            v = sf.read(vpath(b), start=n0, stop=n0 + n)[0]; track[: len(v)] = v * 10 ** (gain.get(b, 0) / 20)
        env = np.ones(n); R = int(0.04 * SR)
        for s in ss:
            if not speech(s): continue
            i0 = max(0, int(float(s["srcStart"]) * SR) - n0); i1 = min(n, i0 + int(src_dur(s) * SR))
            lv = active_db(track[i0:i1])
            if lv is None or N["voiceSegLo"] <= lv <= N["voiceSegHi"]: continue
            g = 10 ** (float(np.clip((N["voiceSegLo"] if lv < N["voiceSegLo"] else N["voiceSegHi"]) - lv, -N["voiceSegMax"], N["voiceSegMax"])) / 20)
            a0, a1 = max(0, i0 - R), min(n, i1 + R)
            env[a0:a1] = np.interp(np.arange(a0, a1), [a0, i0, i1, a1], [env[a0], g, g, env[min(a1, n - 1)]])
        track *= env
        for s in ambs:
            raw = flag(s, "raw"); t0 = float(s["srcStart"]) - 0.2; d = src_dur(s) + 0.4
            cam = camera(os.path.realpath(src), t0, d); lv = active_db(cam)
            if lv is None: continue
            cam = ramp(cam * 10 ** (((N["rawDb"] if raw else N["ambDb"]) - lv) / 20))
            if not raw: cam *= speech_gate(words_of(s), t0, len(cam))
            i0 = int(t0 * SR) - n0; i0c = max(0, i0); cam = cam[i0c - i0:][: max(0, n - i0c)]
            if raw: track[i0c: i0c + len(cam)] *= 0.0
            track[i0c: i0c + len(cam)] += cam
        track = tame(track)
        full = np.zeros(n0 + n); full[n0:] = track   # source seconds stay source seconds (make_proxies windows the file)
        with tempfile.TemporaryDirectory(dir="work/tmp") as tmp:
            w = os.path.join(tmp, "a.wav"); sf.write(w, full, SR, subtype="FLOAT")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", w, "-af", VOICE_AF, "-c:a", "pcm_f32le", target + ".part.wav"], check=True)
        os.replace(target + ".part.wav", target); man[cid] = sig; atomic_json(man, man_p); wrote += 1
        print("mixed", cid, f"gain {gain.get(b, 0):+.1f} dB", f"{len(ambs)} amb/raw" if ambs else "", flush=True)
    print("VOICE_MIX_DONE", a.out, f"{wrote} written, {len(by) - wrote} unchanged/skipped")


if __name__ == "__main__":
    main()
