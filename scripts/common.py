#!/usr/bin/env python3
"""Shared helpers for the reel-studio scripts — one copy of everything that had drifted between scripts (audit 2026-10-22):
numbers, cache paths, LUT lookup, a rotation-aware probe, the voice-activity run, atomic ffmpeg writes, cut-list ranges.

Import:  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from common import N, lut_for, probe, …
CLI:     common.py N <key>            → prints a number from references/craft/numbers.json (shell scripts use it)
         common.py lut <file> [--lut X] [--lut-map map.json]   → which LUT a clip gets and why
         common.py probe <file>       → JSON of probe()
"""
import fnmatch, glob, json, math, os, re, shutil, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from clipid import clip_id, check_unique, ascii_stem, nfc  # noqa: E402,F401  (re-exported)

_NUM = json.load(open(os.path.join(SKILL, "references/craft/numbers.json")))
N = {r["key"]: r["value"] for s in _NUM["sections"] for r in s["rows"]}

CACHE = os.path.expanduser("~/.cache/reel-studio")
LUT_DIR = os.path.join(CACHE, "luts"); FONTS_DIR = os.path.join(CACHE, "fonts")
FONTS = ("Unbounded.ttf", "Montserrat.ttf", "JetBrainsMono.ttf")

# platform: videotoolbox decode and Apple Vision exist on macOS only (deps.py lists what else differs per OS)
HWACCEL = ["-hwaccel", "videotoolbox"] if sys.platform == "darwin" else []

def need_vision(script):
    """Vision (face / people / person masks) is an Apple framework: stop with a clear message elsewhere."""
    if sys.platform != "darwin":
        sys.exit(f"{script} needs Apple Vision (macOS only). On this platform: 16:9 canvas or crop keys by hand; see deps.py")

SCREEN_NAME = re.compile(r"запись\s+экрана|screen\s*recording|^rec_\d", re.I)

def is_camera(path):
    """Camera footage = any video that is not a screen recording or an export put into assets/video (DJI, phone, GoPro, Sony
    alike). A landscape camera clip is cropped to a vertical canvas by the people zones; whether it needs a LUT is lut_for's question."""
    n = nfc(os.path.basename(path)); low = nfc(os.path.abspath(path)).replace(os.sep, "/")
    if "/assets/screenrec/" in low or "/assets/video/" in low: return False
    return not SCREEN_NAME.search(os.path.splitext(n)[0])

def looks_log(path):
    """DJI clips are often shot in D-Log: a hint for the "no LUT" warning, not a rule (Normal-mode DJI footage needs none)."""
    return nfc(os.path.basename(os.path.realpath(path))).upper().startswith("DJI_")

def load_lut_map(path):
    """--lut-map: a JSON file or inline JSON {"DJI_*_0004*": "/abs/Action4.cube", "*rec_*": "none"} — glob on the file name (or the full path)."""
    if not path: return {}
    return json.loads(path) if path.lstrip().startswith("{") else json.load(open(path))

def lut_for(path, lut=None, lut_map=None, info=None):
    """(cube path or None, reason). Order: --lut-map glob → non-camera files get none → explicit --lut / draft LUT →
    none: Rec.709 is assumed — log footage (D-Log, S-Log, V-Log …) needs --lut or --lut-map (ask the user when the inventory
    shows flat grey footage)."""
    b = nfc(os.path.basename(path))
    for pat, cube in (lut_map or {}).items():
        if fnmatch.fnmatch(b, pat) or fnmatch.fnmatch(nfc(path), pat) or fnmatch.fnmatch(nfc(os.path.basename(os.path.realpath(path))), pat):   # alias symlinks match as their source
            if str(cube).lower() in ("none", "", "null"): return None, f"lut-map {pat}: none"
            return os.path.expanduser(cube), f"lut-map {pat}"
    if not is_camera(path): return None, "not a camera clip (Rec.709)"
    if lut: return os.path.expanduser(lut), "--lut / draft"
    info = info or probe(path)
    return None, "no LUT (Rec.709 assumed" + (f", camera tag '{info.get('camera')}'" if info.get("camera") else "") + ")"

