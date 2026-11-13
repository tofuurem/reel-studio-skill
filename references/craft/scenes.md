# Scenes → Reel.tsx

Read `storyboard.md` (what goes where) and, before chapter scenes, `motion-design.md` (how it moves). Then write `work/gen_reel.py` — the only place where graphics are placed. It runs on top of `scripts/reelgen.py` and writes `reel/src/Reel.tsx`; a re-cut is a re-run, nothing generated is edited by hand.

## The generator
Start from an example in `assets/examples/` (copy to `work/gen_reel.py`):

| material | example |
|---|---|
| camera only (raw takes or a CapCut draft) | `gen_reel.example.py` |
| camera + voiceover takes | `gen_reel_split.example.py` |
| voiceover only (boards over carriers) | `gen_reel_voiceover.example.py` |
| images only, no voice (beat grid) | `gen_reel_silent.example.py` |

```python
import os, sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts"))
import reelgen as rg; from reelgen import N, js, tag
R = rg.Project(".")                               # work/tl_words.txt, cutlist.json, face_zones.json, proxy_offsets.json, beats.json
a = R.fw("референс"); b = R.fw("короче", after=a)  # words → frames; a missing word stops with the nearest spellings
band = R.free_bottom(a, b)                        # (top, bottom) free of the face for these frames, within y 300–1350
body = [R.chapter(R.seg(1), "01", "Идея"),
        rg.seq(a, b, tag("ImageCard", src="screens/ref.png", ratio=16/9, top=band[0], maxH=band[1] - band[0]), "card · reference"),
        R.cutaway("crec_day_v", 31.0, a, b, "broll · prototype"), R.music_bed()]
R.write(body)                                     # auto-imports, SPEECH_END, REEL_FRAMES, Captions, EndCard
```
Then `python3 -I work/gen_reel.py && (cd reel && npx tsc --noEmit -p .)`.

- Anchors: `R.fw(word, after, nth, before)`, `R.fw_any([...])`, `R.words_between(a, b)`; words are normalised (case, ё, punctuation) and `tl_words.py` already applied `brands.json` and the caption patches, so anchor on the corrected spelling.
- Structure: `R.seg(i)` / `R.seg_end(i)` (timeline segments), `R.cuts`, `R.END`, `R.silent`, `R.beats(every, start, end)` for silent reels.
- Layers: `R.cutaway(clip_id, src_sec, a, b, name)` and `R.board(a, b, children, name)` are widened around the nearest timeline cut by `coverBefore` / `coverAfter` (`numbers.md`) and log what they widened; `R.chapter(cut, n, title)`; `R.sfx`, `R.sfx_many`, `R.ticks`; `R.music_bed(speech_start=…, speech_end=…, pauses=[(a, b)], under=…)` (keywords: the first positional argument is the file); `R.capcut_voiceovers()` → the draft's own voiceovers at their places.
- Placement on a 16:9 canvas: `R.free_side(a, b)` → `(side, x0, x1)` from the 16:9 rows of `work/face_zones.json` (`layout-rules.md`); a horizontal reel has room beside the face, not above it.
- Placement over a talking head: `R.free_top(a, b)` / `R.free_bottom(a, b)` read `work/face_zones.json` (already in screen coordinates, punch zoom included) and return a band inside y 300–1350; give cards both ends (`top=band[0], maxH=band[1] - band[0]`) — a full-width 16:10 screenshot is 600 px tall and ran over the captions in the dry run.
- Cues inside a scene are LOCAL frames of its Sequence: `R.L(f, start)`, or `R.board(..., children=lambda start: [...])`.
- A segment map comment + `assert len(R.segs) == N` at the top catches a re-cut that moved the segments.

