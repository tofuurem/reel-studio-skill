#!/usr/bin/env python3
"""Frame-exact transparent cutout of the people in a video (VP9 WebM with alpha) for the "text behind the person" effect.

Usage: work/venv/bin/python -I person_matte.py <in.mp4> <out.webm> [--from S] [--to S] [--mode auto|birefnet|person|subject]
           [--feather PX] [--quality accurate|balanced] [--fps 30]
Layers in Remotion: base video -> title -> this cutout (<OffthreadVideo transparent src=out.webm/>), same size/fps/frames.
--from/--to are seconds in the input; output frame N == input frame round(from*fps)+N (prints both frame counts).
--mode birefnet: BiRefNet (MIT, ZhengPeng7/BiRefNet, torch on MPS/CUDA/CPU) — the person WITH what they wear and hold
                 (over-ear headphones, glasses, caps, a phone), crisp edges, real gaps (between a headband and the head) kept
                 open. It runs on one fixed crop around the people (found on a few sampled frames, margins for hair and hands),
                 so a small figure in a 16:9 frame still gets ~1000 px of model input. ≈ 0.7 s per frame on Apple Silicon;
                 the weights (≈ 420 MB) download once into ~/.cache/huggingface on the first run.
--mode person  : Apple Vision person segmentation (macOS). Low-res, people only: over-ear headphones fall OUT of the mask
                 (the title showed through the ear cups as a haze, reel_studio_skill hook, 2026-11-06).
--mode subject : Apple Vision foreground instance mask (macOS 14+) — missed the ear cups on that footage too.
--mode auto    : birefnet when torch + transformers import in this venv (deps.py installs them on macOS), else person.
Temporal: a per-frame model flickers at the edges, and a plain moving average leaves ghost trails when the person moves →
the previous mask is blended in (0.4) only where the picture itself did not change (|frame − previous frame| small).
Outputs: <out.webm>; <out>.mask.json {fps,width,height,from_frame,mode,crop,frames:[{coverage,bbox:[x0,y0,x1,y1]|null}]}
(0-1, top-left); <out>.alpha.npz (alpha at 1/8 size, uint8 [frames,h,w] — common.title_y places the title from it);
line PERSON_MATTE_DONE <out> <frames> frames, person coverage min/mean/max %. WARNs if nobody is found on >20% of frames.
Needs ffmpeg with libvpx-vp9. Cut the range first: only the frames of the shot are processed.
"""
import sys, os, json, subprocess, argparse, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import add_guard_args, guard_reexec

BIREFNET = ("ZhengPeng7/BiRefNet", "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4")   # pinned: the repo ships its own model code
MODEL_SIDE = 1024

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--from", dest="t0", type=float, default=0.0); ap.add_argument("--to", dest="t1", type=float, default=None)
ap.add_argument("--mode", choices=["auto", "birefnet", "person", "subject"], default="auto")
ap.add_argument("--feather", type=float, default=None, help="px at 1080 wide (scaled with width); default 1 for birefnet, 2 for Vision")
ap.add_argument("--quality", choices=["accurate", "balanced"], default="accurate", help="Vision person mode only")
ap.add_argument("--fps", type=float, default=30.0)
ap.add_argument("--choke", type=float, default=None, help="alpha below this → 0 and the edge ramp tightened (default 0.15 birefnet, 0 Vision): "
                "half-transparent edge pixels mix the background into a dark fringe over a white title")
add_guard_args(ap, 10.0)   # BiRefNet at 1024 px on MPS (unified memory)
a = ap.parse_args(); guard_reexec(a)


def has_torch():
    try:
        import torch, transformers  # noqa: F401
        return True
    except Exception:
        return False


mode = a.mode
if mode == "auto": mode = "birefnet" if has_torch() else "person"
if mode == "birefnet" and not has_torch(): sys.exit("person_matte --mode birefnet needs torch + transformers in this venv: python3 -I deps.py --install")
if mode in ("person", "subject") and sys.platform != "darwin": sys.exit("Vision modes need macOS — use --mode birefnet")
feather = a.feather if a.feather is not None else (1.0 if mode == "birefnet" else 2.0)
choke = a.choke if a.choke is not None else (0.15 if mode == "birefnet" else 0.0)


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


