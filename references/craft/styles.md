# Styles: how a reel looks (pick one per reel, try it on a stretch)

A style is a set of rules laid over the same pipeline: which inserts carry the story, the typography, the palette, how cards
and seams behave, which sources it needs. It is **not** the tempo — calm vs action (`motion-design.md` «Two tempos») is
decided by the material and the entry (`SKILL.md` §1); a style sits on top of either.

No single look fits every video: offer styles and try them while building, do not default to the last one used. A drawn
scheme never replaces a real thing that exists (a game, an app, a place) — show the real thing, credited (style 3).

## The step: offer, try, decide

1. **When**: once the cut or the plan is approved and before `work/gen_reel.py` is written (`storyboard.md` step 0). For
   "same as last time" the previous project's style is the default (its `NOTES.md` / `work/intake.json`).
2. **Offer 2–3 styles that fit this material** — one line each: what the viewer would see, and what it costs (comic: a few
   generated plates; real footage: clips the user has, or someone else's after a yes). The default is **calm**; say so.
   Do not offer a style the material cannot feed (no real footage of the thing → no «real footage» for that beat).
3. **Unsure → A/B on one beat, not a full render.** Take the beat where the styles differ most (the hook or the key claim,
   4–10 s), build it in each style with a switch at the top of `gen_reel.py` (`STYLE = "calm"`), and render only that
   stretch: `$S/render_part.sh` per variant → `work/venv/bin/python -I $S/ab_video.py out/ab/style.mp4 v1.mp4 v2.mp4
   --names "calm,comic"` → "1 or 2?" (`ab.md`; version 1 is the default or what they already saw).
4. **Write it down**: `work/intake.json` `"style": {"main": "calm", "accents": ["comic"]}` and a line in `NOTES.md`; then
   build the whole reel in it.

- **One main style per reel**; another style may give accents within its budget (a calm reel with one comic panel on the
  punchline; a real-footage reel with a comic cold open).
- **Never add comic to a montage the user already approved** unless they ask for it. A new style on an approved cut is a
  new A/B, not a silent change.
- Every style keeps the non-negotiables (`SKILL.md` §4): the face stays free, captions calm, the seam budget, no glows /
  blend modes, facts only from the transcript.

| style | carries the story | typography | palette | seams | needs |
|---|---|---|---|---|---|
| calm (default) | own cutaways, cards, chips | phrase captions, Unbounded + Montserrat | a `palettes.ts` preset | dissolve, rare effect | own footage, user screenshots |
| comic | drawn panels with the speaker's own lines | balloons, narrator boxes, misprint titles | `comic` in `theme.ts` | hard page-cut on a full panel | generated plates from real frames |
| real footage | the real thing on screen | calm + small credits | calm | plain; the clip's own motion | own clips → user's → others' with a yes |
| motion board | one object changing state | board type, count-ups | a preset per video | hand-offs | screenshots, renders, numbers |
| action (to a track) | shots on the beat | 2–4 punchlines, title behind a person | footage colour | hard cuts, whips, hits | a track, lots of short shots |

## 1. Calm — the default

- **Inserts**: cutaways from the user's own b-roll on sentences about doing or waiting (`R.cutaway`); cards in the face-free
  band (`Card`, `ImageCard`, `VideoCard`); chips on spoken nouns; chapters; `Stamp` ≤ 2–3 per video; `Stage` / `SplitStage`
  on close-ups. What goes where: `storyboard.md`.
- **Typography**: calm phrase captions (`captions.md`), Unbounded for display, Montserrat for body (`fonts.ts`).
- **Palette**: one preset from `palettes.ts` per video or series (`warm`, `nightPool`, …), text on accents via `inkOn`.
- **Cards**: land flat with a spring, panel shadow from `shadows`, leave faster than they came (`motion-design.md` §4).
- **Seams**: the 7-frame dissolve; an effect seam only for a real change, within `transitions.md` §0.
- **Sources**: the user's footage and screenshots; ask for a missing screenshot by name.
- **Fits**: talking heads, devlogs, vlogs — anything where the speaker is the reel.

## 2. Comic (the «Spider-Verse» look)

The look of the generated covers (`covers.md` «Covers on generated art») moved inside the montage: a picture generated with
`$S/codex_image.sh` from a REAL frame, every word set in Remotion. Needs the Codex CLI (`deps.py` shows `codex (covers)`;
else `deps.py --install --with covers` — do not offer comic until it is there).

- **Inserts** (`scenes/ComicPanel.tsx`, placed with `R.comic_panel`; example `assets/examples/gen_reel_comic.example.py`):
  - **inset panel** over the talking head in the taller free band — a framed plate, tilted ≈ 1.5°, hard ink shadow;
  - **full panel** instead of a cutaway (`full=True`, widened around cuts like `R.cutaway`);
  - a **balloon** (`ComicBalloon`, `kind: "shout"` for a shout) — its tail may point at the speaker's mouth on the talking
    head: their own line as comic speech; a **narrator box** (`ComicBox`: «MEANWHILE…», «spoiler: it took ten days»);
    a **misprint title** (`Misprint`, sized to fit the width);
  - sound words (`ComicSfx`, `words=` on the panel) and words behind a person (`ComicBehind`, `scenes/Comic.tsx`) — each on
    a real sound.
  - A real clip can sit in a comic frame too (`src="footage/c0042.mp4"`, `trimBefore=R.trim(...)`) — the bridge to style 3.
- **Plates** (`reel/public/comic/<n>.png`, prompts and variants in `work/comic/`):
  - Reference = a real frame of this reel (`npx remotion still` or the QA stills): the person, the place, the object of the
    sentence — `codex_image.sh -o reel/public/comic -n p1 -r <frame.png> "<prompt>"`. When the sentence is about a game, an
    app, a place, draw it after real footage of it, never from imagination.
  - One style line shared by every plate of the reel (the same wording each time) so the panels read as one comic:
    «Spider-Verse comic panel: bold ink outlines, halftone shading, cyan/magenta print misregistration, flat saturated colours».
  - No text in the plate (image models garble lettering, Cyrillic worst of all); a calm area where the balloon will sit;
    natural head-to-body proportions when the user's face is in it (no bobble-head); the ratio of the slot (≈ 4:5 or 1:1
    inset, 9:16 full).
  - Generation takes about a minute per plate: make all plates of the reel in one background batch; show a numbered sheet
    of them before building, regenerate only what the user rejects.
