import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { mono } from "../fonts";
import { N } from "../numbers";
import { alpha, colors, safe } from "../theme";
import { steps } from "../ui/anim";
import { blockLife, blockW, clampX, CODE_HEADER, CODE_PAD, CodePanel, codeMetrics, codeTokens, tokStyle, type CodeLang } from "./shared";

/* Code typed out character by character with a caret (idea: HyperFrames registry/blocks/code-typing: a soft per-character
 * fade, the caret on the last typed character). Leading indentation appears at once (an editor auto-indents), each line
 * break adds a short pause. With `maxLines` the code scrolls to keep the caret line in view. */

type Props = {
  code: string;
  file?: string;
  lang?: CodeLang;
  x?: number;
  y?: number;
  w?: number;
  /** code font size (≥ 30); lines ≤ ~40 characters at 32 */
  size?: number;
  /** window lands */
  at?: number;
  /** typing starts (default at + 14) */
  typeAt?: number;
  /** characters per second (30 = one per frame) */
  cps?: number;
  /** pause on each line break (frames) */
  linePause?: number;
  /** visible lines; longer code scrolls with the caret */
  maxLines?: number;
  /** the caret stays this many frames after the last character, then fades */
  caretHold?: number;
  until?: number;
};

/** Frame of the last typed character of `code` relative to typeAt — for placing the next beat after the typing. */
export const typingFrames = (code: string, cps = 30, linePause = 4, fps = 30) => {
  const lines = code.replace(/\t/g, "  ").split("\n");
  const typed = lines.reduce((n, l) => n + Array.from(l.replace(/^\s+/, "")).length, 0);
  return Math.ceil((typed * fps) / cps + (lines.length - 1) * linePause);
};

export const CodeTyping: React.FC<Props> = ({ code, file, lang = "ts", x = safe.x, y = N.bandTop, w = blockW, size = 32, at = 0, typeAt, cps = 30, linePause = 4, maxLines, caretHold = 24, until }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const life = blockLife(frame, fps, at, until, durationInFrames);
  if (frame < at || life.o <= 0) return null;
  const sz = Math.max(30, size);
  const { lh, ch } = codeMetrics(sz);
  const lines = code.replace(/\t/g, "  ").split("\n");
  const t0 = typeAt ?? at + 14;
  const fpc = fps / cps;

  // schedule: the frame each character appears
  let t = t0;
  const lineAt: number[] = [];
  const sched = lines.map((ln, li) => {
    lineAt.push(t);
    const chars = Array.from(ln);
    const lead = chars.length - Array.from(ln.replace(/^\s+/, "")).length;
    const row = chars.map((_, ci) => {
      if (ci < lead) return t;
      const at1 = t;
      t += fpc;
      return at1;
    });
    if (li < lines.length - 1) t += linePause;
    return row;
  });
  const typeEnd = t;

  // caret: after the last shown character of the current line
  let cl = 0;
  for (let li = 0; li < lines.length; li++) if (frame >= lineAt[li]) cl = li;
  const col = sched[cl].filter((s) => s < frame).length; // characters already visible
  const caretO = interpolate(frame, [typeEnd + caretHold, typeEnd + caretHold + 8], [1, 0], clampX);

  const visible = Math.min(lines.length, maxLines ?? lines.length);
  const scroll = steps(
    frame,
    fps,
    0,
    lineAt.map((f, li) => [f, Math.max(0, li - visible + 1) * lh] as [number, number]).filter(([, v], i, arr) => i > 0 && v !== arr[i - 1][1]),
    { damping: 16, mass: 1.2 },
  );
  const numW = ch * 2 + 10;
  const textLeft = CODE_PAD.x + numW + ch * 1.2;

  return (
    <CodePanel x={x} y={y} w={w} h={CODE_HEADER + CODE_PAD.top + visible * lh + CODE_PAD.bottom} file={file} life={life}>
      <div style={{ position: "relative", marginTop: CODE_PAD.top, height: visible * lh, overflow: "hidden", fontFamily: mono, fontSize: sz, fontVariantLigatures: "none" }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 0, translate: `0px ${-scroll}px` }}>
          {lines.map((ln, li) => {
            let ci = 0;
            return (
              <div key={li} style={{ position: "absolute", left: 0, right: 0, top: li * lh, height: lh, display: "flex", alignItems: "center", whiteSpace: "pre" }}>
                <span style={{ position: "absolute", left: CODE_PAD.x, width: numW, textAlign: "right", color: alpha(colors.ink, 0.32), opacity: interpolate(frame, [lineAt[li], lineAt[li] + 4], [0, 1], clampX) }}>{li + 1}</span>
                <span style={{ position: "absolute", left: textLeft, right: CODE_PAD.x, overflow: "hidden" }}>
                  {codeTokens(ln, lang).map((tk, k) => (
                    <span key={k} style={tokStyle(tk.k)}>
                      {Array.from(tk.t).map((c, j) => {
                        const s = sched[li][ci++];
                        return (
                          <span key={j} style={{ opacity: interpolate(frame, [s, s + 3], [0, 1], clampX) }}>
                            {c}
                          </span>
                        );
                      })}
                    </span>
                  ))}
                </span>
              </div>
            );
          })}
          <div style={{ position: "absolute", left: textLeft + col * ch, top: cl * lh + (lh - sz * 1.2) / 2, width: 4, height: sz * 1.2, borderRadius: 2, background: colors.accent2, opacity: caretO }} />
        </div>
      </div>
    </CodePanel>
  );
};
