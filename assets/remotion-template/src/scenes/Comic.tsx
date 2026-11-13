import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, staticFile, useCurrentFrame } from "remotion";
import { display } from "../fonts";
import { N } from "../numbers";
import { comic, footagePath, H, W } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** One comic sound word: pops with an overshoot on `at`, shakes like a laugh (decaying), leaves faster than it came. */
export type ComicWord = { text: string; at: number; x: number; y: number; size: number; rot?: number; shake?: number; until?: number };

const Word: React.FC<{ w: ComicWord; until: number }> = ({ w, until }) => {
  const f = useCurrentFrame();
  const t = f - w.at;
  if (t < 0 || f > until + 6) return null;
  const pop = interpolate(t, [0, 5, 9], [0.2, 1.16, 1], { ...clamp, easing: Easing.out(Easing.quad) });
  const out = interpolate(f, [until, until + 6], [1, 0], clamp);
  const shake = (w.shake ?? 4) * Math.sin(t * 0.95) * Math.exp(-t / 34);
  const bounce = -Math.abs(Math.sin(t * 0.48)) * 10 * Math.exp(-t / 40);
  const sw = Math.max(8, w.size * 0.085);
  // SVG text: the outline sits under the fill (paint-order), the red block is the same word offset — flat, no blur
  const txt = (dx: number, dy: number, fill: string, stroke: string, k: number) => (
    <text x={dx} y={dy} textAnchor="middle" dominantBaseline="central" fontFamily={display} fontWeight={900} fontSize={w.size}
      letterSpacing={-w.size * 0.02} fill={fill} stroke={stroke} strokeWidth={sw * k} strokeLinejoin="round" paintOrder="stroke">
      {w.text}
    </text>
  );
  const off = w.size * 0.07;
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, overflow: "visible", opacity: out }}>
      <g transform={`translate(${w.x * W} ${w.y * H + bounce}) rotate(${(w.rot ?? -7) + shake}) scale(${pop * (1 + (1 - out) * 0.12)}) skewX(-8)`}>
        {txt(off, off, comic.pop, comic.ink, 1)}
        {txt(0, 0, comic.fill, comic.ink, 1)}
      </g>
    </svg>
  );
};

/** Comic sound words over the footage (a shout, «ПОЛИЦИЯ!»): optional jagged burst with halftone dots behind them. */
export const ComicSfx: React.FC<{ words: ComicWord[]; until: number; burst?: { x: number; y: number; r: number; at: number } }> = ({ words, until, burst }) => {
  const f = useCurrentFrame();
  let b: React.ReactNode = null;
  if (burst) {
    const t = f - burst.at;
    const s = interpolate(t, [0, 6, 10], [0.1, 1.1, 1], { ...clamp, easing: Easing.out(Easing.quad) }) * interpolate(f, [until, until + 6], [1, 0.85], clamp);
    const o = interpolate(f, [until, until + 6], [1, 0], clamp) * (t >= 0 ? 1 : 0);
    const n = 14; const pts: string[] = [];
    for (let i = 0; i < n * 2; i++) {
      const a = (i / (n * 2)) * Math.PI * 2 + Math.sin(i * 1.7) * 0.06;
      const rr = burst.r * (i % 2 ? 0.66 + 0.06 * Math.sin(i * 2.3) : 1 + 0.08 * Math.cos(i * 1.3));
      pts.push(`${(Math.cos(a) * rr * 1.25).toFixed(1)},${(Math.sin(a) * rr).toFixed(1)}`);
    }
    b = (
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, overflow: "visible", opacity: o }}>
        <defs>
          <pattern id="halftone" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">
            <circle cx="7" cy="7" r="3.2" fill={comic.dot} />
          </pattern>
        </defs>
        <g transform={`translate(${burst.x * W} ${burst.y * H}) rotate(${-6 + 2 * Math.sin(f * 0.3)}) scale(${s})`}>
          <polygon points={pts.join(" ")} fill={comic.paper} stroke={comic.ink} strokeWidth={9} strokeLinejoin="round" />
          <polygon points={pts.join(" ")} fill="url(#halftone)" />
        </g>
      </svg>
    );
  }
  return (
    <AbsoluteFill>
      {b}
      {words.map((w, i) => <Word key={i} w={w} until={w.until ?? until} />)}
    </AbsoluteFill>
  );
};

/**
 * Comic words BEHIND a person (the banana's laugh on the bike): the clip's own footage again with the Clip's punch / drift
 * (like Censor.tsx's BlurPatch: `at` = frames into the clip, `hold` = its length), the words, then the person cut out of the
 * same frames (person_matte.py → a VP9 WebM with alpha) on top — the banana rides in front of his own «ХА-ХА-ХА».
 */
export const ComicBehind: React.FC<{ src: string; trimBefore: number; matte: string; words: ComicWord[]; until: number; at?: number; punch?: number; drift?: number; hold?: number }> = ({
  src, trimBefore, matte, words, until, at = 0, punch = 1, drift = 0, hold = 1,
}) => {
  const f = useCurrentFrame();
  const scale = interpolate(f + at, [0, Math.max(1, hold)], [punch, punch + drift], { ...clamp, easing: Easing.linear });
  return (
    <AbsoluteFill style={{ transformOrigin: `50% ${((N.punchCenterY / H) * 100).toFixed(2)}%`, scale: String(scale) }}>
      <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} muted objectFit="cover" style={{ width: "100%", height: "100%" }} />
      <ComicSfx words={words} until={until} />
      <AbsoluteFill>
        <OffthreadVideo src={staticFile(matte)} muted transparent style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
