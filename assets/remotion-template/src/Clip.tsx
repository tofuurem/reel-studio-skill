import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { DIALOGUE } from "./dialogueSrc";
import { N } from "./numbers";
import { H, W, footagePath } from "./theme";
import { useDirBlur } from "./ui/DirBlur";
import { zoomBlur } from "@remotion/effects/zoom-blur";
import { LeakLight, NO_LOOK, enterLook, exitLook, leakFilter, mergeLooks, type MatchStart, type SeamKind, type WipePath } from "./ui/Seam";

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
  /** How this clip comes in over the previous one (ui/Seam.tsx; references/craft/transitions.md), over `enterFrames`. */
  enter?: SeamKind;
  enterFrames?: number;
  /** The seam into the NEXT clip: whip animates the overlap tail; push / blur / leak shape the last frames before the cut. */
  exit?: "none" | SeamKind;
  exitFrames?: number;
  /** enter="match": where the head is and how far / how much to move it so it lands on the previous head (seams.py). */
  match?: MatchStart;
  /** enter="bodywipe": the passing person's trailing edge per frame (seams.py). */
  wipe?: WipePath;
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
 * Cuts overlap by a few frames: the incoming clip dissolves (or whips) in over the held outgoing one. Other seams (push, blur,
 * leak, wipe, bodywipe, match, cut) come from ui/Seam.tsx — rare by design (references/craft/transitions.md, seam budget).
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
  match,
  wipe,
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
  // every other seam: ui/Seam.tsx says how the clip looks right after its cut-in and right before its cut-out
  const look = mergeLooks(enter && enter !== "whip" ? enterLook(enter, frame, enterFrames, match, wipe) : NO_LOOK, exit !== "none" && exit !== "whip" ? exitLook(exit, frame, realLen) : NO_LOOK);
  // the leak's light drifts across the cut as one sweep: u runs over the outgoing tail and on through the incoming head
  // (the outgoing clip under the overlap continues ITS sweep from the cut — counting from frame 0 there made the light jump back;
  // a clip that enters and leaves on a leak sweeps at both ends)
  const cl = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  const leakU = exit === "leak" && frame > realLen - N.seamLeakOut
    ? frame <= realLen ? interpolate(frame, [realLen - N.seamLeakOut, realLen], [0, 0.4], cl) : interpolate(frame - realLen, [0, N.seamLeakIn], [0.4, 1], cl)
    : interpolate(frame, [0, N.seamLeakIn], [0.4, 1], cl);

  const opacity = (enter === "whip" ? 1 : look.opacity);
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
  const filters = [dirBlur.filter, look.blur > 0.05 ? `blur(${look.blur.toFixed(2)}px)` : undefined, leakFilter(look.light)].filter(Boolean).join(" ") || undefined;
  // the zoom blur is a WebGL effect on the video itself (@remotion/effects). A clip that has a push seam keeps the effect
  // for its whole life, disabled between seams: an effect added mid-clip was never applied (the outgoing push stayed sharp)
  const cy = Math.min(1, Math.max(0, N.punchCenterY / H));
  const effects = enter === "push" || exit === "push" ? [zoomBlur({ amount: Math.max(1, look.zoomBlur), center: [0.5, cy], disabled: look.zoomBlur <= 0.5 })] : [];
  return (
    <AbsoluteFill
      style={{
        opacity,
        translate: `${translateX}% 0px`,
        filter: filters,
        maskImage: look.mask,
        WebkitMaskImage: look.mask,
      }}
    >
      {dirBlur.defs}
      <AbsoluteFill style={look.matchStyle}>
      <AbsoluteFill
        style={{
          transformOrigin: origin,
          scale: String(
            look.scale *
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
                  <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} volume={vol} muted={muted} playbackRate={playbackRate} effects={effects} style={{ position: "absolute", ...g.video }} />
                </div>
              );
            })()
          ) : (
            <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} volume={vol} muted={muted} playbackRate={playbackRate} effects={effects} objectFit={fit ?? (framing ? "contain" : "cover")} style={{ width: "100%", height: "100%" }} />
          )}
        </AbsoluteFill>
      </AbsoluteFill>
      </AbsoluteFill>
      <LeakLight light={look.light} u={leakU} />
    </AbsoluteFill>
  );
};
