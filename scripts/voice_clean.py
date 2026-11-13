#!/usr/bin/env python3
"""Restore the voice of each speech source ONCE, as little as it needs → work/voice/out/<clipId>_DeepFilterNet3.wav (48 kHz
mono float, the source's full length; the file name is historical — every consumer reads it) + <clipId>.voice.json.

Usage: work/dfvenv/bin/python -I voice_clean.py <project> [--lav <dir|file.wav>]… [--atten auto|N] [--force] <sources…>
       (voice_isolate.sh <project> [--atten-lim-db N] <sources…> calls this)
Per source:
1. Input: the DJI transmitter's own 32-bit float recording when --lav finds one that covers the clip (the camera's track is
   the same mic after a radio link, the receiver's processing and an AAC encode) — found and synced by cross-correlation,
   clock drift between camera and transmitter corrected by resampling; uncovered parts keep the camera track. Else the
   camera's audio track (one lav on both channels → a mono downmix; two different lavs → dualmic.py instead).
2. Measure: speech level, pause floor, SNR, clipped samples (voicelib.analyse).
3. adeclip ONLY when it clipped (numbers.json declipMinSamples) — on clean audio it still rewrote the samples.
4. DeepFilterNet limited to noiseTargetDb − SNR dB (dfnMinAtten…dfnMaxAtten), skipped when the source is already that quiet:
   the residual room stays ≈ 48 dB under the voice instead of digital silence in every pause.
5. Report what the cleanup did to the voice (1/3-octave transfer on the speech frames): a band moved > 2 dB is a WARNING.
No EQ, no dynamics, no level here — dialogue.py does that once over the whole assembled dialogue.
Re-runs skip a source whose inputs and settings did not change. Prints VOICE_DONE.
"""
import argparse, glob, hashlib, json, os, subprocess, sys, tempfile
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, add_guard_args, clip_id, guard_reexec
import voicelib as V

SR = V.SR
VERSION = 4   # bump when the processing changes: every source is redone


def lav_files(specs):
    out = []
    for s in specs or []:
        if os.path.isdir(s): out += sorted(glob.glob(os.path.join(s, "**", "*.[wW][aA][vV]"), recursive=True))
        elif os.path.exists(s): out.append(s)
        else: print("WARNING: --lav", s, "not found")
    return [p for p in out if not os.path.basename(p).startswith("._")]


def envelope(x, rate=400):
    """|x| averaged to `rate` Hz, zero mean, unit variance — for coarse alignment of two recordings of one mic."""
    hop = SR // rate; n = len(x) // hop
    e = np.abs(x[: n * hop]).reshape(n, hop).mean(1)
    e = np.log(e + 1e-5); e -= e.mean(); s = e.std()
    return e / s if s > 0 else e


def xcorr(a, b):
    """Full cross-correlation of b against a (FFT); lag k means b[i] ≈ a[i - k]... returned as (lags, values)."""
    n = len(a) + len(b) - 1; m = 1 << (n - 1).bit_length()
    c = np.fft.irfft(np.fft.rfft(a, m) * np.conj(np.fft.rfft(b, m)), m)
    c = np.concatenate([c[-(len(b) - 1):], c[: len(a)]]) if len(b) > 1 else c[: len(a)]
    return np.arange(-(len(b) - 1), len(a)), c


