import { useId } from "react";

/**
 * A short RGB split on a hit (action reels): red shifts one way, blue the other, green stays — an inline SVG filter, so it
 * works on any layer (OffthreadVideo pieces too) without blend modes. Budget: rgbMax per reel, rgbFrames long, on a hit
 * only (references/craft/transitions.md) — a constant or repeated split reads as a broken screen.
 * Usage: const rgb = useRgbSplit(px); <div style={{ filter: rgb.filter }}>…</div>{rgb.defs}   px = 0 → no filter.
 */
export const useRgbSplit = (px: number, angleDeg = 0) => {
  const id = "rgb" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const on = px > 0.3;
  const dx = Math.cos((angleDeg * Math.PI) / 180) * px, dy = Math.sin((angleDeg * Math.PI) / 180) * px;
  return {
    filter: on ? `url(#${id})` : undefined,
    defs: on ? (
      <svg width={0} height={0} style={{ position: "absolute" }} aria-hidden>
        <filter id={id} x="-5%" y="-5%" width="110%" height="110%" colorInterpolationFilters="sRGB">
          <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
          <feOffset in="r" dx={dx.toFixed(2)} dy={dy.toFixed(2)} result="r2" />
          <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
          <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="b" />
          <feOffset in="b" dx={(-dx).toFixed(2)} dy={(-dy).toFixed(2)} result="b2" />
          <feComposite in="r2" in2="g" operator="arithmetic" k1="0" k2="1" k3="1" k4="0" result="rg" />
          <feComposite in="rg" in2="b2" operator="arithmetic" k1="0" k2="1" k3="1" k4="0" />
        </filter>
      </svg>
    ) : null,
  };
};
