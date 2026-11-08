import React from "react";
import { Audio } from "@remotion/media";
import { AbsoluteFill, Easing, Freeze, OffthreadVideo, Sequence, interpolate, random, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { body, display, mono } from "./fonts";
import { N } from "./numbers";
import { END_FRAMES, HOOK, SHOTS } from "./shotsData";
import { colors, H, W } from "./theme";
import { useDirBlur } from "./ui/DirBlur";
import { BehindTitle } from "./scenes/BehindTitle";
import { sfxLevel } from "./ui/Sfx";

/**
 * The action reel (references/inputs/action-reel.md): shots cut on the track's beat grid, no music in the file — the user
 * adds the same track in Instagram from TRACK_START (ActionTrack previews it). Shots come from work/gen_action.py
 * (scripts/actiongen.py): each piece is already cropped to the people, graded and speed-ramped at 2K; here are only the
 * whips (silent, blurred along the move), punch-ins, shake, the hit flash, the freeze, captions, the title behind a person,
 * the camera-battery gag and the end.
 */
export type Piece = { file: string; frames: number; matte?: string };
export type Shot = {
  note: string; frames: number; pieces: Piece[]; hold?: number; voice?: string; voiceAt?: number; voiceGain?: number;
  whip?: "left" | "right"; punch?: [number, number]; punchAt?: number; flashAt?: number; shake?: boolean; shakeAt?: number;
  caption?: string; captionAt?: number; captionTail?: number; battery?: number; sfx?: [number, string][];
  behind?: { title: string; kicker?: string; at?: number; until?: number; y?: number; x?: number; scale?: number };
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const TEXT_SHADOW = "0 3px 0 rgba(0,0,0,0.55), 0 0 18px rgba(0,0,0,0.7)";
const PORTRAIT = H > W;

export const START: number[] = [];
let acc = 0;
for (const s of SHOTS) { START.push(acc); acc += s.frames + (s.hold ?? 0); }
const SHOTS_END = acc;
export const ACTION_FRAMES = Math.max(1, SHOTS_END + END_FRAMES);

/** One shot: its pieces back to back, then an optional freeze of the last frame. Motion effects wrap the whole shot. */
const ShotView: React.FC<{ s: Shot }> = ({ s }) => {
  const f = useCurrentFrame();
  const total = s.frames + (s.hold ?? 0);
  // whip in: a fast slide over the first 6 frames, blurred only along the move
  const w = s.whip ? interpolate(f, [0, 6], [1, 0], { ...clamp, easing: Easing.out(Easing.cubic) }) : 0;
  const dir = s.whip === "left" ? -1 : 1;
  const blur = useDirBlur(w * 46, 0);
  let scale = 1;
  if (s.punch) {
    const at = s.punchAt ?? 0;
    scale = interpolate(f, [at, at + 6, total], [s.punch[0], s.punch[1], s.punch[1] + 0.03], { ...clamp, easing: Easing.out(Easing.quad) });
  } else scale = interpolate(f, [0, total], [1.0, 1.04], clamp); // every shot drifts in a little: nothing sits still
  const sh = s.shake && f >= (s.shakeAt ?? 0) && f < (s.shakeAt ?? 0) + 10 ? (1 - (f - (s.shakeAt ?? 0)) / 10) * 22 : 0;
  const sx = sh ? (random(`x${f}`) - 0.5) * sh : 0, sy = sh ? (random(`y${f}`) - 0.5) * sh : 0;
  const video = { width: "100%", height: "100%", objectFit: "cover" } as const;
  const layer = (matte: boolean) => {
    let off = 0;
    return s.pieces.map((p, i) => {
      const from = off; off += p.frames;
      if (matte && !p.matte) return null;
      return (
        <Sequence key={`${matte ? "m" : "v"}${i}`} from={from} durationInFrames={p.frames} layout="none">
          <OffthreadVideo src={staticFile(matte ? p.matte! : p.file)} muted transparent={matte} style={video} />
        </Sequence>
      );
    });
  };
  const last = s.pieces[s.pieces.length - 1];
  return (
    <AbsoluteFill style={{ background: "black", overflow: "hidden" }}>
      <AbsoluteFill style={{ translate: `${dir * w * 420 + sx}px ${sy}px`, scale: String(scale + w * 0.08), filter: blur.filter }}>
        {layer(false)}
        {s.hold ? (
          <Sequence from={s.frames} durationInFrames={s.hold} layout="none">
            <Freeze frame={last.frames - 1}>
              <OffthreadVideo src={staticFile(last.file)} muted style={{ ...video, filter: "saturate(0.2) contrast(1.15)" }} />
            </Freeze>
          </Sequence>
        ) : null}
        {s.behind ? <BehindTitle title={s.behind.title} kicker={s.behind.kicker} at={s.behind.at ?? 2} until={s.behind.until ?? s.frames} y={s.behind.y} x={s.behind.x} scale={s.behind.scale} /> : null}
        {s.behind ? <AbsoluteFill>{layer(true)}</AbsoluteFill> : null /* positioned, or the absolute title paints over it */}
        {s.behind?.kicker ? <BehindTitle part="front" title={s.behind.title} kicker={s.behind.kicker} at={s.behind.at ?? 2} until={s.behind.until ?? s.frames} y={s.behind.y} x={s.behind.x} scale={s.behind.scale} /> : null}
      </AbsoluteFill>
      {blur.defs}
      {s.flashAt !== undefined ? <AbsoluteFill style={{ background: "white", opacity: interpolate(f, [s.flashAt, s.flashAt + 1, s.flashAt + 6], [0, N.flashPeak, 0], clamp) }} /> : null}
    </AbsoluteFill>
  );
};

/** A spoken punchline: one phrase, big, lower middle; pops in, holds, fades. */
const Punch: React.FC<{ text: string }> = ({ text }) => {
  const f = useCurrentFrame();
  const { durationInFrames: d } = useVideoConfig();
  const a = interpolate(f, [0, 5], [0, 1], { ...clamp, easing: Easing.out(Easing.back(2)) });
  const o = interpolate(f, [d - 5, d], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: PORTRAIT ? 560 : 150, paddingLeft: 90, paddingRight: PORTRAIT ? 150 : 90 }}>
      <div style={{ fontFamily: body, fontWeight: 900, fontSize: text.length > 30 ? 62 : 74, lineHeight: 1.12, textAlign: "center", whiteSpace: "pre-line", color: colors.ink, textShadow: TEXT_SHADOW, opacity: Math.min(1, a) * o, scale: String(0.85 + 0.15 * a) }}>
        {text}
      </div>
    </AbsoluteFill>
  );
};

