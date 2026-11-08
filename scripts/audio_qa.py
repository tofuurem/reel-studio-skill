#!/usr/bin/env python3
"""Measure the sound of a render (or any media / WAV) against what a finished spoken-word reel needs. Warnings only.

Usage: python -I audio_qa.py <file> [--project <dir>] [--json out.json]     (render.sh runs it on every final file)
Checks (numbers.json «Voice chain» / «Audio levels»):
  loudness     integrated LUFS vs targetLufs, loudness range in [lraMin, lraMax] (2.6 LU = over-compressed, the 2026-11-05 reel),
               true peak ≤ truePeakDb + 0.5 (AAC adds a little), sample overs
  silence      digital silence (frames under −80 dBFS) inside the speech span — a gated denoiser or a hole in the edit
  floor        the pause floor under the speech level (dB): < 35 dB apart = audible room/hiss
  spectrum     the speech's long-term 1/3-octave spectrum against the target shape (voicelib LTASS + FINISH): mud, presence, air
  tones        narrow peaks in the pause spectrum (insects, hum, a fan) — the cleanup cannot remove them without hurting the voice
  clicks       with --project: high-frequency bursts at the dialogue cuts listed in work/voice/dialogue.json
  codec        the audio codec and bitrate of the file
Prints AUDIO_QA_OK or AUDIO_QA_WARN <n>.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N
import voicelib as V

SR = V.SR


def file_loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0", "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    g = lambda k: (lambda m: float(m[-1]) if m else None)(re.findall(k + r":\s+(-?[\d.]+)", r.replace("-inf", "-120")))
    return g("I"), g("LRA"), g("Peak")


def codec(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name,bit_rate,sample_rate,channels", "-of", "json", path],
                       capture_output=True, text=True).stdout
    s = (json.loads(r or "{}").get("streams") or [{}])[0]
    return {"codec": s.get("codec_name"), "kbps": round(int(s["bit_rate"]) / 1000) if s.get("bit_rate", "N/A") != "N/A" else None, "rate": s.get("sample_rate"), "channels": s.get("channels")}


def tones(x, active):
    """Narrow peaks (≥ 10 dB over the ±1/3-octave median) in the spectrum of the quietest 10 % of 85 ms frames, 500 Hz–16 kHz
    (above that the encoder's low-pass edge looks like a peak)."""
    nfft = 4096; n = len(x) // nfft
    if n < 20: return []
    fr = x[: n * nfft].reshape(n, nfft); p = V.db((fr ** 2).mean(1))
    live = p > -90
    if live.sum() < 20: return []
    q = np.flatnonzero(live & (p <= np.percentile(p[live], 10)))[:400]
    spec = V.db((np.abs(np.fft.rfft(fr[q] * np.hanning(nfft), axis=1)) ** 2).mean(0)); fq = np.fft.rfftfreq(nfft, 1 / SR)
    out = []
    for i in range(1, len(fq) - 1):
        f = fq[i]
        if not 500 <= f <= 16000 or spec[i] < spec[i - 1] or spec[i] < spec[i + 1]: continue
        m = (fq > f / 2 ** (1 / 6)) & (fq < f * 2 ** (1 / 6))
        h = spec[i] - np.median(spec[m])
        if h >= 10: out.append((round(float(f)), round(float(h), 1)))
    out.sort(key=lambda t: -t[1]); keep = []
    for f, h in out:
        if all(abs(f - k) > f * 0.06 for k, _ in keep): keep.append((f, h))
    return keep[:4]


def clicks(x, cuts):
    """Cuts with a click: the ±2 ms high-pass energy stands ≥ 10 dB over BOTH sides (5–20 ms before and after) — a burst,
    not the edge of a consonant (a fade out of an «с» or the onset of a «т» rises on one side only)."""
    hp = np.diff(V.ffilter(x, "highpass=f=3000:poles=2"), prepend=0.0) ** 2; bad = []
    ms = SR // 1000
    for t in cuts:
        i = int(t * SR)
        if i - 20 * ms < 0 or i + 20 * ms > len(hp): continue
        core = hp[i - 2 * ms: i + 2 * ms].mean() + 1e-15
        side = max(hp[i - 20 * ms: i - 5 * ms].mean(), hp[i + 5 * ms: i + 20 * ms].mean()) + 1e-15
        r = 10 * np.log10(core / side)
        if r >= 10: bad.append((round(t, 2), round(float(r), 1)))
    return bad


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--project"); ap.add_argument("--json")
    a = ap.parse_args(); warn = []; rep = {}
    I, lra, tp = file_loudness(a.file); rep.update(lufs=I, lra=lra, truePeak=tp, **codec(a.file))
    x = V.read(a.file)
    act = V.active_db(x); f = V.db(V.frame_power(x, 2400)); live = np.flatnonzero(f > -60)
    span = f[live[0]: live[-1] + 1] if len(live) else f
    rep["silentPct"] = round(100 * float(np.mean(span < -80)), 1) if len(span) else 0
    rep["floorUnderSpeechDb"] = round(act - float(np.percentile(span[span > -80], 1)), 1)   # 1st percentile: a tight cut has few pauses, the 5th is quiet speech if act is not None and (span > -80).any() else None
    rep["overs"] = int(np.sum(np.abs(x) >= 0.999))
    if I is not None and abs(I - N["targetLufs"]) > N["lufsTolerance"] and a.project: warn.append(f"loudness {I} LUFS, target {N['targetLufs']}")
    if lra is not None and lra < N["lraMin"]: warn.append(f"loudness range {lra} LU < {N['lraMin']}: over-compressed (flat, lifts noise)")
    if lra is not None and lra > N["lraMax"]: warn.append(f"loudness range {lra} LU > {N['lraMax']}: quiet lines will get lost on a phone")
    if tp is not None and tp > N["truePeakDb"] + 0.5: warn.append(f"true peak {tp} dBTP > {N['truePeakDb'] + 0.5}")
    if rep["overs"]: warn.append(f"{rep['overs']} samples at full scale")
    if rep["silentPct"] > 2: warn.append(f"{rep['silentPct']}% digital silence inside the speech — a gate or a hole in the edit (room tone missing)")
    if rep["floorUnderSpeechDb"] is not None and rep["floorUnderSpeechDb"] < 35: warn.append(f"pause floor only {rep['floorUnderSpeechDb']} dB under the speech: hiss/room audible")
    lt = V.ltas(x)
    if lt:
        tgt = {b: V.LTASS[b] + V.FINISH.get(b, 0) for b in V.BANDS}; ref = [b for b in V.BANDS if 250 <= b <= 4000]
        off = np.mean([lt[b] for b in ref]) - np.mean([tgt[b] for b in ref])
        dev = {b: lt[b] - tgt[b] - off for b in V.BANDS}
        zone = lambda bs: round(float(np.mean([dev[b] for b in bs])), 1)
        rep["spectrum"] = {"mud200-500": zone([200, 250, 315, 400, 500]), "presence2-5k": zone([2000, 2500, 3150, 4000, 5000]), "air8-12k": zone([8000, 10000, 12500])}
        sp = rep["spectrum"]
        if sp["mud200-500"] > 3: warn.append(f"muddy: 200–500 Hz {sp['mud200-500']:+} dB over the target shape")
        if sp["presence2-5k"] < -4: warn.append(f"dull: 2–5 kHz {sp['presence2-5k']:+} dB under the target shape (intelligibility)")
        if sp["air8-12k"] < -6: warn.append(f"no air: 8–12 kHz {sp['air8-12k']:+} dB")
        if sp["presence2-5k"] > 4: warn.append(f"harsh: 2–5 kHz {sp['presence2-5k']:+} dB over the target shape")
    rep["tones"] = tones(x, act)
    if rep["tones"]: warn.append("tonal noise in the pauses at " + ", ".join(f"{f} Hz (+{h} dB)" for f, h in rep["tones"]) + " — insects/hum/fan at the location")
    if a.project:
        dj = os.path.join(a.project, "work/voice/dialogue.json")
        if os.path.exists(dj):
            d = json.load(open(dj)); rep["clicks"] = clicks(x, d.get("cuts", []))
            if rep["clicks"]: warn.append(f"{len(rep['clicks'])} dialogue cut(s) with a click: " + ", ".join(f"{t} s" for t, _ in rep["clicks"][:6]))
        elif os.path.exists(os.path.join(a.project, "work/cutlist.json")): warn.append("no dialogue stem (dialogue.py): the voice came from the proxies, cut hard and encoded more than once")
    if rep.get("codec") == "aac" and rep.get("kbps") and rep["kbps"] < 256: warn.append(f"AAC at {rep['kbps']} kbps (aacBitrate {N['aacBitrate']})")
    sp = rep.get("spectrum", {})
    print(f"sound: {I} LUFS, LRA {lra} LU, true peak {tp} dBTP, {rep.get('codec')} {rep.get('kbps')} kbps; pause floor {rep['floorUnderSpeechDb']} dB under speech, "
          f"digital silence {rep['silentPct']}%; spectrum vs target: mud {sp.get('mud200-500')}, presence {sp.get('presence2-5k')}, air {sp.get('air8-12k')} dB")
    for w in warn: print("  WARNING:", w)
    rep["warnings"] = warn
    if a.json: V.save_json(rep, a.json)
    print("AUDIO_QA_OK" if not warn else f"AUDIO_QA_WARN {len(warn)}")


if __name__ == "__main__":
    main()
