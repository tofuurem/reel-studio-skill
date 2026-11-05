import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { N } from "../numbers";
import { colors, safe, shadows } from "../theme";
import { inAt, outBefore } from "./anim";

/** "01 · Фотоархив" pill at the top-left (y N.tagY). Slides in flat — no tilt, no emoji (birthday reel: tilted pills and
 *  emoji read as clip-art). Usually placed by <Chapter>, which adds the flash and the whoosh. */
export const ChapterTag: React.FC<{ n: string; title: string }> = ({ n, title }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const a = inAt(frame, 0, 12);
  const o = outBefore(frame, durationInFrames, 8);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: N.tagY,
          left: safe.x,
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "16px 28px 16px 18px",
          borderRadius: 999,
          background: colors.ink,
          color: colors.bg,
          fontFamily: body,
          fontWeight: 800,
          fontSize: 38,
          boxShadow: shadows.pill,
          opacity: a * o,
          translate: `${(1 - a) * -80}px 0px`,
        }}
      >
        <span style={{ fontFamily: display, fontWeight: 900, fontSize: 30, background: colors.accent, color: colors.onAccent, borderRadius: 999, padding: "8px 16px" }}>{n}</span>
        <span>{title}</span>
      </div>
    </AbsoluteFill>
  );
};
