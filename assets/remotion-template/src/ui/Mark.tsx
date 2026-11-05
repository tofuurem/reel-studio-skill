import React from "react";
import { colors } from "../theme";

/** ✓ / ✕ drawn as SVG: Unbounded and Montserrat have no check mark, and a font fallback renders it in a random system face. */
export const Mark: React.FC<{ ok?: boolean; size?: number; color?: string; weight?: number }> = ({ ok = true, size = 34, color, weight = 3.2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0, display: "block" }}>
    <path d={ok ? "M4.5 12.5 L9.5 17.5 L19.5 6.5" : "M6.5 6.5 L17.5 17.5 M17.5 6.5 L6.5 17.5"} fill="none" stroke={color ?? (ok ? colors.ok : colors.bad)} strokeWidth={weight} strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