def decoder(select):
    return subprocess.Popen(["ffmpeg", "-v", "error", "-i", a.src, "-vf", f"fps={fps},select='{select}',setpts=N/{fps}/TB",
                             "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)


def resize(m, w, h):
    """Bilinear resize with numpy (no PIL needed)."""
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


def down(x, s):
    h, w = x.shape[0] // s * s, x.shape[1] // s * s
    return x[:h, :w].reshape(h // s, s, w // s, s).mean((1, 3))


# ---------------------------------------------------------------- segmenters: RGB uint8 frame → float32 [0,1] mask (any size) or None
if mode == "birefnet":
    import torch
    from transformers import AutoModelForImageSegmentation
    dev = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if dev != "cpu" else torch.float32
    model = AutoModelForImageSegmentation.from_pretrained(BIREFNET[0], revision=BIREFNET[1], trust_remote_code=True).eval().to(dev).to(dtype)
    MEAN = torch.tensor([0.485, 0.456, 0.406], device=dev).view(1, 3, 1, 1); STD = torch.tensor([0.229, 0.224, 0.225], device=dev).view(1, 3, 1, 1)

    def birefnet(rgb):
        """rgb HxWx3 uint8 → alpha HxW float32; the model runs at MODEL_SIDE² (BiRefNet's training size)."""
        h, w = rgb.shape[:2]
        x = torch.from_numpy(np.array(rgb)).to(dev).permute(2, 0, 1)[None].float() / 255
        x = torch.nn.functional.interpolate(x, (MODEL_SIDE, MODEL_SIDE), mode="bilinear", align_corners=False, antialias=True)
        with torch.no_grad():
            p = model(((x - MEAN) / STD).to(dtype))[-1].float().sigmoid()
        return torch.nn.functional.interpolate(p, (h, w), mode="bilinear", align_corners=False)[0, 0].clamp(0, 1).cpu().numpy()
else:
    import Vision, Quartz
    cs = Quartz.CGColorSpaceCreateDeviceRGB()

    def cgimage(buf, w, h):
        prov = Quartz.CGDataProviderCreateWithData(None, buf, len(buf), None)
        return Quartz.CGImageCreate(w, h, 8, 24, w * 3, cs, Quartz.kCGImageAlphaNone, prov, None, False, Quartz.kCGRenderingIntentDefault)

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

    def vision(rgb):
        img = cgimage(rgb.tobytes(), rgb.shape[1], rgb.shape[0])
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
        if mode == "person":
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


def find_crop():
    """BiRefNet: one fixed crop (x0, y0, x1, y1 in px) around the people of the whole range — the model sees them big, and a
    fixed crop keeps the edges consistent from frame to frame. Found on up to 6 sampled frames at full view; margins for hair,
    raised hands and headphones; the full frame when the people fill most of it."""
    picks = sorted({f0 + round(i * (expected - 1) / 5) for i in range(6)} if expected > 1 else {f0})
    dec = decoder("+".join(f"eq(n\\,{p})" for p in picks)); boxes = []
    while True:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz: break
        m = birefnet(np.frombuffer(buf, np.uint8).reshape(H, W, 3)) > .5
        if m.mean() > .002:
            ys, xs = np.where(m.any(1))[0], np.where(m.any(0))[0]; boxes.append((xs[0], ys[0], xs[-1] + 1, ys[-1] + 1))
    dec.wait()
    if not boxes: return 0, 0, W, H
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes); x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    bw, bh = x1 - x0, y1 - y0; mx, my = .25 * bw + .03 * W, .15 * bh + .03 * H
    x0, x1, y0, y1 = max(0, x0 - mx), min(W, x1 + mx), max(0, y0 - my), min(H, y1 + my)
    side = min(MODEL_SIDE, W, H)   # never feed the model fewer pixels than it works at
    if x1 - x0 < side:
        x0 = max(0, min(W - side, (x0 + x1 - side) / 2)); x1 = x0 + side
    if y1 - y0 < side:
        y0 = max(0, min(H - side, (y0 + y1 - side) / 2)); y1 = y0 + side
    x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
    return (0, 0, W, H) if (x1 - x0) * (y1 - y0) > .8 * W * H else (x0, y0, x1, y1)


crop = find_crop() if mode == "birefnet" else (0, 0, W, H)
cx0, cy0, cx1, cy1 = crop


def segment(rgb):
    if mode == "birefnet":
        m = np.zeros((H, W), np.float32); m[cy0:cy1, cx0:cx1] = birefnet(rgb[cy0:cy1, cx0:cx1]); return m
    m = vision(rgb)
    return None if m is None else resize(m, W, H)


dec = decoder(f"between(n\\,{f0}\\,{f1 - 1})")
part = a.dst + ".part.webm"
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-b:v", "0", "-crf", "18", "-row-mt", "1",
                        "-deadline", "good", "-cpu-used", "2", part], stdin=subprocess.PIPE)
