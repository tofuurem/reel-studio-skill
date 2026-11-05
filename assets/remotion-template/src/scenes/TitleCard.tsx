import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { N } from "../numbers";
import { colors, safe, shadows } from "../theme";
import { inAt, outBefore } from "../ui/anim";

/**
 * Episode title in the top band (lofiroom ep1/ep2 «LofiTitle», made parametric): the series name slams in on a light plate,
 * the episode pill slides in under it (`pillAt`), one quiet line under that (`subAt`). Lands flat — `tilt` only if a design
 * asks for it. Keep it ≤ 3 s and under the cold-open window or over a board.
 */
export const TitleCard: React.FC<{ title: string; pill?: string; pillNote?: string; sub?: string; top?: number; size?: number; at?: number; pillAt?: number; subAt?: number; tilt?: number }> = ({
  title,
  pill,
  pillNote,
  sub,
  top = N.cardTop - 50,
  size = 118,
  at = 0,
  pillAt,
  subAt,
  tilt = 0,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const a = inAt(frame, at, 14);
  const b = inAt(frame, pillAt ?? at + 20, 12);
  const c = inAt(frame, subAt ?? at + 40, 12);
  const o = outBefore(frame, durationInFrames, 10);
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <div style={{ position: "absolute", left: safe.x, right: safe.x, top }}>
        <div
          style={{
            display: "inline-block",
            fontFamily: display,
            fontWeight: 900,
            fontSize: size,
            lineHeight: 1,
            letterSpacing: -4,
            color: colors.bg,
            background: colors.ink,
            padding: `${Math.round(size * 0.2)}px ${Math.round(size * 0.29)}px ${Math.round(size * 0.25)}px`,
            borderRadius: Math.round(size * 0.25),
            opacity: a,
            rotate: `${tilt}deg`,
            scale: String(interpolate(a, [0, 1], [1.5, 1], { easing: Easing.out(Easing.back(1.4)) })),
            transformOrigin: "0% 0%",
            boxShadow: shadows.panel,
          }}
        >
          {title}
        </div>
        {pill ? (
          <div style={{ marginTop: 18 }}>
            <div style={{ display: "inline-flex", alignItems: "baseline", gap: 14, fontFamily: display, fontWeight: 700, fontSize: 44, color: colors.onAccent, background: colors.accent, padding: "14px 26px", borderRadius: 999, boxShadow: shadows.pill, opacity: b, translate: `${(1 - b) * -60}px 0px` }}>
              {pill}
              {pillNote ? <span style={{ fontSize: 30, opacity: 0.8 }}>{pillNote}</span> : null}
            </div>
          </div>
        ) : null}
        {sub ? <div style={{ marginTop: 22, fontFamily: body, fontWeight: 700, fontSize: 32, color: colors.muted, textShadow: shadows.text, opacity: c, translate: `0px ${(1 - c) * 20}px` }}>{sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};
