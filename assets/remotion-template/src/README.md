# Reel template (copied into every project by scripts/scaffold.sh)

Generated, do not edit by hand: `Timeline.tsx` (scripts/gen_timeline.py; the file here is a stub so a fresh scaffold
compiles), `Reel.tsx` (work/gen_reel.py on top of scripts/reelgen.py), `numbers.ts` (scripts/numbers_gen.py from
references/craft/numbers.json).

Conventions
- Every cue is a LOCAL frame of the enclosing `<Sequence>`: `at` = appears, `until` = starts leaving (8-frame fade),
  `<part>At` = a sub-element lands (`subAt`, `noteAt`, `swapAt`, `pillAt`); list items are `{ at, text }`.
- `x`/`y` = left/top edge; a centred element takes `cx`/`cy` (RollPill, MissingMark).
- Colours only from `theme.ts` (`colors` = the palette picked from `palettes.ts`, `inkOn(bg)` for text on a fill,
  `alpha(hex, a)` for tints), shadows only from `shadows` (text / caption / panel / pill / cover), numbers from `N`.
- No backdrop-filter, no mix-blend-mode, no glows, no tilt on landing elements (Stamp is the one rotated element),
  no emoji in UI text (use `<Mark>` for ✓/✕), no text under N.minTextPx (28 px).
- Media Sequences carry `premountFor` (reelgen.seq(..., premount=True) does it); Win keeps its video mounted before `at`.

Kit
- `Clip`, `Stage` — talking head (punch around N.punchCenterY) and the shrink-to-top-window.
- `scenes/Board.tsx` — Board, Win, Pill, CheckRow, DownArrow, Tile, BigFact, MissingMark, SplitStage, SideList,
  SideReview, SideBubble, ChannelPill, Ledger, Plate.
- `scenes/Cards.tsx` — ImageCard, VideoCard (over the talking head, in the face-free band).
- `scenes/TitleCard.tsx`, `scenes/BRoll.tsx`, `scenes/EndCard.tsx`, `scenes/Finale.tsx` (typographic epilogue).
- `scenes/Motion.tsx` — advanced: Camera/Layer parallax, Figure, ScanSwap, RollPill, PriceTag, FactCard, Backdrop, GridFloor.
- `ui/` — Card, ChapterTag, Chapter (flash + tag + whoosh), Flash, Fade (FadeFromBlack/FadeToBlack), Stamp, Mark,
  ChipRow/ChipBand, Chat (Bubble, ChatCard, TypingDots, Strike), Sfx/MusicBed, anim (inAt, outBefore, envelope, sp, steps…).
- `Cover.tsx` — CoverFrame, ArtCover, Cut, Badge, FloorShadow (stills; register them in Root.tsx).
