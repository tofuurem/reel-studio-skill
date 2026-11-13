import { N } from "./numbers";
import { palettes, type Palette } from "./palettes";

export const FPS = 30;
export const W = 1080;
export const H = 1920;

/** The series palette — switch the preset here (palettes.ts), never colour a component by hand. */
export const palette: Palette = palettes.warm;
export const colors = palette;

/** Channel and series names: EndCard, ChannelPill and covers default to these; empty → nothing is drawn. Fill them only
 *  with what the user named for this video (intake), never a guess. */
export const brand = { channel: "", series: "" };

/** One shadow per kind of element, nothing else (birthday reel: «тени и границы странные» was a mix of heavy shadows and
 *  glows). No glows, no tilt on landing pills, no emoji in UI text. */
export const shadows = {
  text: "0 2px 10px rgba(0,0,0,0.6)", // text straight over footage
  caption: "0 2px 0 rgba(0,0,0,0.5), 0 0 16px rgba(0,0,0,0.6), 0 8px 28px rgba(0,0,0,0.5)", // subtitles over any footage
  panel: "0 20px 50px rgba(0,0,0,0.35)", // cards, windows, shrunken footage frames (with colors.panelBorder)
  pill: "0 8px 24px rgba(0,0,0,0.3)", // bubbles, pills, tags, stamps
  cover: "0 24px 60px rgba(0,0,0,0.4)", // plates on covers (stills only)
};

/** Comic lettering (scenes/Comic.tsx; Halloween v5, 2026-11-09: «банан — комиксный герой»): flat yellow fill, a thick ink
 *  outline, a hard red offset (no blur — flat ink, not a glow), a paper burst with halftone dots. */
export const comic = { fill: "#FFE14D", ink: "#141210", pop: "#E8352B", paper: "#FFF7DC", dot: "rgba(232,53,43,0.28)", tag: "#FFFFFF" };

/** Safe area of the 9:16 canvas (Instagram chrome): nothing important above top / below bottom / in the right strip. */
export const safe = { top: N.safeTop, bottom: N.safeBottom, right: N.safeRight, x: N.safeX };

/** Crop guides drawn by `guides` on covers. */
export const guideColors = { crop34: "#00E5FF", crop11: "#FFE600" };

const lum = (hex: string) => {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return null;
  const c = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};

/** Readable text colour on a background: dark ink on light plates, white on dark ones (translucent fills count as dark). */
export const inkOn = (bg: string) => {
  const l = lum(bg);
  return l !== null && l > 0.19 ? colors.onAccent : colors.ink;
};

/** "#RRGGBB" + alpha → rgba() (tinted borders and fills from palette colours). */
export const alpha = (hex: string, a: number) => {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${a})`;
};

/** Footage folder under public/. Set REMOTION_FOOTAGE_DIR=footage2k for the 1440x2560 proxies. */
export const footagePath = (src: string) =>
  src.replace(/^footage\//, `${process.env.REMOTION_FOOTAGE_DIR ?? "footage"}/`);
