import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, staticFile, useCurrentFrame } from "remotion";
import { display, mono } from "../fonts";
import { colors, H, W } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const PORTRAIT = H > W;
/** The title fills ≈ 90 % of the width at most (the display face is wide: ≈ 0.8 em per Cyrillic capital). */
const fit = (t: string) => Math.round(Math.min(PORTRAIT ? 190 : 230, (W * 0.9) / (0.8 * Math.max(1, t.length))));

/**
 * Text behind the person: the title sits between the footage and a cutout of the same frames (person_matte.py: Apple Vision
 * person segmentation → a VP9 WebM with alpha), so the person stands in front of the letters. Place it INSIDE the same
 * transform as the footage (Action's ShotView, BRoll's zoom) so both move together. at / until are local frames.
 * Use it for a hook or a chapter title on a shot where the person is big and still enough; a fast whip or a crowd breaks
 * the illusion. Edges against a contrasting title colour can show a faint halo — --feather 1 or --mode subject.
 */
export const BehindTitle: React.FC<{ title: string; kicker?: string; at: number; until: number; part?: "back" | "front"; y?: number }> = ({ title, kicker, at, until, part = "back", y }) => {
  // part "back" = the big word (under the cutout); "front" = the kicker (above it, so the head never hides it)
  const f = useCurrentFrame();
  const a = interpolate(f, [at, at + 10], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const o = interpolate(f, [until - 8, until], [1, 0], clamp);
  const size = fit(title);
  return (
    <AbsoluteFill style={{ opacity: a * o }}>
      {/* y = the word's centre (0–1 of the height); actiongen / reelgen set it just below the top of the person (mask bbox),
          so the head covers the lower part of the letters and the word stays readable */}
      <div style={{ position: "absolute", left: 0, right: 0, top: `${(y ?? 0.5) * 100}%`, textAlign: "center", translate: `0px calc(-50% + ${(1 - a) * 40}px)` }}>
        <div style={{ fontFamily: mono, fontSize: 40, fontWeight: 700, letterSpacing: 4, lineHeight: 1.2, color: colors.accent, textShadow: "0 2px 10px rgba(0,0,0,0.6)", visibility: kicker && part === "front" ? "visible" : "hidden" }}>{kicker || " "}</div>
        <div style={{ fontFamily: display, fontWeight: 900, fontSize: size, lineHeight: 0.9, letterSpacing: -4, color: colors.ink, scale: String(0.92 + 0.08 * a), visibility: part === "back" ? "visible" : "hidden" }}>{title}</div>
      </div>
    </AbsoluteFill>
  );
};

/** The cutout layer that goes above BehindTitle (frame 0 = the footage's first frame in this Sequence). */
export const MatteLayer: React.FC<{ src: string }> = ({ src }) => (
  // positioned like the title: an in-flow video would paint UNDER an absolutely positioned title whatever the order
  <AbsoluteFill>
    <OffthreadVideo src={staticFile(src)} muted transparent style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  </AbsoluteFill>
);
