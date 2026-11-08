import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { N } from "../numbers";
import { alpha, colors, safe, shadows } from "../theme";
import { countUp, fmt } from "../ui/anim";
import { blockLife, blockW, clampX } from "./shared";

/* A repository card (owner / name, «Public» pill, one-line description, language dot, a star count that counts up) and a
 * list of them that arrive one after another (card craft from HyperFrames x-post / reddit-post / yt-comment-card).
 * No vendor logo: the repo icon is a plain book outline. Heights are fixed (repoCardH) so a list lays out without measuring. */

export type Repo = {
  owner: string;
  name: string;
  /** one line, ≤ ~40 characters; without it the card is compact */
  desc?: string;
  stars: number;
  lang?: string;
  /** language dot colour (a palette token) */
  langColor?: string;
};

/** Card height: 222 px with a description, 166 px without. */
export const repoCardH = (r: { desc?: string }) => (r.desc ? 222 : 166);

const starsText = (n: number, short: boolean) => (short && n >= 1000 ? `${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}k` : fmt(n));

const RepoIcon: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0, display: "block" }}>
    <path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v14.5H6.75A1.75 1.75 0 0 0 5 19.25zM5 19.25A1.75 1.75 0 0 0 6.75 21H19M9 7h6" fill="none" stroke={colors.muted} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const StarIcon: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0, display: "block" }}>
    <path d="M12 3.2l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z" fill={colors.accent2} stroke={colors.accent2} strokeWidth={1.2} strokeLinejoin="round" />
  </svg>
);

type CardProps = Repo & {
  x?: number;
  y?: number;
  w?: number;
  /** card lands */
  at?: number;
  /** stars start counting (default at + 6, 22 frames) */
  starsAt?: number;
  /** 31.2k instead of 31 200 */
  short?: boolean;
  /** 0..1: fade back (another card is picked) */
  dim?: number;
  /** 0..1: accent rim (this card is picked) */
  pick?: number;
  until?: number;
};

export const RepoCard: React.FC<CardProps> = ({ owner, name, desc, stars, lang, langColor = colors.accent, x = safe.x, y = N.bandTop, w = blockW, at = 0, starsAt, short = false, dim = 0, pick = 0, until }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const life = blockLife(frame, fps, at, until, durationInFrames, { damping: 16, mass: 1.2 });
  if (frame < at || life.o <= 0) return null;
  const s0 = starsAt ?? at + 6;
  const n = countUp(frame, s0, s0 + 22, 0, stars);
  const line: React.CSSProperties = { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" };
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        height: repoCardH({ desc }),
        boxSizing: "border-box",
        padding: "28px 34px",
        borderRadius: 28,
        background: colors.panel,
        border: colors.panelBorder,
        boxShadow: shadows.panel,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        opacity: life.o * (1 - 0.55 * dim),
        translate: `0px ${(1 - life.e) * 48 + life.x * 20}px`,
        scale: String(0.97 + 0.03 * life.e),
        transformOrigin: "50% 100%",
      }}
    >
      {pick > 0 ? <div style={{ position: "absolute", inset: -2, borderRadius: 28, border: `3px solid ${colors.accent}`, opacity: pick }} /> : null}
      <div style={{ display: "flex", alignItems: "center", gap: 16, fontFamily: body, fontSize: 40, lineHeight: 1.2 }}>
        <RepoIcon size={40} />
        {/* the owner gives way first: a long name keeps its own text */}
        <span style={{ ...line, minWidth: 0, flexShrink: 1, color: colors.muted, fontWeight: 600, marginRight: -4 }}>{owner} /</span>
        <span style={{ ...line, minWidth: 0, flexShrink: 0, maxWidth: "62%", color: colors.ink, fontWeight: 800 }}>{name}</span>
        <span style={{ flexShrink: 0, padding: "2px 16px", borderRadius: 999, border: `2px solid ${alpha(colors.ink, 0.22)}`, color: colors.muted, fontWeight: 700, fontSize: 28 }}>Public</span>
      </div>
      {desc ? <div style={{ ...line, fontFamily: body, fontWeight: 600, fontSize: 34, color: colors.muted }}>{desc}</div> : null}
      <div style={{ display: "flex", alignItems: "center", gap: 14, fontFamily: body, fontWeight: 700, fontSize: 34, color: colors.muted }}>
        {lang ? (
          <>
            <span style={{ width: 22, height: 22, borderRadius: 99, background: langColor, flexShrink: 0 }} />
            <span style={line}>{lang}</span>
          </>
        ) : null}
        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          <StarIcon size={38} />
          <span style={{ fontFamily: display, fontWeight: 800, fontSize: 40, color: colors.ink, fontVariantNumeric: "tabular-nums", letterSpacing: -0.5 }}>{starsText(n, short)}</span>
        </span>
      </div>
    </div>
  );
};

type ListProps = {
  /** cards in order; each lands on its `at` (anchor it to the spoken name), or the list lands as a group from `at` */
  items: (Repo & { at?: number })[];
  x?: number;
  y?: number;
  w?: number;
  gap?: number;
  at?: number;
  short?: boolean;
  /** index of the card to pick at `pickAt`: accent rim, the others fade back */
  pick?: number;
  pickAt?: number;
  until?: number;
};

/** A stack of RepoCards; 4 with descriptions or 5–6 compact ones fit the content band (y 300–1350). */
export const RepoList: React.FC<ListProps> = ({ items, x = safe.x, y = N.bandTop, w = blockW, gap = 18, at = 0, short, pick, pickAt, until }) => {
  const frame = useCurrentFrame();
  const step = items.length > 1 ? Math.min(4, 15 / (items.length - 1)) : 0;
  const p = pick === undefined || pickAt === undefined ? 0 : interpolate(frame, [pickAt, pickAt + 10], [0, 1], clampX);
  let top = y;
  return (
    <>
      {items.map((it, i) => {
        const t = top;
        top += repoCardH(it) + gap;
        return <RepoCard key={i} {...it} x={x} y={t} w={w} at={it.at ?? Math.round(at + i * step)} short={short} pick={i === pick ? p : 0} dim={pick !== undefined && i !== pick ? p : 0} until={until} />;
      })}
    </>
  );
};
