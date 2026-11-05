#!/usr/bin/env python3
"""Build the timeline speech track from the cut list and transcribe it with word timestamps.

Usage: work/venv/bin/python -I transcribe.py [--cutlist work/cutlist.json] [--public reel/public] [--lang ru] [--model mlx-community/whisper-large-v3-turbo] [--audio-only]
       work/venv/bin/python -I transcribe.py --sources <camera files…>   → work/new/c<id>.json (per-source word JSONs for cut_from_transcript.py / raw takes)
First run downloads the model (≈1.6 GB); large-v3-turbo runs ≈ 10× realtime on M-series.

The timeline track is assembled sample-accurately (16 kHz mono) from the proxies, so the audio matches what plays and word
times are already on the final timeline:
- every main segment sits at its tlStart (gaps stay silent), reads srcDur source seconds and is time-stretched (atempo) to its
  timeline length when CapCut changed the speed;
- muted segments (volume 0: CapCut slivers, plan "mute": true, the silent carrier) are silence — no captions, bleeps or
  fw() anchors come from them;
- CapCut voiceovers (cutlist "tracks", audio, in "voiceovers") are mixed in at their timeline position — from the levelled
  reel/public/audio/<name>.m4a when match_loudness.py made it, else the original file — so captions and anchors cover them;
- a silent cut list (silent_timeline.py, images-only reel) writes an empty transcript and stops.
Writes work/audio/timeline.wav + work/audio/timeline.json. --audio-only stops after the wav (needs no whisper).
"""
import argparse, json, os, subprocess, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import clip_id, load_offsets, proxy_file, speech_tracks, src_dur

SR = 16000

def atempo(speed):
    if abs(speed - 1) < 1e-3: return []
    f, s = [], speed
    while s > 2.0: f.append("atempo=2.0"); s /= 2.0
    while s < 0.5: f.append("atempo=0.5"); s /= 0.5
    return f + [f"atempo={s:.6f}"]

def read_pcm(path, start, dur_src, speed=1.0):
    """float32 mono 16 kHz samples of `dur_src` source seconds from `start`, stretched by `speed`."""
    import numpy as np
    af = ",".join(atempo(speed)) or "anull"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{max(0, start):.4f}", "-t", f"{dur_src:.4f}", "-i", path, "-vn", "-af", af, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

def build_timeline_audio(cl, public, offsets, out_wav):
    """Assemble the timeline speech track (see the module doc). Returns a list of what went where, for the log."""
    import numpy as np
    total = float(cl.get("durationSec") or 0) or cl["totalFrames"] / cl["fps"]
    buf = np.zeros(int(round(total * SR)) + SR, dtype=np.float32); log = []
    if not cl.get("silent"):
        for s in cl["main"]:
            if s.get("materialType", "video") != "video": continue
            n = int(round(float(s["dur"]) * SR)); at = int(round(float(s["tlStart"]) * SR)); vol = float(s.get("volume", 1))
            if vol < 0.01: log.append(f"  {s['tlStart']:7.2f}+{s['dur']:5.2f} silence (muted)"); continue
            cid = clip_id(s["path"]); sd = src_dur(s); speed = sd / float(s["dur"]) if float(s["dur"]) > 0 else 1.0
            x = read_pcm(proxy_file(public, cid), float(s["srcStart"]) - offsets.get(cid, 0), sd, speed)[:n] * vol
            buf[at:at + len(x)] += x[:max(0, len(buf) - at)]
            log.append(f"  {s['tlStart']:7.2f}+{s['dur']:5.2f} {cid} src {s['srcStart']:.2f}+{sd:.2f}" + (f" ×{speed:.2f}" if abs(speed - 1) > 1e-3 else ""))
        for s in speech_tracks(cl):
            stem = os.path.splitext(os.path.basename(s["path"]))[0]; lev = f"{public}/audio/{stem}.m4a"
            path = lev if os.path.exists(lev) else s["path"]; sd = src_dur(s); speed = sd / float(s["dur"]) if float(s["dur"]) > 0 else 1.0
            n = int(round(float(s["dur"]) * SR)); at = int(round(float(s["tlStart"]) * SR))
            x = read_pcm(path, float(s["srcStart"]), sd, speed)[:n] * float(s.get("volume", 1))
            buf[at:at + len(x)] += x[:max(0, len(buf) - at)]
            log.append(f"  {s['tlStart']:7.2f}+{s['dur']:5.2f} voiceover {os.path.basename(path)}")
    buf = buf[:int(round(total * SR))]
    pcm = (np.clip(buf, -1, 1) * 32767).astype("<i2").tobytes()
    os.makedirs(os.path.dirname(out_wav) or ".", exist_ok=True)
    with wave.open(out_wav, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
    return log

def whisper(wav, a):
    try: import mlx_whisper   # lazy: the assembly above needs only numpy + ffmpeg
    except ImportError: mlx_whisper = None
    if mlx_whisper: return mlx_whisper.transcribe(wav, path_or_hf_repo=a.model, language=a.lang, word_timestamps=True, verbose=False)
    # not Apple Silicon: openai-whisper (deps.py installs it there) gives the same result dict; the model by its plain name
    import whisper
    name = a.model.rsplit("/", 1)[-1].removeprefix("whisper-")   # mlx-community/whisper-large-v3-turbo → large-v3-turbo
    print(f"whisper: openai-whisper {name} (no MLX here — slower)", flush=True)
    return whisper.load_model(name).transcribe(wav, language=a.lang, word_timestamps=True, verbose=False)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cutlist", default="work/cutlist.json"); ap.add_argument("--public", default="reel/public")
    ap.add_argument("--lang", default="ru"); ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    ap.add_argument("--sources", nargs="*", help="transcribe these camera files (or isolated-voice WAVs) instead of the timeline → work/new/c<id>.json")
    ap.add_argument("--audio-only", action="store_true", help="build work/audio/timeline.wav and stop")
    a = ap.parse_args()
    if a.sources:
        os.makedirs("work/new", exist_ok=True)
        for src in a.sources:
            cid = clip_id(src); wav = f"work/new/{cid}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", src, "-vn", "-ac", "1", "-ar", str(SR), wav], check=True)
            r = whisper(wav, a); json.dump(r, open(f"work/new/{cid}.json", "w"), ensure_ascii=False, indent=1); os.remove(wav)
            print("=====", cid)
            for s in r["segments"]: print(f"[{s['start']:6.1f}-{s['end']:6.1f}] {s['text'].strip()}")
        print("TRANSCRIBE_DONE"); return
    cl = json.load(open(a.cutlist)); os.makedirs("work/audio", exist_ok=True)
    log = build_timeline_audio(cl, a.public, load_offsets(a.cutlist), "work/audio/timeline.wav")
    print("timeline audio:", *log, sep="\n")
    if cl.get("silent"):
        json.dump({"text": "", "segments": [], "language": a.lang}, open("work/audio/timeline.json", "w"))
        print("silent cut list: nothing to transcribe (captions, tl_words anchors and bleeps are skipped)"); print("TRANSCRIBE_DONE silent"); return
    if a.audio_only: print("TIMELINE_AUDIO_DONE work/audio/timeline.wav"); return
    r = whisper("work/audio/timeline.wav", a)
    json.dump(r, open("work/audio/timeline.json", "w"), ensure_ascii=False, indent=1)
    print("=====", "timeline"); print(r["text"])
    for s in r["segments"]: print(f"[{s['start']:6.1f}-{s['end']:6.1f}] {s['text'].strip()}")
    print("TRANSCRIBE_DONE")

if __name__ == "__main__":
    main()
