import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { mono } from "../fonts";
import { N } from "../numbers";
import { alpha, colors, safe } from "../theme";
import { sp } from "../ui/anim";
import { blockLife, blockW, clampX, CODE_HEADER, CODE_PAD, CodePanel, codeMetrics, codeTokens, tokStyle, type CodeLang } from "./shared";

/* Animated code diff (idea: HyperFrames registry/blocks/code-diff). The file sits in an editor window; on `delAt` the
 * removed lines get a red tint and a strike, then collapse; on `addAt` the added lines open up with a green tint and slide
 * in. Line numbers re-count as rows leave and arrive, like an editor. The window height follows the rows. */

export type DiffOp = { kind: "same" | "del" | "add"; text: string };

/** Line diff (longest common subsequence), the same rule as the registry block. */
export const diffLines = (a: string[], b: string[]): DiffOp[] => {
  const n = a.length;
  const m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const ops: DiffOp[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      ops.push({ kind: "same", text: b[j] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) ops.push({ kind: "del", text: a[i++] });
    else ops.push({ kind: "add", text: b[j++] });
  }
  while (i < n) ops.push({ kind: "del", text: a[i++] });
  while (j < m) ops.push({ kind: "add", text: b[j++] });
  return ops;
};

type Props = {
  /** the code before and after (lines ≤ ~40 characters at size 32, ≤ ~44 at 30) */
  before: string;
  after: string;
  file?: string;
  lang?: CodeLang;
  x?: number;
  y?: number;
  w?: number;
  /** code font size (≥ 30) */
  size?: number;
  /** window lands */
  at?: number;
  /** removed lines get struck (default at + 20) */
  delAt?: number;
  /** added lines open up (default: as the first removed line starts collapsing, so the rows swap in place) */
  addAt?: number;
  /** removed lines stay struck instead of collapsing */
  keepRemoved?: boolean;
  until?: number;
};

const STRIKE = 10; // frames: tint + strike
const HOLD = 6; // struck line is read before it collapses
const COLLAPSE = 14;
const GROW = 14;

export const CodeDiff: React.FC<Props> = ({ before, after, file, lang = "ts", x = safe.x, y = N.bandTop, w = blockW, size = 32, at = 0, delAt, addAt, keepRemoved = false, until }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const life = blockLife(frame, fps, at, until, durationInFrames);
  if (frame < at || life.o <= 0) return null;
  const sz = Math.max(30, size);
  const { lh, ch } = codeMetrics(sz);
  const ops = diffLines(before.replace(/\t/g, "  ").split("\n"), after.replace(/\t/g, "  ").split("\n"));
  const nDel = ops.filter((o) => o.kind === "del").length;
  const nAdd = ops.filter((o) => o.kind === "add").length;
  const step = (n: number) => (n > 1 ? Math.min(4, 15 / (n - 1)) : 0); // a group lands within ~15 frames
  const d0 = delAt ?? at + 20;
  // added lines start opening as the removed ones start collapsing: the rows swap in place, the window does not pump
  const a0 = addAt ?? (nDel ? d0 + STRIKE + (keepRemoved ? 4 + (nDel - 1) * step(nDel) : HOLD) : at + 20);

  let di = 0;
  let ai = 0;
  const rows = ops.map((op) => {
    if (op.kind === "del") {
      const s = d0 + di++ * step(nDel);
      const strike = interpolate(frame, [s, s + STRIKE], [0, 1], { ...clampX, easing: Easing.out(Easing.cubic) });
      const gone = keepRemoved ? 0 : interpolate(frame, [s + STRIKE + HOLD, s + STRIKE + HOLD + COLLAPSE], [0, 1], { ...clampX, easing: Easing.inOut(Easing.cubic) });
      return { op, presence: 1 - gone, strike, slide: 1, tint: strike };
    }
    if (op.kind === "add") {
      const s = a0 + ai++ * step(nAdd);
      const grow = interpolate(frame, [s, s + GROW], [0, 1], { ...clampX, easing: Easing.out(Easing.cubic) });
      return { op, presence: grow, strike: 0, slide: frame < s ? 0 : sp(frame, fps, s, { damping: 13 }), tint: grow };
    }
    return { op, presence: 1, strike: 0, slide: 1, tint: 0 };
  });

  let num = 0;
  const numW = ch * 2 + 10;
  const signW = ch * 2.2;
  const bodyH = rows.reduce((h, r) => h + r.presence * lh, 0);
  const statO = interpolate(frame, [a0, a0 + 10], [0, 1], clampX);
  const stat = (
    <span style={{ fontFamily: mono, fontSize: 30, fontWeight: 700, opacity: statO, whiteSpace: "nowrap" }}>
      <span style={{ color: colors.ok }}>+{nAdd}</span> <span style={{ color: colors.bad }}>−{nDel}</span>
    </span>
  );

  return (
    <CodePanel x={x} y={y} w={w} h={CODE_HEADER + CODE_PAD.top + bodyH + CODE_PAD.bottom} file={file} right={stat} life={life}>
      <div style={{ paddingTop: CODE_PAD.top, fontFamily: mono, fontSize: sz, fontVariantLigatures: "none" }}>
        {rows.map((r, i) => {
          if (r.presence > 0.5) num++;
          const kind = r.op.kind;
          const c = kind === "del" ? colors.bad : colors.ok;
          return (
            <div key={i} style={{ position: "relative", height: r.presence * lh, overflow: "hidden", background: kind === "same" ? undefined : alpha(c, 0.15 * r.tint), opacity: kind === "del" ? Math.min(1, r.presence * 1.4) : 1 }}>
              {kind !== "same" ? <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 5, background: c, opacity: r.tint }} /> : null}
              <div style={{ position: "absolute", left: CODE_PAD.x, right: CODE_PAD.x, top: ((r.presence - 1) * lh) / 2, height: lh, display: "flex", alignItems: "center", whiteSpace: "pre" }}>
                <span style={{ width: numW, flexShrink: 0, textAlign: "right", color: kind === "same" ? alpha(colors.ink, 0.32) : alpha(c, 0.75) }}>{r.presence > 0.5 ? num : ""}</span>
                <span style={{ width: signW, flexShrink: 0, textAlign: "center", color: c, opacity: r.tint, fontWeight: 700 }}>{kind === "del" ? "−" : kind === "add" ? "+" : ""}</span>
                <span style={{ minWidth: 0, overflow: "hidden", opacity: Math.min(1, r.slide * 1.5) * (1 - 0.35 * r.strike), translate: `${(1 - r.slide) * -32}px 0px` }}>
                  {/^\s*/.exec(r.op.text)?.[0]}
                  <span style={{ position: "relative" }}>
                    {codeTokens(r.op.text.replace(/^\s+/, ""), lang).map((t, k) => (
                      <span key={k} style={tokStyle(t.k)}>
                        {t.t}
                      </span>
                    ))}
                    {r.strike > 0 ? <span style={{ position: "absolute", left: 0, top: "52%", height: 3, borderRadius: 2, width: `${r.strike * 100}%`, background: colors.bad }} /> : null}
                  </span>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </CodePanel>
  );
};
