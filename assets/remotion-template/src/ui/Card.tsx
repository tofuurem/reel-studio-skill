import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { N } from "../numbers";
import { colors, safe, shadows } from "../theme";
import { inAt, outBefore } from "./anim";

type Props = {
  children: React.ReactNode;
  /** Top offset in px. Default N.cardTop: under the chapter tag, above a medium-shot face; take the real band from
   *  work/face_zones.json (reelgen.free_top / free_bottom). */
  top?: number;
  height?: number;
  /** frame (inside the sequence) when the card pops in */
  at?: number;
  padding?: number;
  style?: React.CSSProperties;
};

/** Dark panel that pops in from below and fades out before its sequence ends.
 *  No backdrop-filter on purpose: it promotes the card to its own compositor layer and Chrome then drops the text on
 *  random single frames during the render (cards "blink"). */
export const Card: React.FC<Props> = ({ children, top = N.cardTop, height, at = 0, padding = 44, style }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const a = inAt(frame, at, 14);
  const o = outBefore(frame, durationInFrames, 8);
  return (
    <div
      style={{
        position: "absolute",
        left: safe.x,
        right: safe.x, // symmetric; the right button strip (safe.right) only matters below y ≈ 1100
        top,
        height,
        padding,
        borderRadius: 40,
        background: colors.panel,
        border: colors.panelBorder,
        boxShadow: shadows.panel,
        color: colors.ink,
        opacity: a * o,
        translate: `0px ${(1 - a) * 60}px`,
        scale: String(0.96 + a * 0.04),
        transformOrigin: "50% 100%",
        overflow: "hidden",
        ...style,
      }}
    >
      {children}
    </div>
  );
};
