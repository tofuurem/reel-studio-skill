import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame } from "remotion";
import { N } from "../numbers";
import { footagePath, H } from "../theme";

/** One tracked blur: ellipses per tracker frame (cx, cy, rx, ry — 0–1 of the source frame), sampled at `fps`. */
export type CensorTrack = { fps: number; ell: number[][][] };

const NONE = "linear-gradient(transparent, transparent)";

/**
 * A censored cut (Halloween vlog, 2026-11-09): the same footage again over the timeline, blurred, visible only inside soft
 * ellipses that follow a joint, a pipe or a cannabis-leaf sign (censor_track.py → work/censor/*.json →
 * reelgen.censor_blurs()). It repeats the Clip's own framing — the punch zoom with its slow drift around the eye line
 * (`at` = frames into the clip where this patch starts, `hold` = the clip's length) — and the mask sits INSIDE that
 * transform, so the ellipses stay on the source pixels they were tracked on. The video stays mounted while no ellipse is
 * active (a transparent mask): unmounting would re-seek and flash. CSS mask layers, no backdrop-filter.
 */
export const BlurPatch: React.FC<{ src: string; trimBefore: number; track: CensorTrack; at?: number; punch?: number; drift?: number; hold?: number; blur?: number }> = ({
  src, trimBefore, track, at = 0, punch = 1, drift = 0, hold = 1, blur = 28,
}) => {
  const f = useCurrentFrame();
  const e = track.ell[Math.min(track.ell.length - 1, Math.max(0, Math.floor((f * track.fps) / 30)))] ?? [];
  const mask = e.length
    ? e.map(([cx, cy, rx, ry]) => `radial-gradient(ellipse ${(rx * 100).toFixed(2)}% ${(ry * 100).toFixed(2)}% at ${(cx * 100).toFixed(2)}% ${(cy * 100).toFixed(2)}%, black 60%, transparent 100%)`).join(", ")
    : NONE;
  const scale = interpolate(f + at, [0, Math.max(1, hold)], [punch, punch + drift], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.linear });
  return (
    <AbsoluteFill style={{ transformOrigin: `50% ${((N.punchCenterY / H) * 100).toFixed(2)}%`, scale: String(scale) }}>
      <AbsoluteFill style={{ maskImage: mask, WebkitMaskImage: mask }}>
        <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} muted objectFit="cover" style={{ width: "100%", height: "100%", filter: `blur(${blur}px)` }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
