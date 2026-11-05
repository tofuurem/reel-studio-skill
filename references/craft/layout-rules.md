# Layout rules for 1080x1920 reels (scale everything ×4/3 for 2K; the Reel2K comp does this)

A **16:9 canvas** (`"canvas": "16:9"` in intake.json — long vlogs): 1920×1080 layout, 2560×1440 render; nothing is cropped
(camera clips fill the frame), people_zones has nothing to do, the Instagram safe zones below do not apply — keep text
inside a 5 % margin, captions bottom ≈ 960. Action.tsx and BehindTitle switch their positions by `H > W`.

## Safe zones
- Top 0–180: status bar / reel header. Chapter tags at y 200–280 (`N.tagY`); cards start below them at y 300 (`N.cardTop`).
- Bottom 1560–1920: platform UI (caption, buttons). Captions: `paddingBottom: 400` → text bottom at ≈1520.
- Right 90 px: like/comment buttons. Keep cards at `left/right: 64` but nothing essential in the right 90 px at the bottom half.

## People-aware crop (`work/people_zones.json`, before the proxies)
- A 16:9 camera clip on a 9:16 canvas keeps 0.316 of its width. `people_zones.py` decides where, per segment, from Apple Vision boxes on the source: the main person plus the big ones next to them that fit (`N.peopleFitMargin`, `N.peopleNearArea`); the main person is sticky (`N.peopleStickyArea`) so two people who do not fit together do not trade the crop; when the main person alone is wider than the crop, their face decides.
- A subject that moves less than `N.peoplePanMin` of the width gets one fixed centre; a moving one a smoothed pan (`N.peopleSmoothSec`, at most `N.peoplePanSpeed` widths per second, a key every `N.peopleKeyEvery` s). make_proxies writes it as one ffmpeg crop expression per proxy.
- Vision does not see costumes as people (a banana suit), finds nobody in the dark, and «biggest» is not always «the action» (a seated man in front of the one waving): read the sheet, set `cropX` for those ranges.
- Only cut lists made here (plan.json, silent): a CapCut draft keeps the framing the user set in CapCut.
- face_zones.py runs on the cropped proxies, so cards and captions follow the new framing automatically.

## Face-aware placement (`work/face_zones.json`)
- `shot: wide` (face box < 180 px, e.g. couch shot, face y 800–1050): cards in the **top band** (`top: 300`, height ≤ 420). Nothing on the face.
- `shot: medium` (face 180–300 px, y 700–1100): top band `top: 300`, height ≤ 400; or a thin strip below the chin (y 1120–1350) for one-liners.
- `shot: close` (face > 300 px, y 500–1200): no card fits. Use `Stage` windows (video → 0.52 scale at top 190; graphics in y 1200–1350) or small stamps above the head (y 300–450).
- Laptop/table/pool cutaways (from the user's edit or chosen b-roll): free everywhere except the screen area; prefer the top band.

## Components
The kit, its props and conventions: `craft/scenes.md` and the template's `src/README.md`. Placement over a talking head comes from `R.free_top` / `R.free_bottom` in the generator (face zones, punch zoom included).

## Rhythm
- Raw takes: every cut lands on a new framing — `gen_timeline.py` alternates the zoom (base / base + 0.1; `--punch 1.2` raises the base for wide shots) on jump cuts inside one source file; slow drift 0.04 over each take. A CapCut draft keeps the user's own framing (no punch, no drift unless `--punch` is given).
- One idea per card; a card lives 4–12 s; empty dark panels waiting for content look broken → auto-height cards that grow with their bullets.
- Graphics appear on the spoken word (`work/audio/timeline.json` word times → frames), not on round numbers.
- Chapter structure: cold open (the hook) → `Chapter`s → a quiet `EndCard` (a CTA only when asked).


> No `backdrop-filter` and no `mix-blend-mode` on any component — they cause single-frame dropouts in the render (`pitfalls/render-and-qa.md`). Panels are solid `colors.panel`.

## Boards (voiceover stretches and close-up heads)
- One board per thought, 2–6 elements, each entering on its spoken word; something is on screen from the first frame (an empty panel ≥ 2 s reads as broken).
- Content band y 300–1350; two or three windows side by side (300×640 each) show the same action from different sources.
- Split layout for close-ups: head window x 56–596, y 300–1260 (scale 0.5); notes in the right column x 620, width 404.
