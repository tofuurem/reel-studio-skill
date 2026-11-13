# Input: an action reel cut to a track (no talk structure, «кучей событий»)

Use when the user wants a short, lively reel of an event — 15–45 s, many moments, cut to music, a few spoken punchlines at
most — not a talk with captions. Distilled from the Halloween reel (2026-11-04: 45 s, 40 shots, «Pursuit Of Happiness
(Nightmare)» from 2:47.6, drop on frame 218). The talk pipeline (cut list, Timeline, captions) is not used: the shots are cut
straight from the camera files by `scripts/actiongen.py`, the template's `Action.tsx` plays them.

## What the user decided last time (ask again only if unclear)
- **Music is not in the file.** The user adds the track in Instagram (its library licenses it — a downloaded mp3 baked in
  gets the reel muted). The skill renders `Action2K` without music and `ActionTrack` as a preview with the track; tell the
  user the exact second to start the track at («поставь трек с 2:47.6»).
- **No identical sound on every cut** («одинаковый вжух на каждый переход — странно»). Cuts sit on the beat and the track
  carries them; sound only where something happens (the hit on the drop, a beep, the end). Whips are silent and rare —
  phrase starts only.
- Up to 45 s is fine; vertical 9:16 for Instagram (16:9 only when asked: `R = ag.Project(".", canvas="16:9")`).
- Censored: no swearing in the punchlines or captions, nothing illegal on screen.
- Frame the people, not the centre: every landscape shot is cropped by Apple Vision (people_zones); check the sheet.

## Steps
1. **Material map.** Transcripts (`transcribe_gigaam.py`, Russian; another language: `transcribe.py --sources --lang <code>` — `inputs/raw-takes.md` step 2) and the inventory sheets of the event. Write `work/notes/shots.md`:
   candidate moments with clip + seconds, what happens (action, a face, a punchline), how strong. Look at frames
   (`folder_sheet.sh`, `contact_sheet.sh`) — an «action» in a transcript is often someone sitting down. For a specific
   moment the user names («где крутили колесо») search the frames, and if it is not there, say so and offer the nearest one.
2. **The track.** The user picks it (a current one from Instagram's library is fine — they add it there). A link instead of
   a file: `python3 -I $S/fetch.py <project> <url> --as music` → `assets/music/<name>.m4a` (only for the beat grid and the
   preview; the published reel still has no music). With the file:
   `work/venv/bin/python -I $S/track_beats.py <project> <track.mp3>` → tempo, bar energy map, drop candidates, suggested
   windows. Offer 2–3 windows by ear-worthy reasons (the drop at 5–8 s, the end on a phrase end), the user picks; then
   `track_beats.py <project> <track.mp3> --start S --len 45` → `work/track_beats.json` (grid) + `reel/public/audio/track_cut.m4a`.
3. **The shot list.** Copy `assets/examples/gen_action.example.py` to `work/gen_action.py`. Structure on the grid:
   build-up (1–2 beats per picture, the hook title over the first shots) → the drop on the strongest moment (a hit, a jump —
   `sync=(frame, "drop")`, a speed ramp into it, flash ≤ 0.45, shake, `sfx=[(f, "hit")]`) → phrases of 4 bars, each opening on a
   new place or a whip → 2–4 spoken punchlines (`voice=(a, b)` + one caption, 2–3.5 s each, the funniest lines) → an end
   (the battery gag, a freeze, a fade). Mix wide/close, fast/slow; never two near-identical shots in a row.
   Accents (`craft/transitions.md` §3): `bump`, `crashAt`, `rgbAt`, `stutterUntil` (into the drop), `black` (the cold-open
   bumper), `hold` + `circle="auto"` — each on a real drum hit, with plain shots between them (`FX BUDGET` lines are errors:
   the user hates «вжух на каждое действие»). Most cuts are plain hard cuts on the beat.
   Lengths in `beats=` (exact on the grid) or `frames=`; speed ramps as pieces (`R.piece(src_s, frames, speed)`).
4. **Build.** `work/venv/bin/python -I work/gen_action.py` → `ACTION_OK`, the sync table (every cut's distance to the nearest beat, phrase
   and DROP marks, `SYNC WARNING` when a `sync` moment misses or an accent is off the nearest drum hit, `FX BUDGET`, `STILL
   CUTS` — cuts where neither side moves) and `work/action/sheet.jpg` (the middle frame of every shot).
   Read the sheet: a cut-off head, the wrong person, an empty frame → `x=…` for that shot, `--only N` to rebuild it.
   `(cd reel && npx tsc --noEmit -p .)`, `python3 -I $S/lint_reel.py <project>`.
5. **Title behind the person** (optional, one per reel): `behind={"title": …, "kicker": …}` on a shot where one person is
   big and fairly still → `person_matte.py` cuts them out of that piece; the title sits between. Check the frame — a
   crowd or a fast whip breaks the illusion.
6. **Preview and render.** `$S/render.sh <project> ActionTrack <abs>/out/<name>_preview_track_1080.mp4` (with the music — for
   checking the sync by ear) and `$S/render.sh <project> Action2K <abs>/out/<name>_2k.mp4` (the file to publish). Send both;
   say the start second for Instagram. QA: 3 consecutive frames of every whip and the drop (`qa_sheet.sh`).

## Numbers
`numbers.md`: `actionSlowmo` (slower pieces are motion-interpolated), `actionPhraseBars`, `sfxHit` and the other sfx levels,
`flashPeak`. A 115 BPM track: one beat ≈ 15.6 frames at 30 fps; 4 bars ≈ 250 frames.
