import { useId } from "react";

/**
 * Motion blur along one axis (a whip, a fast slide): an inline SVG filter with stdDeviation "x y". CSS blur() smears in
 * every direction and reads as a cheap defocus; a real whip pan only streaks along the move.
 * Usage: const b = useDirBlur(px, 0); <div style={{ filter: b.filter }}>…</div>{b.defs}
 * px = 0 → no filter at all (the element is not re-rasterised on still frames).
 */
export const useDirBlur = (x: number, y = 0) => {
  const id = "db" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const on = x > 0.3 || y > 0.3;
  return {
    filter: on ? `url(#${id})` : undefined,
    defs: on ? (
      <svg width={0} height={0} style={{ position: "absolute" }} aria-hidden>
        <filter id={id} x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
          <feGaussianBlur stdDeviation={`${x.toFixed(2)} ${y.toFixed(2)}`} />
        </filter>
      </svg>
    ) : null,
  };
};
