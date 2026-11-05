import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { body } from "../fonts";
import { colors, inkOn } from "../theme";
import { inAt, outBefore } from "./anim";

/** A chip lands on its word (`at`, local frame). `bg` from the palette; text colour follows the fill. */
export type Chip = { at: number; text: string; bg?: string };

/** Wrapping row of chips (tool names, verbs) — lofiroom ep1/ep2. Flat landing, no tilt. */
export const ChipRow: React.FC<{ chips: Chip[]; size?: number; justify?: React.CSSProperties["justifyContent"] }> = ({ chips, size = 34, justify = "flex-start" }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "12px 14px", justifyContent: justify }}>
      {chips.map((c) => {
        if (frame < c.at) return null;
        const a = inAt(frame, c.at, 12);
        const bg = c.bg ?? colors.chip;
        return (
          <div
            key={c.text}
            style={{
              padding: `${Math.round(size * 0.3)}px ${Math.round(size * 0.65)}px`,
              borderRadius: 999,
              background: bg,
              color: inkOn(bg),
              border: colors.panelBorder,
              fontFamily: body,
              fontWeight: 800,
              fontSize: size,
              whiteSpace: "nowrap",
              opacity: a,
              scale: String(0.6 + a * 0.4),
              translate: `0px ${(1 - a) * -30}px`,
            }}
          >
            {c.text}
          </div>
        );
      })}
    </div>
  );
};

/** ChipRow in its own band (e.g. under a cold-open window), fades out before its sequence ends. */
export const ChipBand: React.FC<{ chips: Chip[]; top: number; size?: number; justify?: React.CSSProperties["justifyContent"] }> = ({ chips, top, size = 40, justify = "center" }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <AbsoluteFill style={{ opacity: outBefore(frame, durationInFrames, 8) }}>
      <div style={{ position: "absolute", left: 40, right: 40, top }}>
        <ChipRow chips={chips} size={size} justify={justify} />
      </div>
    </AbsoluteFill>
  );
};
