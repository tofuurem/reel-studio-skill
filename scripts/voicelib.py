#!/usr/bin/env python3
"""Shared voice DSP: voice_clean.py, dualmic.py, dialogue.py and audio_qa.py use it (numpy + soundfile + ffmpeg, no scipy —
it runs in work/dfvenv). Filters with a fixed shape (high-pass, bells, shelves, band-pass) are ffmpeg biquads run through
a pipe; everything level-dependent (compressor, de-esser, limiter, leveling) is a gain curve on 10 ms / 2.5 ms frames.

Why one module (2026-11-07 audit of the reel-studio reel): the voice went through adeclip on unclipped audio, full-strength
DeepFilterNet (digital silence in every pause, −3 dB hole at 3.15 kHz), three compressors/limiters in a row (LRA 8.5 → 2.6 LU)
and four AAC encodes — each script had its own idea of «clean». Now: restore once per source (voice_clean.py), then ONE
chain over the whole dialogue (dialogue.py), then the master (render.sh). Every number is in numbers.json «Voice chain».
"""
import json, os, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N

SR = 48000
HOP = 480            # 10 ms analysis frames
EPS = 1e-12

# International long-term average speech spectrum (Byrne et al. 1994, male+female, 1/3 octave, dB) — only its SHAPE is used.
LTASS = {100: 54.4, 125: 57.7, 160: 56.8, 200: 60.2, 250: 60.3, 315: 59.0, 400: 62.1, 500: 62.1, 630: 60.5, 800: 56.8,
         1000: 53.7, 1250: 53.0, 1600: 52.0, 2000: 48.7, 2500: 48.1, 3150: 46.8, 4000: 45.6, 5000: 44.5, 6300: 44.3,
         8000: 43.7, 10000: 43.4, 12500: 41.3}
# what a finished spoken-word voice adds to it: less box, a little presence and air (broadcast practice)
FINISH = {250: -1.0, 315: -1.0, 400: -1.0, 2000: 1.0, 2500: 2.0, 3150: 2.0, 4000: 2.0, 5000: 1.0, 8000: 1.0, 10000: 2.0, 12500: 2.0}
BANDS = sorted(LTASS)


# ---------------------------------------------------------------- I/O

def read(src, ss=None, t=None, ch=None, sr=SR):
    """Mono float64 at `sr` from any media file (ch = one channel of a stereo track, else a downmix)."""
    seek = ["-ss", f"{ss:.4f}"] if ss is not None else []
    dur = ["-t", f"{t:.4f}"] if t is not None else []
    if ch is not None: mix = ["-af", f"pan=mono|c0=c{ch}"]
    else:   # the mean of the channels: ffmpeg's -ac 1 adds them at 0.707 each, +3 dB on a lav sent to both (false «clipping»)
        k = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", src],
                               capture_output=True, text=True).stdout.strip() or 1)
        mix = [] if k == 1 else ["-af", "pan=mono|c0=" + "+".join(f"{1 / k:.6f}*c{i}" for i in range(k))]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", *seek, *dur, "-i", src, "-map", "0:a:0", "-vn", *mix, "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def write(path, x, subtype="FLOAT"):
    import soundfile as sf
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".part.wav"
    sf.write(tmp, np.asarray(x, dtype=np.float32 if subtype == "FLOAT" else np.float64), SR, subtype=subtype, format="WAV")
    os.replace(tmp, path)


def fit(y, n):
    return y[:n] if len(y) >= n else np.pad(y, (0, n - len(y)))


def ffilter(x, af, sr=SR):
    """Run an ffmpeg audio filter chain over a mono array (same length back)."""
    if not af or not len(x): return x
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-", "-af", af,
                        "-f", "f32le", "-ar", str(sr), "-ac", "1", "-"], input=np.asarray(x, dtype=np.float32).tobytes(), capture_output=True, check=True)
    return fit(np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64), len(x))


