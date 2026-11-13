"""Head tracks for the name tags (v5, 2026-11-09: «кто это именно, хотя бы первый раз») → work/names/<job>.json.

Usage: work/venv/bin/python -I name_tracks.py <project>      (jobs: work/name_jobs.json) → NAME_TRACKS_DONE
Then in gen_reel.py: per work/names/<id>.json a <NameTag> (scenes/NameTag.tsx) in a Sequence over its segment, with the
segment's punch / drift from work/timeline_zoom.json (like BlurPatch) — see craft/scenes.md «Who is who».
Job: {"id", "name", "role"?, "clip", "src": [a, b] (source s), "hint": [x, y] — the head at a (0–1 of the frame),
      "place"?: "above" (default) | "below" | "left" | "right" (a head near the top edge: beside it),
      "keys"?: [[t, cx, top, w, h], …] instead of Vision (a helmet hides the face)}
Apple Vision faces on the 1080 proxy at 15 fps: the face nearest the hint, then the one nearest the last position (a jump
over 0.15 of the frame is someone else → hold); missing frames hold; a 5-frame moving average takes the jitter out.
Writes {clip, src, fps, box: [[cx, top, w, h]…], below} (below = the head is near the top: the tag goes under the chin) and
work/stills/names/<job>.jpg with the boxes drawn.
"""
import glob, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]): sys.exit(__doc__)
os.chdir(sys.argv[1])
FPS = 15; W, H = 960, 540
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
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{max(0, a - off):.3f}", "-t", f"{b - a:.3f}", "-i", f"reel/public/footage/{job['clip']}.mp4",
                    "-vf", f"fps={FPS},scale={W}:{H}", "-q:v", "3", os.path.join(tmp, "%05d.jpg")], check=True)
    return sorted(glob.glob(os.path.join(tmp, "*.jpg")))

def faces(path):
    import Vision, Quartz
    from Foundation import NSURL
    s = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(path), None); img = Quartz.CGImageSourceCreateImageAtIndex(s, 0, None)
    fr = Vision.VNDetectFaceRectanglesRequest.alloc().init()
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([fr], None)
    out = []
    for r in fr.results() or []:
        b = r.boundingBox(); out.append((b.origin.x + b.size.width / 2, 1 - b.origin.y - b.size.height, b.size.width, b.size.height))
    return out

os.makedirs("work/names", exist_ok=True); os.makedirs("work/stills/names", exist_ok=True)
for job in json.load(open("work/name_jobs.json")):
    W, H = frame_size(job["clip"]); tw, th = W // 3, H // 3
    with tempfile.TemporaryDirectory() as tmp:
        paths = frames(job, tmp); box = []
        if job.get("keys"):
            kf = sorted(job["keys"])
            for k in range(len(paths)):
                t = job["src"][0] + k / FPS
                if t <= kf[0][0]: v = kf[0][1:]
                elif t >= kf[-1][0]: v = kf[-1][1:]
                else:
                    i = next(i for i in range(len(kf) - 1) if kf[i][0] <= t <= kf[i + 1][0]); u = (t - kf[i][0]) / max(1e-6, kf[i + 1][0] - kf[i][0])
                    v = [kf[i][j] + u * (kf[i + 1][j] - kf[i][j]) for j in range(1, 5)]
                box.append(list(v))
        else:
            last = None; ref = job["hint"]
            for p in paths:
                fs = faces(p); cand = None
                if fs:
                    c = min(fs, key=lambda f: np.hypot(f[0] - ref[0], (f[1] + f[3] / 2) - ref[1]))
                    if last is None or np.hypot(c[0] - last[0], c[1] - last[1]) < 0.15: cand = list(c)
                if cand: last = cand; ref = [cand[0], cand[1] + cand[3] / 2]
                box.append(list(last) if last else None)
            first = next((b for b in box if b), None)
            if first is None: print(job["name"], "NO FACE — give keys"); continue
            box = [b if b else first for b in box]
            for i in range(len(box)):
                if box[i] is first: break
            arr = np.array(box); k = 5; pad = np.pad(arr, ((k // 2, k // 2), (0, 0)), mode="edge")
            box = [list(np.mean(pad[i: i + k], axis=0)) for i in range(len(arr))]
        below = float(np.median([b[1] for b in box])) < 0.16
        place = job.get("place") or ("below" if below else "above")   # "left" / "right": beside the head at eye level
        out = {"name": job["name"], "role": job.get("role"), "clip": job["clip"], "src": job["src"], "fps": FPS, "below": below, "place": place, "box": [[round(x, 4) for x in b] for b in box]}
        json.dump(out, open(f"work/names/{job['id']}.json", "w"), ensure_ascii=False)
        idx = list(range(0, len(paths), max(1, len(paths) // 6)))[:6]; tiles = []
        for i in idx:
            im = Image.open(paths[i]).convert("RGB").resize((tw, th)); d = ImageDraw.Draw(im); cx, top, w, h = box[i]
            d.rectangle([(cx - w / 2) * tw, top * th, (cx + w / 2) * tw, (top + h) * th], outline=(0, 255, 0), width=2)
            ty = (top + h + 0.02) * th if below else (top - 0.025) * th
            d.ellipse([cx * tw - 4, ty - 4, cx * tw + 4, ty + 4], fill=(255, 0, 0)); tiles.append(im)
        s = Image.new("RGB", (len(tiles) * tw, th))
        for k, t in enumerate(tiles): s.paste(t, (k * tw, 0))
        s.save(f"work/stills/names/{job['id']}.jpg", quality=85)
        print(f"{job['id']}: {len(box)} frames, below={below}")
print("NAME_TRACKS_DONE")
