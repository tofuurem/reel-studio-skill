import React, { createContext, useContext, useEffect, useState } from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useDelayRender, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { N } from "../numbers";
import { alpha, colors, shadows } from "../theme";
import { countUp, fmt, sp, steps } from "../ui/anim";
import { Mark } from "../ui/Mark";

/**
 * Motion kit v2 (advanced; examples/TripoStory.example.tsx shows it in use) — calm but alive boards:
 *  - a slow camera over the board with parallax layers (depth 0 = screen overlay, 1 = the hero plane);
 *  - values change on spoken words through springs that overlap (no dead stop between two moves);
 *  - objects carry the story: the same figure stays on screen across beats and changes state instead of being replaced;
 *  - numbers count, labels roll, outlines and overlays explain a property ON the object.
 * Cues are LOCAL frames like everywhere else; elements land flat (no tilt) and nothing glows.
 */

// time helpers live in ui/anim.ts; re-exported here because generators import them from the Motion kit
export { countUp, fmt, sp, steps };

// ---------- camera + parallax ----------

type Cam = { x: number; y: number; s: number; r: number };
const CamCtx = createContext<Cam>({ x: 0, y: 0, s: 1, r: 0 });

/** Camera state for the subtree: x/y in px (positive x = camera moves right, content moves left), s = zoom, r = roll in degrees. */
export const Camera: React.FC<{ cam: Cam; children: React.ReactNode }> = ({ cam, children }) => <CamCtx.Provider value={cam}>{children}</CamCtx.Provider>;

/** A plane at a depth: 0 = fixed screen overlay, 1 = hero plane, <1 = far (moves less), >1 = near (moves more). */
export const Layer: React.FC<{ depth?: number; children: React.ReactNode }> = ({ depth = 1, children }) => {
  const c = useContext(CamCtx);
  return <AbsoluteFill style={{ transformOrigin: "540px 960px", translate: `${-c.x * depth}px ${-c.y * depth}px`, scale: String(1 + (c.s - 1) * depth), rotate: `${c.r * depth}deg` }}>{children}</AbsoluteFill>;
};

// ---------- set pieces ----------

