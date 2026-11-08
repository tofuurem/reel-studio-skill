import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { colors, inkOn, safe, shadows, W } from "../theme";
import { sp } from "../ui/anim";
import { clampX, SMALL } from "./shared";

/* Name + kicker plate (ideas: HyperFrames lt-mask-reveal, lt-kicker-name, lt-clean-bar). Two calm variants:
 *  - "mask": the name is uncovered behind an accent bar that sweeps left→right, the kicker pill rises out of a mask under it
 *    (white text straight over the footage, shadows.text);
 *  - "bar": a dark plate wipes in from the left with an accent tab, the name and the kicker rise into it.
 * Default place: left margin, y 1130 — under a medium-shot face, above the captions (y 1400–1520). */

type Props = {
  name: string;
  kicker?: string;
  variant?: "mask" | "bar";
  x?: number;
  /** top edge */
  y?: number;
  /** name font size (shrinks to fit the width) */
  size?: number;
  /** accent of the sweep / tab / kicker pill (a palette token) */
  accent?: string;
  at?: number;
  /** kicker lands (default at + 10) */
  kickerAt?: number;
  until?: number;
};

const OUT = 8;

export const LowerThird: React.FC<Props> = ({ name, kicker, variant = "mask", x = safe.x, y = 1130, size, accent = colors.accent, at = 0, kickerAt, until }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  if (frame < at) return null;
  const u = until ?? durationInFrames - OUT;
  const out = interpolate(frame, [u, u + OUT], [0, 1], { ...clampX, easing: Easing.in(Easing.quad) });
  if (out >= 1) return null;
  const k0 = kickerAt ?? at + 10;
  const maxW = W - x - safe.right;
  const chars = Array.from(name).length;

  if (variant === "bar") {
    const fs = Math.min(size ?? 54, Math.floor((maxW - 120) / (chars * 0.6)));
    const wipe = interpolate(frame, [at, at + 16], [0, 1], { ...clampX, easing: Easing.out(Easing.cubic) });
    const tab = interpolate(frame, [at + 5, at + 18], [0, 1], { ...clampX, easing: Easing.out(Easing.cubic) });
    const nm = sp(frame, fps, at + 7, SMALL);
    const kk = frame < k0 ? 0 : sp(frame, fps, k0, SMALL);
    return (
      <div style={{ position: "absolute", left: x, top: y, maxWidth: maxW, display: "flex", borderRadius: 22, overflow: "hidden", background: colors.panel, border: colors.panelBorder, boxShadow: shadows.panel, clipPath: `inset(0 ${(1 - wipe) * 100}% 0 0 round 22px)`, opacity: 1 - out, translate: `0px ${out * 18}px` }}>
        <div style={{ width: 12, flexShrink: 0, background: accent, scale: `1 ${tab}`, transformOrigin: "50% 0%" }} />
        <div style={{ padding: "22px 40px 24px 28px", display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
          <div style={{ fontFamily: body, fontWeight: 800, fontSize: fs, lineHeight: 1.1, color: colors.ink, whiteSpace: "nowrap", opacity: Math.min(1, nm * 1.4), translate: `0px ${(1 - nm) * 22}px` }}>{name}</div>
          {kicker ? <div style={{ fontFamily: body, fontWeight: 700, fontSize: 34, lineHeight: 1.2, color: colors.muted, whiteSpace: "nowrap", opacity: Math.min(1, kk * 1.4), translate: `0px ${(1 - kk) * 22}px` }}>{kicker}</div> : null}
        </div>
      </div>
    );
  }

  // "mask": accent sweep uncovers the name, the kicker rises out of its mask
  const fs = Math.min(size ?? 72, Math.floor(maxW / (chars * 0.7)));
  const p = interpolate(frame, [at + 2, at + 20], [0, 1], { ...clampX, easing: Easing.inOut(Easing.cubic) });
  const sweepO = interpolate(frame, [at, at + 3, at + 19, at + 25], [0, 1, 1, 0], clampX);
  const kk = frame < k0 ? 0 : sp(frame, fps, k0, SMALL);
  return (
    <div style={{ position: "absolute", left: x, top: y, maxWidth: maxW, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 16 }}>
      <div style={{ position: "relative", padding: "4px 0" }}>
        <div style={{ fontFamily: display, fontWeight: 800, fontSize: fs, lineHeight: 1.05, letterSpacing: -1, color: colors.ink, whiteSpace: "nowrap", textShadow: shadows.text, clipPath: out > 0 ? `inset(0 0 0 ${out * 100}%)` : `inset(-20% ${(1 - p) * 100}% -20% 0)` }}>{name}</div>
        <div style={{ position: "absolute", top: 0, bottom: 0, left: `calc(${p * 100}% - ${p * 12}px)`, width: 12, borderRadius: 3, background: accent, opacity: sweepO }} />
      </div>
      {kicker ? (
        <div style={{ overflow: "hidden", padding: "0 0 4px", opacity: 1 - out }}>
          <div style={{ padding: "6px 20px", borderRadius: 12, background: accent, color: inkOn(accent), fontFamily: body, fontWeight: 800, fontSize: 34, lineHeight: 1.2, whiteSpace: "nowrap", letterSpacing: 0.5, translate: `0px ${(1 - Math.min(1, kk)) * 110}%`, opacity: Math.min(1, kk * 2) }}>{kicker}</div>
        </div>
      ) : null}
    </div>
  );
};
