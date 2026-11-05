import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { body } from "../fonts";
import { colors, alpha, safe, shadows } from "../theme";
import { inAt, outBefore, sp, steps } from "./anim";

/* Chat pieces (birthday reel ChatGPT thread, lofiroom SideBubble): a real-looking thread whose messages land on the words. */

/** A strike line that draws across a failed option (instead of a stamped ✕). `p` 0..1. */
export const Strike: React.FC<{ p: number; color?: string }> = ({ p, color = colors.bad }) => (
  <div style={{ position: "absolute", left: "6%", top: "48%", height: 6, borderRadius: 6, background: color, width: `${88 * Math.min(1, Math.max(0, p))}%`, rotate: "-4deg", transformOrigin: "0% 50%", opacity: Math.min(1, p * 2), boxShadow: shadows.pill }} />
);

/** «typing…» — three dots that breathe; keeps an empty panel alive while the speaker reads the lead-in. */
export const TypingDots: React.FC<{ color?: string; size?: number }> = ({ color = colors.accent, size = 14 }) => {
  const frame = useCurrentFrame();
  return (
    <span style={{ display: "inline-flex", gap: Math.round(size * 0.8) }}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{ width: size, height: size, borderRadius: 99, background: color, opacity: 0.35 + 0.65 * Math.max(0, Math.sin((frame - i * 5) / 5)) }} />
      ))}
    </span>
  );
};

export type ChatFrom = "me" | "them";

/** One chat bubble: mine (accent2, right) or theirs (tinted panel, left). `p` = entrance 0..1. */
export const Bubble: React.FC<{ from: ChatFrom; p?: number; size?: number; maxWidth?: number; children: React.ReactNode }> = ({ from, p = 1, size = 32, maxWidth = 760, children }) => {
  const me = from === "me";
  return (
    <div style={{ display: "flex", justifyContent: me ? "flex-end" : "flex-start" }}>
      <div
        style={{
          maxWidth,
          padding: `${Math.round(size * 0.5)}px ${Math.round(size * 0.75)}px`,
          borderRadius: me ? "24px 24px 6px 24px" : "6px 24px 24px 24px",
          background: me ? colors.accent2 : alpha(colors.accent, 0.12),
          border: me ? undefined : `1px solid ${alpha(colors.accent, 0.26)}`,
          color: me ? colors.onAccent2 : colors.ink,
          fontFamily: body,
          fontWeight: 700,
          fontSize: size,
          lineHeight: 1.25,
          boxShadow: me ? shadows.pill : undefined,
          opacity: Math.min(1, p * 1.5),
          scale: String(0.9 + 0.1 * p),
          translate: `${(1 - p) * (me ? 24 : -24)}px ${(1 - p) * 12}px`,
          transformOrigin: me ? "100% 100%" : "0% 100%",
        }}
      >
        {children}
      </div>
    </div>
  );
};

export type ChatMsg = { at: number; from: ChatFrom; text: string };

/**
 * A chat panel in the card band: `who` as the header, messages land on their frames, «typing…» from `typingFrom` until
 * the next reply of theirs, and the thread scrolls up when it overflows (heights are estimated from the text length).
 * An empty panel for ≥ 2 s is a bug — anchor `at` to the lead-in words and use typingFrom.
 */
export const ChatCard: React.FC<{ who: string; messages: ChatMsg[]; top?: number; height?: number; typingFrom?: number; size?: number; at?: number }> = ({ who, messages, top = 300, height = 620, typingFrom, size = 32, at = 0 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const inP = sp(frame, fps, at, { damping: 16, mass: 1.1 });
  const o = outBefore(frame, durationInFrames, 8);
  const W = 1080 - 2 * safe.x - 2 * 32;
  const maxW = Math.round(W * 0.86);
  const cpl = Math.max(8, Math.floor((maxW - 1.5 * size) / (size * 0.56)));
  const gap = 14;
  const hOf = (t: string) => Math.ceil(t.length / cpl) * size * 1.25 + size + gap;
  const region = height - 96;
  let y = 0;
  const laid = messages.map((m) => {
    const top0 = y;
    y += hOf(m.text);
    return { ...m, top: top0, bottom: y };
  });
  const scroll = steps(frame, fps, 0, laid.filter((m) => m.bottom > region).map((m) => [m.at, m.bottom - region] as [number, number]), { damping: 16, mass: 1.2 });
  const nextThem = laid.find((m) => m.from === "them" && m.at > (typingFrom ?? 1e9));
  const typing = typingFrom !== undefined && frame >= typingFrom && (!nextThem || frame < nextThem.at);
  return (
    <div style={{ position: "absolute", left: safe.x, right: safe.x, top, height, borderRadius: 36, background: colors.panel, border: colors.panelBorder, boxShadow: shadows.panel, overflow: "hidden", opacity: Math.min(1, inP * 1.4) * o, translate: `0px ${(1 - inP) * 70}px`, scale: String(0.97 + 0.03 * inP), transformOrigin: "50% 100%" }}>
      <div style={{ position: "absolute", left: 32, top: 24, fontFamily: body, fontWeight: 800, fontSize: 28, letterSpacing: 3, textTransform: "uppercase", color: colors.muted }}>{who}</div>
      <div style={{ position: "absolute", left: 32, right: 32, top: 80, bottom: 16, overflow: "hidden" }}>
        <div style={{ translate: `0px ${-scroll}px` }}>
          {laid.map((m, i) =>
            frame < m.at ? null : (
              <div key={i} style={{ position: "absolute", left: 0, right: 0, top: m.top }}>
                <Bubble from={m.from} p={inAt(frame, m.at, 10)} size={size} maxWidth={maxW}>
                  {m.text}
                </Bubble>
              </div>
            ),
          )}
          {typing ? (
            <div style={{ position: "absolute", left: 0, top: laid.filter((m) => frame >= m.at).slice(-1)[0]?.bottom ?? 0 }}>
              <Bubble from="them" size={size}>
                <TypingDots />
              </Bubble>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
