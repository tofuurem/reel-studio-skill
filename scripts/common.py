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
POCKET4P_LUT = "DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube"
ACTION5PRO_LUT = "DJI OSMO Action 5 Pro D-Log M to Rec.709 V1.cube"
ACTION4_LUT = "DJI OSMO Action 4 D-Log M to Rec.709 V1.cube"
# The colour profile a DJI camera writes into its «djmd» metadata track (protobuf; checked on 855 clips, 2026-11-08):
# proto name → field path of the profile code.
DJI_COLOR_FIELD = {"dvtm_ac204.proto": "2.4.1",            # Osmo Action 5 Pro
                   "dvtm_ac203.proto": "2.4.1",            # Osmo Action 4 (AC003). Normal checked 2026-11-09 on 3 clips: field 2.4
                   # is written but empty (code 0); that D-Log M lands in 2.4.1 as on ac204 is a guess — no D-Log M sample yet
                   "dvtm_osmo_pocket_4.proto": "2.2.3.1"}  # Osmo Pocket 4 and 4P
DJI_COLOR_CODES = {0: "Normal", 2: "D-Log", 9: "HLG", 19: "D-Log-M", 22: "D-Log2"}
# (model key from the encoder tag, profile) → DJI's own cube (download it from DJI; not shipped, assets/luts/README.md).
# Normal needs none; HLG gets the HDR LUT; a log profile without its cube falls back to --lut, else it is reported.
DJI_LOG_LUTS = {("pocket4p", "D-Log"): POCKET4P_LUT, ("pocket4", "D-Log"): POCKET4P_LUT,
                ("action5pro", "D-Log-M"): ACTION5PRO_LUT, ("action4", "D-Log-M"): ACTION4_LUT}

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

def find_cube(name):
    """A camera's cube by its file name: the LUT cache, the skill's assets/luts, ~/Downloads (where DJI's download lands)."""
    for d in (LUT_DIR, os.path.join(SKILL, "assets/luts"), os.path.expanduser("~/Downloads")):
        p = os.path.join(d, name)
        if os.path.exists(p): return p
    return None

def load_lut_map(path):
    """--lut-map: a JSON file or inline JSON {"DJI_*_0004*": "/abs/Action4.cube", "*rec_*": "none"} — glob on the file name (or the full path)."""
    if not path: return {}
    return json.loads(path) if path.lstrip().startswith("{") else json.load(open(path))

def _varint(b, i):
    r = s = 0
    while True:
        x = b[i]; i += 1
        r |= (x & 0x7F) << s; s += 7
        if x < 0x80: return r, i

def _protobuf_fields(b, prefix="", out=None, depth=0):
    """Schema-less protobuf walk → {"2.4.1": [19], "1.1.1": ["dvtm_ac204.proto"]} (nested messages flattened by path)."""
    out = {} if out is None else out
    i = 0
    while i < len(b):
        key, i = _varint(b, i)
        field, wire = key >> 3, key & 7
        if field == 0: raise ValueError("not protobuf")
        path = f"{prefix}.{field}" if prefix else str(field)
        if wire == 0:
            v, i = _varint(b, i); out.setdefault(path, []).append(v)
        elif wire == 1: i += 8
        elif wire == 5: i += 4
        elif wire == 2:
            n, i = _varint(b, i); sub = b[i:i + n]; i += n; nested = {}
            try:
                if depth > 6 or not sub: raise ValueError
                _protobuf_fields(sub, path, nested, depth + 1)
            except (ValueError, IndexError):
                nested = {}
            if nested:
                for k, v in nested.items(): out.setdefault(k, []).extend(v)
            else:
                try: out.setdefault(path, []).append(sub.decode("utf-8"))
                except UnicodeDecodeError: pass
        else: raise ValueError("not protobuf")
    return out

_DJI_PROFILE = {}

def dji_profile(path):
    """The colour profile a DJI camera recorded the clip in — "Normal" | "D-Log" | "D-Log-M" | "HLG" | "D-Log2" | "Code<n>" —
    read from the first record of its «djmd» metadata track; None when the file has no such track (not DJI, re-encoded)
    or the camera's proto is unknown. One packet is read, so it is cheap; cached per file."""
    src = os.path.realpath(path)
    try: key = (src, os.path.getsize(src), int(os.path.getmtime(src)))
    except OSError: return None
    if key in _DJI_PROFILE: return _DJI_PROFILE[key]
    res = None
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=index,codec_tag_string", "-of", "csv=p=0", src], capture_output=True, text=True)
    idx = next((ln.split(",")[0] for ln in r.stdout.splitlines() if ln.strip().endswith(",djmd")), None)
    if idx is not None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", src, "-map", "0:" + idx, "-c", "copy", "-frames:0", "1", "-f", "data", "pipe:1"], capture_output=True)
        try:
            fields = _protobuf_fields(r.stdout)
            proto = next((v for v in fields.get("1.1.1", []) if isinstance(v, str)), None)
            if proto in DJI_COLOR_FIELD:
                code = (fields.get(DJI_COLOR_FIELD[proto]) or [0])[0]   # protobuf does not write a 0
                res = DJI_COLOR_CODES.get(code, f"Code{code}")
        except (ValueError, IndexError):
            res = None
    _DJI_PROFILE[key] = res
    return res