def _fps(r):
    try:
        a, b = (r or "0/1").split("/"); return float(a) / float(b) if float(b) else 0.0
    except ValueError: return 0.0

def probe(path):
    """{dur, w, h (display, rotation applied), rot, fps (avg), r_fps, vfr, has_video, has_audio, codec, camera, nb_frames}"""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames:stream_tags:stream_side_data",
                        "-of", "json", path], capture_output=True, text=True)
    try: j = json.loads(r.stdout or "{}")
    except json.JSONDecodeError: j = {}
    st = j.get("streams", []); fmt = j.get("format", {})
    v = next((s for s in st if s.get("codec_type") == "video" and (s.get("width") or 0) > 0), {})
    rot = 0
    try: rot = int(float((v.get("tags") or {}).get("rotate", 0)))
    except ValueError: pass
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            try: rot = int(float(sd["rotation"]))
            except (TypeError, ValueError): pass
    w, h = v.get("width") or 0, v.get("height") or 0
    if abs(rot) % 180 == 90: w, h = h, w
    avg, rf = _fps(v.get("avg_frame_rate")), _fps(v.get("r_frame_rate"))
    tags = {**{k.lower(): str(x) for k, x in (fmt.get("tags") or {}).items()}, **{k.lower(): str(x) for k, x in (v.get("tags") or {}).items()}}
    cam = next((tags[k] for k in ("com.apple.quicktime.model", "model", "com.android.model", "encoder", "make", "com.apple.quicktime.make") if tags.get(k) and not tags[k].lower().startswith(("lavf", "lavc", "x264", "h.264", "avc coding"))), "")
    if not cam and tags.get("handler_name", "").lower().startswith("dji"): cam = tags["handler_name"]
    try: dur = float(fmt.get("duration") or 0)
    except ValueError: dur = 0.0
    return {"dur": dur, "w": w, "h": h, "rot": rot, "fps": round(avg, 3), "r_fps": round(rf, 3),
            "vfr": bool(avg and rf and abs(rf - avg) / rf > 0.02), "has_video": bool(v), "has_audio": any(s.get("codec_type") == "audio" for s in st),
            "codec": v.get("codec_name"), "camera": cam, "nb_frames": int(v["nb_frames"]) if str(v.get("nb_frames", "")).isdigit() else None}

def count_frames(path):
    """Video packets in the file (fast; = frames for the h264 the renders and proxies use). 0 for a missing/broken file."""
    if not os.path.exists(path) or os.path.getsize(path) == 0: return 0
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path], capture_output=True, text=True)
    m = re.search(r"\d+", r.stdout or ""); return int(m.group()) if m else 0

def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except ValueError: return 0.0

def speech_run(wav, t, win=2.0, thr=-38, min_pause=0.3):
    """[start, end] of the continuous voice activity around time t (10 ms RMS envelope, usually on the isolated voice).
    Falls back to t ± 0.2 s when there is no audio there (t past the end of the file, < 20 ms decoded)."""
    s = max(0, t - win)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", str(s), "-t", str(2 * win), "-i", wav, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    n = len(raw) // 2
    if n < 320 or t > s + n / 16000: return t - 0.2, t + 0.2
    x = struct.unpack(f"<{n}h", raw[:2 * n]); w = 160
    env = [20 * math.log10(math.sqrt(sum(v * v for v in x[i:i + w]) / w) / 32768 + 1e-9) for i in range(0, n - w, w)]
    if not env: return t - 0.2, t + 0.2
    sm = [max(env[max(0, i - 1):i + 2]) for i in range(len(env))]
    quiet = [v < thr for v in sm]; k = min(len(sm) - 1, int((t - s) / 0.01)); mp = int(min_pause / 0.01)
    i = k
    while i > 0 and not all(quiet[max(0, i - mp):i]): i -= 1
    j = k
    while j < len(sm) and not all(quiet[j:j + mp]): j += 1
    return s + i * 0.01, s + j * 0.01

# ---------------------------------------------------------------- atomic ffmpeg writes

