import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { N } from "../numbers";
import { colors } from "../theme";

/** Soft radial light bloom on chapter cuts (peak N.flashPeak over N.flashFrames; a hard 0.85 hit read as a strobe).
 *  Plain gradient + opacity: no mix-blend-mode — a blended layer gets its own compositor layer and dropped single frames. */
export const Flash: React.FC<{ color?: string }> = ({ color = colors.flash }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 40%, ${color} 0%, transparent 70%)`,
        opacity: interpolate(frame, [0, 3, N.flashFrames], [0, N.flashPeak, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
      }}
    />
  );
};
