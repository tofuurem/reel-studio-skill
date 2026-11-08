import React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { body } from "../fonts";
import { N } from "../numbers";
import { colors, safe, shadows } from "../theme";
import { sp } from "../ui/anim";
import { blockLife, blockW, clampX } from "./shared";

/* Before / after wipe (idea: HyperFrames registry/components/before-after-wipe): "before" is the base, "after" wipes in from
 * the right edge behind a divider that settles at `rest`; `moves` slide the divider on later words. The divider shows only
 * once it leaves the edge. Both sides share one box: align the two pictures so it reads as one surface changing. */

type Side = string | React.ReactNode;

type Props = {
  /** before / after: an image under public/ ("screens/old.png") or any JSX */
  a: Side;
  b: Side;
  labelA?: string;
  labelB?: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  fit?: "cover" | "contain";
  /** window lands */
  at?: number;
  /** the wipe starts (default at + 12) */
  wipeAt?: number;
  /** wipe length (frames) */
  wipeFrames?: number;
  /** divider rest position, 0 = left edge (all "after") … 1 = right edge (all "before") */
  rest?: number;
  /** later divider moves: [local frame, position 0..1] */
  moves?: [number, number][];
  until?: number;
};

const Fill: React.FC<{ side: Side; fit: "cover" | "contain" }> = ({ side, fit }) =>
  typeof side === "string" ? <Img src={staticFile(side)} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: fit }} /> : <div style={{ position: "absolute", inset: 0 }}>{side}</div>;

const Label: React.FC<{ text: string; right?: boolean; o: number }> = ({ text, right, o }) => (
  <div style={{ position: "absolute", top: 22, [right ? "right" : "left"]: 22, padding: "8px 22px", borderRadius: 999, background: colors.panel, border: colors.panelBorder, boxShadow: shadows.pill, color: colors.ink, fontFamily: body, fontWeight: 800, fontSize: 32, whiteSpace: "nowrap", opacity: o }}>{text}</div>
);

export const BeforeAfter: React.FC<Props> = ({ a, b, labelA = "До", labelB = "После", x = safe.x, y = N.bandTop, w = blockW, h = 952, fit = "cover", at = 0, wipeAt, wipeFrames = 32, rest = 0.5, moves = [], until }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const life = blockLife(frame, fps, at, until, durationInFrames);
  if (frame < at || life.o <= 0) return null;
  const w0 = wipeAt ?? at + 12;
  const wipe = interpolate(frame, [w0, w0 + wipeFrames], [0, 1], { ...clampX, easing: Easing.inOut(Easing.cubic) });
  let pos = 1 - (1 - rest) * wipe;
  let prev = rest;
  for (const [f, target] of moves) {
    pos += (target - prev) * sp(frame, fps, f, { damping: 18, mass: 1.4 });
    prev = target;
  }
  pos = Math.min(1, Math.max(0, pos));
  const lineO = Math.min(1, (1 - pos) * 14, pos * 14);
  const labelO = interpolate(frame, [at + 6, at + 16], [0, 1], clampX);
  // a chip fades out when its side gets narrower than the chip
  const fits = (text: string, side: number) => interpolate(side * w, [text.length * 21 + 90, text.length * 21 + 120], [0, 1], clampX);
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: 28, overflow: "hidden", background: colors.panelSolid, border: colors.panelBorder, boxShadow: shadows.panel, opacity: life.o, translate: `0px ${(1 - life.e) * 50 + life.x * 24}px`, scale: String(0.97 + 0.03 * life.e) }}>
      <div style={{ position: "absolute", inset: 0 }}>
        <Fill side={a} fit={fit} />
        {labelA ? <Label text={labelA} o={labelO * fits(labelA, pos)} /> : null}
      </div>
      <div style={{ position: "absolute", inset: 0, clipPath: `inset(0 0 0 ${pos * 100}%)` }}>
        <Fill side={b} fit={fit} />
        {labelB ? <Label text={labelB} right o={labelO * fits(labelB, 1 - pos)} /> : null}
      </div>
      <div style={{ position: "absolute", top: 0, bottom: 0, left: `${pos * 100}%`, width: 0, opacity: lineO }}>
        <div style={{ position: "absolute", top: 0, bottom: 0, left: -3, width: 6, background: colors.ink, boxShadow: shadows.pill }} />
        <div style={{ position: "absolute", top: "50%", left: -38, width: 76, height: 76, marginTop: -38, borderRadius: 99, background: colors.panel, border: colors.panelBorder, boxShadow: shadows.pill, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg width={44} height={44} viewBox="0 0 24 24">
            <path d="M9 6.5L3.5 12 9 17.5M15 6.5l5.5 5.5-5.5 5.5" fill="none" stroke={colors.ink} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
    </div>
  );
};
