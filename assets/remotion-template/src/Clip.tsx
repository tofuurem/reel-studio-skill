import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { DIALOGUE } from "./dialogueSrc";
import { N } from "./numbers";
import { H, W, footagePath } from "./theme";
import { useDirBlur } from "./ui/DirBlur";

type Transition = "dissolve" | "whip";

/** The user's CapCut framing of a clip (cutlist "transform"): scale about the clip centre, then the centre moves by
 *  x / y half-canvas units (y points UP, as in CapCut), rotation in degrees clockwise, optional horizontal flip.
 *  Scale 1 = the source fitted inside the canvas (CapCut's default), so a framed clip renders with objectFit contain. */
export type Framing = { scale?: number; scaleY?: number; x?: number; y?: number; rotation?: number; flipH?: boolean };
/** CapCut crop: the part of the source that stays (0–1 of its width/height); CapCut then fits that part to the canvas. */
export type Crop = { x0: number; y0: number; x1: number; y1: number };

type Props = {
  src: string;
  trimBefore: number;
  /** Framing scale at the first frame (1 = full frame, 1.1 = punch-in). */
  punch?: number;
  /** How much the frame slowly drifts in over the clip (adds life to static shots). */
  drift?: number;
  volume?: number | ((f: number) => number);
  /** Where the zoom pivots. Default: the eye line N.punchCenterY (face_zones.py corrects the face band around the same point). */
  origin?: string;
  /** Real length of the cut; frames after it are the overlap under the next clip (video held, audio muted). */
  hold?: number;
  /** How this clip comes in over the previous one, over `enterFrames`. */
  enter?: Transition;
  enterFrames?: number;
  /** How this clip leaves during its overlap tail (only "whip" animates; a dissolve is done by the next clip). */
  exit?: "none" | "whip";
  exitFrames?: number;
  /** Ramp the sound over N frames (used when a cut lands inside a word). */
  audioFadeIn?: number;
  /** CapCut speed change (cutlist.speed) — forwarded to the video. */
  playbackRate?: number;
  /** CapCut framing / crop (gen_timeline.py emits them from the cut list; punch and drift still apply on top). */
  framing?: Framing;
  crop?: Crop;
  /** Source size in px (needed for crop; cutlist srcW/srcH). */
  srcW?: number;
  srcH?: number;
  /** "cover" fills the canvas (talking heads, the default); "contain" fits like CapCut (any framed or cropped clip). */
  fit?: "cover" | "contain";
  name?: string;
};

/** The box (canvas px) the visible picture occupies before framing: the crop region fitted inside the canvas. */
const cropGeometry = (crop: Crop, srcW: number, srcH: number) => {
  const cw = (crop.x1 - crop.x0) * srcW, ch = (crop.y1 - crop.y0) * srcH;
  const k = Math.min(W / cw, H / ch);
  const bw = cw * k, bh = ch * k, bx = (W - bw) / 2, by = (H - bh) / 2;
  // the whole video element at the same scale, shifted so the crop region lands on the box
  return { box: { left: bx, top: by, width: bw, height: bh }, video: { left: -crop.x0 * srcW * k, top: -crop.y0 * srcH * k, width: srcW * k, height: srcH * k } };
};

const easeOut = Easing.out(Easing.cubic);
const easeIn = Easing.in(Easing.cubic);

/**
 * One talking-head take. The slow drift and optional punch-in are the
 * "reels" rhythm: every cut lands on a slightly different framing.
 * Cuts overlap by a few frames: the incoming clip dissolves (or whips) in over the held outgoing one.
 */
export const Clip: React.FC<Props> = ({
  src,
  trimBefore,
  punch = 1,
  drift = N.punchDrift,
  volume = 1,
  origin = `50% ${((N.punchCenterY / H) * 100).toFixed(2)}%`,
  hold,
  enter,
  enterFrames = N.xfade,
  exit = "none",
  exitFrames = N.xfade,
  audioFadeIn = 0,
  playbackRate = 1,
  framing,
  crop,
  srcW,
  srcH,
  fit,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const realLen = hold ?? durationInFrames;

  // the dialogue stem (dialogue.py) carries the voice: the proxy's own sound would double it
  const muted = DIALOGUE !== null;
  const vol = (f: number) => {
    const base = typeof volume === "function" ? volume(f) : volume;
    if (f >= realLen) return 0;
    if (audioFadeIn > 0 && f < audioFadeIn) return base * (f / audioFadeIn);
    return base;
  };

  const inP = enter ? interpolate(frame, [0, Math.max(1, enterFrames)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeOut }) : 1;
  const outP = exit === "whip" ? interpolate(frame, [realLen, realLen + Math.max(1, exitFrames)], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: easeIn }) : 0;

  const opacity = enter === "dissolve" ? inP : 1;
  let translateX = 0;
  let blur = 0;
  if (enter === "whip") {
    translateX += (1 - inP) * 45;
    blur += (1 - inP) * 26;
  }
  if (exit === "whip") {
    translateX -= outP * 45;
    blur += outP * 26;
  }

  // the whip streaks only along the move (an SVG filter): CSS blur() smeared in every direction and read as a defocus
  const dirBlur = useDirBlur(blur * 1.6, 0);
  return (
    <AbsoluteFill
      style={{
        opacity,
        translate: `${translateX}% 0px`,
        filter: dirBlur.filter,
      }}
    >
      {dirBlur.defs}
      <AbsoluteFill
        style={{
          transformOrigin: origin,
          scale: String(
            interpolate(frame, [0, Math.max(1, realLen)], [punch, punch + drift], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.linear,
            }),
          ),
        }}
      >
        <AbsoluteFill
          style={
            framing
              ? {
                  translate: `${(framing.x ?? 0) * 50}% ${-(framing.y ?? 0) * 50}%`,
                  rotate: `${framing.rotation ?? 0}deg`,
                  scale: `${(framing.flipH ? -1 : 1) * (framing.scale ?? 1)} ${framing.scaleY ?? framing.scale ?? 1}`,
                }
              : undefined
          }
        >
          {crop && srcW && srcH ? (
            (() => {
              const g = cropGeometry(crop, srcW, srcH);
              return (
                <div style={{ position: "absolute", ...g.box, overflow: "hidden" }}>
                  <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} volume={vol} muted={muted} playbackRate={playbackRate} style={{ position: "absolute", ...g.video }} />
                </div>
              );
            })()
          ) : (
            <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} volume={vol} muted={muted} playbackRate={playbackRate} objectFit={fit ?? (framing ? "contain" : "cover")} style={{ width: "100%", height: "100%" }} />
          )}
        </AbsoluteFill>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
