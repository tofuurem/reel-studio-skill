import React from "react";
import { AbsoluteFill, Easing, interpolate } from "remotion";
import { N } from "../numbers";
import { W } from "../theme";

/**
 * Seams between two timeline clips (references/craft/transitions.md). Clip.tsx asks this file what a clip looks like in
 * the last frames before its cut (`exitLook`) and the first frames after it (`enterLook`); gen_timeline.py writes the
 * kinds from the cut list's "transition". Most cuts stay a plain dissolve — an effect seam is the exception
 * (seamFxPerMin, seamFxGapCuts: gen_timeline.py warns when the budget is broken).
 */
export type SeamKind = "dissolve" | "cut" | "whip" | "push" | "blur" | "leak" | "wipe" | "bodywipe" | "match";
/** match: the incoming clip starts moved / zoomed so the head lands where the previous head was (seams.py). */
export type MatchStart = { x: number; y: number; dx: number; dy: number; k: number };
/** bodywipe: the canvas x of the passing person's trailing edge per frame of the wipe, and which way they walk (seams.py). */
export type WipePath = { xs: number[]; dir: "left" | "right" };

export type Look = {
  opacity: number;
  scale: number; // multiplies the clip's own punch / drift
  zoomBlur: number; // px, radial (@remotion/effects zoomBlur on the video)
  blur: number; // px, CSS defocus
  light: number; // 0–1 warm light (leak)
  mask?: string; // CSS mask-image on the incoming clip
  matchStyle?: React.CSSProperties;
};
export const NO_LOOK: Look = { opacity: 1, scale: 1, zoomBlur: 0, blur: 0, light: 0 };

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const easeIn = Easing.in(Easing.cubic);
const easeOut = Easing.out(Easing.cubic);
const SHORT = 4; // the few dissolve frames that soften a blur / leak cut

/** How long the outgoing clip must stay under the incoming one for this kind (Sequence overlap). */
export const overlapFor = (kind: SeamKind | undefined, xfade: number, wipe?: WipePath) =>
  kind === "bodywipe" && wipe ? wipe.xs.length : kind === "wipe" ? N.seamWipeFrames : kind === "cut" || kind === "push" ? 1 : xfade;

/** The outgoing clip over its last frames before the cut (frame f of the clip, the cut at `cutAt`). */
export const exitLook = (kind: SeamKind | undefined, f: number, cutAt: number): Look => {
  const t = f - cutAt; // < 0 before the cut
  if (kind === "push") {
    const p = interpolate(t, [-N.seamPushOut, 0], [0, 1], { ...clamp, easing: easeIn });
    return { ...NO_LOOK, scale: 1 + (N.seamPushScale - 1) * p, zoomBlur: N.seamPushBlur * p };
  }
  if (kind === "blur") {
    const p = interpolate(t, [-N.seamBlurOut, 0], [0, 1], { ...clamp, easing: easeIn });
    return { ...NO_LOOK, blur: N.seamBlurPx * p };
  }
  if (kind === "leak") {
    const p = interpolate(t, [-N.seamLeakOut, 0], [0, 1], { ...clamp, easing: Easing.in(Easing.quad) });
    return { ...NO_LOOK, light: p };
  }
  return NO_LOOK;
};

