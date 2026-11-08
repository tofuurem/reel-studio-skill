#!/usr/bin/env python3
"""HDR (HLG / PQ, BT.2020) → SDR Rec.709 3D LUTs, generated locally — iPhone «HDR video», Android HDR10, DJI / Sony HLG.

Usage: python3 -I hdr_lut.py [--out ~/.cache/reel-studio/luts] [--size 65]     → HLG_BT2020_to_Rec709.cube, PQ_BT2020_to_Rec709.cube
       (common.hdr_lut() writes them on first use; make_proxies / inventory / night_lift pick them for HDR sources)

Why: Chrome and the proxies are SDR Rec.709. An HLG clip tagged bt709 without conversion looks grey, flat and pale (the
2026-11-08 check on iPhone 13 clips) — the transfer curve and the wide BT.2020 primaries are read as Rec.709.

The chain per RGB triplet (input is the source's non-linear R'G'B', full range, decoded with the BT.2020 matrix):
  HLG: inverse OETF → scene light → OOTF (Lw 1000 nits, γ 1.2) → display light in nits     (ITU-R BT.2100)
  PQ:  EOTF → display light in nits
  → BT.2020 → BT.709 primaries (linear) → HDR reference white (203 nits, BT.2408) scaled by `white` → saturation `sat`
  → an exponential roll-off of the luminance from `knee` up (hue kept: RGB scaled by the luminance ratio) → out-of-gamut
  colours pulled to their luminance → BT.1886 inverse (γ `gamma`).
The defaults were fitted (2026-11-08) to Apple's own conversion (VideoToolbox `scale_vt`, what Photos / QuickTime show) on
four iPhone 13 HLG clips — day, night, indoor: the fitted knee is so low that the roll-off is one soft curve over the whole
range. On two clips left out of the fit the mean error is 4 code values of 255 (95 % of pixels within 10) — the same picture.
ffmpeg's auto-inserted conversions pick the right matrices (BT.2020 in, BT.709 out) when the output is tagged bt709;
the proxies are, so the LUT simply follows the scale like the D-Log one. PQ uses the same curve after its EOTF (untested on
real PQ footage — none on disk).
"""
import argparse, os
import numpy as np

M2020_709 = np.array([[1.6604910, -0.5876411, -0.0728499], [-0.1245505, 1.1328999, -0.0083494], [-0.0181508, -0.1005789, 1.1187297]])
Y2020 = np.array([0.2627, 0.6780, 0.0593]); Y709 = np.array([0.2126, 0.7152, 0.0722])
REF_WHITE = 203.0
DEFAULT = {"white": 0.29, "knee": 0.05, "gamma": 2.71, "sat": 1.24}   # fitted to VideoToolbox, see the module doc
NAMES = {"hlg": "HLG_BT2020_to_Rec709.cube", "pq": "PQ_BT2020_to_Rec709.cube"}


def hlg_to_nits(e):
    a, b, c = 0.17883277, 0.28466892, 0.55991073
    e = np.clip(e, 0, 1)
    scene = np.where(e <= 0.5, e * e / 3.0, (np.exp((e - c) / a) + b) / 12.0)
    ys = np.maximum(scene @ Y2020, 1e-9)[..., None]
    return 1000.0 * ys ** 0.2 * scene


def pq_to_nits(e):
    m1, m2, c1, c2, c3 = 0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875
    p = np.clip(e, 0, 1) ** (1 / m2)
    return 10000.0 * (np.maximum(p - c1, 0) / (c2 - c3 * p)) ** (1 / m1)


def to_sdr(rgb, kind="hlg", white=1.0, knee=0.75, gamma=2.4, sat=1.0):
    """rgb: (..., 3) non-linear BT.2020 signal 0..1 → (..., 3) Rec.709 signal 0..1."""
    nits = hlg_to_nits(rgb) if kind == "hlg" else pq_to_nits(rgb)
    lin = (nits @ M2020_709.T) / REF_WHITE * white
    y = np.maximum(lin @ Y709, 1e-9)[..., None]
    if sat != 1.0: lin = y + (lin - y) * sat
    # shoulder: identity up to the knee, then an exponential roll-off that reaches 1.0 only at infinity
    room = 1.0 - knee
    ym = np.where(y <= knee, y, knee + room * (1 - np.exp(-(y - knee) / room)))
    lin = lin * (ym / y)
    # out of gamut: negatives (BT.2020 colours outside Rec.709) and channels over 1 pulled toward the luminance
    lo = np.min(lin, axis=-1, keepdims=True); hi = np.max(lin, axis=-1, keepdims=True)
    t_lo = np.where(lo < 0, ym / np.maximum(ym - lo, 1e-9), 1.0)
    t_hi = np.where(hi > 1, (1 - ym) / np.maximum(hi - ym, 1e-9), 1.0)
    t = np.clip(np.minimum(t_lo, t_hi), 0, 1)
    lin = ym + (lin - ym) * t
    return np.clip(lin, 0, 1) ** (1 / gamma)


def write_cube(path, kind, size=65, **kw):
    g = np.linspace(0, 1, size)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")          # .cube order: red changes fastest
    out = to_sdr(np.stack([r, gg, b], -1).reshape(-1, 3), kind, **{**DEFAULT, **kw})
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(f'TITLE "{kind.upper()} BT.2020 to Rec.709 (reel-studio hdr_lut.py)"\nLUT_3D_SIZE {size}\n')
        np.savetxt(f, out, fmt="%.6f")
    os.replace(tmp, path)
    return path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="~/.cache/reel-studio/luts"); ap.add_argument("--size", type=int, default=65)
    a = ap.parse_args(); d = os.path.expanduser(a.out); os.makedirs(d, exist_ok=True)
    for k, n in NAMES.items(): print("wrote", write_cube(os.path.join(d, n), k, a.size))
    print("HDR_LUT_OK")


if __name__ == "__main__":
    main()
