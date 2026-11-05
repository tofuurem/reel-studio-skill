# Examples (not part of the template — copy, then adapt)

Generators (copy to `work/gen_reel.py`; all use scripts/reelgen.py and only template components):
- `gen_reel.example.py` — camera only: title, chapters, a card in the free band, a widened cutaway, chips, a stamp.
- `gen_reel_split.example.py` — camera + voiceover takes: SplitStage + SideList / SideBubble, a Board over the carriers.
- `gen_reel_voiceover.example.py` — voiceover only: crossfading boards (tiles, ChatCard, Ledger), a closing Plate.
- `gen_reel_silent.example.py` — images only, no voice: pictures on the bed's beat grid, no captions.

Scenes (copy to `reel/src/scenes/`):
- `TripoStory.example.tsx` — one object carries a chapter (Motion kit: camera, ScanSwap, PriceTag, FactCard).
- `Covers.example.tsx` — copy to `reel/src/Covers.tsx`: CoverFrame covers of a series + an ArtCover on a generated plate.

Contrast of the palettes (WCAG ratio; small text needs ≥ 4.5, display text ≥ 3):

| pair | warm | nightPool |
|---|---|---|
| ink on bg | 19.5 | 16.5 |
| ink on panel | 19.3 | 17.1 |
| onAccent on accent | 7.4 | 9.8 |
| ink (white) on accent — not used any more | 2.6 | 1.7 |
| onAccent2 on accent2 | 13.5 | 10.6 |
| onPlate on okPlate / badPlate | 5.1 / 5.9 | 5.1 / 5.9 |
| ok / bad on panel | 12.1 / 8.4 | 11.8 / 8.1 |
| accent on panel | 7.5 | 10.1 |
| paperAccent on paper (display numbers only) | 4.4 | 4.7 |
