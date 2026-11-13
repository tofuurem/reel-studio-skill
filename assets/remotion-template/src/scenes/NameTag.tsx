import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { body, display } from "../fonts";
import { N } from "../numbers";
import { colors, H, shadows } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** A face track (name_tracks.py): per tracker frame [cx, top, w, h] of the head, 0–1 of the source frame. */
export type FaceTrack = { fps: number; box: number[][]; below?: boolean; place?: "above" | "below" | "left" | "right" };

/**
 * «Кто это» (v5, 2026-11-09: the user wanted to know who is talking, at least the first time): a small name pill that
 * rides above the person's head — tracked by Apple Vision, smoothed — with a caret pointing at it. It sits inside the
 * Clip's own punch / drift (like BlurPatch) so it stays on the head, and is scaled back so its size does not breathe.
 * Pops in, holds, leaves faster; never over the face (above the hairline, or under the chin when the head is near the top).
 */
export const NameTag: React.FC<{ name: string; role?: string; track: FaceTrack; dur: number; at?: number; punch?: number; drift?: number; hold?: number }> = ({
  name, role, track, dur, at = 0, punch = 1, drift = 0, hold = 1,
}) => {
  const f = useCurrentFrame();
  const i = Math.min(track.box.length - 1, Math.max(0, Math.floor((f * track.fps) / 30)));
  const j = Math.min(track.box.length - 1, i + 1);
  const u = (f * track.fps) / 30 - Math.floor((f * track.fps) / 30);
  const a = track.box[i], b = track.box[j];
  const [cx, top, , h] = a.map((v, k) => v + (b[k] - v) * u);
  const scale = interpolate(f + at, [0, Math.max(1, hold)], [punch, punch + drift], { ...clamp, easing: Easing.linear });
  const pin = interpolate(f, [0, 9], [0, 1], { ...clamp, easing: Easing.out(Easing.back(1.8)) });
  const out = interpolate(f, [dur - 7, dur], [1, 0], clamp);
  const place = track.place ?? (track.below ? "below" : "above");
  // the face box from Vision starts at the brows: the hair adds ≈ 0.4 of its height above it
  const pos = place === "above" ? { x: cx, y: top - 0.42 * h - 0.012, tr: "-50% -100%", dir: "column" as const, rot: 0 }
    : place === "below" ? { x: cx, y: top + h + 0.02, tr: "-50% 0%", dir: "column-reverse" as const, rot: 180 }
    : place === "left" ? { x: cx - 0.5 * a[2] - 0.012, y: top + 0.4 * h, tr: "-100% -50%", dir: "row" as const, rot: -90 }
    : { x: cx + 0.5 * a[2] + 0.012, y: top + 0.4 * h, tr: "0% -50%", dir: "row-reverse" as const, rot: 90 };
  const origin = place === "above" ? "50% 100%" : place === "below" ? "50% 0%" : place === "left" ? "100% 50%" : "0% 50%";
  const lift = place === "above" ? -10 : place === "below" ? 10 : 0;
  return (
    <AbsoluteFill style={{ transformOrigin: `50% ${((N.punchCenterY / H) * 100).toFixed(2)}%`, scale: String(scale) }}>
      <div style={{ position: "absolute", left: `${pos.x * 100}%`, top: `${pos.y * 100}%`, translate: pos.tr, opacity: Math.min(1, pin * 1.4) * out }}>
        <div style={{ scale: String((0.7 + 0.3 * pin) / scale), transformOrigin: origin, display: "flex", flexDirection: pos.dir, alignItems: "center", translate: `0px ${(1 - out) * lift}px` }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "10px 24px 12px", borderRadius: 18, background: colors.panel, border: colors.panelBorder, boxShadow: shadows.pill }}>
            <div style={{ fontFamily: display, fontWeight: 800, fontSize: 40, lineHeight: 1.05, color: colors.ink }}>{name}</div>
            {role ? <div style={{ fontFamily: body, fontWeight: 700, fontSize: 28, lineHeight: 1.2, color: colors.accent, marginTop: 2 }}>{role}</div> : null}
          </div>
          <svg width={26} height={14} viewBox="0 0 26 14" style={{ rotate: `${pos.rot}deg`, margin: place === "left" || place === "right" ? "0 -6px" : "-1px 0" }}>
            <polygon points="0,0 26,0 13,14" fill={colors.panelSolid} />
          </svg>
        </div>
      </div>
    </AbsoluteFill>
  );
};