def _dji_model(info):
    """"DJI OsmoAction5 Pro" → "action5pro", "DJI OsmoPocket4P" → "pocket4p" (the keys of DJI_LOG_LUTS)."""
    return re.sub(r"^dji|osmo|[\s_-]", "", (info.get("camera") or "").lower())

def lut_for(path, lut=None, lut_map=None, info=None):
    """(cube path or None, reason). Order: --lut-map glob → an HDR source (HLG / PQ, any file: iPhone, Android HDR10, a camera
    in HLG mode) gets the HDR → Rec.709 LUT (hdr_lut.py) → non-camera files get none → the DJI colour profile recorded in the
    file (djmd: Normal → none, HLG → the HDR LUT, D-Log / D-Log M → that camera's cube when it is installed, else --lut, else
    reported) → explicit --lut / draft LUT → none: Rec.709 is assumed — other log footage (S-Log, V-Log …) needs --lut or
    --lut-map (ask the user when the inventory shows flat grey footage). Reasons starting with "lut-map" or "djmd" are decisions."""
    b = nfc(os.path.basename(path))
    for pat, cube in (lut_map or {}).items():
        if fnmatch.fnmatch(b, pat) or fnmatch.fnmatch(nfc(path), pat) or fnmatch.fnmatch(nfc(os.path.basename(os.path.realpath(path))), pat):   # alias symlinks match as their source
            if str(cube).lower() in ("none", "", "null"): return None, f"lut-map {pat}: none"
            return os.path.expanduser(cube), f"lut-map {pat}"
    info = info if info and "hdr" in info else probe(path)
    if info.get("hdr"): return hdr_lut(info["hdr"]), f"HDR {info['hdr'].upper()} ({info.get('transfer')}) → Rec.709"
    if not is_camera(path): return None, "not a camera clip (Rec.709)"
    prof = dji_profile(path)
    if prof:
        model = _dji_model(info)
        if prof == "Normal": return None, f"djmd: {info.get('camera') or 'DJI'} Normal (Rec.709)"
        if prof == "HLG": return hdr_lut("hlg"), f"djmd: {info.get('camera') or 'DJI'} HLG → Rec.709"
        name = DJI_LOG_LUTS.get((model, prof))
        p = find_cube(name) if name else None
        if p: return p, f"djmd: {info.get('camera')} {prof}"
        if lut: return os.path.expanduser(lut), f"--lut / draft ({info.get('camera')} {prof}: no cube of its own)"
        return None, f"NO LUT FOUND for {info.get('camera') or 'DJI'} {prof}" + (f" (missing {name})" if name else "") + " — pass --lut or --lut-map"
    if lut: return os.path.expanduser(lut), "--lut / draft"
    return None, "no LUT (Rec.709 assumed" + (f", camera tag '{info.get('camera')}'" if info.get("camera") else "") + ")"

HDR_TRANSFERS = {"arib-std-b67": "hlg", "smpte2084": "pq"}

HDR_NAMES = {"hlg": "HLG_BT2020_to_Rec709.cube", "pq": "PQ_BT2020_to_Rec709.cube"}   # = hdr_lut.NAMES

def hdr_lut(kind):
    """The HDR → Rec.709 cube in LUT_DIR, generated on first use (hdr_lut.py, numpy; ≈ 3 s). make_proxies / inventory run on a
    plain python3 that may have no numpy: then the shared venv's python writes the cubes."""
    p = os.path.join(LUT_DIR, HDR_NAMES[kind])
    if not os.path.exists(p):
        os.makedirs(LUT_DIR, exist_ok=True)
        try:
            import hdr_lut as H
            H.write_cube(p, kind)
        except ImportError:
            py = os.path.join(CACHE, "venv", "bin", "python")
            if not os.path.exists(py): sys.exit("numpy is needed for the HDR LUT — run setup_env.sh (it builds ~/.cache/reel-studio/venv)")
            subprocess.run([py, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "hdr_lut.py"), "--out", LUT_DIR], check=True, capture_output=True)
        print("generated", p)
    return p

def _fps(r):
    try:
        a, b = (r or "0/1").split("/"); return float(a) / float(b) if float(b) else 0.0
    except ValueError: return 0.0