def ebur128(x, sr=SR):
    """(integrated LUFS, LRA LU, true peak dBTP) of a mono array — ffmpeg's ebur128 with true-peak."""
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-", "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
                       input=np.asarray(x, dtype=np.float32).tobytes(), capture_output=True).stderr.decode(errors="replace")
    g = lambda k: (lambda m: float(m[-1]) if m else None)(re.findall(k + r":\s+(-?[\d.]+|-inf)", r.replace("-inf", "-120")))
    return g("I"), g("LRA"), g("Peak")


# ---------------------------------------------------------------- analysis

def frame_power(x, hop=HOP):
    n = len(x) // hop
    return (x[: n * hop].reshape(n, hop) ** 2).mean(1) + EPS if n else np.zeros(0)


def db(p):
    return 10 * np.log10(np.maximum(p, EPS))


def active_db(x, hop=960):
    """Level of the speech itself: power mean of the 20 ms frames within 30 dB of the loudest (pauses do not count)."""
    f = db(frame_power(x, hop))
    if not len(f): return None
    act = f[f > f.max() - 30]; act = act[act > -60]
    return None if len(act) < 10 else float(10 * np.log10(np.mean(10 ** (act / 10))))


def analyse(x):
    """speechDb (active level), floorDb (10th percentile of the 50 ms frames that are not digital silence), snrDb, peakDb,
    clipSamples (|x| ≥ 0.985: a lav at the mouth clips in the transmitter), silentFrac (frames under −80 dBFS)."""
    f = db(frame_power(x, 2400)); live = f[f > -90]
    sp = active_db(x); fl = float(np.percentile(live, 10)) if len(live) else -120.0
    pk = float(20 * np.log10(max(np.abs(x).max() if len(x) else 0, EPS)))
    return {"speechDb": None if sp is None else round(sp, 1), "floorDb": round(fl, 1), "snrDb": None if sp is None else round(sp - fl, 1),
            "peakDb": round(pk, 1), "clipSamples": int(np.sum(np.abs(x) >= 0.985)), "silentFrac": round(float(np.mean(f < -80)) if len(f) else 0.0, 3)}


def ltas(x, active=True, nfft=4096):
    """1/3-octave band levels (dB, LTASS bands) over the active-speech frames (power within 15 dB of the speech level)."""
    n = len(x) // nfft
    if n < 4: return None
    fr = x[: n * nfft].reshape(n, nfft)
    p = (fr ** 2).mean(1); keep = np.ones(n, bool)
    if active:
        sp = active_db(x)
        if sp is None: return None
        keep = db(p) > sp - 15
        if keep.sum() < 4: return None
    idx = np.flatnonzero(keep); idx = idx[np.linspace(0, len(idx) - 1, min(len(idx), 1500)).astype(int)]   # bounded memory on long takes
    spec = (np.abs(np.fft.rfft(fr[idx] * np.hanning(nfft), axis=1)) ** 2).mean(0)
    fq = np.fft.rfftfreq(nfft, 1 / SR); out = {}
    for b in BANDS:
        m = (fq >= b / 2 ** (1 / 6)) & (fq < b * 2 ** (1 / 6))
        out[b] = float(db(spec[m].sum()))
    return out


def transfer(before, after):
    """1/3-octave change after − before over the frames where the voice is active in `before` (same length, same timing)."""
    n = min(len(before), len(after)); nfft = 4096; k = n // nfft
    if k < 4: return {}
    b = before[: k * nfft].reshape(k, nfft); a = after[: k * nfft].reshape(k, nfft)
    sp = active_db(before[:n]); keep = db((b ** 2).mean(1)) > (sp if sp is not None else -40) - 10
    if keep.sum() < 4: return {}
    w = np.hanning(nfft); idx = np.flatnonzero(keep); idx = idx[np.linspace(0, len(idx) - 1, min(len(idx), 1500)).astype(int)]
    sb = (np.abs(np.fft.rfft(b[idx] * w, axis=1)) ** 2).mean(0); sa = (np.abs(np.fft.rfft(a[idx] * w, axis=1)) ** 2).mean(0)
    fq = np.fft.rfftfreq(nfft, 1 / SR); out = {}
    for c in BANDS + [16000]:
        m = (fq >= c / 2 ** (1 / 6)) & (fq < c * 2 ** (1 / 6))
        out[c] = round(float(db(sa[m].sum()) - db(sb[m].sum())), 1)
    return out


