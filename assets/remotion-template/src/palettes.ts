/**
 * Semantic colour tokens, one preset per series (pick it in theme.ts). Components never hard-code a colour: a board in a
 * new palette must not come out brown. Text on an accent plate uses onAccent / onAccent2 (dark): white on coral was 2.6:1.
 * Ratios (WCAG) are listed in assets/examples/README.md; keep small text ≥ 4.5:1 and display text ≥ 3:1.
 */
export type Palette = {
  bg: string; // reel background, carrier
  ink: string; // main text on dark
  muted: string; // secondary text on dark
  accent: string; // plates, numbers, marks
  accent2: string; // second accent (highlights, my chat bubbles)
  onAccent: string; // text on an accent plate
  onAccent2: string; // text on an accent2 plate
  panel: string; // cards and windows (translucent, solid enough — no backdrop-filter)
  panelSolid: string; // inside of image windows / tiles before the picture loads
  panelBorder: string; // hairline around panels
  chip: string; // pill / list-row fill on dark
  scrim: string; // dark veil over footage or pictures
  boardBg: string; // full-frame board background (gradient)
  stageGlow: string; // soft light behind a hero on a Motion backdrop (background light, not a UI glow)
  grid: string; // GridFloor lines
  ok: string; // ✓ marks and borders on dark
  bad: string; // ✕ marks and borders on dark
  okPlate: string; // filled "yes" plate (white text)
  badPlate: string; // filled "no" plate (white text)
  onPlate: string; // text on ok/bad plates
  paper: string; // receipts, price tags
  paperInk: string;
  paperAccent: string; // the number on paper
  flash: string; // chapter flash light
  claude: string; // brand dot for Claude quotes
  black: string;
};

export const palettes = {
  /** lofiroom devlog: warm night room, coral + amber. */
  warm: {
    bg: "#0E0C0B",
    ink: "#FFFFFF",
    muted: "rgba(255,255,255,0.72)",
    accent: "#FF7A59",
    accent2: "#F6D59A",
    onAccent: "#140F0D",
    onAccent2: "#140F0D",
    panel: "rgba(16,14,13,0.92)",
    panelSolid: "#1A1715",
    panelBorder: "1.5px solid rgba(255,255,255,0.08)",
    chip: "rgba(255,255,255,0.10)",
    scrim: "rgba(14,12,11,0.55)",
    boardBg: "linear-gradient(180deg, #1C1714 0%, #100E0D 62%, #0E0C0B 100%)",
    stageGlow: "rgba(255,170,110,0.28)",
    grid: "rgba(255,190,140,0.22)",
    ok: "#7BE38B",
    bad: "#FF8A80",
    okPlate: "#2F7D4A",
    badPlate: "#B5392B",
    onPlate: "#FFFFFF",
    paper: "#F6EFE4",
    paperInk: "#1B1613",
    paperAccent: "#C2452A",
    flash: "#FFE9C7",
    claude: "#D97757",
    black: "#000000",
  },
  /** «Ночной бассейн» (birthday reel): pool water at night, aqua light + gold villa lamps. */
  nightPool: {
    bg: "#0B1A20",
    ink: "#F4F7F7",
    muted: "rgba(244,247,247,0.7)",
    accent: "#5BD1D7",
    accent2: "#F2C14E",
    onAccent: "#0B1A20",
    onAccent2: "#0B1A20",
    panel: "rgba(8,22,28,0.92)",
    panelSolid: "#061417",
    panelBorder: "1.5px solid rgba(91,209,215,0.22)",
    chip: "rgba(91,209,215,0.10)",
    scrim: "rgba(8,22,28,0.55)",
    boardBg: "linear-gradient(180deg, #123F48 0%, #0A2228 62%, #061417 100%)",
    stageGlow: "rgba(242,193,78,0.22)",
    grid: "rgba(91,209,215,0.2)",
    ok: "#7BE3B0",
    bad: "#FF8A80",
    okPlate: "#2F7D4A",
    badPlate: "#B5392B",
    onPlate: "#FFFFFF",
    paper: "#F4F7F7",
    paperInk: "#0B1A20",
    paperAccent: "#C2452A",
    flash: "#DDF6F7",
    claude: "#D97757",
    black: "#000000",
  },
} satisfies Record<string, Palette>;