def probe(path):
    """{dur, w, h (display, rotation applied), rot, fps (avg), r_fps, vfr, has_video, has_audio, codec, camera, nb_frames,
    transfer, primaries, pix_fmt, hdr ("hlg" | "pq" | None)}"""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:format_tags:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,pix_fmt,color_transfer,color_primaries,color_space:stream_tags:stream_side_data",
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
            "codec": v.get("codec_name"), "camera": cam, "nb_frames": int(v["nb_frames"]) if str(v.get("nb_frames", "")).isdigit() else None,
            "transfer": v.get("color_transfer"), "primaries": v.get("color_primaries"), "pix_fmt": v.get("pix_fmt"),
            "hdr": HDR_TRANSFERS.get(v.get("color_transfer") or "")}

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
    """caption_patches.json on RAW recognizer tokens (before gluing): drop, drop_at [[sec, token]], replace {old: new},
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
    """A recognizer may split a word into tokens without a leading space ("Яндекс" + ".Облаке"): glue them into words."""
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

# ---- memory guard: ONE mechanism for every heavy python step (a model, DeepFilterNet, BiRefNet, earshot) ----
def add_guard_args(ap, max_gb):
    """--max-gb / --min-free-gb / --no-guard for a heavy script; call guard_reexec(args) right after parse_args()."""
    ap.add_argument("--max-gb", type=float, default=max_gb, help="memory guard: kill the run (and its children) above this footprint, GB")
    ap.add_argument("--min-free-gb", type=float, default=4.0, help="memory guard: memory always left to the Mac, GB")
    ap.add_argument("--no-guard", action="store_true", help="run without the memory guard (do not)")

def guard_reexec(a):
    """Re-run this very command under mem_guard.py (macOS only; once — MEM_GUARDED=1 marks the inner run). The guard kills the
    process tree with exit 137 when it passes --max-gb or the Mac has less than --min-free-gb left, and prints the peak."""
    if a.no_guard or os.environ.get("MEM_GUARDED") or sys.platform != "darwin": return
    guard = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mem_guard.py")
    cmd = [sys.executable, "-I", guard, "--max-gb", str(a.max_gb), "--min-free-gb", str(a.min_free_gb), "--",
           sys.executable, "-I", os.path.abspath(sys.argv[0]), *sys.argv[1:]]
    sys.stdout.flush(); sys.stderr.flush()
    os.execve(sys.executable, cmd, {**os.environ, "MEM_GUARDED": "1"})


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


def title_box(title, canvas=(1080, 1920)):
    """(height, width) of BehindTitle's word as fractions of the canvas: the same size rule as scenes/BehindTitle.tsx
    (≈ 0.8 em per capital, at most 90 % of the width, 190 px portrait / 230 px landscape); caps ≈ 0.72 em tall."""
    w, h = canvas; size = min(190 if h > w else 230, w * 0.9 / (0.8 * max(1, len(title))))
    return 0.72 * size / h, min(0.9, 0.8 * size * len(title) / w)


def title_place(mask_json, title=None, canvas=None, zoom=None, kicker=False):
    """Where BehindTitle's word goes: {"x", "y", "scale"} (x, y = the word's centre 0–1 of the canvas; scale × the fitted font
    size), or None if nobody was found in the matte.
    mask_json: one person_matte.py .mask.json, or a list of (mask_json, zoom) pairs when one title spans several shots (a hook
    over three jump cuts): one place that works for all of them.
    With the mattes' .alpha.npz and the title text, every candidate (height × horizontal shift × size 1 / 0.85 / 0.7) is scored
    on the alpha averaged over each shot: the person hides part of the word (≥ 2 %, ideally ≈ 10 %), the tops of the letters
    stay visible, the top of the head (not a shoulder edge) is what crosses the word, as few real letters as possible are
    hidden (the head over the hyphen or the space of «REEL-STUDIO», not over «EL»; the first and last letters never — a
    shoulder edge over the «R» read as «EEL-STUDIO»), and the word does not cross soft or moving mask edges (hair strands,
    hands — the time-averaged alpha is mid-grey there). Bigger and centred wins a tie.
    The old rule «bbox top + 5 %» put a 16:9 title across the ears of a seated speaker: whole letters vanished and the
    headphones' missing mask showed as a haze over the word (reel_studio_skill hook, 2026-11-06).
    zoom=(scale, cx, cy): the footage is shown scaled around (cx, cy) (0–1; a punch-in) — the word is placed on the frame the
    viewer sees. kicker=True keeps room above the word for the kicker line (it must not leave the top safe zone).
    Without the npz (older mattes) or the title: x 0.5, y a little below the top of the people's box, scale 1, as before."""
    import numpy as np
    pairs = [(mask_json, zoom)] if isinstance(mask_json, str) else list(mask_json)
    segs, fallback = [], None
    for mj, zm in pairs:
        m = load_json(mj, {}) or {}
        tops = sorted(f["bbox"][1] for f in m.get("frames", []) if f.get("bbox"))
        if not tops: continue
        zs, zx, zy = zm or (1.0, 0.5, 0.5)
        if fallback is None:
            fallback = {"x": 0.5, "y": round(zy + (max(0.14, min(0.62, tops[len(tops) // 2] + 0.05)) - zy) * zs, 3), "scale": 1.0}
        npz = mj[:-len(".mask.json")] + ".alpha.npz" if mj.endswith(".mask.json") else None
        if not npz or not os.path.exists(npz): continue
        Am = (np.load(npz)["alpha"].astype(np.float32) / 255).mean(0); h, w = Am.shape
        soft = ((Am > 0.15) & (Am < 0.85)).astype(np.float32)
        on = Am > 0.5
        crown = int(np.argmax(on.any(1))) if on.any() else h                           # first row of the silhouette = top of the head
        segs.append(dict(h=h, w=w, z=(zs, zx, zy), crown=crown, cum=np.vstack([np.zeros((1, w), np.float32), np.cumsum(Am, 0)]),
                         cs=np.vstack([np.zeros((1, w), np.float32), np.cumsum(soft, 0)]), size=(m.get("width", 1080), m.get("height", 1920))))
    if fallback is None: return None
    if not title or not segs or len(segs) < len(pairs): return fallback
    weight = np.array([0.0 if ch in " -–—·.,:!?" else 1.0 for ch in title])
    weight[0] = weight[-1] = 4.0                                                          # «EEL-STUDIO»: the first and last letters always read
    bh0, bw0 = title_box(title, canvas or segs[0]["size"])

    def seg_score(g, sc, x, y, bh, bw):
        h, w = g["h"], g["w"]; zs, zx, zy = g["z"]; to_src = lambda v, c: c + (v - c) / zs   # canvas 0–1 → proxy 0–1
        c0, c1 = max(0, round(to_src(x - bw / 2, zx) * w)), min(w, round(to_src(x + bw / 2, zx) * w))
        r0, r1 = max(0, round(to_src(y - bh / 2, zy) * h)), min(h, round(to_src(y + bh / 2, zy) * h))
        if c1 - c0 < len(title) or r1 - r0 < 3: return None
        cum, cs = g["cum"], g["cs"]
        col = (cum[r1, c0:c1] - cum[r0, c0:c1]) / (r1 - r0)                          # share of each column hidden
        occ = float(col.mean())
        if occ < 0.02: return None                                                   # nobody behind the word: no effect
        rt = r0 + max(1, (r1 - r0) * 2 // 5)
        top = float((cum[rt, c0:c1] - cum[r0, c0:c1]).mean() / (rt - r0))           # upper 40 % of the letters
        edges = np.linspace(0, c1 - c0, len(title) + 1).round().astype(int); covered = col > 0.5
        lost = sum(weight[i] for i in range(len(title)) if covered[edges[i]:edges[i + 1]].mean() > 0.4)
        fringe = float((cs[r1, c0:c1] - cs[r0, c0:c1]).sum() / ((r1 - r0) * (c1 - c0)) / max(occ, 0.01))
        head = r0 - 0.15 * (r1 - r0) <= g["crown"] <= r1                             # the top of the head is what hides the word
        return abs(occ - 0.10) * 2 + max(0.0, top - 0.03) * 4 + lost * 0.25 + fringe * 0.5 + (0 if head else 0.6)

    best = None
    for sc in (1.0, 0.85, 0.7):
        bh, bw = bh0 * sc, bw0 * sc
        for x in np.arange(max(0.25, bw / 2 + 0.04), min(0.75, 1 - bw / 2 - 0.04) + 1e-6, 0.01):
            for y in np.arange(bh / 2 + (0.11 if kicker else 0.06), 0.78, 0.005):
                parts = [seg_score(g, sc, x, y, bh, bw) for g in segs]
                if any(p is None for p in parts): continue
                score = sum(parts) / len(parts) + (1 - sc) * 0.6 + abs(x - 0.5) * 0.3
                if best is None or score < best[0]: best = (score, float(x), float(y), sc)
    if best is None: return fallback
    return {"x": round(best[1], 3), "y": round(best[2], 3), "scale": best[3]}


def title_y(mask_json, title=None, canvas=None, zoom=None, kicker=False):
    """The y of title_place() (callers that only move the word up and down)."""
    p = title_place(mask_json, title, canvas, zoom, kicker)
    return None if p is None else p["y"]