- **Typography**: Unbounded 900 caps in balloons and titles, Montserrat 900 caps in boxes; the words are the speaker's own
  (from the transcript) or a short narrator line — never a new fact. A balloon must not repeat the caption on screen at the
  same moment: quote a line said just before or after, or use a box.
- **Palette**: `comic` in `theme.ts` — yellow fill, ink, paper, cyan / magenta misregistration, red pop. The calm palette
  stays for everything that is not a panel (captions, chapters).
- **Behaviour**: a panel slaps in (`comicPanelIn`: scale 0.86 → 1.03 → 1, the cyan and magenta frames converge), the plate
  pushes in slowly, the balloon pops a few frames later, the box slides in; everything leaves together in `comicPanelOut`.
  Length `comicPanelMinFrames`–`comicPanelMaxFrames`; ≤ `comicPanelsPerMin` per minute as the main style, 1–2 per reel as an
  accent (`STYLE BUDGET` from `R.write`). Sound: a `pop` on the panel, nothing on the balloon.
- **Seams**: a full panel enters on a hard page-cut and counts as an effect seam in the `transitions.md` budget; an inset
  panel does not.
- **Fits**: a funny story, self-irony, the punchline, what the speaker imagined or the camera missed. **Not** for proof,
  numbers, screenshots, or the thing being talked about when real footage of it exists — that is style 3.

## 3. Real footage

What the speaker talks about is shown as itself. Graphics only mark something ON the real picture.

- **Sources, in this order**:
  1. the user's own footage — when it lives on one of the video-library skill's drives (`SKILL.md` §1), search that drive's video map first (the
     drive's root `CLAUDE.md` names the search tool), then the inventory sheets;
  2. what the user can still make: a screenshot, a screen recording, a phone clip — ask for it by name;
  3. someone else's footage (gameplay, a product demo): only after the user's explicit yes for that use — and it needs the
     owner's permission or a licence that allows reuse; respect the platform's terms.
     `python3 -I $S/fetch.py <project> <url> --as footage --section 0:00-0:20` → `assets/video/<name>.mp4` (picture
     only) + `.source.json`, prints the licence and a `CREDIT:` line. Short pieces, the author credited on screen for as
     long as the picture is visible (`credit=` on `ImageCard` / `VideoCard` / `BRoll` / `ComicPanel`), a sources table in
     `NOTES.md` (title, author, link, licence, what was taken and where).
  4. graphics — only as an accent on top of the real picture (a detection box, a circle on the «!», a count-up chip), never
     a drawn scheme instead of a real thing that exists.
- **Inserts**: `VideoCard` / `ImageCard` with a `credit`, a full `BRoll` with a `credit`, the reaction cut on the spoken word
  (`motion-design.md` §5b), a slow camera push into the detail being spoken (a crop of the real frame), a marker drawn on the
  real picture on its word.
- **Typography, palette, seams**: as calm; the clip's own motion is the energy — no effect seams to "liven it up".
- **Fits**: devlogs about a game or an app, anything with a real object, place or result; proof beats in any style.

## 4. Motion board — one object carries the chapter

Already in the kit: `motion-design.md` §1–§5, `scenes/Motion.tsx`, `scenes/Board.tsx`,
`assets/examples/TripoStory.example.tsx`, the `blocks/` pieces.

- **Inserts**: full boards over voiceover stretches; one hero (a figure, a window, a number) changes state on each spoken
  beat instead of boards fading in and out; count-ups, `RollPill`, `PriceTag`, `FactCard`; `CodeDiff` / `RepoCard` for devlogs.
- **Typography**: board type and big numbers (`BigFact`, 132 px payoff counters); calm captions stay.
- **Palette**: its own preset in `palettes.ts` for the video (e.g. `nightPool`).
- **Seams**: hand-offs (the same object carries the cut), the vector law (`motion-design.md` §5a).
- **Needs**: screenshots, renders, numbers from the transcript; a scene card for every key beat (`motion-design.md` §2).
- **Fits**: voiceover over screens, explanations of a process, numbers. Not a replacement for real footage that exists.

## 5. Action (cut to a track)

Already a separate entry: `inputs/action-reel.md`, `scripts/actiongen.py`, `Action.tsx`, `motion-design.md` «Two tempos».
Hard cuts on the beat grid, silent whips on phrase starts, speed ramps into the moment, a hit + shake on the drop, 2–4
punchline captions, one title behind a person; no cards. It is a style and a tempo at once; the generator differs, so pick
it at intake (§1), not at the storyboard. A silent "cinematic lo-fi" reel (5–8 slow shots, one line of small lowercase
text, a shared film look) is the calm tempo, not this style.