sigma = feather * W / 1080.0
prev = prev_g = None; stats = []; small = []; n = 0; t_start = time.time()
while True:
    buf = dec.stdout.read(fsz)
    if len(buf) < fsz: break
    rgb = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    m = segment(rgb)
    if m is None: m = np.zeros((H, W), np.float32)
    g = down(rgb.mean(2).astype(np.float32) / 255, 8)
    if prev is not None:
        still = (blur(np.abs(g - prev_g), 1.5) < .025).astype(np.float32)   # the picture did not change here
        m = m + resize(still, W, H) * .4 * (prev - m)
    prev, prev_g = m, g
    out = np.clip((blur(m, sigma) - choke) / (1 - 1.5 * choke), 0, 1)        # tighter edge: no background fringe over the title
    cov = float(out.mean()); sel = out > .5
    if sel.any():
        ys, xs = np.where(sel.any(1))[0], np.where(sel.any(0))[0]
        bbox = [round(xs[0] / W, 4), round(ys[0] / H, 4), round((xs[-1] + 1) / W, 4), round((ys[-1] + 1) / H, 4)]
    else: bbox = None
    stats.append({"coverage": round(cov, 5), "bbox": bbox}); small.append((down(out, 8) * 255 + .5).astype(np.uint8))
    rgba = np.empty((H, W, 4), np.uint8); rgba[..., :3] = rgb; rgba[..., 3] = (out * 255 + .5).astype(np.uint8)
    enc.stdin.write(rgba.tobytes()); n += 1
    if n % 30 == 0: print(f"  {n}/{expected} frames, {(time.time() - t_start) / n:.2f}s/frame", file=sys.stderr, flush=True)
enc.stdin.close(); dec.wait()
if enc.wait() != 0: sys.exit("encoder failed")
print(f"frames: input range {expected}, output {n}, {(time.time() - t_start) / max(n, 1):.2f}s/frame, mode {mode}, crop {list(crop)}")
if n != expected: sys.exit(f"FRAME COUNT MISMATCH: expected {expected}, got {n}")
os.replace(part, a.dst)
base = a.dst[:-5] if a.dst.endswith(".webm") else a.dst
json.dump({"fps": fps, "width": W, "height": H, "from_frame": f0, "mode": mode, "crop": list(crop), "frames": stats}, open(base + ".mask.json", "w"))
np.savez_compressed(base + ".alpha.npz", alpha=np.stack(small))
c = np.array([s["coverage"] for s in stats]) * 100
print(f"PERSON_MATTE_DONE {a.dst} {n} frames, person coverage {c.min():.1f}/{c.mean():.1f}/{c.max():.1f} %")
if (c < 0.3).mean() > 0.2: print("WARN: nobody found on >20% of frames; check the shot has a person (or try another --mode)")
