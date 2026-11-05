import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { N } from "../numbers";
import { alpha, brand, colors, footagePath, inkOn, shadows } from "../theme";
import { envelope, inAt, leaveAt, outBefore, windowProgress } from "../ui/anim";
import { Mark } from "../ui/Mark";

/**
 * "Board" kit for voiceover stretches (no talking head underneath): a full-frame board background with windows
 * (images / screen recordings), pills and check rows placed in absolute 1080x1920 coordinates.
 * Content lives in the band N.bandTop–N.bandBottom (300–1350): the chapter tag sits above (y 200), captions below (y 1400–1520).
 *
 * Conventions (the whole template): every cue is a LOCAL frame of the enclosing <Sequence> — `at` = appears, `until` =
 * starts leaving (8-frame fade), `<part>At` = a sub-element lands (subAt, noteAt, swapAt); list items are `{ at, text }`.
 * `x`/`y` are the left/top edge (a centred element takes `cx`). Colours come from theme.ts tokens only.
 * No backdrop-filter / mix-blend-mode anywhere (single-frame dropouts in the render).
 */

export const BOARD_BG = colors.boardBg;
export const OK = colors.ok;
export const BAD = colors.bad;

/** Full-frame board that covers the timeline; fades like a cutaway (must start ≥ N.coverBefore frames before a cut and end
 *  ≥ N.coverAfter after it — reelgen.cover() widens the range). fadeIn/fadeOut 0 = hard edge, no blank frame. */
export const Board: React.FC<{ children?: React.ReactNode; fadeIn?: number; fadeOut?: number }> = ({ children, fadeIn = N.layerFade, fadeOut = N.layerFade }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return <AbsoluteFill style={{ background: colors.boardBg, opacity: envelope(frame, durationInFrames, fadeIn, fadeOut) }}>{children}</AbsoluteFill>;
};

type WinProps = {
  /** image under public/ (screens/…) or, with `video`, a footage path (footage/…). */
  src: string;
  video?: boolean;
  trimBefore?: number;
  x: number;
  y: number;
  w: number;
  h: number;
  /** frame when the window pops in; before it the window is mounted but invisible (the video decodes in sync, no black frame) */
  at?: number;
  /** frame when it fades away (8 frames). */
  until?: number;
  fit?: "cover" | "contain";
  label?: string;
  /** label plate colour (palette token); its text colour follows */
  labelColor?: string;
  zoomFrom?: number;
  zoomTo?: number;
  origin?: string;
  bg?: string;
  children?: React.ReactNode;
};

/** A rounded window with an image or a muted video, optional corner label and slow push-in. */
export const Win: React.FC<WinProps> = ({ src, video, trimBefore = 0, x, y, w, h, at = 0, until, fit = "cover", label, labelColor, zoomFrom = 1, zoomTo = 1.05, origin = "50% 50%", bg = colors.panelSolid, children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const o = leaveAt(frame, until);
  if (o <= 0) return null;
  const a = frame < at ? 0 : inAt(frame, at, 12);
  const zoom = interpolate(frame, [at, Math.max(at + 1, until ?? durationInFrames)], [zoomFrom, zoomTo], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.linear });
  const lbg = labelColor ?? colors.panel;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: 28, overflow: "hidden", background: bg, border: colors.panelBorder, boxShadow: shadows.panel, opacity: a * o, translate: `0px ${(1 - a) * 44}px`, scale: String(0.96 + a * 0.04) }}>
      <div style={{ width: "100%", height: "100%", scale: String(zoom), transformOrigin: origin }}>
        {video ? (
          <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} muted objectFit={fit} style={{ width: "100%", height: "100%" }} />
        ) : (
          <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: fit }} />
        )}
      </div>
      {children}
      {label ? (
        <div style={{ position: "absolute", left: 14, top: 14, padding: "7px 18px", borderRadius: 999, background: lbg, color: inkOn(lbg), fontFamily: body, fontWeight: 800, fontSize: 28, whiteSpace: "nowrap" }}>{label}</div>
      ) : null}
    </div>
  );
};

