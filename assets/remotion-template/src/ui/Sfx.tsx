import React from "react";
import { Audio } from "@remotion/media";
import { interpolate, staticFile, useVideoConfig } from "remotion";
import { N } from "../numbers";

/** Sound kinds made locally by scripts/make_sfx.sh → public/audio/sfx/<kind>.wav (no network at render time): designed
 *  sounds from earshot's bank when it is installed (sfx_bank.py), synthesized otherwise. whoosh, softwhoosh, pop and hit also
 *  exist as <kind>2 / <kind>3: reelgen.sfx() cycles them, so a repeat is never the same sample. real_<name>: a real
 *  recording sfx_find.py fetched from Openverse (CC0 / CC BY). */
export type SfxKind = "tick" | "pop" | "done" | "whoosh" | "softwhoosh" | "hit" | "shutter" | "rewind" | "riser" | "beep" | "powerdown";
export type SfxName = SfxKind | `${"whoosh" | "softwhoosh" | "pop" | "hit"}${2 | 3}` | `real_${string}`;   // real_*: sfx_find.py (Openverse)

/** Levels from numbers.json: a different sound per kind of action, all quiet (≈ 20 LU under speech); hit is the loud one. */
export const SFX_LEVEL: Record<SfxKind, number> = {
  tick: N.sfxTick, pop: N.sfxPop, done: N.sfxDone, whoosh: N.sfxWhoosh, softwhoosh: N.sfxSoftWhoosh,
  hit: N.sfxHit, shutter: N.sfxShutter, rewind: N.sfxRewind, riser: N.sfxRiser, beep: N.sfxBeep, powerdown: N.sfxPowerdown,
};
/** The level of a kind or one of its variants ("whoosh2" → whoosh). */
export const sfxLevel = (name: string) => (name.startsWith("real_") ? N.sfxReal : (SFX_LEVEL as Record<string, number>)[name.replace(/\d+$/, "")] ?? 0.3);

/** One sound effect; put it in a <Sequence from={frame} durationInFrames={N.sfxFrames}> (reelgen.sfx() does). */
export const Sfx: React.FC<{ kind: SfxName; volume?: number }> = ({ kind, volume }) => <Audio src={staticFile(`audio/sfx/${kind}.wav`)} volume={volume ?? sfxLevel(kind)} />;

type Range = [number, number];

/**
 * The music bed over the whole reel (place it at the top level, not inside a Sequence: frames are reel frames).
 * bedOpen before the first word, in wordless pauses and after the last word; bedUnder (≈ 20 LU down) under speech;
 * N.bedRamp-frame ramps between them (a jump is heard as a cut) and an N.bedFadeOut fade at the very end.
 */
export const MusicBed: React.FC<{ src?: string; speechStart?: number; speechEnd: number; pauses?: Range[]; under?: number; open?: number; name?: string }> = ({
  src = "audio/lofi_bed.wav",
  speechStart = 0,
  speechEnd,
  pauses = [],
  under = N.bedUnder,
  open = N.bedOpen,
  name = "music bed",
}) => {
  const { durationInFrames } = useVideoConfig();
  const R = N.bedRamp;
  const c = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  const openness = (f: number) => {
    let o = speechStart > 0 ? interpolate(f, [speechStart - R, speechStart], [1, 0], c) : 0;
    o = Math.max(o, interpolate(f, [speechEnd, speechEnd + R], [0, 1], c));
    for (const [a, b] of pauses) {
      const r = Math.min(R, Math.floor((b - a - 1) / 2)); // a short pause ramps faster instead of throwing (a+r must stay < b-r)
      if (r < 1) continue;
      o = Math.max(o, interpolate(f, [a, a + r, b - r, b], [0, 1, 1, 0], c));
    }
    return o;
  };
  const end = (f: number) => interpolate(f, [durationInFrames - 1 - N.bedFadeOut, durationInFrames - 1], [1, 0], c);
  return <Audio src={staticFile(src)} name={name} volume={(f) => (under + (open - under) * openness(f)) * end(f)} />;
};
