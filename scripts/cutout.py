#!/usr/bin/env python3
"""Cut the main subject(s) out of an image → RGBA PNG (for covers, stickers, floating heroes).

Usage: work/venv/bin/python -I cutout.py <in.jpg|png> <out.png> [--crop] [--engine vision|birefnet]   (--crop trims to the subject)
Engines (engines.py, cap cutout): vision = macOS "subject lifting" (foreground instance mask, macOS 14+), the default on macOS;
birefnet = BiRefNet (the person_matte.py model; torch in work/venv), the default elsewhere — it keeps what a person holds
and wears, and on a busy background may also keep a big foreground object.
Works on photos (a person in a room) and on renders with a flat background. Check the result on a coloured background: thin
things (fingers against bright windows, hair wisps) can lose pixels — then pick another frame rather than fixing the mask by hand.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engines

ap = argparse.ArgumentParser(description="Cut the main subject out of an image → RGBA PNG.")
ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--crop", action="store_true", help="trim to the subject's bounding box")
ap.add_argument("--engine", choices=engines.ENGINES["cutout"], help="cutout engine (default: engines.py choice — vision on macOS, birefnet elsewhere)")
a = ap.parse_args()
e = engines.require("cutout", "cutout.py", a.engine)
w, h, note = engines.cutout(a.src, a.dst, e, a.crop)
print(f"CUTOUT_OK {a.dst} {w}x{h} {note}" + ("" if e == "vision" else f" engine={e}"))
