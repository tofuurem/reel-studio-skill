# Layout and graphics

Traps when writing components and placing graphics. Safe areas, face bands, card bands and `R.free_*` are owned by `craft/layout-rules.md`; the crop of landscape footage by `sources-and-footage.md`.

- **Glyphs**: the fonts have no ✓ / ✗ → draw them (`Mark`); no emoji in UI text; any new font must have Cyrillic and be a local file in `reel/public/fonts` (a network font stalls offline renders).
- **Text off the canvas** → big display words fit ≈ 90 % of the width; a rotated stamp ≤ 92 px on 1080 (118 px overflowed).
- **`interpolate` with `fadeIn={0}` / `fadeOut={1}`** gets a non-monotonic input range → clamp in the component (`Math.max`, see `BRoll.tsx`).
- **Text on a coloured fill** → `inkOn(bg)` / `onAccent` from the palette, never white by habit (white on coral was 2.6:1).
- **Close-up selfie framing** leaves no band for cards → `SplitStage` (take in a left window, notes in the right column): column items ≥ 33 px, numbers ≈ 64 px. In a 16:9 video body text ≥ 32 px (28 px read as tiny on a phone).
- **A title «behind» the person painted over them** → every layer of the stack is an `AbsoluteFill` (`scenes/BehindTitle.tsx`); an in-flow layer loses to any absolutely positioned one whatever the JSX order. The head crosses the word, never its first or last letter: let `title_place` score it, mapping the matte through the zoom the viewer sees with the project's own `numbers.ts`.
- **Facts on screen** → re-check each against the files; when docs and files disagree, count the files.
