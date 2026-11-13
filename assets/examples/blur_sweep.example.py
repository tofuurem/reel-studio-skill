"""Dense check of the joint blur in a FINISHED censored render (example from the Halloween vlog, 2026-11-13: mid-patch
stills had passed while six joints still showed — copy to work/audit/ and run from the project folder).

For every censor patch in reel/src/Reel.tsx (sign patches skipped) it takes frames every STEP seconds from PAD seconds
before the patch to PAD seconds after it, from the censored render and from the uncensored one (same cut, same
captions). Where they differ is the blur; each tile is a crop around that spot (the patch's union box outside it),
so a joint sticking out of the blur, or one in view before/after the patch, is visible on the sheet.

    work/venv/bin/python -I work/audit/blur_sweep.py <censored.mp4> <uncensored.mp4> [out_dir] [--only a,b] [--offset s]
→ <out_dir>/<patch>_<n>.jpg sheets (6 columns), <out_dir>/index.tsv (sheet, tile, time, inside patch)
"""
import os, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FPS = 30
STEP = 0.2            # s between tiles
PAD = 1.5             # s before / after each patch
W, H = 1280, 720      # decode size (half of 2K)
TILE_W = 420
COLS, ROWS = 6, 5
SIGNS = set()        # patch names to skip (Halloween v5 skipped its sign jobs this way); or pass --only a,b

args = sys.argv[1:]
only = None
if "--only" in args:
    i = args.index("--only"); only = set(args[i + 1].split(",")); del args[i:i + 2]
OFFSET = 0.0   # --offset s: the censored file is a partial render starting at this timeline second
if "--offset" in args:
    i = args.index("--offset"); OFFSET = float(args[i + 1]); del args[i:i + 2]
cens, unc = args[0], args[1]
out = args[2] if len(args) > 2 else "work/audit/blur_sweep"
os.makedirs(out, exist_ok=True)
src = open("reel/src/Reel.tsx", encoding="utf-8").read()
pats = [(n, int(f), int(d)) for n, f, d in
        re.findall(r'<Sequence name="censor ([^"]+)" from=\{(\d+)\} durationInFrames=\{(\d+)\}', src)]
pats = [p for p in pats if p[0] not in SIGNS and (only is None or p[0] in only)]
try: FONT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
except Exception: FONT = ImageFont.load_default()


def frames(path, t0, dur, tmp, tag):
    pat = os.path.join(tmp, f"{tag}_%04d.png")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t0:.3f}", "-i", path, "-t", f"{dur:.3f}",
                    "-vf", f"fps={1/STEP},scale={W}:{H}", pat], check=True)
    fs = sorted(f for f in os.listdir(tmp) if f.startswith(tag + "_"))
    return [np.asarray(Image.open(os.path.join(tmp, f)).convert("RGB")) for f in fs]


def bbox(a, b):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(2) > 18
    ys, xs = np.nonzero(d)
    if len(xs) < 80: return None
    return np.percentile(xs, 1), np.percentile(ys, 1), np.percentile(xs, 99), np.percentile(ys, 99)


index = ["sheet\ttile\ttime\tinside"]
for name, f, d in pats:
    t0 = max(0.0, f / FPS - PAD); dur = d / FPS + 2 * PAD
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(out))) as tmp:
        A = frames(cens, t0 - OFFSET, dur, tmp, "c"); B = frames(unc, t0, dur, tmp, "u")
    n = min(len(A), len(B)); boxes = [bbox(A[i], B[i]) for i in range(n)]
    have = [b for b in boxes if b]
    if not have: print(f"{name}: no blur found"); continue
    U = (min(b[0] for b in have), min(b[1] for b in have), max(b[2] for b in have), max(b[3] for b in have))
    tiles = []
    for i in range(n):
        t = t0 + i * STEP; b = boxes[i] or U
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        bw, bh = max(b[2] - b[0], 60), max(b[3] - b[1], 60)
        cw = max(bw * 2.6, 380); ch = cw * 9 / 16
        if ch < bh * 2.2: ch = bh * 2.2; cw = ch * 16 / 9
        x0 = int(min(max(cx - cw / 2, 0), W - min(cw, W))); y0 = int(min(max(cy - ch / 2, 0), H - min(ch, H)))
        crop = Image.fromarray(A[i]).crop((x0, y0, x0 + int(min(cw, W)), y0 + int(min(ch, H)))).resize((TILE_W, int(TILE_W * 9 / 16)))
        dr = ImageDraw.Draw(crop); inside = boxes[i] is not None
        lab = f"{len(tiles):02d} {int(t)//60}:{t % 60:04.1f}{'' if inside else '  no blur'}"
        dr.rectangle([0, 0, 12 + 11 * len(lab), 28], fill=(0, 0, 0)); dr.text((6, 3), lab, fill=(255, 230, 0) if inside else (255, 80, 80), font=FONT)
        tiles.append((crop, t, inside))
    per = COLS * ROWS
    for s in range(0, len(tiles), per):
        chunk = tiles[s:s + per]; rows = (len(chunk) + COLS - 1) // COLS; th = chunk[0][0].size[1]
        sheet = Image.new("RGB", (COLS * TILE_W, rows * th + 34), (16, 16, 16))
        ImageDraw.Draw(sheet).text((8, 6), f"{name}  (patch {f/FPS//60:.0f}:{f/FPS%60:04.1f}–{(f+d)/FPS//60:.0f}:{(f+d)/FPS%60:04.1f})", fill=(255, 255, 255), font=FONT)
        for j, (im, t, inside) in enumerate(chunk): sheet.paste(im, ((j % COLS) * TILE_W, 34 + (j // COLS) * th))
        p = os.path.join(out, f"{name}@{f}_{s // per}.jpg"); sheet.save(p, quality=82)
        for j, (im, t, inside) in enumerate(chunk): index.append(f"{os.path.basename(p)}\t{s + j:02d}\t{t:.2f}\t{int(inside)}")
        print(p)
open(os.path.join(out, "index.tsv"), "w").write("\n".join(index) + "\n")
print("BLUR_SWEEP_DONE", out)
