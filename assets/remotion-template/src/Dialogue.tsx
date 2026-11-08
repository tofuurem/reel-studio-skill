import React from "react";
import { Audio } from "@remotion/media";
import { staticFile } from "remotion";
import { DIALOGUE } from "./dialogueSrc";

/** The whole dialogue as ONE processed stem (scripts/dialogue.py → public/audio/dialogue.wav): every cut crossfaded from
 *  source handles, room tone in the gaps, one EQ/compressor/de-esser chain. Placed at frame 0 of the reel by reelgen.write;
 *  Clip mutes the proxies' own sound while DIALOGUE is set. Renders as PCM (render.sh) — the AAC encode happens once, last. */
export const Dialogue: React.FC = () => (DIALOGUE ? <Audio src={staticFile(DIALOGUE)} /> : null);