/** Board background with a soft light that can follow the hero (background light, not a UI glow). */
export const Backdrop: React.FC<{ glowX?: number; glowY?: number }> = ({ glowX = 540, glowY = 880 }) => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse 620px 520px at ${glowX}px ${glowY}px, ${colors.stageGlow} 0%, transparent 70%), ${colors.boardBg}` }} />
);

/** Perspective floor grid: says "3D space" without a single word. */
export const GridFloor: React.FC<{ top?: number; opacity?: number; color?: string }> = ({ top = 1180, opacity = 1, color = colors.grid }) => (
  <div
    style={{
      position: "absolute",
      left: -420,
      width: 1920,
      top,
      height: 900,
      opacity,
      backgroundImage: `repeating-linear-gradient(0deg, ${color} 0 2px, transparent 2px 80px), repeating-linear-gradient(90deg, ${color} 0 2px, transparent 2px 80px)`,
      transform: "perspective(700px) rotateX(72deg)",
      transformOrigin: "50% 0%",
      WebkitMaskImage: "radial-gradient(ellipse 50% 60% at 50% 0%, black 0%, transparent 100%)",
      maskImage: "radial-gradient(ellipse 50% 60% at 50% 0%, black 0%, transparent 100%)",
    }}
  />
);

/** The CSS mask (mesh overlay) loads its image on its own, outside <Img>: hold the render until it is decoded,
 *  otherwise the first mesh frames render unmasked. */
const useImageReady = (url: string) => {
  const { delayRender, continueRender } = useDelayRender();
  const [handle] = useState(() => delayRender(`mask image ${url}`));
  useEffect(() => {
    const im = new Image();
    const done = () => continueRender(handle);
    im.onload = done;
    im.onerror = done;
    im.src = url;
  }, [continueRender, handle, url]);
};

type FigProps = {
  src: string;
  x: number;
  y: number;
  w: number;
  h: number;
  opacity?: number;
  /** accent outline strength 0..1 (one thin rim, not a glow) */
  outline?: number;
  dim?: number;
  /** triangle-mesh overlay strength 0..1, masked by the figure's own alpha */
  mesh?: number;
  children?: React.ReactNode;
};

/** A cut-out figure in a box (contain, bottom-centred), soft contact shadow, optional outline and mesh overlay.
 *  One drop-shadow at most (the old version stacked four per frame — doubled inside ScanSwap). */
export const Figure: React.FC<FigProps> = ({ src, x, y, w, h, opacity = 1, outline = 0, dim = 0, mesh = 0, children }) => {
  const url = staticFile(src);
  useImageReady(url);
  const rim = outline > 0.01 ? `drop-shadow(0 0 ${1.5 + 1.5 * outline}px ${alpha(colors.accent, Math.min(1, outline))}) ` : "";
  const mask = { WebkitMaskImage: `url(${url})`, maskImage: `url(${url})`, WebkitMaskSize: "contain", maskSize: "contain", WebkitMaskPosition: "bottom center", maskPosition: "bottom center", WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat" } as React.CSSProperties;
  const line = alpha(colors.accent, 0.95);
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h, opacity }}>
      <div style={{ position: "absolute", left: "8%", right: "8%", bottom: -26, height: 52, borderRadius: "50%", background: "radial-gradient(ellipse at center, rgba(0,0,0,0.55) 0%, transparent 70%)" }} />
      <Img src={url} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", objectPosition: "bottom center", filter: `${rim}brightness(${1 - 0.35 * dim}) saturate(${1 - 0.5 * dim})` }} />
      {mesh > 0.01 ? (
        <div style={{ position: "absolute", inset: 0, opacity: mesh, backgroundImage: `repeating-linear-gradient(60deg, ${line} 0 1.6px, transparent 1.6px 22px), repeating-linear-gradient(-60deg, ${line} 0 1.6px, transparent 1.6px 22px), repeating-linear-gradient(0deg, ${line} 0 1.6px, transparent 1.6px 19px)`, ...mask }} />
      ) : null}
      {children}
    </div>
  );
};

/** Two images in the same box; a scan line runs top→bottom between `from` and `to`: A stays above it, B appears below. */
export const ScanSwap: React.FC<{ a: string; b: string; x: number; y: number; w: number; h: number; from: number; to: number; outline?: number; mesh?: number; dim?: number }> = ({ a, b, x, y, w, h, from, to, outline = 0, mesh = 0, dim = 0 }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [from, Math.max(from + 1, to)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.sin) });
  const line = p * 100;
  const scanning = p > 0 && p < 1;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h }}>
      <div style={{ position: "absolute", inset: 0, clipPath: `inset(0 0 ${100 - line}% 0)` }}>
        <Figure src={b} x={0} y={0} w={w} h={h} outline={outline} mesh={mesh} dim={dim} />
      </div>
      <div style={{ position: "absolute", inset: 0, clipPath: `inset(${line}% 0 0 0)` }}>
        <Figure src={a} x={0} y={0} w={w} h={h} />
      </div>
      {scanning ? <div style={{ position: "absolute", left: -60, right: -60, top: `calc(${line}% - 3px)`, height: 6, borderRadius: 6, background: colors.accent2, boxShadow: shadows.pill }} /> : null}
    </div>
  );
};

/** A pill whose word rolls to a new word at `swapAt` (same box, vertical roll). Centred on `cx`. */
export const RollPill: React.FC<{ a: string; b: string; swapAt: number; cx: number; y: number; at: number; bg?: string; size?: number }> = ({ a, b, swapAt, cx, y, at, bg = colors.panel, size = 34 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < at) return null;
  const e = sp(frame, fps, at, { damping: 13 });
  const r = sp(frame, fps, swapAt, { damping: 16 });
  const lh = Math.round(size * 1.3);
  return (
    <div style={{ position: "absolute", left: cx, top: y, height: lh + Math.round(size * 0.7), boxSizing: "border-box", padding: `${Math.round(size * 0.35)}px ${Math.round(size * 0.7)}px`, borderRadius: 999, background: bg, border: colors.panelBorder, overflow: "hidden", opacity: Math.min(1, e * 1.4), scale: String(0.7 + 0.3 * e), transformOrigin: "50% 50%", translate: "-50% 0px", fontFamily: body, fontWeight: 800, fontSize: size, lineHeight: `${lh}px`, color: colors.ink, whiteSpace: "nowrap" }}>
      <div style={{ height: lh, overflow: "hidden" }}>
        <div style={{ translate: `0px ${-r * lh}px` }}>
          <div style={{ height: lh }}>{a}</div>
          <div style={{ height: lh, color: colors.accent2 }}>{b}</div>
        </div>
      </div>
    </div>
  );
};

/** Price tag with a counting number; drops in flat and slides away at `until`. */
export const PriceTag: React.FC<{ x: number; y: number; at: number; value: number; prefix?: string; sub: string; subAt: number; until?: number }> = ({ x, y, at, value, prefix = "$", sub, subAt, until = 1e9 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < at) return null;
  const e = sp(frame, fps, at, { damping: 11, mass: 0.9 });
  const out = sp(frame, fps, until, { damping: 20 });
  const s = sp(frame, fps, subAt, { damping: 14 });
  const n = countUp(frame, at, at + 16, 0, value);
  return (
    <div style={{ position: "absolute", left: x, top: y, width: 360, boxSizing: "border-box", padding: "26px 30px 28px", borderRadius: 28, background: colors.paper, color: colors.paperInk, boxShadow: shadows.panel, opacity: e * (1 - out), translate: `${out * 420}px ${(1 - e) * -60}px` }}>
      <div style={{ position: "absolute", top: 18, left: 26, width: 22, height: 22, borderRadius: 99, background: colors.bg }} />
      <div style={{ fontFamily: display, fontWeight: 900, fontSize: 104, letterSpacing: -3, lineHeight: 1, marginTop: 22, color: colors.paperAccent }}>
        {prefix}
        {fmt(n)}
      </div>
      <div style={{ marginTop: 10, fontFamily: body, fontWeight: 800, fontSize: 32, opacity: s, translate: `0px ${(1 - s) * 14}px` }}>{sub}</div>
    </div>
  );
};

/** A fact card in screen space that lands with weight (flat); optional live number in `title`. */
export const FactCard: React.FC<{ x: number; y: number; w?: number; at: number; title: React.ReactNode; sub?: string; bad?: boolean }> = ({ x, y, w = 360, at, title, sub, bad = true }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < at) return null;
  const e = sp(frame, fps, at, { damping: 13, mass: 1.1 });
  const c = bad ? colors.bad : colors.ok;
  return (
    <div style={{ position: "absolute", left: x, top: y, width: w, boxSizing: "border-box", padding: "20px 24px 22px", borderRadius: 24, background: colors.panel, border: `2.5px solid ${c}`, boxShadow: shadows.panel, opacity: Math.min(1, e * 1.3), translate: `${(1 - e) * 80}px 0px` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, fontFamily: display, fontWeight: 900, fontSize: 38, lineHeight: 1.05, color: colors.ink, letterSpacing: -1, whiteSpace: "nowrap" }}>
        <Mark ok={!bad} size={34} />
        <span>{title}</span>
      </div>
      {sub ? <div style={{ marginTop: 8, fontFamily: body, fontWeight: 800, fontSize: Math.max(28, N.minTextPx), lineHeight: 1.2, color: colors.muted }}>{sub}</div> : null}
    </div>
  );
};
