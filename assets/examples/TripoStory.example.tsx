import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { colors } from "../theme";
import { Pill } from "./Board";
import { Backdrop, Camera, FactCard, Figure, GridFloor, Layer, PriceTag, RollPill, ScanSwap, countUp, fmt, sp, steps } from "./Motion";

/**
 * EXAMPLE (lofiroom ep2, chapter 03 «Tripo») — copy into reel/src/scenes/ and adapt. One continuous scene instead of
 * two boards: picture → scan → 3D model (same box, the model is born from the picture) → price tag counts up →
 * the same model slides aside for the comparison with Claude's v2 → camera leans in and the problems are shown ON the model.
 * All cues are LOCAL frames of the scene's <Sequence> (reelgen: `c = {k: R.fw(...) - start}`), like every component.
 */
export type TripoStoryCues = {
  brand: number; scanFrom: number; scanTo: number; swap: number;
  priceMove: number; price: number; credits: number; priceOut: number;
  compare: number; v2In: number; better: number; v2Out: number;
  tris: number; onePiece: number; chair: number; end: number;
};

export const TripoStory: React.FC<{ c: TripoStoryCues }> = ({ c }) => {
  const g = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // board fade in/out (it replaces cutaways that faded the same way)
  const fade = interpolate(g, [0, 12, durationInFrames - 12, durationInFrames - 1], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // hero box (Tripo model, born from the picture): centre → left for the price → right for the comparison → left for the inspection
  const W = 460, H = 860, Y = 380;
  const heroX = steps(g, fps, 310, [[c.priceMove, 150], [c.compare, 560], [c.v2Out + 4, 150]], { damping: 16, mass: 1.3 });
  const v2X = steps(g, fps, -500, [[c.v2In, 70], [c.v2Out, -520]], { damping: 17, mass: 1.2 });
  // camera: slow lean-in while the scan runs, back out for the price, lean in again for the inspection
  const cam = {
    x: steps(g, fps, 0, [[c.scanFrom, 0], [c.v2Out + 6, 10]], { damping: 30, mass: 3 }),
    y: steps(g, fps, 0, [[c.scanFrom, -18], [c.priceMove, 0], [c.v2Out + 6, -10]], { damping: 30, mass: 3 }),
    s: steps(g, fps, 1, [[c.brand, 1.03], [c.scanFrom, 1.08], [c.priceMove, 1.0], [c.v2Out + 6, 1.13]], { damping: 30, mass: 3 }),
    r: steps(g, fps, 0, [[c.scanFrom, -0.6], [c.priceMove, 0.4], [c.v2Out + 6, -0.4]], { damping: 30, mass: 3 }),
  };
  const better = sp(g, fps, c.better, { damping: 12 }) * (1 - sp(g, fps, c.v2Out, { damping: 20 }));
  const mesh = interpolate(g, [c.tris, c.tris + 10, c.onePiece - 4, c.onePiece + 6], [0, 0.85, 0.85, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const outline = interpolate(g, [c.onePiece, c.onePiece + 8, c.chair - 6, c.chair + 6], [0, 1, 1, 0.35], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const labelsA = 1 - sp(g, fps, c.priceMove - 6, { damping: 20 });
  const labelsB = sp(g, fps, c.v2In + 6, { damping: 16 }) * (1 - sp(g, fps, c.v2Out, { damping: 20 }));
  const tris = countUp(g, c.tris, c.tris + 26, 0, 1470000);

  return (
    <AbsoluteFill style={{ opacity: fade }}>
      <Camera cam={cam}>
        <Layer depth={0.35}>
          <Backdrop glowX={heroX + W / 2} glowY={900} />
        </Layer>
        <Layer depth={0.8}>
          <GridFloor top={Y + H - 26} />
        </Layer>
        <Layer depth={1}>
          {/* Claude's v2 for the comparison: dimmer, slightly behind */}
          <Figure src="screens/v2_front_cut.png" x={v2X} y={Y + 60} w={400} h={H - 60} dim={0.35} />
          {/* the picture becomes the model in the same box */}
          <ScanSwap a="screens/codex_girl_cut.png" b="screens/tripo_v1_front_cut.png" x={heroX} y={Y} w={W} h={H} from={c.scanFrom} to={c.scanTo} outline={outline} mesh={mesh} />
        </Layer>
        <Layer depth={1.15}>
          <div style={{ opacity: labelsA }}>
            <RollPill a="картинка" b="3D-модель" swapAt={c.swap} cx={heroX + W / 2} y={Y + H + 22} at={10} />
          </div>
          <div style={{ opacity: labelsB }}>
            <Pill text="Claude в Blender" x={v2X + 70} y={Y + H + 22} size={30} />
            <Pill text="Tripo" x={heroX + 160} y={Y + H + 22} size={30} bg={colors.accent} />
          </div>
          <div style={{ position: "absolute", left: heroX + 70, top: Y - 40, opacity: Math.min(1, better * 1.3), scale: String(0.6 + 0.4 * better), transformOrigin: "0% 50%" }}>
            <Pill text="сильно лучше" x={0} y={0} size={34} bg={colors.okPlate} />
          </div>
        </Layer>
      </Camera>

      {/* screen-space overlay: brand, price, facts (they do not ride the camera) */}
      {/* right edge ≤ 990: the right 90 px strip belongs to the Instagram buttons */}
      <Pill text="Tripo" x={64} y={300} at={c.brand} until={c.v2In} bg={colors.ink} size={52} font="display" />
      <PriceTag x={620} y={430} at={c.price} value={55} sub="за 5000 кредитов" subAt={c.credits} until={c.priceOut} />
      <FactCard x={600} y={440} w={390} at={c.tris} title={fmt(tris)} sub="треугольников" />
      <FactCard x={590} y={620} w={400} at={c.onePiece} title="одним куском" sub="наушники, худи и волосы не снимаются" />
      <FactCard x={600} y={850} w={390} at={c.chair} title="рост 1,30 м" sub="на стул не садится" />
    </AbsoluteFill>
  );
};
