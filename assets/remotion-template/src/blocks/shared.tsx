import React from "react";
import { Easing, interpolate } from "remotion";
import { mono } from "../fonts";
import { alpha, colors, safe, shadows, W } from "../theme";
import { sp, type SpringCfg } from "../ui/anim";

/* Shared pieces of the blocks/ kit (ideas ported from HeyGen's HyperFrames registry, Apache-2.0, re-implemented
 * frame-driven): the entrance/exit envelope, the code window and a tiny tokenizer. Coordinates are the 1080-wide canvas;
 * Reel2K scales the whole layout by 4/3, so nothing here knows about 2K. */

export const clampX = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Default block width: the canvas minus the side margins (952 px on 1080). */
export const blockW = W - 2 * safe.x;

/** Heavy things (windows, cards) and small things (pills, tags) — motion-design.md §4. */
export const HEAVY: SpringCfg = { damping: 16, mass: 1.3 };
export const SMALL: SpringCfg = { damping: 12, mass: 1 };

/**
 * Entrance and exit of a block: `e` = spring 0→1 from `at`, `x` = exit 0→1 over `len` frames from `until` (default: the
 * last `len` frames of the Sequence, so a block placed with rg.seq leaves on its own), `o` = opacity of both.
 */
export const blockLife = (frame: number, fps: number, at: number, until: number | undefined, duration: number, cfg: SpringCfg = HEAVY, len = 8) => {
  const e = frame < at ? 0 : sp(frame, fps, at, cfg);
  const u = until ?? duration - len;
  const x = interpolate(frame, [u, u + len], [0, 1], { ...clampX, easing: Easing.in(Easing.quad) });
  return { e, x, o: Math.min(1, e * 1.4) * (1 - x) };
};

// ---------- code

export type CodeLang = "ts" | "py" | "sh";
export type TokKind = "kw" | "str" | "com" | "num" | "fn" | "id" | "punc" | "ws";
export type Tok = { t: string; k: TokKind };

const KW = new Set(
  (
    "const let var function return if else for while do async await import from export default class new type interface " +
    "extends implements true false null undefined this of in try catch finally throw switch case break continue typeof as " +
    "def lambda None True False elif not and or is with pass yield global raise except self " +
    "echo cd then fi done esac local"
  ).split(" "),
);

/** One line → tokens (keywords, strings, comments, numbers, called names). No grammar: good enough for a reel. */
export const codeTokens = (line: string, lang: CodeLang = "ts"): Tok[] => {
  const com = lang === "ts" ? String.raw`\/\/.*$` : String.raw`#.*$`;
  const re = new RegExp(String.raw`(\s+)|(${com})|("(?:[^"\\]|\\.)*"?|'(?:[^'\\]|\\.)*'?|\x60(?:[^\x60\\]|\\.)*\x60?)|(\b\d[\d_.]*\b)|([\p{L}_$][\p{L}\p{N}_$]*)|(.)`, "gu");
  const out: Tok[] = [];
  for (let m = re.exec(line); m; m = re.exec(line)) {
    const t = m[0];
    let k: TokKind = "punc";
    if (m[1]) k = "ws";
    else if (m[2]) k = "com";
    else if (m[3]) k = "str";
    else if (m[4]) k = "num";
    else if (m[5]) {
      const rest = line.slice((m.index ?? 0) + t.length);
      const key = lang === "ts" && /^\s*:(?!:)/.test(rest); // an object key («from: a») is not the keyword
      k = KW.has(t) && !key ? "kw" : /^\s*\(/.test(rest) ? "fn" : "id";
    }
    out.push({ t, k });
  }
  return out;
};

/** Token colours from the palette (keywords accent, strings accent2, numbers ok, comments dimmed italic). */
export const tokStyle = (k: TokKind): React.CSSProperties => {
  switch (k) {
    case "kw":
      return { color: colors.accent, fontWeight: 700 };
    case "str":
      return { color: colors.accent2 };
    case "com":
      return { color: alpha(colors.ink, 0.5), fontStyle: "italic" };
    case "num":
      return { color: colors.ok };
    case "fn":
      return { color: colors.ink, fontWeight: 700 };
    case "punc":
      return { color: alpha(colors.ink, 0.6) };
    default:
      return { color: alpha(colors.ink, 0.88) };
  }
};

/** Line height and character advance of JetBrains Mono (600/1000 em) at a font size. */
export const codeMetrics = (size: number) => ({ lh: Math.round(size * 1.5), ch: size * 0.6 });

export const CODE_HEADER = 76;
export const CODE_PAD = { top: 22, bottom: 26, x: 26 };

/** The editor window around CodeDiff / CodeTyping: three neutral dots, a file name, an optional right-hand slot. */
export const CodePanel: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  file?: string;
  right?: React.ReactNode;
  life: { e: number; x: number; o: number };
  children: React.ReactNode;
}> = ({ x, y, w, h, file, right, life, children }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: w,
      height: h,
      borderRadius: 32,
      background: colors.panel,
      border: colors.panelBorder,
      boxShadow: shadows.panel,
      overflow: "hidden",
      opacity: life.o,
      translate: `0px ${(1 - life.e) * 60 + life.x * 24}px`,
      scale: String(0.97 + 0.03 * life.e),
      transformOrigin: "50% 100%",
    }}
  >
    <div style={{ height: CODE_HEADER, boxSizing: "border-box", display: "flex", alignItems: "center", gap: 22, padding: `0 ${CODE_PAD.x + 4}px`, borderBottom: colors.panelBorder }}>
      <div style={{ display: "flex", gap: 11 }}>
        {[0, 1, 2].map((i) => (
          <span key={i} style={{ width: 16, height: 16, borderRadius: 99, background: alpha(colors.ink, 0.16) }} />
        ))}
      </div>
      {file ? <span style={{ fontFamily: mono, fontSize: 30, color: colors.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{file}</span> : null}
      <span style={{ marginLeft: "auto" }}>{right}</span>
    </div>
    {children}
  </div>
);
