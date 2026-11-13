"""Where to blur in a censored cut (a joint, a pipe, a cannabis-leaf sign, a logo) → work/censor/<job>.json: per-frame
ellipses (0–1 of the frame, top-left origin) that reelgen.censor_blurs() turns into BlurPatch layers (scenes/Censor.tsx).

Usage: work/venv/bin/python -I censor_track.py <project> [job names…]      (jobs: work/censor_jobs.json; none = all)
→ work/censor/<job>.json + work/stills/censor/track_<job>.jpg (24 frames with the ellipses drawn — look at every sheet:
  a joint the tracker missed is the one thing that must not ship). Prints CENSOR_TRACK_DONE.
Why (Halloween vlog censored, 2026-11-09, for YouTube or family): blur only what has to go, so the scenes stay whole —
the user wanted the full-length cut «просто более культурной», not a 5-minute one.
       work/venv/bin/python -I censor_track.py <project> --grid <clip> <a> <b> [step]
→ work/stills/censor/grid_<clip>_<a>.jpg: source frames of that clip with a 10 % grid and source seconds, to read keys off.
Job: {"name", "clip": "c0081", "src": [a, b] (source s), "mode": "follow" | "hands" | "sign" | "box", …}
 follow — THE DEFAULT for a joint (v5, 2026-11-09): keyframes [[t, cx, cy, r], …] (source s; centre 0–1 of the frame,
         r = radius as a share of the frame HEIGHT) on the joint itself (+ the fingers or the lips holding it), read off a
         --grid sheet; linear in between. With "snap": true (default) each frame moves the centre onto the nearest Vision
         hand within 1.3 r of the key (a hand moves faster than keys are placed); no hand there → the key as is. A joint in
         the lips or sticking up out of a fist then ends up outside the blur — there "snap": false and keys on the joint
         (Halloween 2026-11-13: six misses with snap). Only what
         the keys mark is blurred — never a hand that holds a mic. Only the inner 60 % of r is blurred fully (the yellow
         ring on the sheet): make r ≈ 1.5× the half-length of the joint + fingers (Halloween v5: r 0.18 for a close-up).
 hands — (v4; avoid: it blurred every hand near a face — on the beach the hands holding a mic, Halloween v4 censored
         review «слишком много срабатываний, где нету никаких сигарет») Apple Vision faces + hand poses on the 1080 proxy at FPS: the biggest face ("faces": n for more) taller than
         minFace (default 0.12 of the frame) — the smoker — and the hands within reach (2.4 face heights) of it get an
         ellipse (the hand + room for what it holds); a hand within 0.9 face heights of the mouth also blurs the mouth. A face whose hands vanish keeps its last
         ellipses for hold s (a hand at the mouth is often not detected).
 sign  — bright neon cyan/green blobs (the LV cannabis-leaf sign) bigger than minArea inside the optional "region".
 box   — keyframes [[t, cx, cy, rx, ry], …] (source s; rx of the width, ry of the height), linearly interpolated.
Every frame's set also takes its neighbours' ellipses (±1 frame) — a blur that blinks off for one frame shows the joint.
Halloween: the hand pose found the joint at the mouth on the beach and in the bar; it missed a face half out of frame
(a box job filled it) and the sign mode needed cyanFrac 0.03 for a sign seen through motion blur. Wall paintings of a leaf
are box jobs. A job may add "mouthAlways": [[a, b], …] — the mouth blurred with no hand near it (a joint held in the lips).
Apple Vision only (macOS); elsewhere use box jobs.
"""
import glob, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

FPS = 15; W, H = 960, 540
if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]): sys.exit(__doc__)
os.chdir(sys.argv[1]); sys.argv = sys.argv[1:]
OFFS = json.load(open("work/proxy_offsets.json"))

