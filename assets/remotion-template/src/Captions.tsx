import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AbsoluteFill, Easing, interpolate, Sequence, staticFile, useCurrentFrame, useDelayRender, useVideoConfig } from "remotion";
import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption, TikTokPage } from "@remotion/captions";
import { body } from "./fonts";
import { N } from "./numbers";
import { H, W, colors, shadows } from "./theme";

/** Pages are cut by pageBreakAfter flags computed in work/ (punctuation, word/second/character caps); the combine window is huge on purpose. */
const SWITCH_CAPTIONS_EVERY_MS = 60000;
/** If the next phrase starts within this gap, the line stays up and the text soft-swaps (no blink). */
const BRIDGE_MS = N.capBridgeMs;
/** Soft swap: outgoing fades/rises while the incoming fades/rises in, over the same frames → the sum of opacities stays ≈1. */
const SWAP = N.capSwap;
/** Isolated appear/disappear (a real pause before/after). */
const FADE = N.capFade;
const HOLD_AFTER_MS = N.capHoldMs;
/** Caption column width; a page longer than two lines at N.capFontPx gets a smaller font instead of a third line
 *  (a third line climbs into the card band). make_captions.py --max-chars keeps pages short in the first place. */
const LANDSCAPE = W > H;
/** 16:9: a wider column over the road at the bottom, text bottom at ≈ 960 (layout-rules.md); 9:16 keeps the reel values. */
const COL_W = LANDSCAPE ? 1240 : 1080 - 2 * 80;
const PAD_BOTTOM = LANDSCAPE ? 118 : N.capBottomPad;
const PAD_X = (W - COL_W) / 2;
const fontFor = (text: string) => Math.max(40, Math.min(N.capFontPx, Math.floor((COL_W * 2) / (0.58 * Math.max(1, text.length)))));

const ease = Easing.inOut(Easing.quad);

type Timing = { start: number; end: number; fadeIn: number; fadeOut: number; swapIn: boolean; swapOut: boolean };

/** Calm, semi-static subtitle. No per-word highlight. */
const CaptionPage: React.FC<{ page: TikTokPage; t: Timing }> = ({ page, t }) => {
  const frame = useCurrentFrame();
  const text = page.tokens.map((x) => x.text).join("").trim();
  const dur = t.end - t.start;
  const a = interpolate(frame, [0, t.fadeIn], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: t.swapIn ? Easing.linear : ease });
  const o = interpolate(frame, [dur - t.fadeOut, dur], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: t.swapOut ? Easing.linear : ease });
  // a little vertical travel makes the swap read as "next line", not as a flicker
  const rise = (t.swapIn ? (1 - a) * 6 : (1 - a) * 8) - (t.swapOut ? (1 - o) * 6 : 0);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: PAD_BOTTOM, paddingLeft: PAD_X, paddingRight: PAD_X }}>
      <div
        style={{
          fontFamily: body,
          fontWeight: 700,
          fontSize: fontFor(text),
          lineHeight: 1.2,
          textAlign: "center",
          color: colors.ink,
          textShadow: shadows.caption,
          opacity: a * o,
          translate: `0px ${rise}px`,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

/** Calm phrase subtitles from public/<src> (make_captions.py). A missing or broken file renders nothing instead of killing
 *  the render — doctor.py reports it, and a silent reel has no captions at all. No page outlives the parent sequence. */
export const Captions: React.FC<{ src: string }> = ({ src }) => {
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const { delayRender, continueRender } = useDelayRender();
  const [handle] = useState(() => delayRender("captions"));
  const { fps, durationInFrames } = useVideoConfig();

  const fetchCaptions = useCallback(async () => {
    try {
      const res = await fetch(staticFile(src));
      if (!res.ok) throw new Error(`${res.status} ${src}`);
      setCaptions((await res.json()) as Caption[]);
    } catch (e) {
      console.warn(`Captions: ${src} not loaded (${String(e)}) — rendering without captions`);
      setCaptions([]);
    }
    continueRender(handle);
  }, [continueRender, handle, src]);

  useEffect(() => {
    fetchCaptions();
  }, [fetchCaptions]);

  const pages = useMemo(() => {
    if (!captions) return [];
    return createTikTokStyleCaptions({ captions, combineTokensWithinMilliseconds: SWITCH_CAPTIONS_EVERY_MS }).pages;
  }, [captions]);

  const timings = useMemo<Timing[]>(() => {
    const toF = (ms: number) => Math.round((ms / 1000) * fps);
    const ends = pages.map((p) => p.tokens[p.tokens.length - 1]?.toMs ?? p.startMs);
    const bridged = pages.map((p, i) => (pages[i + 1] ? pages[i + 1].startMs - ends[i] < BRIDGE_MS : false));
    return pages.map((p, i) => {
      const swapIn = i > 0 && bridged[i - 1];
      const swapOut = bridged[i];
      const start = toF(p.startMs);
      const want = swapOut ? toF(pages[i + 1].startMs) + SWAP : toF(ends[i] + HOLD_AFTER_MS);
      // never past the parent sequence: a page cut off by the sequence end vanished at full opacity
      const end = Math.min(Math.max(want, start + 2), durationInFrames);
      const cut = end < want;
      return { start, end, fadeIn: swapIn ? SWAP : FADE, fadeOut: swapOut && !cut ? SWAP : FADE, swapIn, swapOut: swapOut && !cut };
    });
  }, [pages, fps, durationInFrames]);

  if (!captions) return null;

  return (
    <AbsoluteFill>
      {pages.map((page, index) => {
        const t = timings[index];
        if (t.end - t.start < 2) return null; // starts after the sequence end
        return (
          <Sequence key={index} from={t.start} durationInFrames={t.end - t.start} name={`cap ${index}`}>
            <CaptionPage page={page} t={t} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
