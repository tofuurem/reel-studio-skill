#!/usr/bin/env python3
"""Cut the main subject(s) out of an image with macOS Vision "subject lifting" → RGBA PNG (for covers, stickers, floating heroes).

Usage: work/venv/bin/python -I cutout.py <in.jpg|png> <out.png> [--crop]      (--crop trims to the subject's bounding box)
Works on photos (a person in a room) and on renders with a flat background. Needs macOS 14+ and work/venv (pyobjc Vision).
Check the result on a coloured background: thin things (fingers against bright windows, hair wisps) can lose pixels —
then pick another frame rather than fixing the mask by hand.
"""
import sys, os
if sys.platform != "darwin": sys.exit("cutout.py needs Apple Vision (macOS only) — use a generated cover plate instead (deps.py)")
import Vision, Quartz
from Foundation import NSURL
src, dst = sys.argv[1], sys.argv[2]; crop = "--crop" in sys.argv
isrc = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(os.path.abspath(src)), None)
img = Quartz.CGImageSourceCreateImageAtIndex(isrc, 0, None)
if img is None: sys.exit(f"cannot read {src}")
handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
req = Vision.VNGenerateForegroundInstanceMaskRequest.alloc().init()
ok, err = handler.performRequests_error_([req], None)
if not ok or not req.results(): sys.exit(f"no subject found in {src}: {err}")
obs = req.results()[0]
buf, err = obs.generateMaskedImageOfInstances_fromRequestHandler_croppedToInstancesExtent_error_(obs.allInstances(), handler, crop, None)
if buf is None: sys.exit(f"mask failed: {err}")
ci = Quartz.CIImage.imageWithCVPixelBuffer_(buf)
ctx = Quartz.CIContext.contextWithOptions_(None)
cs = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
ok, err = ctx.writePNGRepresentationOfImage_toURL_format_colorSpace_options_error_(ci, NSURL.fileURLWithPath_(os.path.abspath(dst)), Quartz.kCIFormatRGBA8, cs, {}, None)
if not ok: sys.exit(f"write failed: {err}")
e = ci.extent(); print(f"CUTOUT_OK {dst} {int(e.size.width)}x{int(e.size.height)} instances={len(obs.allInstances())}")
