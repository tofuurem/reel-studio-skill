#!/usr/bin/env python3
"""Copy the material the user handed over into the project under safe ASCII names (and log it), so every script can read it.

Usage: python3 -I ingest.py <project> <source dir|file>… [--dry-run] [--camera skip|link|copy]

Sorted by kind (a directory is walked recursively):
  camera clips   any other video (DJI, phone, GoPro …) → stay where they are by default (`--camera skip`, scripts take their paths);
                                                `link` puts symlinks into assets/camera/, `copy` copies them there
  screen recordings «Запись экрана — 2026-10-10 в 13.58.13.mov», «Screen Recording 2026-10-10 at 1.58.13 PM.mov»
                                                → assets/screenrec/rec_20261010_135813.mov
  screenshots    «Снимок экрана — … .png», «Screenshot 2026-10-09 at 16.10.38.png» → assets/screens/shot_20261009_161038.png
                 («… (2).png» → …_2.png)
  images         png/jpg/jpeg/webp/gif           → assets/screens/<name>   («image-1791478480074.png» → img_1791478480074.png)
                 heic                            → converted to .jpg with sips (Chrome cannot show HEIC); the log keeps the mapping
  voice          aac/m4a/wav/mp3/aif            → assets/voiceover/<name>   (longer than 150 s and no music hint: still voice,
                                                  printed with "check: long audio" — a long monologue is more common than an unnamed track)
  music          the same types when the name or a parent folder says music/музыка/bed/track/song/песня → assets/music/<name>
  3D and rigs    fbx/glb/gltf/blend/obj/usdz     → assets/models/<name>
  anything else  is listed and skipped.

Why: macOS names carry NFD letters and U+00A0 (a pasted path does not open, regexes with a space miss), the external volume
has AppleDouble `._name` sidecars next to every file (a copy loop once copied the 4 KB sidecar instead of the recording), and
Cyrillic ids break clip_id(). Names are NFC-normalised, U+00A0 counts as a space, `._*` / `.DS_Store` are skipped, other
Cyrillic is transliterated. Linked camera clips whose DJI counter is already taken by another clip of the project get a
`b`, `c` … suffix in the link name (DJI_<date>_0005b_D.MP4), so clip ids stay unique without copying gigabytes. A target with the same size is kept (re-runs are cheap); a different file with the same name gets
`_2`, `_3`. Every copy goes to a hidden temp name first, is verified by size and only then renamed — an interrupted copy never
holds the real name. The mapping goes to assets/ingest_log.json (source → target, bytes, mtime), rewritten after every file.
"""
import argparse, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ascii_stem, atomic_json, duration, is_camera, nfc

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("sources", nargs="+")
ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--camera", choices=["skip", "link", "copy"], default="skip")
a = ap.parse_args()
P = os.path.abspath(a.project); A = os.path.join(P, "assets")

def ascii_name(stem): return ascii_stem(stem, lower=True, keep="")

# «2026-10-10 в 13.58.13», «2026-10-10 at 13.58.13», «2026-10-10 at 1.58.13 PM» (U+202F before PM is normalised by nfc)
STAMP = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s+(?:в|at)\s+(\d{1,2})\.(\d{2})\.(\d{2})(?:\s*([AP]M))?(?:\s*\((\d+)\))?", re.I)
VIDEO = {".mp4", ".mov", ".m4v"}; IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"}
AUDIO = {".aac", ".m4a", ".wav", ".mp3", ".aif", ".aiff"}; MODEL = {".fbx", ".glb", ".gltf", ".blend", ".obj", ".usdz"}
LONG_AUDIO = 150

def link_name(target_dir, name):
    """DJI_<date>_<NNNN>_D.MP4 → keep, or add b/c/… when another linked clip already uses the counter NNNN."""
    m = re.match(r"(DJI_\d+_)(\d{4})([a-z]?)(_D\.\w+)$", name, re.I)
    if not m or not os.path.isdir(target_dir): return name
    taken = {re.match(r"DJI_\d+_(\d{4}[a-z]?)_", f, re.I)[1] for f in os.listdir(target_dir) if re.match(r"DJI_\d+_(\d{4}[a-z]?)_", f, re.I) and f != name}
    if m[2] not in taken: return name
    for suf in "bcdefgh":
        if m[2] + suf not in taken: return f"{m[1]}{m[2]}{suf}{m[4]}"
    return name

