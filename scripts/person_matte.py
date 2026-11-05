#!/usr/bin/env python3
"""Frame-exact transparent cutout of the people in a video (VP9 WebM with alpha) for the "text behind the person" effect.

Usage: work/venv/bin/python -I person_matte.py <in.mp4> <out.webm> [--from S] [--to S] [--mode person|subject]
           [--feather PX] [--quality accurate|balanced] [--fps 30]
Layers in Remotion: base video -> title -> this cutout (<OffthreadVideo transparent src=out.webm/>), same size/fps/frames.
--from/--to are seconds in the input; output frame N == input frame round(from*fps)+N (prints both frame counts).
--mode person  : Vision person segmentation (fast, people only).  --mode subject: foreground instance mask, macOS 14+
                 (all instances; also catches costumes/props that person mode misses, but may add held objects).
Mask: scaled to the frame, temporal smoothing (0.35 previous), gaussian feather (default 2px per 1080 width).
Outputs: <out.webm>, <out>.mask.json {fps,width,height,from_frame,frames:[{coverage,bbox:[x0,y0,x1,y1]|null}]} (0-1, top-left),
         line PERSON_MATTE_DONE <out> <frames> frames, person coverage min/mean/max %. WARNs if nobody is found on >20% of frames.
Needs ffmpeg with libvpx-vp9 and the pyobjc venv (numpy only, no PIL). Slow (about a second per 1440x2560 frame): cut the range first.
"""
import sys, os, json, subprocess, argparse, time
if sys.platform != "darwin": sys.exit("person_matte.py needs Apple Vision (macOS only) — no title behind the person on this platform (deps.py)")
import numpy as np
import Vision, Quartz

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--from", dest="t0", type=float, default=0.0); ap.add_argument("--to", dest="t1", type=float, default=None)
ap.add_argument("--mode", choices=["person", "subject"], default="person")
ap.add_argument("--feather", type=float, default=2.0, help="px at 1080 wide (scaled with width)")
ap.add_argument("--quality", choices=["accurate", "balanced"], default="accurate")
ap.add_argument("--fps", type=float, default=30.0)
a = ap.parse_args()

def probe(args): return subprocess.run(["ffprobe", "-v", "error", *args, a.src], capture_output=True, text=True).stdout.strip()
_s = json.loads(probe(["-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json"]))["streams"][0]
W, H = int(_s["width"]), int(_s["height"])  # input is expected to be unrotated (cropped proxy / shot piece)
fps = a.fps
f0 = round(a.t0 * fps)
total = int(probe(["-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0"]).split()[0])
f1 = min(round(a.t1 * fps), total) if a.t1 is not None else total
expected = f1 - f0
if expected <= 0: sys.exit(f"empty range: frames {f0}..{f1} of {total}")
fsz = W * H * 3
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.src, "-vf", f"fps={fps},select='between(n\\,{f0}\\,{f1 - 1})',setpts=N/{fps}/TB",
                        "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
part = a.dst + ".part.webm"
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-b:v", "0", "-crf", "20", "-row-mt", "1",
                        "-deadline", "good", "-cpu-used", "2", part], stdin=subprocess.PIPE)

cs = Quartz.CGColorSpaceCreateDeviceRGB()
def cgimage(buf):
    prov = Quartz.CGDataProviderCreateWithData(None, buf, len(buf), None)
    return Quartz.CGImageCreate(W, H, 8, 24, W * 3, cs, Quartz.kCGImageAlphaNone, prov, None, False, Quartz.kCGRenderingIntentDefault)

def pb_array(pb):
    """CVPixelBuffer (8-bit or float32 one-component) -> float32 [0,1] array."""
    Quartz.CVPixelBufferLockBaseAddress(pb, 1)
    try:
        w, h = Quartz.CVPixelBufferGetWidth(pb), Quartz.CVPixelBufferGetHeight(pb); bpr = Quartz.CVPixelBufferGetBytesPerRow(pb)
        raw = bytes(Quartz.CVPixelBufferGetBaseAddress(pb).as_buffer(bpr * h))
    finally: Quartz.CVPixelBufferUnlockBaseAddress(pb, 1)
    if Quartz.CVPixelBufferGetPixelFormatType(pb) == 0x4C303066:  # 'L00f'
        return np.frombuffer(raw, np.uint8).reshape(h, bpr)[:, :w * 4].copy().view(np.float32).reshape(h, w).clip(0, 1)
    return np.frombuffer(raw, np.uint8).reshape(h, bpr)[:, :w].astype(np.float32) / 255.0

