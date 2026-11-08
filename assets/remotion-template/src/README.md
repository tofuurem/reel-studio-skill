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
- `ui/Seam.tsx` — the seams between timeline clips (push / blur / leak / wipe / bodywipe / match / cut; `Clip` reads them, `gen_timeline.py` writes them, `references/craft/transitions.md`); `ui/RgbSplit.tsx` — the short RGB split of an action accent (SVG filter, no blend modes). Rare by design: the seam budget.
- `Cover.tsx` — CoverFrame, ArtCover, Cut, Badge, FloorShadow (stills; register them in Root.tsx).

Blocks (`blocks/`, ready-made devlog beats; when and how: references/craft/blocks.md; preview: the `BlocksDemo` composition)
- `CodeDiff` (removed lines strike and collapse, added lines open up), `CodeTyping` (typed with a caret), `RepoCard` /
  `RepoList` (repository cards, stars count up), `Notify` / `NotifyStack` (the newest pushes the others down), `LowerThird`
  (`mask` / `bar`), `BeforeAfter` (wipe between two images or two JSX panels).
- Same cue names as above; `until` defaults to the last 8 frames of the Sequence; layout in 1080-wide px (Reel2K scales).
  Shared helpers (`blockLife`, `codeTokens`, `CodePanel`) live in `blocks/shared.tsx`.
