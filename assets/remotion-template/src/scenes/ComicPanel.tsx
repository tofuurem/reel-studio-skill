import React, { useId } from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { N } from "../numbers";
import { comic, footagePath, H, safe, W } from "../theme";
import { ComicSfx, type ComicWord } from "./Comic";

/* Comic panels INSIDE the reel (styles.md «comic»): the Spider-Verse look of the generated covers (covers.md — balloon,
   box, misprint title, plate) moved into the montage. The picture is a plate generated with scripts/codex_image.sh from a
   REAL frame of the reel (no text in it — image models garble lettering, Cyrillic worst of all), or a real clip in a comic
   frame; every word is set here. Two placements:
   - inset (default): a framed panel over the talking head, in the face-free band (`top` / `maxH` from R.free_top /
     R.free_bottom; R.comic_panel picks the taller band);
   - full: the whole frame instead of a cutaway (R.comic_panel(..., full=True) widens it around cuts like R.cutaway).
   A balloon may point its tail at the speaker's mouth on the talking head — his own line as comic speech. All coordinates
   are canvas px (1080×1920), all cues LOCAL frames of the Sequence; the panel enters on 0 and leaves at the end. Flat ink
   only: hard offset shadows (no blur), no glow, no blend modes. */

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const sid = (id: string) => id.replace(/[^a-zA-Z0-9_-]/g, "");

/** Pop with a small overshoot (0 before `at`), the same curve for panels, balloons and boxes. */
const pop = (t: number, len: number, from = 0.86) =>
  t < 0 ? 0 : interpolate(t, [0, len * 0.6, len], [from, 1.03, 1], { ...clamp, easing: Easing.out(Easing.quad) });

/** Letters with a print misregistration: a cyan copy down-right, a magenta copy up-left, the fill with an ink outline on top. */
export const Misprint: React.FC<{ text: string; size: number; top: number; at?: number; fill?: string; left?: number; center?: boolean; rotate?: number; lh?: number }> = ({
  text, size: wanted, top, at = 0, fill = comic.fill, left = 0, center = true, rotate = -2, lh = 0.95,
}) => {
  const t = useCurrentFrame() - at;
  if (t < 0) return null;
  // Unbounded caps take ≈ 0.9 em per letter with the misprint offsets: the longest line must fit the safe width
  const longest = Math.max(...text.split("\n").map((l) => l.length), 1);
  const size = Math.min(wanted, Math.floor((W - 2 * safe.x) / (longest * 0.9)));
  const s = pop(t, N.comicPanelIn, 0.7);
  const d = interpolate(t, [0, N.comicPanelIn + 4], [2.2, 1], clamp); // the plates slide into register
  const base: React.CSSProperties = { position: "absolute", top: 0, left: 0, fontFamily: display, fontWeight: 900, fontSize: size, lineHeight: lh, whiteSpace: "pre", textAlign: center ? "center" : "left", textTransform: "uppercase" };
  const sw = `${size * 0.06}px ${comic.ink}`;
  return (
    <div style={{ position: "absolute", top, left: center ? "50%" : left, translate: center ? "-50% 0" : undefined, rotate: `${rotate}deg`, scale: String(s) }}>
      <div style={{ ...base, position: "relative", visibility: "hidden" }}>{text}</div>
      <div style={{ ...base, color: comic.cyan, transform: `translate(${size * 0.06 * d}px, ${size * 0.055 * d}px)`, WebkitTextStroke: sw, paintOrder: "stroke fill" }}>{text}</div>
      <div style={{ ...base, color: comic.magenta, transform: `translate(${-size * 0.045 * d}px, ${-size * 0.035 * d}px)` }}>{text}</div>
      <div style={{ ...base, color: fill, WebkitTextStroke: sw, paintOrder: "stroke fill" }}>{text}</div>
    </div>
  );
};