/** Free-standing pill (label, step badge, brand). Text colour follows the fill. Lands flat (`rot` only if a design asks). */
export const Pill: React.FC<{ text: string; x: number; y: number; at?: number; until?: number; bg?: string; fg?: string; size?: number; rot?: number; font?: "body" | "display" }> = ({
  text,
  x,
  y,
  at = 0,
  until,
  bg = colors.chip,
  fg,
  size = 30,
  rot = 0,
  font = "body",
}) => {
  const frame = useCurrentFrame();
  if (frame < at) return null;
  const a = inAt(frame, at, 12);
  const o = leaveAt(frame, until);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        padding: `${Math.round(size * 0.34)}px ${Math.round(size * 0.74)}px`,
        borderRadius: 999,
        background: bg,
        color: fg ?? inkOn(bg),
        border: colors.panelBorder,
        fontFamily: font === "display" ? display : body,
        fontWeight: 800,
        fontSize: Math.max(size, N.minTextPx),
        lineHeight: 1.1,
        whiteSpace: "nowrap",
        opacity: a * o,
        rotate: `${rot * a}deg`,
        scale: String(0.6 + a * 0.4),
        transformOrigin: "0% 50%",
        translate: `0px ${(1 - a) * -24}px`,
      }}
    >
      {text}
    </div>
  );
};

/** One ✓/✕ row (shared by CheckRow and SideReview). */
const MarkRow: React.FC<{ text: string; ok: boolean; size: number; h: number; style?: React.CSSProperties }> = ({ text, ok, size, h, style }) => (
  <div
    style={{
      height: h,
      boxSizing: "border-box",
      display: "flex",
      alignItems: "center",
      gap: 16,
      padding: "0 24px",
      borderRadius: 22,
      background: colors.panel,
      border: `2px solid ${ok ? colors.ok : colors.bad}`,
      color: colors.ink,
      fontFamily: body,
      fontWeight: 800,
      fontSize: size,
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    <Mark ok={ok} size={Math.round(size * 1.05)} />
    <span>{text}</span>
  </div>
);

/** Wide row with a ✓ / ✕ mark — one fact per row. */
export const CheckRow: React.FC<{ text: string; ok?: boolean; x: number; y: number; w: number; at?: number; size?: number; h?: number }> = ({ text, ok = false, x, y, w, at = 0, size = 40, h = 96 }) => {
  const frame = useCurrentFrame();
  if (frame < at) return null;
  const a = inAt(frame, at, 12);
  return <MarkRow text={text} ok={ok} size={size} h={h} style={{ position: "absolute", left: x, top: y, width: w, opacity: a, translate: `${(1 - a) * -50}px 0px` }} />;
};

/** Animated arrow pointing down (or right) with a small caption. */
export const DownArrow: React.FC<{ x: number; y: number; at?: number; text?: string; dir?: "down" | "right" }> = ({ x, y, at = 0, text, dir = "down" }) => {
  const frame = useCurrentFrame();
  if (frame < at) return null;
  const a = inAt(frame, at, 14);
  return (
    <div style={{ position: "absolute", left: x, top: y, display: "flex", alignItems: "center", gap: 18, opacity: a, translate: dir === "down" ? `0px ${(1 - a) * -30}px` : `${(1 - a) * -30}px 0px` }}>
      <svg width="64" height="76" viewBox="0 0 64 76" style={{ rotate: dir === "right" ? "-90deg" : "0deg" }}>
        <path d="M32 4 V58 M10 40 L32 66 L54 40" fill="none" stroke={colors.accent} strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {text ? <span style={{ fontFamily: display, fontWeight: 800, fontSize: 40, color: colors.ink }}>{text}</span> : null}
    </div>
  );
};

/** Square tile with a caption under it; lights up on its word. */
export const Tile: React.FC<{ src: string; label: string; x: number; y: number; size: number; at?: number }> = ({ src, label, x, y, size, at = 0 }) => {
  const frame = useCurrentFrame();
  const a = frame < at ? 0 : inAt(frame, at, 12);
  return (
    <div style={{ position: "absolute", left: x, top: y, width: size, opacity: a, scale: String(0.7 + a * 0.3), translate: `0px ${(1 - a) * 30}px` }}>
      <div style={{ width: size, height: size, borderRadius: 26, overflow: "hidden", background: colors.panelSolid, border: colors.panelBorder, boxShadow: shadows.panel }}>
        <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <div style={{ marginTop: 12, textAlign: "center", fontFamily: body, fontWeight: 800, fontSize: 32, color: colors.ink }}>{label}</div>
    </div>
  );
};

/** Big number with a caption (price tag, budget). The payoff number gets its own card, not a header slot. */
export const BigFact: React.FC<{ big: string; sub?: string; subAt?: number; x: number; y: number; w: number; at?: number; note?: string; noteAt?: number; bigSize?: number; color?: string }> = ({ big, sub, subAt, x, y, w, at = 0, note, noteAt, bigSize = 92, color = colors.accent }) => {
  const frame = useCurrentFrame();
  if (frame < at) return null;
  const a = inAt(frame, at, 12);
  const b = inAt(frame, subAt ?? at + 6, 12);
  const c = inAt(frame, noteAt ?? at + 14, 12);
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, boxSizing: "border-box", padding: "22px 26px 24px", borderRadius: 28, background: colors.panel, border: colors.panelBorder, boxShadow: shadows.panel, opacity: a, scale: String(interpolate(a, [0, 1], [1.25, 1], { easing: Easing.out(Easing.back(1.4)) })), transformOrigin: "50% 50%" }}>
      <div style={{ fontFamily: display, fontWeight: 900, fontSize: bigSize, lineHeight: 1, letterSpacing: -2, color }}>{big}</div>
      {sub ? <div style={{ marginTop: 10, fontFamily: body, fontWeight: 800, fontSize: 32, color: colors.ink, opacity: b, translate: `0px ${(1 - b) * 14}px` }}>{sub}</div> : null}
      {note ? <div style={{ marginTop: 8, fontFamily: body, fontWeight: 700, fontSize: 28, color: colors.muted, opacity: c }}>{note}</div> : null}
    </div>
  );
};