def tmp_for(out, tmp_dir=None):
    """A temp path for `out` outside reel/public (the Remotion bundler copies public/ and dies on a vanishing half file)."""
    d = tmp_dir or os.path.join("work", "tmp")
    if not os.path.isdir(os.path.dirname(os.path.abspath(d)) or "."): d = os.path.dirname(os.path.abspath(out))
    os.makedirs(d, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(out)); parent = os.path.basename(os.path.dirname(os.path.abspath(out)))
    return os.path.join(d, f".{parent}_{stem}.{os.getpid()}.tmp{ext}")   # parent: footage/ and footage2k/ outputs of one run differ

def ffmpeg(args, quiet=True):
    """ffmpeg with -nostdin -y (a leftover output never turns into a silent "Not overwriting" + exit 0)."""
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", *(["-loglevel", "error"] if quiet else []), *args]
    return subprocess.run(cmd).returncode

def commit(tmp, out, expect=None, tol=0.6):
    """Verify tmp (ffprobe duration > 0 and ≈ expect when given), then move it over out. Returns (ok, message)."""
    d = duration(tmp) if os.path.exists(tmp) else 0.0
    if d <= 0: _rm(tmp); return False, f"{os.path.basename(out)}: encode produced no media"
    if expect is not None and abs(d - expect) > tol: _rm(tmp); return False, f"{os.path.basename(out)}: {d:.2f} s instead of {expect:.2f} s"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    try: os.replace(tmp, out)
    except OSError: shutil.move(tmp, out)
    return True, f"{os.path.basename(out)} {d:.2f} s"

def run_ffmpeg_atomic(args, out, expect=None, tol=0.6, tmp_dir=None):
    """ffmpeg <args> <tmp> → verify → os.replace(tmp, out). `args` holds inputs, filters and output options (not the output path)."""
    tmp = tmp_for(out, tmp_dir)
    rc = ffmpeg([*args, tmp])
    if rc != 0: _rm(tmp); return False, f"{os.path.basename(out)}: ffmpeg exit {rc}"
    return commit(tmp, out, expect, tol)

def _rm(p):
    try: os.remove(p)
    except OSError: pass

def atomic_json(obj, path):
    """Write JSON via a temp file; an unchanged file is left alone, so its mtime keeps meaning "this changed" (doctor.py
    compares mtimes: rewriting proxy_offsets.json on every make_proxies run made Timeline.tsx look stale)."""
    text = json.dumps(obj, ensure_ascii=False, indent=1)
    if os.path.exists(path):
        try:
            if open(path, encoding="utf-8").read() == text: return
        except OSError: pass
    tmp = path + ".tmp"; open(tmp, "w", encoding="utf-8").write(text); os.replace(tmp, path)

# ---------------------------------------------------------------- cut list helpers

def src_dur(seg):
    """Source seconds a segment consumes: CapCut gives srcDur (speed already in it); older lists only dur × speed."""
    return float(seg.get("srcDur") or 0) or float(seg["dur"]) * float(seg.get("speed", 1) or 1)

def speech_tracks(cl):
    """Audio-track segments that are voiceovers (CapCut voice recordings) with sound."""
    vo = set(cl.get("voiceovers", []))
    return [s for t in cl.get("tracks", []) if t.get("type") == "audio" for s in t.get("segments", []) if s.get("path") in vo and s.get("volume", 1) >= 0.01]

def _subtract(ranges, cuts):
    out = []
    for a, b in ranges:
        parts = [(a, b)]
        for c, d in cuts:
            nxt = []
            for x, y in parts:
                if d <= x or c >= y: nxt.append((x, y)); continue
                if c > x: nxt.append((x, c))
                if d < y: nxt.append((d, y))
            parts = nxt
        out += [(x, y) for x, y in parts if y - x > 0.05]
    return out