def resize(m, w, h):
    """Bilinear resize with numpy (no PIL in the venv)."""
    if m.shape == (h, w): return m
    ys = np.clip((np.arange(h) + .5) * m.shape[0] / h - .5, 0, m.shape[0] - 1); xs = np.clip((np.arange(w) + .5) * m.shape[1] / w - .5, 0, m.shape[1] - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int); y1, x1 = np.minimum(y0 + 1, m.shape[0] - 1), np.minimum(x0 + 1, m.shape[1] - 1)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    top = m[y0][:, x0] * (1 - fx) + m[y0][:, x1] * fx; bot = m[y1][:, x0] * (1 - fx) + m[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy

def blur(m, sigma):
    if sigma < .3: return m
    r = int(sigma * 3); k = np.exp(-(np.arange(-r, r + 1) ** 2) / (2 * sigma ** 2)); k /= k.sum()
    p = np.pad(m, ((0, 0), (r, r)), mode="edge"); m = sum(k[i] * p[:, i:i + m.shape[1]] for i in range(2 * r + 1))
    p = np.pad(m, ((r, r), (0, 0)), mode="edge"); return sum(k[i] * p[i:i + m.shape[0]] for i in range(2 * r + 1))

def segment(img):
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
    if a.mode == "person":
        req = Vision.VNGeneratePersonSegmentationRequest.alloc().initWithCompletionHandler_(None)
        req.setQualityLevel_(Vision.VNGeneratePersonSegmentationRequestQualityLevelAccurate if a.quality == "accurate"
                             else Vision.VNGeneratePersonSegmentationRequestQualityLevelBalanced)
        ok, err = handler.performRequests_error_([req], None)
        if not ok: sys.exit(f"vision failed: {err}")
        res = req.results()
        return pb_array(res[0].pixelBuffer()) if res else None
    req = Vision.VNGenerateForegroundInstanceMaskRequest.alloc().init()
    ok, err = handler.performRequests_error_([req], None)
    if not ok: sys.exit(f"vision failed: {err}")
    res = req.results()
    if not res or len(res[0].allInstances()) == 0: return None
    pb, err = res[0].generateScaledMaskForImageForInstances_fromRequestHandler_error_(res[0].allInstances(), handler, None)
    return pb_array(pb) if pb is not None else None

sigma = a.feather * W / 1080.0
prev = None; stats = []; n = 0; t_start = time.time()
while True:
    buf = dec.stdout.read(fsz)
    if len(buf) < fsz: break
    m = segment(cgimage(buf))
    m = np.zeros((H, W), np.float32) if m is None else resize(m, W, H)
    if prev is not None: m = 0.65 * m + 0.35 * prev
    prev = m
    m = np.clip(blur(m, sigma), 0, 1)
    cov = float(m.mean()); sel = m > .5
    if sel.any():
        ys, xs = np.where(sel.any(1))[0], np.where(sel.any(0))[0]
        bbox = [round(xs[0] / W, 4), round(ys[0] / H, 4), round((xs[-1] + 1) / W, 4), round((ys[-1] + 1) / H, 4)]
    else: bbox = None
    stats.append({"coverage": round(cov, 5), "bbox": bbox})
    rgba = np.empty((H, W, 4), np.uint8); rgba[..., :3] = np.frombuffer(buf, np.uint8).reshape(H, W, 3); rgba[..., 3] = (m * 255 + .5).astype(np.uint8)
    enc.stdin.write(rgba.tobytes()); n += 1
    if n % 30 == 0: print(f"  {n}/{expected} frames, {(time.time() - t_start) / n:.2f}s/frame", file=sys.stderr, flush=True)
enc.stdin.close(); dec.wait()
if enc.wait() != 0: sys.exit("encoder failed")
print(f"frames: input range {expected}, output {n}, {(time.time() - t_start) / max(n, 1):.2f}s/frame")
if n != expected: sys.exit(f"FRAME COUNT MISMATCH: expected {expected}, got {n}")
os.replace(part, a.dst)
json.dump({"fps": fps, "width": W, "height": H, "from_frame": f0, "mode": a.mode, "frames": stats}, open(a.dst + ".mask.json" if not a.dst.endswith(".webm") else a.dst[:-5] + ".mask.json", "w"))
c = np.array([s["coverage"] for s in stats]) * 100
print(f"PERSON_MATTE_DONE {a.dst} {n} frames, person coverage {c.min():.1f}/{c.mean():.1f}/{c.max():.1f} %")
if (c < 0.3).mean() > 0.2: print("WARN: nobody found on >20% of frames; try --mode subject (or check the shot has a person)")