## The kit (`assets/remotion-template/src`, conventions in its `README.md`)
- **Over a talking head:** `Card` (`at`, `top` default 300), `ImageCard` / `VideoCard` (`scenes/Cards.tsx`), `TitleCard`, `Stamp` (the one rotated element, ≤ 92 px), `ChipRow` / `ChipBand`, `Chapter` (flash + `ChapterTag` + whoosh), `BRoll` (full-frame cutaway, via `R.cutaway`), `Stage` (head shrinks into a top window), `SplitStage` + `SideList` / `SideReview` / `SideBubble` (close-ups: head left, notes right).
- **Voiceover stretches (no head):** `Board` (via `R.board`) with `Win` (image or muted video window), `Pill`, `CheckRow`, `Mark` (✓/✕ as SVG), `Tile`, `BigFact`, `DownArrow`, `MissingMark` (`cx`/`cy`), `Ledger`, `ChatCard` / `Bubble` / `TypingDots` / `Strike` (`ui/Chat.tsx`), full-bleed `Plate`. Content band y 300–1350.
- **Motion kit (advanced, `scenes/Motion.tsx`):** `Camera` / `Layer` parallax, `Figure`, `ScanSwap`, `RollPill` (`cx`), `PriceTag`, `FactCard`, `Backdrop`, `GridFloor` — one object carrying a chapter (`assets/examples/TripoStory.example.tsx`).
- **Text behind a person:** `R.cutaway(cid, src_sec, a, b, name, behind={"title": "ХЭЛЛОУИН", "kicker": "31.10", "at": 6})` → person_matte.py cuts the people out of the 2K proxy for exactly those frames (`reel/public/mattes/`), `BRoll` draws footage → title → cutout → kicker (`scenes/BehindTitle.tsx`). The cutout is BiRefNet by default (`"mode": "auto"`: the person with headphones, glasses, caps, props; Apple Vision `"person"` drops over-ear headphones). x, y and size come from the matte (`common.title_place`); pass `"y"` (and `"x"`, `"scale"`) to place it by hand. A title spanning several shots (a hook over jump cuts): `title_place([(mask_json, (punch, 0.5, cy)), …], title, canvas, kicker=True)` for one place on the punched-in frames — `cy` from the project's `numbers.ts`, not `N` (a 16:9 project overrides `punchCenterY`). Look at the hook frames zoomed at the head before rendering.
- **Blocks (`blocks/`, `blocks.md`):** `CodeDiff`, `CodeTyping`, `RepoCard` / `RepoList` (GitHub-style cards with a star count-up), `Notify` / `NotifyStack`, `LowerThird`, `BeforeAfter` — ready pieces for devlog beats, ported from HyperFrames' catalogue (Apache-2.0) to frame-driven Remotion; they take `at` / `until` and `y` from `R.free_top` / `R.free_bottom` like any card.
- **Who is who (event vlogs):** `NameTag` (`scenes/NameTag.tsx`) — a name pill riding on the person's head the first time each one appears (Halloween v5: «кто это именно, хотя бы первый раз»). `work/venv/bin/python -I $S/name_tracks.py <project>` tracks the head (Apple Vision, the face nearest a hint, smoothed; `keys` for a helmet) from `work/name_jobs.json` → `work/names/<id>.json` + `work/stills/names/<id>.jpg`; `place` above / below / left / right (a head near the top edge: beside it). In the Sequence pass the segment's `punch` / `drift` / `hold` and `at` like `BlurPatch`, so the pill stays on the head through the punch zoom.
- **Comic lettering:** `ComicSfx` (sound words with a pop, a decaying laugh-shake, a jagged halftone burst) and `ComicBehind` (the same words BEHIND a person: footage copy → words → `person_matte.py` cutout, with the clip's punch / drift) in `scenes/Comic.tsx`, colours `comic` in `theme.ts`. For a hero who is a cartoon (a banana costume): a laugh, a shout — two or three per vlog, each on a real sound (earshot finds it: `earshot find <clip> "a man laughing" --top 5`).
- **Action reel:** not this generator — `scripts/actiongen.py` + the template's `Action.tsx` (`inputs/action-reel.md`).
- **Endings and audio:** `EndCard` (channel pill + fade to black, any tail length), `FadeFromBlack` / `FadeToBlack` (`ui/Fade.tsx`), `Finale` (typographic epilogue), `MusicBed`, `Sfx` (`tick | pop | done | whoosh | softwhoosh | hit | shutter | rewind | riser | beep | powerdown` from `make_sfx.sh`, levels from `N`; `R.sfx` cycles the variants whoosh2/3, softwhoosh2/3, pop2/3, hit2/3).
- Conventions: `at` appears, `until` starts leaving, `<part>At` for sub-elements, list items `{at, text}`; `x`/`y` left/top, `cx`/`cy` centre; colours from `theme.ts` (`colors`, `inkOn(bg)`, `alpha`), shadows from `shadows`, numbers from `N`. `python3 -I $S/lint_reel.py <project>` checks the rules (no backdrop-filter / blend modes / glows / emoji / tiny text / stray hex colours).
- **Palette and brand:** `theme.ts` picks a preset from `palettes.ts` (`warm` = lofiroom, `nightPool` = birthday) and holds `brand` (channel, series). A new video or series with its own look gets a new preset in `palettes.ts`, not hand-edited colours in 17 files; text on accent plates is dark (`onAccent`), white on coral was 2.6:1.
- Project-specific scenes go to `reel/src/scenes/<Topic>.tsx`; `R.write` finds them by their `export const`.

## Placing other material
- Proxies are named by `clipid.py`: `footage/c<NNNN>.mp4` for `DJI_…_NNNN_D.MP4`, `footage/c<ascii basename>.mp4` for anything else (`work/broll/rec_x.mov` → `footage/crec_x.mp4`).
- A CapCut draft's voiceovers and overlay inserts are placed at the frames `draft_summary.md` lists (`inputs/capcut-draft.md`).
- Covers are `<Still>`s registered in `Root.tsx` (commented block there; `covers.md`).
- If the speech ends before the story does, write the missing lines (`inputs/voiceover.md`) or build a typographic epilogue (`Finale`).