def classify(path):
    """(assets subfolder, kind, target name, note)"""
    name = nfc(os.path.basename(path))
    stem, ext = os.path.splitext(name); ext = ext.lower()
    m = STAMP.search(stem); stamp = None
    if m:
        hh = int(m[4]); ap_ = (m[7] or "").upper()
        if ap_ == "PM" and hh < 12: hh += 12
        if ap_ == "AM" and hh == 12: hh = 0
        stamp = f"{m[1]}{m[2]}{m[3]}_{hh:02d}{m[5]}{m[6]}" + (f"_{m[8]}" if m[8] else "")
    out_ext = ".jpg" if ext == ".heic" else ext; note = "heic→jpg" if ext == ".heic" else ""
    if ext in VIDEO and stamp and re.search(r"запись\s+экрана|screen\s+recording", stem, re.I): return "screenrec", "screenrec", f"rec_{stamp}{ext}", ""
    if ext in VIDEO and is_camera(path): return "camera", "camera", name, ""
    if ext in IMAGE and stamp and re.search(r"снимок\s+экрана|screen\s*shot", stem, re.I): return "screens", "screenshot", f"shot_{stamp}{out_ext}", note
    if ext in IMAGE:
        m2 = re.match(r"image-(\d+)$", stem)
        return "screens", "image", (f"img_{m2[1]}" if m2 else ascii_name(stem)) + out_ext, note
    if ext in AUDIO:
        if re.search(r"music|музык|\bbed\b|track|song|песн", nfc(path).lower()): return "music", "music", ascii_name(stem) + ext, ""
        d = duration(path)
        return "voiceover", "audio", ascii_name(stem) + ext, (f"check: long audio ({d:.0f} s) — music? move it to assets/music" if d > LONG_AUDIO else "")
    if ext in VIDEO: return "video", "video", ascii_name(stem) + ext, ""
    if ext in MODEL: return "models", "model", ascii_name(stem) + ext, ""
    return None, "other", name, ""

def walk(src):
    if os.path.isfile(src): yield src; return
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for f in sorted(files):
            if f.startswith(".") or f == "Icon\r": continue   # AppleDouble sidecars, .DS_Store
            yield os.path.join(root, f)

def heic_cmd(src, out):
    """HEIC → JPEG: sips on macOS, heif-convert (libheif) or ImageMagick elsewhere (deps.py installs heif-convert)."""
    if shutil.which("sips"): return ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92", src, "--out", out]
    if shutil.which("heif-convert"): return ["heif-convert", "-q", "92", src, out]
    if shutil.which("magick"): return ["magick", src, "-quality", "92", "jpeg:" + out]
    return ["false"]

def put(src, target, convert):
    """Copy (or convert) to a hidden temp name in the target folder, verify, rename. Returns an error text or None."""
    tmp = os.path.join(os.path.dirname(target), "." + os.path.basename(target) + ".part")
    try:
        if convert: r = subprocess.run(heic_cmd(src, tmp), capture_output=True, text=True); ok = r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0
        else: shutil.copy2(src, tmp); ok = os.path.getsize(tmp) == os.path.getsize(src)
    except OSError as e: ok = False
    if not ok:
        if os.path.exists(tmp): os.remove(tmp)
        return f"copy failed: {src}"
    os.replace(tmp, target); return None

log_path = os.path.join(A, "ingest_log.json")
log = json.load(open(log_path)) if os.path.exists(log_path) else []
done_src = {e["source"]: e for e in log}
rows = []; counts = {}
for src in a.sources:
    if not os.path.exists(src): sys.exit(f"missing: {src} (volume not mounted?)")
    for f in walk(src):
        f = os.path.abspath(f); sub, kind, target_name, note = classify(f); size = os.path.getsize(f); convert = note == "heic→jpg"
        counts[kind] = counts.get(kind, 0) + 1
        if sub is None: rows.append((kind, f, "skipped (unknown type)")); continue
        if kind == "camera" and a.camera == "skip": rows.append((kind, f, "stays on the volume (pass this path to the scripts)")); continue
        prev = done_src.get(f)
        if prev and os.path.exists(prev["target"]) and (prev.get("converted") or (os.path.getsize(prev["target"]) == size and not os.path.islink(prev["target"]))) or (prev and a.camera == "link" and os.path.islink(prev["target"])):
            rows.append((kind, f, os.path.relpath(prev["target"], P) + "  (already there)")); continue
        d = os.path.join(A, sub)
        if kind == "camera" and a.camera == "link": target_name = link_name(d, target_name)
        base, ext = os.path.splitext(target_name); target = os.path.join(d, target_name); n = 2
        while os.path.exists(target) and (convert or not (os.path.getsize(target) == size and not os.path.islink(target))):
            target = os.path.join(d, f"{base}_{n}{ext}"); n += 1
        if os.path.exists(target):
            rows.append((kind, f, os.path.relpath(target, P) + "  (same file, kept)"))
            if not a.dry_run: log.append({"source": f, "target": target, "bytes": size, "kind": kind}); atomic_json(log, log_path)
            continue
        rows.append((kind, f, os.path.relpath(target, P) + (f"  ({note})" if note else "")))
        if a.dry_run: continue
        os.makedirs(d, exist_ok=True)
        if kind == "camera" and a.camera == "link": os.symlink(f, target)
        else:
            err = put(f, target, convert)
            if err: atomic_json(log, log_path); sys.exit(err)
        log.append({"source": f, "target": target, "bytes": size, "mtime": int(os.path.getmtime(f)), "kind": kind, **({"converted": "heic→jpg"} if convert else {})})
        os.makedirs(A, exist_ok=True); atomic_json(log, log_path)   # after every file: an interrupted run keeps a true log

for kind, f, t in rows: print(f"{kind:10s} {os.path.basename(f)[:60]:60s} → {t}")
print("INGEST_" + ("DRY_RUN" if a.dry_run else "DONE"), " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