/** Opening tag over the first shots: a small kicker over a big title, slides in from the left. */
const Hook: React.FC<{ kicker?: string; title: string }> = ({ kicker, title }) => {
  const f = useCurrentFrame();
  const { durationInFrames: d } = useVideoConfig();
  const a = interpolate(f, [0, 8], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const o = interpolate(f, [d - 6, d], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <div style={{ position: "absolute", left: 80, bottom: PORTRAIT ? 520 : 120, translate: `${(1 - a) * -60}px 0px`, opacity: a }}>
        {kicker ? <div style={{ fontFamily: mono, fontSize: 34, fontWeight: 700, letterSpacing: 3, color: colors.accent, textShadow: TEXT_SHADOW }}>{kicker}</div> : null}
        <div style={{ fontFamily: display, fontSize: 104, fontWeight: 900, lineHeight: 1, color: colors.ink, textShadow: TEXT_SHADOW }}>{title}</div>
      </div>
    </AbsoluteFill>
  );
};

/** Camera battery, top right; ≤ 9 % turns red and blinks (the «the battery dies with the night» gag). */
const Battery: React.FC<{ pct: number }> = ({ pct }) => {
  const f = useCurrentFrame();
  const a = interpolate(f, [0, 8], [0, 1], clamp);
  const low = pct <= 9;
  const blink = low ? 0.5 + 0.5 * Math.round((Math.sin(f / 3.5) + 1) / 2) : 1;
  const col = low ? colors.bad : colors.ok;
  const w = 96, h = 46;
  return (
    <AbsoluteFill style={{ opacity: a }}>
      <div style={{ position: "absolute", right: PORTRAIT ? 150 : 80, top: PORTRAIT ? 250 : 60, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ fontFamily: mono, fontSize: 42, fontWeight: 700, color: col, opacity: blink, textShadow: TEXT_SHADOW }}>{pct}%</div>
        <svg width={w + 10} height={h} viewBox={`0 0 ${w + 10} ${h}`}>
          <rect x={2} y={2} width={w - 4} height={h - 4} rx={9} fill="rgba(0,0,0,0.35)" stroke={colors.ink} strokeWidth={4} />
          <rect x={w} y={h / 2 - 8} width={8} height={16} rx={3} fill={colors.ink} />
          <rect x={9} y={9} width={Math.max(4, ((w - 18) * pct) / 100)} height={h - 18} rx={4} fill={col} opacity={blink} />
        </svg>
      </div>
    </AbsoluteFill>
  );
};

/** The end with the battery gag: black, a red dead-battery mark blinks; without it a plain fade to black. */
const Dead: React.FC = () => {
  const f = useCurrentFrame();
  const on = f > 3 && Math.floor(f / 5) % 2 === 0 ? 1 : 0.15;
  return (
    <AbsoluteFill style={{ background: "black", justifyContent: "center", alignItems: "center" }}>
      <svg width={260} height={120} viewBox="0 0 260 120" style={{ opacity: on }}>
        <rect x={5} y={5} width={232} height={110} rx={16} fill="none" stroke={colors.bad} strokeWidth={8} />
        <rect x={240} y={42} width={16} height={36} rx={5} fill={colors.bad} />
        <rect x={22} y={22} width={12} height={76} rx={3} fill={colors.bad} />
      </svg>
    </AbsoluteFill>
  );
};
const Black: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: "black", opacity: interpolate(f, [0, 8], [0, 1], clamp) }} />;
};