/** Dashed pulsing ring with a "?" — the missing thing (the heroine, a step). Centred on cx/cy. */
export const MissingMark: React.FC<{ cx: number; cy: number; r?: number; at?: number }> = ({ cx, cy, r = 86, at = 0 }) => {
  const frame = useCurrentFrame();
  if (frame < at) return null;
  const a = inAt(frame, at, 12);
  const pulse = 1 + 0.05 * Math.sin((frame - at) / 5);
  return (
    <div style={{ position: "absolute", left: cx - r, top: cy - r, width: r * 2, height: r * 2, boxSizing: "border-box", borderRadius: 999, border: `7px dashed ${colors.accent}`, background: colors.scrim, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: display, fontWeight: 900, fontSize: r, color: colors.accent, opacity: a, scale: String(pulse * (0.6 + a * 0.4)) }}>
      ?
    </div>
  );
};

/* ---------- split layout: talking-head close-up in a window on the left, notes in a column on the right ---------- */

type Range = { from: number; to: number };

/** Shrinks the timeline layer into a rounded window (left, x/top) for the given frame ranges; 12-frame ease.
 *  (Stage does the same into a centred top window; kept separate because the two move from different origins.) */
export const SplitStage: React.FC<{ windows: Range[]; scale?: number; x?: number; top?: number; children: React.ReactNode }> = ({ windows, scale = 0.5, x = 56, top = N.bandTop, children }) => {
  const frame = useCurrentFrame();
  const p = windowProgress(frame, windows);
  const s = 1 - (1 - scale) * p;
  return (
    <AbsoluteFill style={{ background: colors.boardBg }}>
      <AbsoluteFill style={{ transformOrigin: "0% 0%", translate: `${x * p}px ${top * p}px`, scale: String(s), borderRadius: (p * 40) / s, overflow: "hidden", boxShadow: p > 0 ? shadows.panel : undefined }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

/** A list item that lands on its word; `icon` is an optional element (e.g. <Mark/>), not an emoji. */
export type SideItem = { at: number; icon?: React.ReactNode; text: string };

/** Right column: header + items that appear on their words (+ optional footer chip and a big-number card). */
export const SideList: React.FC<{ x: number; y: number; w: number; header: string; items: SideItem[]; footer?: { at: number; text: string }; fact?: { at: number; big: string; sub: string; note?: string } }> = ({ x, y, w, header, items, footer, fact }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const o = outBefore(frame, durationInFrames, 8);
  const h = inAt(frame, 6, 12);
  const step = 78;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, opacity: o }}>
      <div style={{ fontFamily: display, fontWeight: 800, fontSize: 32, lineHeight: 1.15, color: colors.muted, opacity: h, height: 72 }}>{header}</div>
      {items.map((it, i) => {
        if (frame < it.at) return null;
        const a = inAt(frame, it.at, 10);
        return (
          <div key={it.text} style={{ position: "absolute", left: 0, top: 72 + i * step, width: w, height: 66, boxSizing: "border-box", display: "flex", alignItems: "center", gap: 14, padding: "0 20px", borderRadius: 18, background: colors.chip, border: colors.panelBorder, fontFamily: body, fontWeight: 800, fontSize: 33, color: colors.ink, opacity: a, translate: `${(1 - a) * 40}px 0px` }}>
            {it.icon ?? null}
            <span>{it.text}</span>
          </div>
        );
      })}
      {footer && frame >= footer.at ? (
        <div style={{ position: "absolute", left: 0, top: 72 + items.length * step + 8, width: w, boxSizing: "border-box", padding: "14px 20px", borderRadius: 18, background: colors.accent, color: colors.onAccent, fontFamily: body, fontWeight: 800, fontSize: 29, lineHeight: 1.15, opacity: inAt(frame, footer.at, 10), scale: String(0.9 + inAt(frame, footer.at, 10) * 0.1) }}>
          {footer.text}
        </div>
      ) : null}
      {fact ? <BigFact big={fact.big} sub={fact.sub} note={fact.note} x={0} y={72 + items.length * step + 100} w={w} at={fact.at} bigSize={64} color={colors.accent2} /> : null}
    </div>
  );
};

