# Cut and timeline

Traps in the user's edit, cutaways, cut points and synced windows. Seam choice, alternation and the seam budget are owned by `craft/transitions.md` §0.

- **A CapCut draft is final** → transfer the cut 1:1, never shorten speech, keep the 0.3-s mutes (`volume 0.001`: they hide clicks). Keyframed (animated) framing is not reproduced: `draft_summary.md` lists those segments — rebuild them by hand.
- **The user already has cutaways in the main track** → check the contact sheet before laying b-roll over them; covering theirs looks like a mistake.
- **A cutaway that reads as a jump cut** → it must show a different framing (not a snippet of the same static take) and not the thing the user's next shot shows.
- **A talking-head take flashes through 3–4 frames at a cut** → `R.cutaway` / `R.board` widen themselves; anything placed by hand starts ≥ 8 frames before the cut and ends ≥ 19 frames after it. Inside a montage use hard cuts: `BRoll fadeIn={0} fadeOut={0}`, each shot starting 2 frames before the previous one ends.
- **Cold open on a cutaway lets the face peek through frame 0** → `fadeIn={0}` + `ui/FadeFromBlack`; hold the cutaway through the timeline's dissolve and fade it out after.
- **Trimming pauses or cutting inside a take** → word ends drift ±0.1–0.3 s: get real boundaries with `pauses.py <voice.wav> <start> <dur> [thr_db] [min_s]` on the cleaned wav and write them as `"exact": true` seconds.
- **`cut_from_transcript.py` prints MID-SENTENCE** → fix each listed range before going on.
- **Sound bites instead of scenes** (every scene cut to 3–5-s quotes) → plan whole scenes: setup, joke, laugh. `splitPauses` (≈ 2.4 s) only removes dead air.
- **A wide shot leaves the speaker tiny** → `gen_timeline.py --punch 1.2`, or `"punch"` on one segment.
- **Synchronised windows** (one action from several sources) → find the moment in each source on a strip of frames every 0.5 s, then `trimBefore = moment·30 − lead`. A `<Video>` in a window that pops in later still plays on the sequence clock: do not add the pop-in frame.
