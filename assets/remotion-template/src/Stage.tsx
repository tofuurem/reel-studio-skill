import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { colors, shadows } from "./theme";
import { windowProgress } from "./ui/anim";

type Window = { from: number; to: number; scale: number; top: number };

/**
 * Shrinks the talking-head layer into a rounded window at the top for the given frame ranges, freeing the lower half
 * for graphics (close-ups that need notes). 12-frame ease in/out. SplitStage (scenes/Board.tsx) is the left-window variant.
 */
export const Stage: React.FC<{ windows: Window[]; children: React.ReactNode }> = ({ windows, children }) => {
  const frame = useCurrentFrame();
  let p = 0;
  let w: Window | null = null;
  for (const win of windows) {
    const v = windowProgress(frame, [win]);
    if (v > p) {
      p = v;
      w = win;
    }
  }
  const scale = w ? 1 - (1 - w.scale) * p : 1;
  const top = w ? w.top * p : 0;
  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg }}>
      <AbsoluteFill style={{ transformOrigin: "50% 0%", scale: String(scale), translate: `0px ${top}px`, borderRadius: p * 48, overflow: "hidden", boxShadow: p > 0 ? shadows.panel : undefined }}>
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
