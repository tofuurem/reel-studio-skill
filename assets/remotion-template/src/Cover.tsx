import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { display } from "./fonts";
import { N } from "./numbers";
import { brand as BRAND, colors, guideColors, inkOn, shadows } from "./theme";

/**
 * Cover kit (stills, 1080x1920). Few words on purpose: a brand plate, a giant episode number behind the hero and ONE word.
 * Instagram shows the centre of the cover in the profile grid: 3:4 → y 240–1680, old 1:1 → y 420–1500 (N.coverCrop*).
 * Keep faces and the word inside y 420–1500 (the default word sits there); `guides` draws both crops for a check render.
 * Colours default to the palette; the word plate's text colour follows the plate (white on coral was 2.6:1).
 * Heroes are cut-outs made with scripts/cutout.py (RGBA PNG under public/covers/).
 * ArtCover is the second kind: a full-bleed plate generated from a real frame (scripts/codex_image.sh, Codex CLI), with the same
 * brand plate and word on top (text always stays here: image models garble Cyrillic).
 */

type Side = "left" | "right";

export const CoverFrame: React.FC<{
  /** top and bottom colours of the background and the colour of the glow behind the hero */
  bg: [string, string];
  glow?: string;
  glowAt?: string;
  number: string;
  numberSide?: Side;
  numberColor?: string;
  brand?: string;
  brandSide?: Side;
  word: string;
  wordSize?: number;
  wordTop?: number;
  wordSide?: Side;
  plate?: string;
  plateInk?: string;
  wordRotate?: number;
  guides?: boolean;
  children?: React.ReactNode;
}> = ({ bg, glow = colors.stageGlow, glowAt = "50% 52%", number, numberSide = "right", numberColor = "rgba(255,255,255,0.16)", brand = BRAND.series, brandSide = "left", word, wordSize = 120, wordTop: wordTopProp, wordSide = "left", plate = colors.accent, plateInk, wordRotate = -3, guides = false, children }) => {
  // default: the plate's bottom 20 px above the 1:1 crop (y 1500) whatever the word size
  const wordTop = wordTopProp ?? Math.round(1920 - N.coverCrop11Top - 20 - wordSize * 1.46);
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${bg[0]} 0%, ${bg[1]} 100%)`, overflow: "hidden" }}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse 70% 42% at ${glowAt}, ${glow} 0%, transparent 70%)` }} />
      <div
        style={{
          position: "absolute",
          top: 250,
          [numberSide]: 36,
          fontFamily: display,
          fontWeight: 900,
          fontSize: 520,
          lineHeight: 0.82,
          letterSpacing: -24,
          color: numberColor,
        }}
      >
        {number}
      </div>
      {children}
      {brand ? (<div
        style={{
          position: "absolute",
          top: 300,
          [brandSide]: 64,
          fontFamily: display,
          fontWeight: 900,
          fontSize: 82,
          lineHeight: 1,
          letterSpacing: -3,
          color: colors.bg,
          background: colors.ink,
          padding: "18px 28px 24px",
          borderRadius: 26,
          rotate: brandSide === "left" ? "-3deg" : "3deg",
          boxShadow: shadows.cover,
        }}
      >
        {brand}
      </div>) : null}
      <div
        style={{
          position: "absolute",
          top: wordTop,
          [wordSide]: 56,
          fontFamily: display,
          fontWeight: 900,
          fontSize: wordSize,
          lineHeight: 1,
          letterSpacing: -4,
          color: plateInk ?? inkOn(plate),
          background: plate,
          padding: `${Math.round(wordSize * 0.2)}px ${Math.round(wordSize * 0.34)}px ${Math.round(wordSize * 0.26)}px`,
          borderRadius: Math.round(wordSize * 0.3),
          rotate: `${wordRotate}deg`,
          whiteSpace: "nowrap",
          boxShadow: shadows.cover,
        }}
      >
        {word}
      </div>
      {guides ? (
        <Guides />
      ) : null}
    </AbsoluteFill>
  );
};

/** Both Instagram grid crops as dashed frames (check renders only). */
const Guides: React.FC = () => (
  <AbsoluteFill>
    <div style={{ position: "absolute", left: 0, right: 0, top: N.coverCrop34Top, height: 1920 - 2 * N.coverCrop34Top, border: `4px dashed ${guideColors.crop34}`, boxSizing: "border-box" }} />
    <div style={{ position: "absolute", left: 0, right: 0, top: N.coverCrop11Top, height: 1920 - 2 * N.coverCrop11Top, border: `4px dashed ${guideColors.crop11}`, boxSizing: "border-box" }} />
  </AbsoluteFill>
);

