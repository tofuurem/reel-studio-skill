#!/usr/bin/env python3
"""Video A/B: short versions of the same moment in ONE mp4 the user watches on the phone — a card «1» (one beep), version 1,
a card «2» (two beeps), version 2 … with the version's number in the corner and the sound matched in loudness — or all
versions side by side (--grid) for a look decision (LUT, night lift, crop, caption style) where the order would mislead.

Usage: work/venv/bin/python -I ab_video.py <out.mp4> <file>[@start:dur] <file>[@start:dur] … [--names "как сейчас,теплее"]
           [--vf K "<ffmpeg video filters>"] [--af K "<ffmpeg audio filters>"]   (on version K, 1-based; repeatable;
           --vf runs after the downscale — a LUT on 4K costs 4× the time and looks the same at phone size)
           [--grid [--audio K]] [--lufs -16] [--max-h 1920] [--card 1.4]
Versions come from render_part.sh (a few seconds of each variant of the reel) or straight from sources: the same clip
twice with a different --vf is an A/B of a LUT / crop / speed without rendering anything
(e.g. --vf 2 "lut3d=file=/path/look.cube"). Needs Pillow (python3 or work/venv) and ffmpeg (no drawtext needed).
Prints the legend and AB_VIDEO_DONE. Craft: references/craft/ab.md; audio-only decisions: ab.py / eq_test.py (smaller).
"""
import argparse, json, os, re, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FONTS_DIR  # noqa: E402

SR = 48000


def beeps(k, freq=740.0):   # the same signal as ab.py: k × 160 ms at −20 dBFS, 120 ms apart
    n = int(0.16 * SR); one = 0.1 * np.sin(2 * np.pi * freq * np.arange(n) / SR) * np.hanning(n)
    return np.concatenate([np.concatenate([one, np.zeros(int(0.12 * SR))]) for _ in range(k)])


def wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def probe(path):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,width,height,r_frame_rate:stream_side_data=rotation:format=duration", "-of", "json", path], capture_output=True, text=True, check=True).stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    if v is None: sys.exit(f"{path}: no video stream")
    w, h = int(v["width"]), int(v["height"])
    rot = next((abs(int(sd.get("rotation", 0))) for sd in v.get("side_data_list", []) if "rotation" in sd), 0)
    if rot in (90, 270): w, h = h, w
    num, den = (int(t) for t in v["r_frame_rate"].split("/"))
    return {"w": w, "h": h, "fps": num / max(den, 1), "audio": any(s["codec_type"] == "audio" for s in j["streams"]), "dur": float(j["format"].get("duration", 0))}


