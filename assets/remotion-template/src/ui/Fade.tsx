import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { colors } from "../theme";

/** Opening fade from black over the whole sequence (N.fadeFromBlack frames). Use it when the reel starts on a cutaway: a
 *  b-roll with its own fade-in lets the talking head peek through on frame 0. */
export const FadeFromBlack: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return <AbsoluteFill style={{ background: colors.black, opacity: interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.quad) }) }} />;
};

/** Fades to black over `over` frames and holds it (the end of the reel). */
export const FadeToBlack: React.FC<{ over?: number }> = ({ over = 16 }) => {
  const frame = useCurrentFrame();
  return <AbsoluteFill style={{ background: colors.black, opacity: interpolate(frame, [0, Math.max(1, over)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.quad) }) }} />;
};