# ---------------------------------------------------------------- restoration

def boxcar(x, k):
    """Moving average over 2k+1 samples (cumsum, O(n))."""
    c = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); n = len(x)
    i = np.arange(n); lo = np.maximum(0, i - k); hi = np.minimum(n, i + k + 1)
    return ((c[hi] - c[lo]) / (hi - lo)).astype(np.float32)


def declip_local(x):
    """adeclip only around the clipped samples (±20 ms, 5 ms ramps): on clean audio adeclip still rewrites the waveform."""
    d = (ffilter(x * 0.5, "adeclip") * 2).astype(np.float32)
    m = (boxcar((np.abs(x) >= 0.985).astype(np.float32), int(0.02 * SR)) > 0).astype(np.float32)
    m = boxcar(m, int(0.005 * SR))
    return (x + m * (d - x)).astype(np.float32), float(m.mean())


# ---------------------------------------------------------------- gain curves

def smooth_gr(gr, hop, attack_ms, release_ms):
    """One-pole smoothing of a gain-reduction curve (dB ≥ 0): fast when the reduction grows, slow when it lets go."""
    a = 1 - np.exp(-hop / SR * 1000 / attack_ms); r = 1 - np.exp(-hop / SR * 1000 / release_ms)
    out = np.empty_like(gr); g = 0.0
    for i, v in enumerate(gr):
        g += (a if v > g else r) * (v - g); out[i] = g
    return out


def apply_db(x, gr_db, hop, sign=-1):
    """Multiply x by 10^(sign·gr/20), the frame curve interpolated to samples (frame centres)."""
    if not len(gr_db): return x
    t = np.arange(len(gr_db)) * hop + hop / 2
    return x * 10 ** (sign * np.interp(np.arange(len(x)), t, gr_db) / 20)


def compress(x, thr_db, ratio, knee_db=6.0, attack_ms=10.0, release_ms=120.0, hop=HOP):
    """Soft-knee RMS compressor on 10 ms frames → (y, stats)."""
    L = db(frame_power(x, hop)); o = L - thr_db; k = knee_db / 2; s = 1 - 1 / ratio
    gr = np.where(o <= -k, 0.0, np.where(o >= k, o * s, s * (o + k) ** 2 / (2 * knee_db)))
    gr = smooth_gr(gr, hop, attack_ms, release_ms)
    live = L > thr_db - 30
    return apply_db(x, gr, hop), {"overPct": round(100 * float(np.mean(gr[live] > 0.5)) if live.any() else 0, 1), "maxGrDb": round(float(gr.max()) if len(gr) else 0, 1)}


def deess(x, ref_db, freq=6500, q=1.0, over_db=-6.0, ratio=3.0, max_db=6.0, hop=120):
    """Dynamic bell cut on the sibilant band: y = x − k(t)·BP(x) (a unity-peak band-pass, so k is the depth of a peaking cut).
    Acts only where the band is louder than ref_db + over_db AND carries most of the energy (an «s», not a bright vowel)."""
    bp = ffilter(x, f"bandpass=f={freq}:width_type=q:w={q}")
    Lb = db(frame_power(bp, hop)); Lf = db(frame_power(x, hop))
    o = np.where(Lb - Lf > -6, Lb - (ref_db + over_db), 0.0)
    gr = smooth_gr(np.clip(o * (1 - 1 / ratio), 0, max_db), hop, 1.0, 40.0)
    k = 1 - 10 ** (-gr / 20)
    t = np.arange(len(k)) * hop + hop / 2
    y = x - np.interp(np.arange(len(x)), t, k) * bp
    live = Lf > ref_db - 25
    return y, {"activePct": round(100 * float(np.mean(gr[live] > 1)) if live.any() else 0, 1), "maxDb": round(float(gr.max()) if len(gr) else 0, 1)}