def silent_ranges(cl):
    """Timeline seconds where nothing speaks: muted main segments (CapCut slivers, plan "mute": true, silent carrier) minus
    the voiceovers that play there; the whole reel for a silent (images-only) cut list. Captions, tl_words and bleeps skip them."""
    total = float(cl.get("durationSec") or 0)
    if cl.get("silent"): return [(0.0, total or 1e9)]
    muted = [(float(s["tlStart"]), float(s["tlStart"]) + float(s["dur"])) for s in cl.get("main", []) if s.get("materialType", "video") == "video" and float(s.get("volume", 1)) < 0.01]
    vo = [(float(s["tlStart"]), float(s["tlStart"]) + float(s["dur"])) for s in speech_tracks(cl)]
    return _subtract(muted, vo)

def in_ranges(t, ranges, tol=0.0):
    return any(a - tol <= t < b + tol for a, b in ranges)

def proxy_file(public, cid):
    """The proxy of clip `cid` under <public>: footage/ (1080) when it exists, else footage2k/ — a «2K only» intake makes
    no 1080 proxies, and transcribe.py read silence from the empty footage/ folder (reel-studio reel, 2026-11-05)."""
    for folder in ("footage", "footage2k"):
        p = os.path.join(public, folder, f"{cid}.mp4")
        if os.path.exists(p): return p
    return os.path.join(public, "footage", f"{cid}.mp4")


def load_offsets(cutlist_path):
    p = os.path.join(os.path.dirname(cutlist_path) or ".", "proxy_offsets.json")
    return json.load(open(p)) if os.path.exists(p) else {}

# ---------------------------------------------------------------- word patches (make_captions.py and tl_words.py share them)

def apply_patches(raw, patches):
    """caption_patches.json on RAW whisper tokens (before gluing): drop, drop_at [[sec, token]], replace {old: new},
    replace_at [[sec, old, new]] (±1.5 s). Returns (kept tokens, dropped count)."""
    if not patches: return raw, 0
    drop = set(patches.get("drop", [])); rep = patches.get("replace", {}); rep_at = patches.get("replace_at", []); drop_at = patches.get("drop_at", [])
    kept = []
    for w in raw:
        t = w["word"].strip()
        if t in drop: continue
        if any(t == old and abs(w["start"] - t0) <= 1.5 for t0, old in drop_at): continue
        for t0, old, new in rep_at:
            if t == old and abs(w["start"] - t0) <= 1.5: w = dict(w, word=" " + new)
        if t in rep: w = dict(w, word=" " + rep[t])
        kept.append(w)
    return kept, len(raw) - len(kept)

def glue(raw):
    """Whisper splits a word into tokens without a leading space ("Яндекс" + ".Облаке"): glue them into words."""
    out = []
    for w in raw:
        if out and not w["word"].startswith(" "): out[-1]["word"] += w["word"]; out[-1]["end"] = w["end"]
        else: out.append(dict(w))
    return out

def brand(text, brands):
    """brands.json {"трипо": "Tripo"}: canonical spelling of a word, punctuation kept."""
    core = text.strip().strip(".,!?…:;«»\"()"); low = core.lower()
    return text.replace(core, brands[low]) if core and low in brands else text

def load_json(path, default=None):
    return json.load(open(path)) if path and os.path.exists(path) else default

# ---------------------------------------------------------------- people-aware crop (people_zones.py → make_proxies.py, doctor.py)

def needs_crop(cl, seg, info):
    """A main segment whose source is cut to the canvas aspect: a camera clip wider than a portrait canvas in a cut list made
    here (plan.json / silent). A CapCut draft is the user's framing — what they saw in CapCut stays (non-negotiable)."""
    if cl.get("draft") not in (None, "transcript-cut", "silent"): return False
    cw, ch = (cl.get("canvas") or {}).get("w") or 1080, (cl.get("canvas") or {}).get("h") or 1920
    return bool(ch > cw and is_camera(seg["path"]) and info and info.get("w", 0) > info.get("h", 0) and not seg.get("transform") and not seg.get("crop"))

def crop_keys(zones, src):
    """Absolute source keyframes [[t, centre 0–1], …] for one source from people_zones.json rows; None when no row covers it."""
    rows = [r for r in (zones or {}).get("segments", []) if r.get("src") == src]
    if not rows: return None
    return [list(k) for k in sorted({(round(t, 2), round(c, 4)) for r in rows for t, c in r["keys"]})]

