import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { body } from "../fonts";
import { colors, footagePath, safe } from "../theme";
import { Card } from "../ui/Card";
import { ChipRow, type Chip } from "../ui/ChipRow";
import { inAt } from "../ui/anim";

/* Cards over the talking head (lofiroom ep1 ImageCard / PrototypeCard, made generic): a real screenshot or a screen
   recording in the face-free band, one caption line or chips under it. Place it with `top` + `maxH` from a reelgen band
   (`a, b = R.free_bottom(t0, t1)` → `top=a, maxH=b - a`): the picture shrinks to fit the band, so the card never reaches the
   captions (y ≥ 1400) — a 16:10 screenshot at full width is 600 px tall and ran over them in the 2026-10-22 dry run. */

const PAD = 24;
const innerW = 1080 - 2 * safe.x - 2 * PAD;
const CAPTION_H = 16 + 38; // marginTop + one 30 px line

/** Picture size inside a card: full inner width, or smaller (same ratio) when the card must fit in `maxH` px. */
const fitBox = (ratio: number, maxH?: number, extra = 0) => {
  const h0 = Math.round(innerW / ratio);
  if (!maxH) return { w: innerW, h: h0 };
  const h = Math.max(120, Math.min(h0, maxH - 2 * PAD - extra));
  return { w: Math.round(h * ratio), h };
};
/** A narrower picture gets a narrower card, centred (no wide empty panel around a small screenshot). */
const sideFor = (w: number) => ({ left: Math.max(safe.x, Math.round((1080 - w - 2 * PAD) / 2)), right: Math.max(safe.x, Math.round((1080 - w - 2 * PAD) / 2)) });

/** A real screenshot with a slow push-in and one caption line (CapCut overlay inserts land here too). */
export const ImageCard: React.FC<{ src: string; ratio: number; caption?: string; zoomTo?: number; top?: number; maxH?: number; at?: number }> = ({ src, ratio, caption, zoomTo = 1.08, top, maxH, at = 0 }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const { w, h } = fitBox(ratio, maxH, caption ? CAPTION_H : 0);
  const cap = inAt(frame, at + 10, 12);
  return (
    <AbsoluteFill>
      <Card top={top} padding={PAD} at={at} style={sideFor(w)}>
        <div style={{ width: w, height: h, margin: "0 auto", borderRadius: 24, overflow: "hidden", background: colors.panelSolid }}>
          <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover", scale: String(interpolate(frame, [0, Math.max(1, durationInFrames)], [1, zoomTo], { extrapolateRight: "clamp" })) }} />
        </div>
        {caption ? <div style={{ marginTop: 16, fontFamily: body, fontWeight: 700, fontSize: 30, color: colors.muted, opacity: cap, textAlign: "center" }}>{caption}</div> : null}
      </Card>
    </AbsoluteFill>
  );
};

/** A screen recording (footage/c….mp4 proxy) in a card, optional corner label and chips that land on the spoken verbs. */
export const VideoCard: React.FC<{ src: string; trimBefore: number; ratio: number; chips?: Chip[]; label?: string; top?: number; maxH?: number; zoom?: number; at?: number }> = ({ src, trimBefore, ratio, chips, label, top, maxH, zoom = 1, at = 0 }) => {
  const frame = useCurrentFrame();
  const { w, h } = fitBox(ratio, maxH, chips?.length ? 16 + 56 : 0);
  const l = inAt(frame, at + 8, 12);
  return (
    <AbsoluteFill>
      <Card top={top} padding={PAD} at={at} style={sideFor(w)}>
        <div style={{ position: "relative", width: w, height: h, margin: "0 auto", borderRadius: 24, overflow: "hidden", background: colors.panelSolid }}>
          <Video src={staticFile(footagePath(src))} trimBefore={trimBefore} muted objectFit="cover" style={{ width: "100%", height: "100%", scale: String(zoom), transformOrigin: "50% 56%" }} />
          {label ? <div style={{ position: "absolute", right: 16, bottom: 14, padding: "6px 16px", borderRadius: 999, background: colors.panel, fontFamily: body, fontWeight: 800, fontSize: 28, color: colors.ink, opacity: l }}>{label}</div> : null}
        </div>
        {chips?.length ? (
          <div style={{ marginTop: 16 }}>
            <ChipRow chips={chips} size={30} />
          </div>
        ) : null}
      </Card>
    </AbsoluteFill>
  );
};
