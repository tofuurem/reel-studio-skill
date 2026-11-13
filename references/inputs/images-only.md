# Input: pictures only, no voice

Use when the user brings screenshots, renders, photos or short silent recordings and nothing spoken.

1. **Offer a voice first.** A reel without a voice has nothing to anchor the pictures to and holds attention worse. Propose 4–8 short lines from the material (`inputs/voiceover.md`, "Writing the lines") and how to record them; if the user records them, it is a voiceover episode.
2. **No voice after all** (a mood reel, a gallery of renders, a teaser): the pictures run on the music's beat grid.
   - `python3 -I $S/silent_timeline.py <project> --seconds <S> --preset <warm|night|bright|dusk>` → `SILENT_TIMELINE_DONE`: a silent carrier, `work/cutlist.json` with `"silent": true` and one muted segment, `work/beats.json` (the preset's BPM → beat frames, bars). Length: ≈ 2–3 s per picture, 20–45 s in total.
   - Core pipeline without voice: proxies (`--res both`, the carrier and any `--extra` recordings) → timeline → music (`make_bed.sh` with the same preset, or the user's track — `craft/audio.md` step 4; then measure its tempo and rewrite `work/beats.json` in the same format: `bpm`, beat `frames`) → SFX → scenes. Transcribe, captions, bleeps and face zones are skipped; `doctor.py` knows a silent cut list.
   - Scenes: start from `assets/examples/gen_reel_silent.example.py` — `R.beats(every=4)` gives a picture change every bar; pictures in `Win` / `ImageCard` / full-bleed `Plate`, a `TitleCard` at the start, a soft whoosh on a few changes, not on every one (`craft/transitions.md` §0), no captions (`R.write(..., captions=False)` is the default for a silent cut list).
   - Words on screen come only from the user or the material (titles of the renders, the app's own UI) — no invented claims.
3. Render, QA and hand-off as in the core pipeline.