def peak_limit(x, ceil_db, lookahead=144, release_ms=80.0):
    """Look-ahead peak limiter (3 ms) with a smooth release: the gain reaches its value before the peak arrives, so nothing
    is clipped (render.sh's true-peak limiter then has almost nothing to do — the old crackle came from driving it)."""
    ceil = 10 ** (ceil_db / 20); B = 48; m = len(x) // B + 1
    pk = np.zeros(m * B); pk[: len(x)] = np.abs(x); pk = pk.reshape(m, B).max(1)
    req = np.minimum(1, ceil / np.maximum(pk, 1e-9)); ahead = req.copy()
    for k in range(1, lookahead // B + 1): ahead[:-k] = np.minimum(ahead[:-k], req[k:])
    out = np.empty(m); v = 1.0; up = 1 - np.exp(-B / SR * 1000 / release_ms)
    for i in range(m):
        v = ahead[i] if ahead[i] < v else v + up * (ahead[i] - v); out[i] = v
    y = np.clip(x * np.interp(np.arange(len(x)), np.arange(m) * B + B / 2, out), -ceil, ceil)
    return y, {"limitedPct": round(100 * float(np.mean(out < 0.98)), 2), "maxGrDb": round(float(-20 * np.log10(out.min())) if len(out) else 0, 1)}


# ---------------------------------------------------------------- tonal match

def tone_plan(x):
    """Bounded EQ moves that bring the voice's long-term spectrum toward LTASS + FINISH (shape only, normalised over
    250 Hz – 4 kHz), corrected by numbers.json eqAmount. Returns {"cuts": [...], "boosts": [...], "dev": {band: dB}}."""
    m = ltas(x)
    if not m: return {"cuts": [], "boosts": [], "dev": {}}
    tgt = {b: LTASS[b] + FINISH.get(b, 0.0) for b in BANDS}
    ref = [b for b in BANDS if 250 <= b <= 4000]
    off = np.mean([m[b] for b in ref]) - np.mean([tgt[b] for b in ref])
    dev = {b: round(m[b] - tgt[b] - off, 1) for b in BANDS}   # + = louder than the target shape
    amt = N["eqAmount"]
    move = lambda bands, lo, hi: round(float(np.clip(-amt * np.mean([dev[b] for b in bands]), lo, hi)), 1)
    mud = move([200, 250, 315, 400, 500], -N["eqMaxCut"], 1.0)
    box = move([630, 800, 1000, 1250], -N["eqMaxCut"], 1.0)
    pres = move([2000, 2500, 3150, 4000, 5000], -2.0, N["eqMaxBoost"])
    air = move([8000, 10000, 12500], -2.0, N["eqMaxAir"])
    cuts = [f"equalizer=f=315:t=q:w=1.0:g={mud}" for _ in [0] if abs(mud) >= 0.5] + [f"equalizer=f=900:t=q:w=1.4:g={box}" for _ in [0] if abs(box) >= 0.5]
    boosts = [f"equalizer=f=3500:t=q:w=0.8:g={pres}" for _ in [0] if abs(pres) >= 0.5] + [f"highshelf=f=9000:t=q:w=0.7:g={air}" for _ in [0] if abs(air) >= 0.5]
    return {"cuts": cuts, "boosts": boosts, "dev": dev, "moves": {"mud315": mud, "box900": box, "presence3k5": pres, "air9k": air}}


# ---------------------------------------------------------------- the chain

def voice_chain(x, level_db=None):
    """The ONE processing chain of the dialogue (dialogue.py runs it over the whole assembled stem):
    high-pass + phase rotator → corrective cuts (mud/box) → one soft-knee compressor → presence/air → de-esser → static gain to the stem
    loudness (numbers.json stemLufs) → look-ahead peak limiter. `level_db` = the speech level the leveling aimed at."""
    rep = {}
    lvl = N["voiceTargetDb"] if level_db is None else level_db
    x = ffilter(x, f"highpass=f={N['hpfHz']}:poles=2," + ",".join([f"allpass=f={N['phaseRotHz']}:width_type=q:w=0.7"] * 4))
    plan = tone_plan(x); rep["eq"] = plan.get("moves", {}); rep["ltasDev"] = plan["dev"]
    if plan["cuts"]: x = ffilter(x, ",".join(plan["cuts"]))
    x, rep["comp"] = compress(x, lvl + N["compOverDb"], N["compRatio"], N["compKneeDb"], N["compAttackMs"], N["compReleaseMs"], hop=int(N["compWindowMs"] / 1000 * SR))
    if plan["boosts"]: x = ffilter(x, ",".join(plan["boosts"]))
    sp = active_db(x)
    if sp is not None: x, rep["deess"] = deess(x, sp, over_db=N["deessOverDb"], max_db=N["deessMaxDb"])
    I, _, _ = ebur128(x)
    if I is not None and I > -70: x = x * 10 ** ((N["stemLufs"] - I) / 20)
    x, rep["limit"] = peak_limit(x, N["stemPeakDb"])
    I, lra, tp = ebur128(x); rep["out"] = {"lufs": I, "lra": lra, "truePeak": tp}
    return x, rep


# ---------------------------------------------------------------- room tone

def quiet_stretch(x, seconds_min=0.3):
    """The longest stretch of `x` (cleaned voice of one take) within 3 dB of its 15th-percentile level — the room under the
    voice. None when the take has no stretch of at least `seconds_min`."""
    if len(x) < SR: return None
    hop = 2400; f = db(frame_power(x, hop)); live = f > -90
    if live.sum() < 10: return None
    thr = np.percentile(f[live], 15) + 3; q = (f <= thr) & live
    best, cur, start, bs = 0, 0, 0, 0
    for i, v in enumerate(q):
        if v:
            if cur == 0: start = i
            cur += 1
            if cur > best: best, bs = cur, start
        else: cur = 0
    seg = x[(bs + 1) * hop: (bs + best - 1) * hop] if best > 4 else x[bs * hop: (bs + best) * hop]
    return np.asarray(seg, dtype=np.float64) if len(seg) >= seconds_min * SR else None


def loop_fill(seg, n):
    """n samples of `seg` looped with 40 ms equal-power crossfades (uncorrelated noise keeps its level)."""
    X = min(int(0.04 * SR), len(seg) // 3); out = np.zeros(n); pos = 0; first = True
    w_in = np.sin(np.linspace(0, np.pi / 2, X)); w_out = w_in[::-1]
    while pos < n:
        piece = seg.copy()
        if not first: piece[:X] *= w_in
        piece[-X:] *= w_out
        k = min(len(piece), n - pos); out[pos: pos + k] += piece[:k]
        pos += len(seg) - X; first = False
    return out


def bleep_tone(d, peak_db):
    """The soft two-tone «boop» of bleep.py (two decaying partials, low-passed), d seconds at peak_db dBFS."""
    t = np.arange(int(max(0.12, d) * SR)) / SR
    y = (0.55 * np.sin(2 * np.pi * 740 * t) + 0.35 * np.sin(2 * np.pi * 1110 * t)) * (0.35 + 0.65 * np.exp(-2.2 * t))
    y = ffilter(y, "lowpass=f=2400")
    fi, fo = int(0.012 * SR), int(0.06 * SR); y[:fi] *= np.linspace(0, 1, fi); y[-fo:] *= np.linspace(1, 0, fo)
    return y / max(np.abs(y).max(), EPS) * 10 ** (peak_db / 20)


def save_json(obj, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"; json.dump(obj, open(tmp, "w"), ensure_ascii=False, indent=1); os.replace(tmp, path)