/** Narrator box («MEANWHILE…», «spoiler: it took ten days»): a light rectangle, ink frame, hard shadow; slides in on `at`. */
export type BoxSpec = { text: string; x: number; y: number; at?: number; size?: number; rotate?: number; bg?: "paper" | "yellow" };
export const ComicBox: React.FC<BoxSpec> = ({ text, x, y, at = 6, size = 40, rotate = -2, bg = "paper" }) => {
  const t = useCurrentFrame() - at;
  if (t < 0) return null;
  const k = interpolate(t, [0, N.comicPanelIn], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  return (
    <div style={{ position: "absolute", left: x, top: y, rotate: `${rotate}deg`, translate: `${(1 - k) * -40}px 0`, opacity: k, background: bg === "yellow" ? comic.fill : comic.paper, color: comic.ink, border: `6px solid ${comic.ink}`, boxShadow: `${N.comicShadow * 0.65}px ${N.comicShadow * 0.65}px 0 ${comic.ink}`, padding: `${size * 0.28}px ${size * 0.5}px ${size * 0.32}px`, fontFamily: body, fontWeight: 900, fontSize: size, lineHeight: 1.05, letterSpacing: 0.5, textTransform: "uppercase", whiteSpace: "pre" }}>
      {text}
    </div>
  );
};

/** Speech balloon (ellipse) or shout (jagged) with a tail to (tailX, tailY); `accent` = indices of lines set in magenta. */
export type BalloonSpec = { lines: string[]; accent?: number[]; cx: number; cy: number; rx: number; ry: number; tailX: number; tailY: number; at?: number; size?: number; rotate?: number; kind?: "speech" | "shout" };
export const ComicBalloon: React.FC<BalloonSpec> = ({ lines, accent = [], cx, cy, rx, ry, tailX, tailY, at = 4, size = 60, rotate = -3, kind = "speech" }) => {
  const t = useCurrentFrame() - at;
  if (t < 0) return null;
  const s = pop(t, N.comicPanelIn, 0.3);
  const sh = N.comicShadow;
  // tail base on the balloon edge, towards the target
  const ang = Math.atan2(tailY - cy, tailX - cx);
  const bx = cx + Math.cos(ang) * rx * 0.82, by = cy + Math.sin(ang) * ry * 0.82;
  const nx = -Math.sin(ang) * 48, ny = Math.cos(ang) * 48;
  const tail = `M ${bx + nx} ${by + ny} L ${tailX} ${tailY} L ${bx - nx} ${by - ny} Z`;
  let shape: React.ReactNode;
  if (kind === "shout") {
    const n = 16; const pts: string[] = [];
    for (let i = 0; i < n * 2; i++) {
      const a = (i / (n * 2)) * Math.PI * 2;
      const k = i % 2 ? 0.84 + 0.04 * Math.sin(i * 2.3) : 1.08 + 0.05 * Math.cos(i * 1.3);
      pts.push(`${(cx + Math.cos(a) * rx * k).toFixed(1)},${(cy + Math.sin(a) * ry * k).toFixed(1)}`);
    }
    shape = <polygon points={pts.join(" ")} />;
  } else shape = <ellipse cx={cx} cy={cy} rx={rx} ry={ry} />;
  return (
    <AbsoluteFill style={{ transformOrigin: `${cx}px ${cy}px`, scale: String(s), rotate: `${rotate}deg` }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        <g transform={`translate(${sh} ${sh})`} fill={comic.cyan}>{shape}<path d={tail} /></g>
        <g fill={comic.tag} stroke={comic.ink} strokeWidth={9} strokeLinejoin="round">{shape}<path d={tail} /></g>
        {/* cover the tail's root line inside the balloon */}
        <g fill={comic.tag}>{kind === "shout" ? null : <ellipse cx={cx} cy={cy} rx={rx - 5} ry={ry - 5} />}</g>
      </svg>
      <div style={{ position: "absolute", left: cx - rx * 0.85, top: cy, width: rx * 1.7, translate: "0 -50%", textAlign: "center", fontFamily: display, fontWeight: 900, fontSize: size, lineHeight: 1.04, color: comic.ink, letterSpacing: -0.5, textTransform: "uppercase" }}>
        {lines.map((l, i) => <div key={i} style={{ color: accent.includes(i) ? comic.magenta : comic.ink }}>{l}</div>)}
      </div>
    </AbsoluteFill>
  );
};

/** Halftone dots growing towards one corner (print shading over the plate; SVG only, no blend modes). */
const Halftone: React.FC<{ w: number; h: number; corner?: "br" | "tl" }> = ({ w, h, corner = "br" }) => {
  const id = sid(useId());
  const [x, y] = corner === "br" ? ["100%", "100%"] : ["0%", "0%"];
  return (
    <svg width={w} height={h} style={{ position: "absolute", inset: 0 }}>
      <defs>
        <pattern id={`ht${id}`} width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">
          <circle cx="8" cy="8" r="3.6" fill={comic.ink} />
        </pattern>
        <radialGradient id={`hg${id}`} cx={x} cy={y} r="75%">
          <stop offset="0%" stopColor="white" stopOpacity="0.55" />
          <stop offset="100%" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <mask id={`hm${id}`}><rect width={w} height={h} fill={`url(#hg${id})`} /></mask>
      </defs>
      <rect width={w} height={h} fill={`url(#ht${id})`} mask={`url(#hm${id})`} />
    </svg>
  );
};

type PanelProps = {
  /** public/ path of the generated plate (comic/p1.png) or a clip (footage/c0042.mp4 with trimBefore, or any public .mp4). */
  src: string;
  trimBefore?: number;
  /** true = the whole frame instead of a cutaway (widened around cuts by R.comic_panel). */
  full?: boolean;
  /** inset: band top and the most height it may take (from R.free_top / R.free_bottom), picture ratio w/h, tilt in degrees. */
  top?: number;
  maxH?: number;
  ratio?: number;
  rotate?: number;
  zoomTo?: number;
  /** where the plate's subject sits (CSS object-position), e.g. "50% 30%". */
  focus?: string;
  halftone?: boolean;
  title?: { text: string; top: number; size?: number; at?: number };
  box?: BoxSpec;
  balloon?: BalloonSpec;
  /** sound words over the panel (scenes/Comic.tsx), each on a real sound. */
  words?: ComicWord[];
  /** someone else's footage inside the frame: «gameplay: Author · YouTube». */
  credit?: string;
};

/** A comic panel over the talking head (inset) or instead of a cutaway (full). See the file header. */
export const ComicPanel: React.FC<PanelProps> = ({ src, trimBefore = 0, full = false, top = N.cardTop, maxH, ratio = 4 / 5, rotate, zoomTo = 1.05, focus = "50% 50%", halftone = true, title, box, balloon, words, credit }) => {
  const f = useCurrentFrame();
  const { durationInFrames: dur } = useVideoConfig();
  const B = N.comicBorder, S = N.comicShadow;
  const out = interpolate(f, [dur - 1 - N.comicPanelOut, dur - 1], [1, 0], clamp);
  const misreg = interpolate(f, [0, N.comicPanelIn], [18, 0], { ...clamp, easing: Easing.out(Easing.cubic) });
  const zoom = interpolate(f, [0, Math.max(1, dur)], [1, zoomTo], { ...clamp, easing: Easing.linear });

  // geometry: full = the canvas minus a paper gutter; inset = full width of the safe area, shrunk to fit maxH
  let x: number, y: number, w: number, h: number;
  if (full) {
    x = 28; y = 28; w = W - 56; h = H - 56;
  } else {
    w = W - 2 * safe.x; h = Math.round(w / ratio);
    // never past the band: a band lower than comicPanelMinH + the shadow squeezes the panel (reelgen logs a WARNING for it)
    if (maxH && h + S > maxH) { h = Math.max(1, maxH - S); w = Math.min(W - 2 * safe.x, Math.round(h * ratio)); }
    x = Math.round((W - w) / 2); y = top;
  }
  const isVideo = /\.(mp4|mov|webm)$/i.test(src);
  const media = isVideo ? (
    <Video src={staticFile(src.startsWith("footage/") ? footagePath(src) : src)} trimBefore={trimBefore} muted objectFit="cover" style={{ width: "100%", height: "100%", objectPosition: focus, scale: String(zoom) }} />
  ) : (
    <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: focus, scale: String(zoom) }} />
  );
  const frameBox = (dx: number, dy: number, color: string) => (
    <div style={{ position: "absolute", left: x + dx, top: y + dy, width: w, height: h, border: `${B}px solid ${color}`, boxSizing: "border-box", opacity: misreg / 18 }} />
  );
  const panelPop = full ? interpolate(f, [0, N.comicPanelIn], [1.04, 1], { ...clamp, easing: Easing.out(Easing.quad) }) : pop(f, N.comicPanelIn);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      {full ? <AbsoluteFill style={{ background: comic.paper }} /> : null}
      <AbsoluteFill style={{ transformOrigin: `${x + w / 2}px ${y + h / 2}px`, scale: String(panelPop), rotate: `${rotate ?? (full ? 0 : -1.5)}deg` }}>
        {frameBox(misreg, misreg, comic.cyan)}
        {frameBox(-misreg * 0.7, -misreg * 0.7, comic.magenta)}
        <div style={{ position: "absolute", left: x, top: y, width: w, height: h, border: `${B}px solid ${comic.ink}`, boxSizing: "border-box", boxShadow: full ? undefined : `${S}px ${S}px 0 ${comic.ink}`, background: comic.paper, overflow: "hidden" }}>
          {media}
          {halftone ? <Halftone w={w - 2 * B} h={h - 2 * B} /> : null}
          {credit ? (
            <div style={{ position: "absolute", right: 14, bottom: 10, padding: "4px 12px", background: comic.paper, border: `3px solid ${comic.ink}`, fontFamily: body, fontWeight: 700, fontSize: N.creditFontPx, color: comic.ink }}>{credit}</div>
          ) : null}
        </div>
      </AbsoluteFill>
      {title ? <Misprint text={title.text} size={title.size ?? 104} top={title.top} at={title.at ?? 2} /> : null}
      {box ? <ComicBox {...box} /> : null}
      {balloon ? <ComicBalloon {...balloon} /> : null}
      {words?.length ? <ComicSfx words={words} until={dur - 1 - N.comicPanelOut} /> : null}
    </AbsoluteFill>
  );
};
