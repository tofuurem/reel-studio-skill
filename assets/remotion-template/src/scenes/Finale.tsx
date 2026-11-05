import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { body, display } from "../fonts";
import { alpha, colors, footagePath } from "../theme";
import { inAt, outBefore } from "../ui/anim";

export type Beat = { dur: number; kind?: "title" | "text" | "ps" | "cta"; text: string; sub?: string };

/**
 * The ending the shoot never got: the article's second half as a typographic epilogue over a
 * soft, darkened cutaway. Beat durations are data so they can be re-timed to a voiceover. `*word` = accent colour.
 */
const BeatView: React.FC<{ beat: Beat }> = ({ beat }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const a = inAt(frame, 0, 14);
  const o = outBefore(frame, durationInFrames, 10);
  const words = beat.text.split(" ");
  const isTitle = beat.kind === "title";
  const isPs = beat.kind === "ps";
  const isCta = beat.kind === "cta";
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: "0 80px", opacity: o }}>
      <div style={{ textAlign: "center", translate: `0px ${(1 - a) * 30}px` }}>
        {isTitle ? (
          <div style={{ fontFamily: display, fontWeight: 900, fontSize: 72, lineHeight: 1.05, color: colors.ink, opacity: a }}>
            {beat.text}
          </div>
        ) : isCta ? (
          <>
            <div style={{ fontFamily: body, fontWeight: 600, fontSize: 32, color: colors.muted, opacity: a }}>{beat.text}</div>
            <div style={{ marginTop: 18, display: "inline-block", fontFamily: display, fontWeight: 700, fontSize: 44, color: colors.bg, background: colors.ink, padding: "18px 30px", borderRadius: 999, opacity: a, scale: String(0.9 + a * 0.1) }}>
              {beat.sub}
            </div>
          </>
        ) : (
          <div style={{ fontFamily: isPs ? display : body, fontWeight: 700, fontSize: isPs ? 56 : 52, lineHeight: 1.2, color: colors.ink }}>
            {words.map((w, i) => {
              const wa = inAt(frame, 4 + i * 2, 8); // word-by-word reveal, calm (opacity only)
              const accent = w.startsWith("*");
              return (
                <span key={i} style={{ opacity: wa, color: accent ? colors.accent2 : colors.ink }}>
                  {w.replace(/\*/g, "")}{" "}
                </span>
              );
            })}
          </div>
        )}
        {beat.sub && !isCta ? (
          <div style={{ marginTop: 20, fontFamily: body, fontWeight: 600, fontSize: 30, color: colors.muted, opacity: inAt(frame, 30, 10) }}>{beat.sub}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

export const Finale: React.FC<{ beats: Beat[]; bg: string; bgTrim: number }> = ({ beats, bg, bgTrim }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const dip = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp", easing: Easing.inOut(Easing.quad) });
  const fadeOut = interpolate(frame, [durationInFrames - 24, durationInFrames - 1], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  let cursor = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: colors.bg }}>
      {/* softness without a full-frame blur filter (expensive per frame): the video is drawn at 1/4 size and scaled up,
          the small blur runs on 1/16 of the pixels */}
      <AbsoluteFill style={{ opacity: 0.5 * dip * fadeOut }}>
        <div style={{ position: "absolute", left: 0, top: 0, width: "25%", height: "25%", scale: "4.32", transformOrigin: "0% 0%", translate: "-1% -1%", filter: "blur(3px) saturate(0.8)" }}>
          <Video src={staticFile(footagePath(bg))} trimBefore={bgTrim} muted objectFit="cover" style={{ width: "100%", height: "100%" }} />
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 45%, ${alpha(colors.bg, 0)} 0%, ${alpha(colors.bg, 0.85)} 80%)` }} />
      <AbsoluteFill style={{ opacity: fadeOut }}>
        {beats.map((b, i) => {
          const from = cursor;
          cursor += b.dur;
          return (
            <Sequence key={i} name={`beat ${i + 1}`} from={from} durationInFrames={b.dur}>
              <BeatView beat={b} />
            </Sequence>
          );
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