def lav_sync(cam, lav_path):
    """(offset seconds at camera t=0, drift, score) so that lav(t_lav) = cam(t) at t_lav = offset + t·(1 + drift); None if
    the recordings do not match. Coarse: 400 Hz log-envelopes over the whole files; fine: 48 kHz waveforms at three points."""
    info = sf.info(lav_path)
    if info.samplerate < 16000: return None
    lav = V.read(lav_path)
    ec, el = envelope(cam), envelope(lav)
    if len(ec) < 400 * 5 or len(el) < 400 * 5: return None
    lags, c = xcorr(el, ec)               # el[i + k] ≈ ec[i]
    k = int(lags[np.argmax(c)]); score = float(c.max() / min(len(ec), len(el)))
    if score < 0.35: return {"score": round(score, 2)}
    off0 = k / 400.0; pts = []
    dur = len(cam) / SR
    for frac in (0.08, 0.5, 0.92):
        t = frac * dur; w = 3.0
        a0 = int(t * SR); a = cam[a0: a0 + int(w * SR)]
        b0 = int((t + off0 - 0.05) * SR); b = lav[max(0, b0): max(0, b0) + int((w + 0.1) * SR)]
        if len(a) < SR or len(b) < len(a) or np.abs(a).max() < 1e-4: continue
        lg, cc = xcorr(b, a); ok = (lg >= 0) & (lg <= len(b) - len(a)); i = int(np.argmax(np.where(ok, cc, -np.inf)))
        pts.append((t, (max(0, b0) + lg[i]) / SR - t))
    if len(pts) >= 2:
        ts, os_ = np.array(pts).T; drift, off = np.polyfit(ts, os_, 1)
    elif pts: off, drift = pts[0][1] - 0.0, 0.0
    else: off, drift = off0, 0.0
    return {"offset": float(off), "drift": float(drift), "score": round(score, 2), "points": [[round(t, 1), round(o, 5)] for t, o in pts], "lav": lav}


def aligned_lav(cam, m):
    """The lav recording resampled onto the camera's timeline (same length as cam; uncovered samples = camera, level-matched)."""
    lav, off, drift = m["lav"], m["offset"], m["drift"]
    n = len(cam); need = int(np.ceil(n * (1 + drift))) + SR
    s0 = int(round(off * SR)); pad_front = max(0, -s0)
    seg = np.concatenate([np.zeros(pad_front), lav[max(0, s0): max(0, s0) + need - pad_front]])
    if abs(drift) * n > 0.25:   # more than a quarter sample over the clip: resample (soxr when ffmpeg has it)
        rate = SR * (1 + drift)
        soxr = "libsoxr" in subprocess.run(["ffmpeg", "-hide_banner", "-buildconf"], capture_output=True, text=True).stdout
        seg = V.ffilter(seg, f"asetrate={rate:.6f},aresample={SR}" + (":resampler=soxr:precision=28" if soxr else ":filter_size=64:phase_shift=10"))
    seg = V.fit(seg, n)
    covered = np.zeros(n, bool); a = pad_front; b = min(n, int((len(lav) - s0) / (1 + drift)))
    covered[a:max(a, b)] = True
    if covered.all(): return seg, 1.0
    both = covered & (np.abs(cam) > 1e-4)
    g = float(np.sqrt((seg[both] ** 2).mean() / max((cam[both] ** 2).mean(), 1e-12))) if both.sum() > SR else 1.0
    out = np.where(covered, seg, cam * g)
    return out, float(covered.mean())