const level = sfxLevel;

/** withTrack: the preview only — the track (track_beats.py cut it into audio/track_cut.m4a) under everything. */
export const Action: React.FC<{ withTrack?: boolean }> = ({ withTrack = false }) => {
  const hasBattery = SHOTS.some((s) => s.battery !== undefined);
  return (
    <AbsoluteFill style={{ background: "black" }}>
      {SHOTS.map((s, i) => (
        <Sequence key={`v${i}`} name={`${String(i + 1).padStart(2, "0")} · ${s.note}`} from={START[i]} durationInFrames={s.frames + (s.hold ?? 0)}>
          <ShotView s={s} />
        </Sequence>
      ))}
      {SHOTS.map((s, i) =>
        s.voice ? (
          <Sequence key={`a${i}`} name={`voice · ${s.note}`} from={START[i] + (s.voiceAt ?? 0)} durationInFrames={s.frames + 30}>
            <Audio src={staticFile(s.voice)} volume={s.voiceGain ?? 1} />
          </Sequence>
        ) : null,
      )}
      {SHOTS.map((s, i) =>
        s.caption ? (
          <Sequence key={`c${i}`} name={`caption · ${s.caption}`} from={START[i] + (s.captionAt ?? 2)} durationInFrames={s.frames + (s.hold ?? 0) - (s.captionAt ?? 2) + (s.captionTail ?? 0)}>
            <Punch text={s.caption} />
          </Sequence>
        ) : null,
      )}
      {SHOTS.flatMap((s, i) => (s.sfx ?? []).map(([at, kind], k) => (
        <Sequence key={`s${i}-${k}`} name={`sfx · ${kind}`} from={Math.max(0, START[i] + at)} durationInFrames={45}>
          <Audio src={staticFile(`audio/sfx/${kind}.wav`)} volume={level(kind)} />
        </Sequence>
      )))}
      {withTrack ? <Audio src={staticFile("audio/track_cut.m4a")} name="track (preview)" volume={0.55} /> : null}
      {HOOK && SHOTS.length > HOOK.from ? (
        <Sequence name="hook" from={START[HOOK.from]} durationInFrames={Math.max(1, (HOOK.to < SHOTS.length ? START[HOOK.to] : SHOTS_END) - START[HOOK.from])}>
          <Hook kicker={HOOK.kicker} title={HOOK.title} />
        </Sequence>
      ) : null}
      {SHOTS.map((s, i) => {
        if (s.battery === undefined) return null;
        const next = SHOTS.findIndex((t, j) => j > i && t.battery !== undefined);
        const to = next < 0 ? SHOTS_END : START[next];
        return (
          <Sequence key={`b${i}`} name={`battery ${s.battery}%`} from={START[i]} durationInFrames={to - START[i]}>
            <Battery pct={s.battery} />
          </Sequence>
        );
      })}
      {END_FRAMES > 0 && SHOTS.length ? (
        <Sequence name="end" from={SHOTS_END} durationInFrames={END_FRAMES}>
          {hasBattery ? <Dead /> : <Black />}
          {hasBattery ? <Audio src={staticFile("audio/sfx/powerdown.wav")} volume={level("powerdown")} /> : null}
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};