def font(px):
    for f in (os.path.join(FONTS_DIR, "Unbounded.ttf"), "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(f): return ImageFont.truetype(f, px)
    return ImageFont.load_default()


def card(path, W, H, k, name):
    im = Image.new("RGB", (W, H), (17, 17, 17)); d = ImageDraw.Draw(im)
    f1 = font(H // 4); t = str(k); bb = d.textbbox((0, 0), t, font=f1)
    d.text(((W - bb[2] + bb[0]) / 2 - bb[0], H * 0.42 - (bb[3] - bb[1]) / 2 - bb[1]), t, font=f1, fill=(240, 240, 240))
    if name:
        f2 = font(max(18, H // 28)); bb = d.textbbox((0, 0), name, font=f2)
        d.text(((W - bb[2] + bb[0]) / 2 - bb[0], H * 0.62), name, font=f2, fill=(170, 170, 170))
    im.save(path)


def badge(path, H, k):
    s = max(40, H // 14); im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 4, fill=(0, 0, 0, 150))
    f = font(int(s * 0.6)); bb = d.textbbox((0, 0), str(k), font=f)
    d.text(((s - bb[2] + bb[0]) / 2 - bb[0], (s - bb[3] + bb[1]) / 2 - bb[1]), str(k), font=f, fill=(255, 255, 255, 235)); im.save(path)


def lufs(path, ss, t, af):
    """Integrated loudness of [ss, ss+t) after the version's audio filters (None = silent / no audio)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *ss, *t, "-i", path, "-vn", "-af", (af + "," if af else "") + "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m and float(m[-1]) > -70 else None


def spec(s):
    path, _, rng = s.partition("@")
    if not os.path.exists(path): sys.exit(f"no file {path}")
    st, du = (float(v) for v in rng.split(":")) if rng else (None, None)
    return path, (["-ss", f"{st:.3f}"] if st is not None else []), (["-t", f"{du:.3f}"] if du is not None else [])


def run(cmd):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *cmd], capture_output=True, text=True)
    if r.returncode: sys.exit("ffmpeg failed:\n" + r.stderr[-2000:])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("clips", nargs="+")
    ap.add_argument("--names", default=""); ap.add_argument("--vf", nargs=2, action="append", default=[], metavar=("K", "FILTERS"))
    ap.add_argument("--af", nargs=2, action="append", default=[], metavar=("K", "FILTERS")); ap.add_argument("--grid", action="store_true")
    ap.add_argument("--audio", type=int, default=1); ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--max-h", type=int, default=1920); ap.add_argument("--card", type=float, default=1.4)
    a = ap.parse_args()
    names = [s.strip() for s in a.names.split(",")] if a.names else []
    vf = {int(k): f for k, f in a.vf}; af = {int(k): f for k, f in a.af}
    specs = [spec(c) for c in a.clips]; p0 = probe(specs[0][0]); fps = round(p0["fps"], 3) or 30
    out = os.path.abspath(a.out); os.makedirs(os.path.dirname(out), exist_ok=True)
    enc = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-ac", "2"]
    with tempfile.TemporaryDirectory() as tmp:
        if a.grid:
            n = len(specs); h = min(a.max_h, p0["h"]) // 2 * 2
            while n * (round(h * p0["w"] / p0["h"]) // 2 * 2) > 3840 and h > 360: h -= 16   # stay within 4K width
            w = round(h * p0["w"] / p0["h"]) // 2 * 2
            ins, fl = [], []
            for k, (path, ss, t) in enumerate(specs, 1):
                badge(os.path.join(tmp, f"b{k}.png"), h, k); ins += [*ss, *t, "-i", path]
            for k in range(1, n + 1): ins += ["-i", os.path.join(tmp, f"b{k}.png")]
            for k in range(1, n + 1):
                pre = (vf[k] + ",") if k in vf else ""
                fl.append(f"[{k - 1}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,{pre}pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1[s{k}];"
                          f"[s{k}][{n + k - 1}:v]overlay=24:24[v{k}]")
            fl.append("".join(f"[v{k}]" for k in range(1, n + 1)) + (f"hstack=inputs={n}:shortest=1[v]" if n > 1 else "copy[v]"))
            K = min(max(1, a.audio), n); path, ss, t = specs[K - 1]; amap = []
            if probe(path)["audio"]:
                I = lufs(path, ss, t, af.get(K)); g = 0.0 if I is None else a.lufs - I
                fl.append(f"[{K - 1}:a]{(af[K] + ',') if K in af else ''}volume={g:.2f}dB[a]"); amap = ["-map", "[a]"]
            run([*ins, "-filter_complex", ";".join(fl), "-map", "[v]", *amap, "-shortest", *enc, "-movflags", "+faststart", out])
            print(f"grid: {n} versions side by side, {n * w}×{h}; sound of version {K}")
        else:
            W = min(p0["w"], round(a.max_h * p0["w"] / p0["h"])) // 2 * 2; H = min(p0["h"], a.max_h) // 2 * 2
            parts = []
            for k, (path, ss, t) in enumerate(specs, 1):
                c, b, bw = (os.path.join(tmp, f"{x}{k}.{e}") for x, e in (("card", "png"), ("badge", "png"), ("beep", "wav")))
                card(c, W, H, k, names[k - 1] if k <= len(names) else ""); badge(b, H, k)
                bp = beeps(k); dur = max(a.card, len(bp) / SR + 0.5); wav(bw, np.concatenate([np.zeros(int(0.15 * SR)), bp]))
                run(["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", c, "-i", bw, "-filter_complex",
                     f"[0:v]format=yuv420p[v];[1:a]apad=whole_dur={dur:.3f}[a]", "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *enc, os.path.join(tmp, f"p{k}a.mp4")])
                pr = probe(path); pre = (vf[k] + ",") if k in vf else ""
                vchain = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,{pre}pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1[s];[s][1:v]overlay=24:24[v]"
                if pr["audio"]:
                    I = lufs(path, ss, t, af.get(k)); g = 0.0 if I is None else a.lufs - I
                    run([*ss, *t, "-i", path, "-i", b, "-filter_complex", vchain + f";[0:a]{(af[k] + ',') if k in af else ''}volume={g:.2f}dB[a]",
                         "-map", "[v]", "-map", "[a]", *enc, os.path.join(tmp, f"p{k}b.mp4")])
                else:
                    run([*ss, *t, "-i", path, "-i", b, "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-filter_complex", vchain,
                         "-map", "[v]", "-map", "2:a", "-shortest", *enc, os.path.join(tmp, f"p{k}b.mp4")])
                parts += [os.path.join(tmp, f"p{k}a.mp4"), os.path.join(tmp, f"p{k}b.mp4")]
            lst = os.path.join(tmp, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
            run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
    for k in range(1, len(specs) + 1):
        extra = " ".join(x for x in ((f"vf: {vf[k]}" if k in vf else ""), (f"af: {af[k]}" if k in af else "")) if x)
        print(f"  {k} = {names[k - 1] if k <= len(names) else a.clips[k - 1]}{'  (' + extra + ')' if extra else ''}")
    print(f"AB_VIDEO_DONE {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
