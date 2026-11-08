import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { N } from "../numbers";
import { footagePath } from "../theme";
import { envelope } from "../ui/anim";
import { BehindTitle, MatteLayer } from "./BehindTitle";

type Props = {
  src: string;
  trimBefore: number;
  /** Slow push-in for life. */
  zoomFrom?: number;
  zoomTo?: number;
  /** 0 = hard edge (montage cuts): the first/last frame stays fully opaque. */
  fadeIn?: number;
  fadeOut?: number;
  /** A title behind the person (reelgen.cutaway(..., behind={...}) makes the matte with person_matte.py). Local frames. */
  behind?: { matte: string; title: string; kicker?: string; at?: number; until?: number; y?: number; x?: number; scale?: number };
  children?: React.ReactNode;
};

/** Full-frame cutaway over the talking head. Audio keeps coming from the main timeline.
 *  Its Sequence should start ≥ N.coverBefore frames before the cut it covers and end ≥ N.coverAfter after it
 *  (reelgen.cover() / reelgen.cutaway() widen the range) and carry premountFor (reelgen does). */
export const BRoll: React.FC<Props> = ({ src, trimBefore, zoomFrom = 1, zoomTo = 1.08, fadeIn = N.layerFade, fadeOut = N.layerFade, behind, children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <AbsoluteFill style={{ opacity: envelope(frame, durationInFrames, fadeIn, fadeOut) }}>
      <AbsoluteFill style={{ scale: String(interpolate(frame, [0, Math.max(1, durationInFrames)], [zoomFrom, zoomTo], { extrapolateRight: "clamp", easing: Easing.linear })) }}>
        <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} muted objectFit="cover" style={{ width: "100%", height: "100%" }} />
        {behind ? <BehindTitle title={behind.title} kicker={behind.kicker} at={behind.at ?? 4} until={behind.until ?? durationInFrames} y={behind.y} x={behind.x} scale={behind.scale} /> : null}
        {behind ? <MatteLayer src={behind.matte} /> : null}
        {behind?.kicker ? <BehindTitle part="front" title={behind.title} kicker={behind.kicker} at={behind.at ?? 4} until={behind.until ?? durationInFrames} y={behind.y} x={behind.x} scale={behind.scale} /> : null}
      </AbsoluteFill>
      {children}
    </AbsoluteFill>
  );
};