def dfn(df, x, att, tmp):
    """DeepFilterNet limited to `att` dB. Its output is 16-bit: the input is scaled to −1 dBFS peak first and back after."""
    pk = max(float(np.abs(x).max()), 1e-6); k = 10 ** (-1 / 20) / pk
    f = os.path.join(tmp, "v.wav"); sf.write(f, (x * k).astype(np.float32), SR, subtype="FLOAT")
    V.df_run(df, f, tmp, att)   # long files in 2-minute pieces: DeepFilterNet needs ≈ 1 GB of RAM per minute
    return (V.fit(sf.read(os.path.join(tmp, "v_DeepFilterNet3.wav"), dtype="float32")[0], len(x)) / k).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("sources", nargs="+")
    ap.add_argument("--lav", action="append", default=[], help="DJI transmitter recordings: a folder or a WAV file (repeat the flag for more): the mic's own 32-bit float file")
    ap.add_argument("--atten", default="auto", help="DeepFilterNet limit in dB, or auto (noiseTargetDb − SNR); 0 = no DeepFilterNet")
    ap.add_argument("--force", action="store_true"); add_guard_args(ap, 8.0)
    a = ap.parse_args(); guard_reexec(a); P = os.path.abspath(a.project)
    ids = [clip_id(s) for s in a.sources]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup: sys.exit(f"clip id collision {sorted(dup)} (two cameras with the same DJI counter?) — see clipid.py")
    outdir = os.path.join(P, "work/voice/out"); os.makedirs(outdir, exist_ok=True); os.makedirs(os.path.join(P, "work/tmp"), exist_ok=True)
    df = os.path.join(P, "work/dfvenv/bin/deepFilter")
    lavs = lav_files(a.lav)
    if a.lav and not lavs: sys.exit("--lav: no WAV files found")
    warns = []
    for src in a.sources:
        cid = clip_id(src); out = os.path.join(outdir, f"{cid}_DeepFilterNet3.wav"); rp = os.path.join(outdir, f"{cid}.voice.json")
        st = os.stat(src)
        sig = hashlib.md5(json.dumps([VERSION, os.path.realpath(src), st.st_size, int(st.st_mtime), a.atten, [os.path.basename(x) for x in lavs],
                                      {k: N[k] for k in ("declipMinSamples", "noiseTargetDb", "dfnMinAtten", "dfnMaxAtten")}]).encode()).hexdigest()[:12]
        old = json.load(open(rp)) if os.path.exists(rp) else {}
        if not a.force and os.path.exists(out) and old.get("sig") == sig: print("skip", cid, "(done)"); continue
        x = V.read(src).astype(np.float32); rep = {"sig": sig, "source": os.path.realpath(src), "input": "camera"}
        if not len(x): warns.append(f"{cid}: no audio track"); continue
        for lp in lavs:
            m = lav_sync(x, lp)
            if m and "offset" in m:
                x, cov = aligned_lav(x, m); x = x.astype(np.float32)
                rep.update(input="lav", lav=lp, lavOffset=round(m["offset"], 4), lavDriftPpm=round(m["drift"] * 1e6, 1), lavScore=m["score"], lavPoints=m["points"], lavCoverage=round(cov, 3))
                print(f"{cid}: transmitter recording {os.path.basename(lp)} offset {m['offset']:.3f} s, drift {m['drift'] * 1e6:+.1f} ppm, covers {cov:.0%}")
                if cov < 0.98: warns.append(f"{cid}: the transmitter file covers {cov:.0%} — the rest is the camera track")
                break
        if lavs and rep["input"] == "camera": warns.append(f"{cid}: no transmitter recording matches — camera track used")
        ana = V.analyse(x); rep["before"] = ana; raw = x
        if ana["clipSamples"] >= N["declipMinSamples"]: x, share = V.declip_local(x); rep["declip"] = round(share, 5)
        else: rep["declip"] = False
        snr = ana["snrDb"] or 0.0
        if a.atten == "auto": att = 0 if snr >= N["noiseTargetDb"] else int(round(min(N["dfnMaxAtten"], max(N["dfnMinAtten"], N["noiseTargetDb"] - snr))))
        else: att = int(float(a.atten))
        rep["attenDb"] = att
        print(f"{cid}: speech {ana['speechDb']} dB, floor {ana['floorDb']} dB, SNR {snr:.0f} dB, clipped samples {ana['clipSamples']}"
              f" → {'adeclip, ' if rep['declip'] else ''}{f'DeepFilterNet limited to {att} dB' if att else 'no DeepFilterNet (quiet enough)'}", flush=True)
        if att > 0:
            if not os.path.exists(df): sys.exit(f"DeepFilterNet missing: run setup_env.sh {P} first")
            with tempfile.TemporaryDirectory(dir=os.path.join(P, "work/tmp")) as tmp: y = dfn(df, x, att, tmp)
        else: y = x
        rep["after"] = V.analyse(y); tr = V.transfer(raw, y); rep["transfer"] = tr
        holes = {b: d for b, d in tr.items() if 150 <= b <= 12500 and abs(d) > 2.0}
        if holes: warns.append(f"{cid}: cleanup changed the voice at {', '.join(f'{b} Hz {d:+.1f} dB' for b, d in holes.items())} — listen; --atten lower if it sounds hollow")
        V.write(out, y); V.save_json(rep, rp)
        print(f"done {cid}: pause floor {ana['floorDb']} → {rep['after']['floorDb']} dB, silent frames {rep['after']['silentFrac']:.0%}", flush=True)
        del x, y, raw
    for w in warns: print("WARNING:", w)
    print("VOICE_DONE", " ".join(sorted(os.path.basename(f) for f in glob.glob(os.path.join(outdir, "*_DeepFilterNet3.wav")))))


if __name__ == "__main__":
    main()