/** Right column: an image tile with review notes under it (✕ rows). */
export const SideReview: React.FC<{ x: number; y: number; w: number; header: string; image: string; imageLabel?: string; items: SideItem[] }> = ({ x, y, w, header, image, imageLabel, items }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const o = outBefore(frame, durationInFrames, 8);
  const h = inAt(frame, 6, 12);
  const im = inAt(frame, 14, 14);
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, opacity: o }}>
      <div style={{ fontFamily: display, fontWeight: 800, fontSize: 32, color: colors.muted, opacity: h, height: 56 }}>{header}</div>
      <div style={{ position: "relative", width: w, height: w, borderRadius: 24, overflow: "hidden", border: colors.panelBorder, background: colors.panelSolid, opacity: im, scale: String(0.94 + im * 0.06) }}>
        <Img src={staticFile(image)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        {imageLabel ? <div style={{ position: "absolute", left: 12, top: 12, padding: "6px 14px", borderRadius: 999, background: colors.panel, fontFamily: body, fontWeight: 800, fontSize: 28, color: colors.ink }}>{imageLabel}</div> : null}
      </div>
      {items.map((it) => {
        if (frame < it.at) return null;
        const a = inAt(frame, it.at, 10);
        return <MarkRow key={it.text} text={it.text} ok={false} size={31} h={72} style={{ marginTop: 14, opacity: a, translate: `${(1 - a) * 40}px 0px` }} />;
      })}
    </div>
  );
};

/** Right column: a chat bubble with a quote and its author, plus an optional follow-up pill. */
export const SideBubble: React.FC<{ x: number; y: number; w: number; text: string; who: string; then?: { at: number; text: string } }> = ({ x, y, w, text, who, then }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const o = outBefore(frame, durationInFrames, 8);
  const a = inAt(frame, 4, 14);
  const b = inAt(frame, 16, 12);
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, opacity: o }}>
      <div style={{ padding: "24px 24px 26px", borderRadius: "28px 28px 28px 8px", background: colors.ink, color: colors.bg, fontFamily: body, fontWeight: 800, fontSize: 34, lineHeight: 1.22, boxShadow: shadows.pill, opacity: a, scale: String(0.9 + a * 0.1), transformOrigin: "0% 100%" }}>{text}</div>
      <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 10, fontFamily: body, fontWeight: 800, fontSize: 28, color: colors.muted, opacity: b }}>
        <span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 999, background: colors.claude }} />
        {who}
      </div>
      {then && frame >= then.at ? (
        <div style={{ marginTop: 30, display: "inline-block", padding: "14px 26px", borderRadius: 999, background: colors.accent, color: colors.onAccent, fontFamily: display, fontWeight: 800, fontSize: 34, opacity: inAt(frame, then.at, 12), scale: String(0.7 + inAt(frame, then.at, 12) * 0.3), transformOrigin: "0% 50%" }}>
          {then.text}
        </div>
      ) : null}
    </div>
  );
};