def frame_size(clip):
    """Analysis frames keep the proxy's own aspect (short side 540): a squashed 960×540 frame of a 9:16 proxy made every
    blur 3× too narrow on the canvas (ellipse radii are shares of the width and of the height)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                        f"reel/public/footage/{clip}.mp4"], capture_output=True, text=True, check=True)
    vw, vh = (int(x) for x in r.stdout.strip().split(",")[:2]); k = 540 / min(vw, vh)
    return round(vw * k / 2) * 2, round(vh * k / 2) * 2


def frames(job, tmp):
    a, b = job["src"]; off = OFFS[job["clip"]]
    src = f"reel/public/footage/{job['clip']}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{max(0, a - off):.3f}", "-t", f"{b - a:.3f}", "-i", src,
                    "-vf", f"fps={FPS},scale={W}:{H}", "-q:v", "3", os.path.join(tmp, "%05d.jpg")], check=True)
    return sorted(glob.glob(os.path.join(tmp, "*.jpg")))


def vision(path):
    """faces [(x, y, w, h)] and hands [(x0, y0, x1, y1)], 0–1, top-left origin."""
    import Vision, Quartz
    from Foundation import NSURL
    s = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(path), None); img = Quartz.CGImageSourceCreateImageAtIndex(s, 0, None)
    fr = Vision.VNDetectFaceRectanglesRequest.alloc().init()
    hr = Vision.VNDetectHumanHandPoseRequest.alloc().init(); hr.setMaximumHandCount_(6)
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([fr, hr], None)
    faces = []
    for r in fr.results() or []:
        b = r.boundingBox(); faces.append((b.origin.x, 1 - b.origin.y - b.size.height, b.size.width, b.size.height))
    hands = []
    for o in hr.results() or []:
        pts, _ = o.recognizedPointsForJointsGroupName_error_(Vision.VNHumanHandPoseObservationJointsGroupNameAll, None)
        xy = [(p.location().x, 1 - p.location().y) for p in (pts or {}).values() if p.confidence() > 0.3]
        if len(xy) >= 4:
            xs, ys = zip(*xy); hands.append((min(xs), min(ys), max(xs), max(ys)))
    return faces, hands


def circle(cx, cy, r_px):
    return [round(cx, 4), round(cy, 4), round(r_px / W, 4), round(r_px / H, 4)]


def hands_mode(job, paths):
    min_face = job.get("minFace", 0.12); reach = job.get("reach", 2.4); hold = int(job.get("hold", 0.8) * FPS)
    out, last = [], {}
    for k, p in enumerate(paths):
        faces, hands = vision(p); ell = []
        for fi, (fx, fy, fw, fh) in enumerate(sorted(faces, key=lambda f: -f[3])[:job.get("faces", 1)]):   # the smoker = the biggest face
            if fh < min_face: continue
            fcx, fcy = fx + fw / 2, fy + fh / 2; fh_px = fh * H; mine = []
            mouth = (fcx, fy + 0.8 * fh)
            for (x0, y0, x1, y1) in hands:
                hcx, hcy = (x0 + x1) / 2, (y0 + y1) / 2
                if np.hypot((hcx - fcx) * W, (hcy - fcy) * H) > reach * fh_px: continue
                size = max((x1 - x0) * W, (y1 - y0) * H)
                mine.append(circle(hcx, hcy, 0.6 * size + 0.2 * fh_px))
                if np.hypot((hcx - mouth[0]) * W, (hcy - mouth[1]) * H) < 0.9 * fh_px:   # the hand at the mouth: the joint is there too
                    mine.append(circle(mouth[0], mouth[1], 0.42 * fh_px))
            t = job["src"][0] + k / FPS
            if any(a <= t <= b for a, b in job.get("mouthAlways", [])):   # a joint in the mouth with no hand near it
                mine.append(circle(mouth[0], mouth[1], 0.42 * fh_px))
            key = round(fcx, 1)   # the same face across frames, roughly by position
            if mine: last[key] = (k, mine)
            elif key in last and k - last[key][0] <= hold: mine = last[key][1]
            ell += mine
        out.append(ell)
    return out


def sign_mode(job, paths):
    rg = job.get("region", [0, 0, 1, 1]); min_area = job.get("minArea", 0.006); out = []
    for p in paths:
        im = np.asarray(Image.open(p).convert("HSV")).astype(np.float32) / 255
        h, s, v = im[..., 0] * 360, im[..., 1], im[..., 2]
        cyan = (v > 0.75) & (s > 0.3) & (h > 140) & (h < 200)
        m = cyan | ((s < 0.25) & (v > 0.95))
        m[:int(rg[1] * H)] = False; m[int(rg[3] * H):] = False; m[:, :int(rg[0] * W)] = False; m[:, int(rg[2] * W):] = False
        m = ndimage.binary_dilation(m, iterations=6)
        lab, n = ndimage.label(m); ell = []
        for sl in ndimage.find_objects(lab):
            ys, xs = sl; bw, bh = (xs.stop - xs.start), (ys.stop - ys.start)
            if bw * bh < min_area * W * H or not (0.35 < bw / max(bh, 1) < 2.8): continue
            if cyan[sl].sum() < job.get("cyanFrac", 0.08) * bw * bh: continue   # string lights and screens are white, the LV leaf is neon cyan
            ell.append(circle((xs.start + bw / 2) / W, (ys.start + bh / 2) / H, 0.62 * max(bw, bh) + 12))
        out.append(ell)
    return out


def follow_mode(job, paths):
    kf = sorted(job["keys"]); a = job["src"][0]; snap = job.get("snap", True); out = []
    for k, p in enumerate(paths):
        t = a + k / FPS
        if t <= kf[0][0]: v = kf[0][1:]
        elif t >= kf[-1][0]: v = kf[-1][1:]
        else:
            i = next(i for i in range(len(kf) - 1) if kf[i][0] <= t <= kf[i + 1][0]); u = (t - kf[i][0]) / max(1e-6, kf[i + 1][0] - kf[i][0])
            v = [kf[i][j] + u * (kf[i + 1][j] - kf[i][j]) for j in range(1, 4)]
        cx, cy, r = v
        if snap:
            _, hands = vision(p)
            best = None
            for (x0, y0, x1, y1) in hands:
                hx, hy = (x0 + x1) / 2, (y0 + y1) / 2; d = np.hypot((hx - cx) * W, (hy - cy) * H) / H
                if d < 1.3 * r and (best is None or d < best[0]): best = (d, hx, hy)
            if best: cx, cy = 0.35 * cx + 0.65 * best[1], 0.35 * cy + 0.65 * best[2]
        out.append([circle(cx, cy, r * H)])
    return out


def grid(clip, a, b, step=0.5):
    """Source frames of a clip with a 10 % grid and their source seconds — read follow / box keys off it."""
    global W, H
    job = {"clip": clip, "src": [a, b]}; W, H = frame_size(clip); tw, th = W // 2, H // 2
    with tempfile.TemporaryDirectory() as tmp:
        paths = frames(job, tmp); idx = list(range(0, len(paths), max(1, int(round(step * FPS)))))[:24]; tiles = []
        for i in idx:
            im = Image.open(paths[i]).convert("RGB").resize((tw, th)); d = ImageDraw.Draw(im)
            for g in range(1, 10):
                d.line([(g * tw / 10, 0), (g * tw / 10, th)], fill=(255, 255, 0) if g == 5 else (90, 90, 90)); d.line([(0, g * th / 10), (tw, g * th / 10)], fill=(255, 255, 0) if g == 5 else (90, 90, 90))
            d.rectangle([0, 0, 70, 14], fill=(0, 0, 0)); d.text((3, 2), f"{a + i / FPS:.2f}s", fill=(255, 255, 0)); tiles.append(im)
        s = Image.new("RGB", (4 * tw, ((len(tiles) + 3) // 4) * th))
        for k, t in enumerate(tiles): s.paste(t, ((k % 4) * tw, (k // 4) * th))
        out = f"work/stills/censor/grid_{clip}_{a:.1f}.jpg"; os.makedirs(os.path.dirname(out), exist_ok=True); s.save(out, quality=84); print(out)


def box_mode(job, n):
    kf = sorted(job["keys"]); a = job["src"][0]; out = []
    for k in range(n):
        t = a + k / FPS
        if t <= kf[0][0]: v = kf[0][1:]
        elif t >= kf[-1][0]: v = kf[-1][1:]
        else:
            i = next(i for i in range(len(kf) - 1) if kf[i][0] <= t <= kf[i + 1][0]); u = (t - kf[i][0]) / max(1e-6, kf[i + 1][0] - kf[i][0])
            v = [kf[i][j] + u * (kf[i + 1][j] - kf[i][j]) for j in range(1, 5)]
        out.append([[round(x, 4) for x in v]])
    return out


def sheet(job, paths, ell, out):
    idx = list(range(0, len(paths), max(1, len(paths) // 24)))[:24]; tiles = []; tw, th = W // 3, H // 3
    for i in idx:
        im = Image.open(paths[i]).convert("RGB").resize((tw, th)); d = ImageDraw.Draw(im)
        for cx, cy, rx, ry in ell[i]:   # red: the soft edge; yellow: the core BlurPatch blurs fully (black 60 % of the radius)
            d.ellipse([(cx - rx) * tw, (cy - ry) * th, (cx + rx) * tw, (cy + ry) * th], outline=(255, 0, 0), width=2)
            d.ellipse([(cx - 0.6 * rx) * tw, (cy - 0.6 * ry) * th, (cx + 0.6 * rx) * tw, (cy + 0.6 * ry) * th], outline=(255, 230, 0), width=2)
        d.text((6, 4), f"{job['src'][0] + i / FPS:.1f}s", fill=(255, 255, 0)); tiles.append(im)
    s = Image.new("RGB", (6 * tw, ((len(tiles) + 5) // 6) * th))
    for k, t in enumerate(tiles): s.paste(t, ((k % 6) * tw, (k // 6) * th))
    s.save(out, quality=82)


if "--grid" in sys.argv:
    g = sys.argv[sys.argv.index("--grid") + 1:]; grid(g[0], float(g[1]), float(g[2]), float(g[3]) if len(g) > 3 else 0.5); sys.exit(0)
jobs = json.load(open("work/censor_jobs.json")); want = [x for x in sys.argv[1:] if not x.startswith("--")]
os.makedirs("work/censor", exist_ok=True); os.makedirs("work/stills/censor", exist_ok=True)
for job in jobs:
    if want and job["name"] not in want: continue
    W, H = frame_size(job["clip"])
    with tempfile.TemporaryDirectory() as tmp:
        paths = frames(job, tmp)
        mode = job["mode"]
        raw = follow_mode(job, paths) if mode == "follow" else hands_mode(job, paths) if mode == "hands" else sign_mode(job, paths) if mode == "sign" else box_mode(job, len(paths))
        ell = [raw[k] + (raw[k - 1] if k else []) + (raw[k + 1] if k + 1 < len(raw) else []) for k in range(len(raw))]
        json.dump({"clip": job["clip"], "src": job["src"], "fps": FPS, "ellipses": ell}, open(f"work/censor/{job['name']}.json", "w"))
        sheet(job, paths, ell, f"work/stills/censor/track_{job['name']}.jpg")
        print(f"{job['name']}: {len(paths)} frames, {sum(1 for e in raw if e)} with a blur, max {max((len(e) for e in raw), default=0)} ellipses", flush=True)
print("CENSOR_TRACK_DONE")
