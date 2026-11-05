import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

/**
 * Local variable fonts from public/fonts (scaffold.sh copies them from ~/.cache/reel-studio/fonts, setup_env.sh downloads
 * them once): a render needs no network — Google Fonts at render time timed out offline. Each file covers weights 100–900,
 * Latin + Cyrillic. ✓ ✗ are in none of them and ✕ ▍ only in JetBrains Mono: the stacks fall back to JetBrains Mono, then
 * Apple Symbols; for check marks prefer <Mark> (ui/Mark.tsx), which does not depend on a font at all.
 */
const face = (family: string, file: string) => {
  void loadFont({ family, url: staticFile(`fonts/${file}`), weight: "100 900", style: "normal" });
};
face("Unbounded", "Unbounded.ttf");
face("Montserrat", "Montserrat.ttf");
face("JetBrains Mono", "JetBrainsMono.ttf");

const FALLBACK = `"JetBrains Mono", "Apple Symbols", sans-serif`;
export const display = `"Unbounded", ${FALLBACK}`;
export const body = `"Montserrat", ${FALLBACK}`;
export const mono = `"JetBrains Mono", "Apple Symbols", monospace`;
