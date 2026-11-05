import React from "react";
import { ArtCover, Badge, CoverFrame, Cut, FloorShadow } from "./Cover";
import { colors } from "./theme";
import { Mark } from "./ui/Mark";

/* EXAMPLE: lofiroom devlog covers — copy to reel/src/Covers.tsx and register each as a <Still> (commented block in Root.tsx).
   Render: scripts/cover.sh <project> <covers>/public <abs out prefix> Cover1 Cover2 … (a check sheet with both crops comes out too).
   The background pair is per episode on purpose (one colour per episode, the grid reads as a set); everything else is tokens. */
type P = { guides?: boolean };

/** 01 · the idea — the concept room floating in the night. */
export const Cover1: React.FC<P> = ({ guides }) => (
  <CoverFrame bg={["#2B3063", "#0D0E20"]} glow="rgba(255,176,96,0.5)" glowAt="50% 54%" number="01" word="ИДЕЯ" wordSize={170} wordTop={1235} guides={guides}>
    <Cut src="covers/room_night.png" x={20} y={400} h={1040} />
  </CoverFrame>
);

/** 02 · the character — the first attempt looming behind the girl we wanted. */
export const Cover2: React.FC<P> = ({ guides }) => (
  <CoverFrame bg={["#FF9469", "#CF4F2C"]} glow="rgba(255,236,200,0.55)" glowAt="62% 52%" number="02" numberColor="rgba(255,255,255,0.24)" word="ПЕРСОНАЖ" wordSize={108} wordTop={1310} plate={colors.ink} plateInk={colors.bg} guides={guides}>
    <Cut src="covers/fail_face.png" x={-110} y={470} h={800} rotate={-7} filter="saturate(0.55) brightness(0.82)" />
    <Badge x={380} y={500} bg={colors.badPlate}>
      <Mark ok={false} size={84} color={colors.onPlate} weight={3.6} />
    </Badge>
    <Cut src="covers/girl_codex.png" x={540} y={470} h={900} />
    <Badge x={880} y={520} bg={colors.okPlate} size={130}>
      <Mark size={72} color={colors.onPlate} weight={3.6} />
    </Badge>
  </CoverFrame>
);

/** 03 · animations — me and her in the same pose. */
export const Cover3: React.FC<P> = ({ guides }) => (
  <CoverFrame bg={["#44966E", "#12301F"]} glow="rgba(255,232,170,0.42)" glowAt="50% 50%" number="03" numberSide="left" brandSide="right" word="АНИМАЦИИ" wordSize={108} wordTop={1310} guides={guides}>
    <FloorShadow x={70} y={1266} w={440} />
    <FloorShadow x={600} y={1266} w={420} />
    <Cut src="covers/me_wave.png" x={120} y={400} h={900} />
    <Cut src="covers/girl_wave.png" x={630} y={610} h={690} />
    <Badge x={462} y={820} bg={colors.accent} size={140}>→</Badge>
  </CoverFrame>
);

/** Cover on a generated plate: covers/gen/hero.png made by scripts/codex_image.sh from a real frame, 9:16, no text. */
export const CoverArt: React.FC<P> = ({ guides }) => (
  <ArtCover src="covers/gen/hero.png" word="ВЫВОДЫ" wordTop={1290} brand="КАНАЛ" plate={colors.accent2} shadeColor="6,20,23" guides={guides} />
);