/** Moved to ui/Fade.tsx; re-exported so old generators keep compiling. */
export { FadeToBlack } from "../ui/Fade";

/** Channel pill, centred (EndCard, end boards). */
export const ChannelPill: React.FC<{ label?: string; top?: number; at?: number }> = ({ label = brand.channel, top = 900, at = 6 }) => {
  const frame = useCurrentFrame();
  const p = inAt(frame, at, 14);
  if (!label) return null;   // no channel name given → no pill
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top, textAlign: "center", opacity: p, translate: `0px ${(1 - p) * 20}px` }}>
      <span style={{ display: "inline-block", padding: "14px 30px", borderRadius: 999, background: colors.accent, color: colors.onAccent, fontFamily: body, fontWeight: 800, fontSize: 34 }}>{label}</span>
    </div>
  );
};

export type LedgerRow = { at: number; name: string; value: string; note?: string; noteAt?: number };

/** A receipt: rows land on the spoken numbers (name ..... value, optional small note under the row). Lands flat. */
export const Ledger: React.FC<{ x: number; y: number; w: number; title: string; sub?: string; rows: LedgerRow[] }> = ({ x, y, w, title, sub, rows }) => {
  const frame = useCurrentFrame();
  const a = inAt(frame, 4, 14);
  const rule = `3px dashed ${alpha(colors.paperInk, 0.35)}`;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, boxSizing: "border-box", padding: "34px 40px 30px", borderRadius: 34, background: colors.paper, color: colors.paperInk, boxShadow: shadows.panel, opacity: a, translate: `0px ${(1 - a) * 50}px` }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", borderBottom: rule, paddingBottom: 18 }}>
        <span style={{ fontFamily: display, fontWeight: 900, fontSize: 52, letterSpacing: -1 }}>{title}</span>
        {sub ? <span style={{ fontFamily: body, fontWeight: 800, fontSize: 28, opacity: 0.6 }}>{sub}</span> : null}
      </div>
      {rows.map((r, i) => {
        if (frame < r.at) return null;
        const p = inAt(frame, r.at, 10);
        const n = inAt(frame, r.noteAt ?? r.at + 8, 10);
        return (
          <div key={i} style={{ paddingTop: 22, opacity: p, translate: `${(1 - p) * -30}px 0px` }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
              <span style={{ fontFamily: body, fontWeight: 800, fontSize: 40, whiteSpace: "nowrap" }}>{r.name}</span>
              <span style={{ flex: 1, borderBottom: `3px dotted ${alpha(colors.paperInk, 0.35)}`, translate: "0px -8px" }} />
              <span style={{ fontFamily: display, fontWeight: 900, fontSize: 44, letterSpacing: -1, whiteSpace: "nowrap", color: colors.paperAccent }}>{r.value}</span>
            </div>
            {r.note ? <div style={{ marginTop: 6, fontFamily: body, fontWeight: 700, fontSize: 28, opacity: 0.62 * n }}>{r.note}</div> : null}
          </div>
        );
      })}
    </div>
  );
};

/** Full-bleed generated plate (scripts/codex_image.sh, under public/screens/) with a slow push-in — e.g. the closing frame that matches an ArtCover. */
export const Plate: React.FC<{ src: string; fadeIn?: number; zoomFrom?: number; zoomTo?: number; bg?: string }> = ({ src, fadeIn = 14, zoomFrom = 1, zoomTo = 1.07, bg = colors.bg }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const o = interpolate(frame, [0, Math.max(1, fadeIn)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const z = interpolate(frame, [0, Math.max(1, durationInFrames)], [zoomFrom, zoomTo], { extrapolateRight: "clamp", easing: Easing.linear });
  return (
    <AbsoluteFill style={{ opacity: o, background: bg }}>
      <Img src={staticFile(src)} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", scale: String(z), transformOrigin: "50% 60%" }} />
    </AbsoluteFill>
  );
};
