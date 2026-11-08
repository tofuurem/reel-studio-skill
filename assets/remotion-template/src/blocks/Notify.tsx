import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { N } from "../numbers";
import { colors, inkOn, safe, shadows } from "../theme";
import { sp, steps } from "../ui/anim";
import { blockLife, blockW } from "./shared";

/* A generic notification card that drops in from above, and NotifyStack: several of them, the newest on top pushing the
 * others down (ideas: HyperFrames notification-cascade, macos-notification, message-thread-reveal). No vendor styling: the
 * app icon is a rounded square in a palette colour with a letter. Heights are estimated from the text (≤ 2 lines). */

export type Note = {
  /** app name in the header (small caps) */
  app: string;
  title: string;
  /** body text, clamped to two lines */
  text?: string;
  /** «сейчас», «2 мин» */
  time?: string;
  /** icon letter (default: the app's first letter) */
  icon?: string;
  /** icon fill, a palette token (default colors.accent); the letter colour follows it */
  iconBg?: string;
};

const ICON = 88;
const PAD = 26;
const TEXT = 34;
const TEXT_LH = Math.round(TEXT * 1.25);
const PUSH = 4;

const textLines = (n: Note, w: number) => {
  if (!n.text) return 0;
  const cpl = Math.max(10, Math.floor((w - 2 * PAD - ICON - 24) / (TEXT * 0.56)));
  return Math.min(2, Math.ceil(n.text.length / cpl));
};

/** Card height for a note at width w (fixed, so a stack lays out without measuring). */
export const notifyH = (n: Note, w = blockW) => 2 * PAD + 38 + 50 + textLines(n, w) * TEXT_LH;

const NoteCard: React.FC<{ note: Note; w: number }> = ({ note, w }) => {
  const bg = note.iconBg ?? colors.accent;
  return (
    <div style={{ width: w, height: notifyH(note, w), boxSizing: "border-box", padding: PAD, display: "flex", gap: 24, borderRadius: 36, background: colors.panel, border: colors.panelBorder, boxShadow: shadows.panel, fontFamily: body }}>
      <div style={{ width: ICON, height: ICON, flexShrink: 0, borderRadius: 24, background: bg, color: inkOn(bg), display: "flex", alignItems: "center", justifyContent: "center", fontFamily: display, fontWeight: 800, fontSize: 44 }}>
        {(note.icon ?? note.app.slice(0, 1)).toUpperCase()}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ height: 38, display: "flex", alignItems: "center", gap: 16, fontSize: 28, fontWeight: 700, color: colors.muted }}>
          <span style={{ textTransform: "uppercase", letterSpacing: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{note.app}</span>
          {note.time ? <span style={{ marginLeft: "auto", flexShrink: 0, fontWeight: 600 }}>{note.time}</span> : null}
        </div>
        <div style={{ height: 50, lineHeight: "50px", fontSize: 38, fontWeight: 800, color: colors.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{note.title}</div>
        {note.text ? (
          <div style={{ fontSize: TEXT, lineHeight: `${TEXT_LH}px`, fontWeight: 600, color: colors.muted, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{note.text}</div>
        ) : null}
      </div>
    </div>
  );
};

type NotifyProps = Note & { x?: number; y?: number; w?: number; at?: number; until?: number };

/** One notification: drops in from above at `at`, slides back up at `until` (faster). */
export const Notify: React.FC<NotifyProps> = ({ x = safe.x, y = N.bandTop, w = blockW, at = 0, until, ...note }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const life = blockLife(frame, fps, at, until, durationInFrames, { damping: 14, mass: 1 });
  if (frame < at || life.o <= 0) return null;
  return (
    <div style={{ position: "absolute", left: x, top: y, opacity: life.o, translate: `0px ${(1 - life.e) * -56 - life.x * 40}px`, scale: String(0.96 + 0.04 * life.e), transformOrigin: "50% 0%" }}>
      <NoteCard note={note} w={w} />
    </div>
  );
};

type StackProps = {
  /** notes in arrival order; each lands on its `at` (≥ 12 frames apart reads as a cascade), or as a group from `at` */
  items: (Note & { at?: number })[];
  x?: number;
  y?: number;
  w?: number;
  gap?: number;
  /** cards kept on screen; an older one fades out as it is pushed past this */
  max?: number;
  /** "top": the newest lands on top and pushes the others down; "bottom": each lands under the previous */
  order?: "top" | "bottom";
  at?: number;
  until?: number;
};

export const NotifyStack: React.FC<StackProps> = ({ items, x = safe.x, y = N.bandTop, w = blockW, gap = 18, max = 4, order = "top", at = 0, until }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const step = items.length > 1 ? Math.min(5, 15 / (items.length - 1)) : 0;
  const ats = items.map((it, i) => it.at ?? Math.round(at + i * step));
  const hs = items.map((it) => notifyH(it, w) + gap);
  return (
    <>
      {items.map((it, i) => {
        const a = ats[i];
        const life = blockLife(frame, fps, a, until, durationInFrames, { damping: 14, mass: 1 });
        if (frame < a || life.o <= 0) return null;
        let top = y;
        let gone = 0;
        if (order === "top") {
          // every newer card pushes this one down by its own height
          const newer = items.map((_, j) => j).filter((j) => j > i);
          let acc = 0;
          // the stack starts making room PUSH frames before the newcomer lands (no overlap while it drops in)
          top += steps(frame, fps, 0, newer.map((j) => [ats[j] - PUSH, (acc += hs[j])] as [number, number]), { damping: 16, mass: 1.1 });
          if (newer.length >= max) gone = sp(frame, fps, ats[newer[max - 1]], { damping: 20 });
        } else {
          for (let j = 0; j < i; j++) top += hs[j];
        }
        return (
          <div key={i} style={{ position: "absolute", left: x, top, opacity: life.o * (1 - gone), translate: `0px ${(1 - life.e) * -56 - life.x * 40}px`, scale: String((0.96 + 0.04 * life.e) * (1 - 0.04 * gone)), transformOrigin: "50% 0%" }}>
            <NoteCard note={it} w={w} />
          </div>
        );
      })}
    </>
  );
};
