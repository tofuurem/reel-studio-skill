import { Easing, interpolate, spring } from "remotion";

export const ease = Easing.bezier(0.16, 1, 0.3, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** 0→1 pop-in over `len` frames starting at `start`. */
export const inAt = (frame: number, start: number, len = 10) => interpolate(frame, [start, start + len], [0, 1], { ...clamp, easing: ease });

/** 1→0 over the last `len` frames of a sequence of `duration` frames. */
export const outBefore = (frame: number, duration: number, len = 8) =>
  interpolate(frame, [duration - len, duration - 1], [1, 0], { ...clamp, easing: Easing.in(Easing.quad) });

/** 1→0 over `len` frames from `until` (an element that leaves inside its sequence). */
export const leaveAt = (frame: number, until: number | undefined, len = 8) => (until === undefined ? 1 : interpolate(frame, [until, until + len], [1, 0], clamp));

/**
 * Opacity of a full-frame layer (BRoll, Board) that fades in over `fadeIn` and out over the last `fadeOut` frames.
 * Frame 0 is already slightly visible (no empty first frame); fadeIn/fadeOut 0 = hard edge — the last frame stays opaque
 * (the old curve blanked it, which flashed the carrier on montage hard cuts).
 */
export const envelope = (frame: number, duration: number, fadeIn: number, fadeOut: number) => {
  const a = fadeIn > 0 ? interpolate(frame, [-1, fadeIn], [0, 1], clamp) : 1;
  const b = fadeOut > 0 ? interpolate(frame, [duration - 1 - fadeOut, duration - 1], [1, 0], clamp) : 1;
  return a * b;
};

/** Progress 0..1 of the strongest window among frame ranges, `edge` frames ease at each end (Stage / SplitStage). */
export const windowProgress = (frame: number, windows: { from: number; to: number }[], edge = 12) => {
  let p = 0;
  for (const w of windows) {
    const e = Math.min(edge, Math.floor((w.to - w.from - 1) / 2)); // a short window eases faster instead of throwing
    if (e < 1) continue;
    const v = interpolate(frame, [w.from, w.from + e, w.to - e, w.to], [0, 1, 1, 0], { ...clamp, easing: Easing.inOut(Easing.cubic) });
    if (v > p) p = v;
  }
  return p;
};

/** 1470000 → «1 470 000» (Russian grouping with a no-break space). */
export const fmt = (n: number) => n.toLocaleString("ru-RU").replace(/\s/g, " ");

// ---------- springs (Motion kit; here so ui/ components can use them without importing scenes/)

export type SpringCfg = { damping?: number; mass?: number; stiffness?: number };
/** 0→1 spring that starts at frame `at` (slight overshoot with the default config). */
export const sp = (frame: number, fps: number, at: number, cfg: SpringCfg = {}) =>
  spring({ frame: frame - at, fps, config: { damping: cfg.damping ?? 15, mass: cfg.mass ?? 1, stiffness: cfg.stiffness ?? 110 } });

/** A value that moves to each new target on its frame; consecutive moves overlap instead of stopping dead. */
export const steps = (frame: number, fps: number, initial: number, changes: [number, number][], cfg: SpringCfg = {}) => {
  let v = initial;
  let prev = initial;
  for (const [at, target] of changes) {
    v += (target - prev) * sp(frame, fps, at, cfg);
    prev = target;
  }
  return v;
};

/** Integer count from a to b between frames `from` and `to` (ease-out). */
export const countUp = (frame: number, from: number, to: number, a: number, b: number) =>
  Math.round(interpolate(frame, [from, Math.max(from + 1, to)], [a, b], { ...clamp, easing: Easing.out(Easing.cubic) }));