/** A cut-out (RGBA PNG) placed by its box; `h` sets the height, the width follows. Soft drop shadow, optional flip / tilt / dimming. */
export const Cut: React.FC<{ src: string; x: number; y: number; h: number; flip?: boolean; rotate?: number; opacity?: number; filter?: string; shadow?: boolean }> = ({ src, x, y, h, flip, rotate = 0, opacity = 1, filter = "", shadow = true }) => (
  <Img
    src={staticFile(src)}
    style={{
      position: "absolute",
      left: x,
      top: y,
      height: h,
      opacity,
      rotate: `${rotate}deg`,
      scale: flip ? "-1 1" : undefined,
      filter: `${shadow ? "drop-shadow(0px 34px 36px rgba(0,0,0,0.45)) " : ""}${filter}`.trim() || undefined, // a still: one heavy shadow is fine here
    }}
  />
);

/** Round badge with a mark (✓ ✕ + → or an emoji) — a wordless hint. */
export const Badge: React.FC<{ x: number; y: number; size?: number; bg: string; ink?: string; children: React.ReactNode; rotate?: number }> = ({ x, y, size = 150, bg, ink, children, rotate = 0 }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: size,
      height: size,
      borderRadius: 999,
      background: bg,
      color: ink ?? inkOn(bg),
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: display,
      fontWeight: 900,
      fontSize: Math.round(size * 0.56),
      lineHeight: 1,
      rotate: `${rotate}deg`,
      border: `8px solid ${colors.ink}`,
      boxSizing: "border-box",
      boxShadow: shadows.cover,
    }}
  >
    {children}
  </div>
);

/** Soft floor shadow under a standing figure. */
export const FloorShadow: React.FC<{ x: number; y: number; w: number }> = ({ x, y, w }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, height: Math.round(w * 0.16), borderRadius: "50%", background: "radial-gradient(ellipse at center, rgba(0,0,0,0.45) 0%, transparent 70%)" }} />
);

/** Cover on a generated plate (9:16, no text in the image, under public/covers/gen/): the plate, a shade for the word, the same brand plate and word as CoverFrame. */
export const ArtCover: React.FC<{
  src: string;
  word: string;
  wordSize?: number;
  wordTop?: number;
  wordSide?: Side;
  brand?: string;
  brandSide?: Side;
  plate?: string;
  plateInk?: string;
  /** colour of the shade (the darkest tone of the plate) and its strength at the bottom edge */
  shadeColor?: string;
  shade?: number;
  guides?: boolean;
}> = ({ src, word, wordSize = 150, wordTop, wordSide = "left", brand = BRAND.series, brandSide = "left", plate = colors.accent, plateInk, shadeColor = "14,12,11", shade = 0.55, guides = false }) => (
  <AbsoluteFill style={{ background: `rgb(${shadeColor})`, overflow: "hidden" }}>
    <Img src={staticFile(src)} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
    <AbsoluteFill style={{ background: `linear-gradient(180deg, rgba(${shadeColor},0.35) 0%, rgba(${shadeColor},0) 22%, rgba(${shadeColor},0) 62%, rgba(${shadeColor},${shade}) 100%)` }} />
    {brand ? (<div style={{ position: "absolute", top: 300, [brandSide]: 64, fontFamily: display, fontWeight: 900, fontSize: 82, lineHeight: 1, letterSpacing: -3, color: colors.bg, background: colors.ink, padding: "18px 28px 24px", borderRadius: 26, rotate: brandSide === "left" ? "-3deg" : "3deg", boxShadow: shadows.cover }}>
      {brand}
    </div>) : null}
    <div style={{ position: "absolute", top: wordTop ?? Math.round(1920 - N.coverCrop11Top - 20 - wordSize * 1.34), [wordSide]: 56, fontFamily: display, fontWeight: 900, fontSize: wordSize, lineHeight: 0.95, letterSpacing: -4, color: plateInk ?? inkOn(plate), background: plate, padding: `${Math.round(wordSize * 0.18)}px ${Math.round(wordSize * 0.24)}px ${Math.round(wordSize * 0.21)}px`, borderRadius: Math.round(wordSize * 0.2), rotate: "-3deg", whiteSpace: "nowrap", boxShadow: shadows.cover }}>
      {word}
    </div>
    {guides ? <Guides /> : null}
  </AbsoluteFill>
);