/** The incoming clip over its first frames (frame f of the clip; the cut is frame 0). */
export const enterLook = (kind: SeamKind | undefined, f: number, frames: number, match?: MatchStart, wipe?: WipePath): Look => {
  if (!kind) return NO_LOOK;
  const fade = (n: number) => interpolate(f, [0, Math.max(1, n)], [0, 1], { ...clamp, easing: easeOut });
  if (kind === "dissolve") return { ...NO_LOOK, opacity: fade(frames) };
  if (kind === "cut") return NO_LOOK;
  if (kind === "push") {
    const p = interpolate(f, [0, N.seamPushIn], [0, 1], { ...clamp, easing: easeOut });
    return { ...NO_LOOK, scale: 1 + N.seamPushGrow * p, zoomBlur: N.seamPushBlur * (1 - p) };
  }
  if (kind === "blur") {
    const p = interpolate(f, [0, N.seamBlurIn], [0, 1], { ...clamp, easing: easeOut });
    return { ...NO_LOOK, opacity: fade(SHORT), blur: N.seamBlurPx * (1 - p) };
  }
  if (kind === "leak") {
    const p = interpolate(f, [0, N.seamLeakIn], [0, 1], { ...clamp, easing: easeOut });
    return { ...NO_LOOK, opacity: fade(SHORT), light: 1 - p };
  }
  if (kind === "wipe" || (kind === "bodywipe" && wipe)) {
    // the edge moves right → left (the reel's current) or follows the passing person; the new picture is BEHIND the edge
    const feather = N.seamWipeFeather * W;
    let edge: number, dir: "left" | "right";
    if (kind === "bodywipe" && wipe) {
      const i = Math.min(wipe.xs.length - 1, Math.max(0, Math.round(f)));
      edge = wipe.xs[i]; dir = wipe.dir;
      if (f >= wipe.xs.length) return NO_LOOK;
    } else {
      const p = interpolate(f, [0, N.seamWipeFrames], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
      if (p >= 1) return NO_LOOK;
      edge = W + feather - p * (W + 2 * feather); dir = "left";
    }
    // walking left: the new scene shows to the right of the person's trailing (right) edge, and the other way round
    const a = ((dir === "left" ? edge : edge - feather) / W) * 100, b = ((dir === "left" ? edge + feather : edge) / W) * 100;
    const mask = dir === "left" ? `linear-gradient(to right, transparent ${a}%, black ${b}%)` : `linear-gradient(to right, black ${a}%, transparent ${b}%)`;
    return { ...NO_LOOK, mask };
  }
  if (kind === "match" && match) {
    const p = interpolate(f, [0, N.seamMatchFrames], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
    const q = 1 - p;
    return {
      ...NO_LOOK,
      opacity: fade(frames),
      matchStyle: q > 0 ? { transformOrigin: `${match.x}px ${match.y}px`, translate: `${match.dx * q}px ${match.dy * q}px`, scale: String(1 + (match.k - 1) * q) } : undefined,
    };
  }
  return { ...NO_LOOK, opacity: fade(frames) };
};

/** Combine the two looks a clip can have at once (it enters with one seam and leaves with another). */
export const mergeLooks = (a: Look, b: Look): Look => ({
  opacity: a.opacity * b.opacity,
  scale: a.scale * b.scale,
  zoomBlur: a.zoomBlur + b.zoomBlur,
  blur: a.blur + b.blur,
  light: Math.max(a.light, b.light),
  mask: a.mask ?? b.mask,
  matchStyle: a.matchStyle ?? b.matchStyle,
});

/** CSS filter of the picture under a leak: lighter, flatter, a little less saturated — light, not a white flash. */
export const leakFilter = (light: number) =>
  light > 0.002 ? `brightness(${(1 + N.seamLeakLift * light).toFixed(3)}) contrast(${(1 - 0.2 * light).toFixed(3)}) saturate(${(1 - 0.15 * light).toFixed(3)})` : undefined;

/** Warm light drifting diagonally across the frame: plain radial gradients at a capped opacity (no blend modes —
 *  lint_reel.py; a blended layer drops single frames). `light` 0–1 is the strength, `u` 0–1 the sweep position. */
export const LeakLight: React.FC<{ light: number; u: number }> = ({ light, u }) => {
  if (light <= 0.002) return null;
  const x = 85 - 70 * u, y = 10 + 50 * u;
  return (
    <AbsoluteFill
      style={{
        opacity: N.seamLeakPeak * light,
        background: [
          `radial-gradient(ellipse 55% 45% at ${x}% ${y}%, rgba(255, 196, 120, 0.95) 0%, rgba(255, 150, 70, 0.5) 45%, transparent 75%)`,
          `radial-gradient(ellipse 40% 60% at ${x + 18}% ${y + 22}%, rgba(255, 120, 60, 0.7) 0%, transparent 70%)`,
          `radial-gradient(ellipse 35% 30% at ${x - 22}% ${y - 6}%, rgba(255, 228, 170, 0.8) 0%, transparent 70%)`,
        ].join(", "),
      }}
    />
  );
};
