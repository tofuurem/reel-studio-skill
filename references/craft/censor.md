# A censored version (same cut, more «культурная»)

For a second version of a finished video that family or a platform will see. Keep it long and whole — not a shorter cut.
Nothing is cut: words are bleeped, captions masked, things in the picture blurred. The uncensored version keeps its own
stem and files.

**Ask which half the user wants before building the words part**: bleeps (steps 1–3), blur (step 4), or both. Blur only
means the uncensored stem (`work/bleeps.json` = [], `dialogue.py` without `--out`) and the uncensored captions, no
asterisks — asterisks only ever mirror bleeps.

1. **Words.** Keep `cut_from_transcript.py`'s swear list (copy `work/bleeps.json` before the uncensored cut empties it), then
   `python3 -I $S/censor_bleeps.py <project> --swears <that copy>` → `work/bleeps_censored.json`: the swears + rude words
   `swear.py` does not count («сука», «наркоман») + weed and mushroom talk («курим», «накуривается», «косяки», «грибов»);
   `--no-drugs` for swears only. Extend `CENSOR_WORDS` / `DRUG_WORDS` there when the user names more.
   Padding and merging in the scripts: a swear spans the word −0.2 / +0.28 s, clamped to the voice's speech run, at least
   0.25 s (`cut_from_transcript.py`, `bleeps_from_timeline.py`); censor_bleeps.py's extra words span −0.1 / +0.2 s
   (capped by the word's length); every script merges bleeps closer than 350 ms.
   **Then check the list against the stem itself**: a recognizer on each source clip hears the far mic and background
   voices (bleeps over innocent lines) and misses words. Run it on the uncensored stem
   (`work/gigvenv/bin/python -I $S/transcribe.py --sources work/audit/stemu.wav` → `work/new/cstemu.json`, timeline seconds)
   and time the bleeps from that with `assets/examples/stem_bleeps.example.py` (bleeps + `work/bleep_patches.json`): word
   −0.2 / +0.28 s, at least 0.38 s, neighbours merged only under 0.15 s — one long bleep over several words reads as a
   broken track. Listen to every bleep once and keep the decisions in the patches file (`add` by time for a swear it missed
   over wind or music, `drop` for a false hit). `caption_words.example.py` builds full captions on the same transcript,
   masked by bleep spans, page-level fixes in `work/caption_fixes.json`.
2. **Stem.** `work/dfvenv/bin/python -I $S/dialogue.py <project> --bleeps work/bleeps_censored.json
   --out reel/public/audio/dialogue_censored.wav` — the soft boop replaces each word inside the one dialogue stem;
   `dialogueSrc.ts` now points at it (doctor checks the stem that file names). Re-run without `--out` for the uncensored one.
3. **Captions.** Every caption text through `censor_bleeps.censor_text()` («к*****», first letter kept) — key lines,
   cards, the caption pages; a masked word must also be bleeped, or the asterisks read as a joke. With full captions mask
   by TIME: every caption word whose middle lies inside a bleep span, nothing else — then the two always agree. Build the
   caption words on the same GigaAM transcript the bleeps are timed from; never swap single words between two recognizers
   by time (it puts swears on the wrong words).
4. **Picture.** Blur the joint itself, nothing else: no blanket `hands` jobs (they blur every hand near a face — a mic, a
   phone); an ordinary cigarette stays unless the user says so — ask. Signs (`sign` for neon leaf signs, `box` with
   keyframes for a leaf painted on a wall) only when the user wants signs blurred at all.
   - **Find every joint first.** A 1 s contact sheet of the uncensored render over every scene the transcript flags, plus a
     3 s sheet of the whole video for what nobody talks about (signs, wall art). For a long video split the render into
     4-minute ranges and give each to a subagent with labelled 1 s contact sheets (`sheets.py`-style tiles with the time
     burnt in) and full-res zooms, asking for start–end, who, where in the frame and what (in hand / at the mouth / smoke),
     plus the look-alikes (a DJI mic at the mouth, a phone, a straw, a can). Check people at the frame edges and smoking
     through a costume's mouth hole. Verify each finding yourself on a zoom.
   - **One `follow` job per finding**: read keys off `censor_track.py <project> --grid <clip> <a> <b> 0.25` (source frames
     with a 10 % grid), radius ≈ 1.5× the joint + fingers (only the inner 60 % is blurred fully — the yellow ring on the
     track sheet); split a scene into several jobs where the joint leaves the frame.
   - **Keys go on the joint, not on the hand**: `"snap": true` pulls the centre onto the Vision hand, which leaves a joint
     held in the lips, sticking up out of a fist or a lit tip beside the fingers outside the blur. Use `"snap": false` with
     keys every 0.1–0.15 s on the joint's middle wherever it is at the mouth or held up; keep snap only for a joint inside a
     moving hand.
   - A job whose joint is still there when its clip ends runs through the clip's dissolve tail (segment end + 7 frames):
     `censor_blurs()` holds the last ellipse there, but only when the job reaches the clip's end.
   - Run `work/venv/bin/python -I $S/censor_track.py <project>` and look at EVERY `work/stills/censor/track_*.jpg`. Then in
     `gen_reel.py`: `body = R.censor_blurs() + body` (BlurPatch layers, `scenes/Censor.tsx`, a 28 px blur inside soft
     ellipses; tracks in `reel/src/censorData.ts`).
5. **QA on the rendered file, densely** — mid-patch stills miss joints. Diff the censored render against the uncensored one
   (same cut, same captions → the difference IS the blur) and crop around it every 0.2 s from 1.5 s before to 1.5 s after
   each patch: `assets/examples/blur_sweep.example.py` (also takes a partial check render with `--offset`). Look at every
   tile for a joint outside the blur, at the dissolve frames too, then render only the fixed ranges
   (`npx remotion render Reel2K out/demo/x.mp4 --frames=a-b`) and sweep them before the full render. Render to
   `<name>_censored.mp4`; both versions go to the user.
