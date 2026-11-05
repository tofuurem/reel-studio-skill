import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { brand, colors } from "../theme";
import { ChannelPill } from "./Board";

/** Quiet ending: a slow fade to black, with a channel pill only when a channel name is given (brand.channel or label).
 *  No "watch the previous video" card — related videos are linked on the platform. Works with any tail length: the fade is clamped
 *  into the sequence (a tail under 72 frames used to throw). */
export const EndCard: React.FC<{ label?: string; pillAt?: number; blackFrom?: number; top?: number }> = ({ label = brand.channel, pillAt = 16, blackFrom = 70, top = 1300 }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const last = Math.max(1, durationInFrames - 1);
  const bf = Math.min(blackFrom, last - 1);
  const k = interpolate(frame, [bf, last], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.quad) });
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: colors.black, opacity: k }} />
      <AbsoluteFill style={{ opacity: 1 - k }}>
        <ChannelPill label={label} top={top} at={Math.min(pillAt, Math.max(0, bf - 14))} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