def zone_covers(zones, seg):
    """people_zones.json has a row for exactly this segment's source range (a re-cut moves ranges → re-run people_zones.py)."""
    a, b = float(seg["srcStart"]), float(seg["srcStart"]) + src_dur(seg)
    return any(r.get("src") == seg["path"] and abs(r["srcStart"] - a) < 0.02 and abs(r["srcEnd"] - b) < 0.02 for r in (zones or {}).get("segments", []))

def crop_sig(keys):
    """Manifest value: the keyframes as text (None = the old centre crop, so older manifests still match a centre crop)."""
    if not keys or all(abs(c - 0.5) < 1e-3 for _, c in keys): return None
    return ";".join(f"{t:.2f}:{c:.4f}" for t, c in keys)

def crop_expr(keys, start, scaled_w, out_w):
    """ffmpeg crop x for a proxy cut from `start`: piecewise-linear centre over the keyframes (t = proxy seconds), in pixels of
    the frame scaled to the canvas height, clamped inside the frame. Single-quoted: the commas stay inside the expression."""
    pts = [(t - start, c * scaled_w - out_w / 2) for t, c in keys]
    if len(pts) == 1 or all(abs(x - pts[0][1]) < 1 for _, x in pts):
        return str(int(max(0, min(scaled_w - out_w, round(pts[0][1])))))
    e = f"{pts[-1][1]:.1f}"
    for (t0, x0), (t1, x1) in reversed(list(zip(pts, pts[1:]))):
        seg = f"{x0:.1f}" if t1 - t0 < 1e-3 else f"{x0:.1f}+({x1 - x0:.1f})*(t-{t0:.3f})/{t1 - t0:.3f}"
        e = f"if(lt(t,{t1:.3f}),{seg},{e})"
    e = f"if(lt(t,{pts[0][0]:.3f}),{pts[0][1]:.1f},{e})"   # before the first key: hold it (no extrapolation)
    return f"'max(0,min({scaled_w - out_w},{e}))'"

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["N"] and len(a) > 1: print(N[a[1]])
    elif a[:1] == ["probe"] and len(a) > 1: print(json.dumps(probe(a[1]), ensure_ascii=False, indent=1))
    elif a[:1] == ["lut"] and len(a) > 1:
        lut = a[a.index("--lut") + 1] if "--lut" in a else None; lm = load_lut_map(a[a.index("--lut-map") + 1]) if "--lut-map" in a else {}
        print(*lut_for(a[1], lut, lm), sep="  ←  ")
    else: print(__doc__)


CANVASES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "4:5": (1080, 1350), "1:1": (1080, 1080)}


def canvas_size(spec=None, project=None):
    """(w, h) of the canvas: an explicit spec ("16:9" or {"w", "h"}), else work/intake.json "canvas", else 9:16 (1080×1920).
    The 1080-based layout size; Reel2K renders it ×4/3 (2560×1440 for 16:9)."""
    if spec is None and project:
        spec = (load_json(os.path.join(project, "work/intake.json"), {}) or {}).get("canvas")
    if isinstance(spec, dict) and spec.get("w") and spec.get("h"): return int(spec["w"]), int(spec["h"])
    if isinstance(spec, str) and spec in CANVASES: return CANVASES[spec]
    if spec: sys.exit(f"unknown canvas {spec!r}: one of {', '.join(CANVASES)} or {{\"w\": …, \"h\": …}}")
    return CANVASES["9:16"]


def title_y(mask_json):
    """Vertical centre (0–1) for a title behind the person: a little below the top of the people's box (median over the
    frames of person_matte.py's .mask.json), so the head covers the lower part of the letters. None if nobody was found."""
    m = load_json(mask_json, {}) or {}
    tops = sorted(f["bbox"][1] for f in m.get("frames", []) if f.get("bbox"))
    return None if not tops else round(max(0.14, min(0.62, tops[len(tops) // 2] + 0.05)), 3)
