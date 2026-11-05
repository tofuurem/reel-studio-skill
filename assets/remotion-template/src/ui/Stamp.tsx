import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { display } from "../fonts";
import { N } from "../numbers";
import { colors, inkOn, shadows } from "../theme";
import { outBefore } from "./anim";

/** Big slammed-in word, like a rubber stamp (the one element that is meant to sit rotated). Default position: the top band
 *  (N.cardTop), away from a medium-shot face; size ≤ N.stampMaxPx when rotated (118 overflowed 1080 px). */
export const Stamp: React.FC<{ text: string; color?: string; top?: number; rotate?: number; size?: number }> = ({ text, color = colors.accent, top = N.cardTop, rotate = -6, size = N.stampMaxPx }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const o = outBefore(frame, durationInFrames, 6);
  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          top,
          fontFamily: display,
          fontWeight: 900,
          fontSize: Math.min(size, N.stampMaxPx),
          lineHeight: 1,
          letterSpacing: -2,
          color: inkOn(color),
          background: color,
          padding: "22px 40px",
          borderRadius: 24,
          whiteSpace: "nowrap",
          boxShadow: shadows.pill,
          rotate: `${rotate}deg`,
          opacity: interpolate(frame, [0, 2], [0, 1], { extrapolateRight: "clamp" }) * o,
          scale: String(interpolate(frame, [0, 10], [1.8, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.back(1.6)), output: "perceptual-scale" })),
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
