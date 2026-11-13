# A censored version (same cut, more «культурная»)

For a second version of a finished video that family or a platform will see (Halloween vlog, 2026-11-09: YouTube or family). The user's words: keep it long and whole — «просто сделать её более культурной», not a 5-minute cut. So nothing is
cut: words are bleeped, captions masked, things in the picture blurred. The uncensored version keeps its own stem and files.

**Ask which half the user wants before building the words part.** After v5 of that vlog the user dropped the bleeps
altogether: «убрать запикивание всех матов и оставить только закрытие косяков». The censored version became BLUR ONLY
(step 4): the uncensored stem (`work/bleeps.json` = [], `dialogue.py` without `--out`) and the uncensored captions, no
asterisks — asterisks only ever mirror bleeps. Steps 1–3 run only when the user asks for bleeps.

1. **Words.** Keep `cut_from_transcript.py`'s swear list (copy `work/bleeps.json` before the uncensored cut empties it), then
   `python3 -I $S/censor_bleeps.py <project> --swears <that copy>` → `work/bleeps_censored.json`: the swears + rude words
   `swear.py` does not count («сука», «наркоман») + weed and mushroom talk («курим», «накуривается», «косяки», «грибов»);
   `--no-drugs` for swears only. Extend `CENSOR_WORDS` / `DRUG_WORDS` there when the user names more.
   **Then check the list against the stem itself** (Halloween v5 review, 2026-11-09: «некоторые маты не запикиваются»,
   «иногда нету никакого мата, но он запикивает»): a recognizer on each source clip hears the far mic and background voices
   (a bleep over «Сейчас нет, ему больно»), and misses words. Run the recognizer on the uncensored
   stem (`work/gigvenv/bin/python -I $S/transcribe.py --sources work/audit/stemu.wav` → `work/new/cstemu.json`, timeline
   seconds) and time the bleeps from that. Its word ends are ±0.1–0.26 s (40 ms token grid), so a bleep spans the word
   −0.2 / +0.28 s, at least 0.38 s (the skill's own bleeps use the same pad). Listen to every bleep once and keep the
   decisions in a patches file (`add` by time for a swear it missed over wind or music, `drop` for a false hit). Bleeps
   closer than 0.15 s merge; one long bleep over three words (v4: 3.3 s over three repeated words) reads as a
   broken track. Worked scripts: `assets/examples/stem_bleeps.example.py` (bleeps + `work/bleep_patches.json`),
   `caption_words.example.py` (full captions on the same transcript, masked by bleep spans, page-level fixes in
   `work/caption_fixes.json`).
2. **Stem.** `work/dfvenv/bin/python -I $S/dialogue.py <project> --bleeps work/bleeps_censored.json
   --out reel/public/audio/dialogue_censored.wav` — the soft boop replaces each word inside the one dialogue stem;
   `dialogueSrc.ts` now points at it (doctor checks the stem that file names). Re-run without `--out` for the uncensored one.
3. **Captions.** Every caption text through `censor_bleeps.censor_text()` («к*****», first letter kept) — key lines,
   cards, the caption pages; a masked word must also be bleeped, or the asterisks read as a joke. With full captions mask
   by TIME: every caption word whose middle lies inside a bleep span, nothing else — then the two always agree. Build the
   caption words on the same GigaAM transcript the bleeps are timed from (swapping single words between two recognizers by
   time once put swears on the wrong words).
4. **Picture.** Blur the joint itself, nothing else (v5 review: the v4 `hands` jobs blurred every hand near a face — on the
   beach the guys only held a mic: «слишком много срабатываний, где нету никаких сигарет»; an ordinary cigarette stays
   unless the user says so — ask). **Find every joint first**: split the uncensored render into 4-minute ranges and give
   each to a subagent with labelled 1 s contact sheets (`sheets.py`-style tiles with the time burnt in) and full-res zooms,
   asking for start–end, who, where in the frame and what (in hand / at the mouth / smoke), plus the look-alikes (a DJI
   mic at the mouth, a phone, a straw, a can) — v4 had missed three people and a person smoking through a costume's mouth hole. Verify each finding yourself on a zoom. Then per finding a `follow` job: read keys off
   `censor_track.py <project> --grid <clip> <a> <b> 0.25` (source frames with a 10 % grid), radius ≈ 1.5× the joint + fingers
   (only the inner 60 % is blurred fully — the yellow ring on the track sheet), split a scene into several jobs where the
   joint leaves the frame. **Keys go on the joint, not on the hand**: `"snap": true` pulls the centre onto the Vision hand,
   and a joint held in the lips or sticking up out of a fist is then left outside the blur (2026-11-13, after v5: six
   misses — a joint held in the lips, a joint above a fist, a lit tip beside the fingers). Use
   `"snap": false` with keys every 0.1–0.15 s on the joint's middle wherever it is at the mouth or held up; keep snap only
   for a joint inside a moving hand. A job whose joint is still there when its clip ends runs through the clip's dissolve
   tail (segment end + 7 frames): `censor_blurs()` holds the last ellipse there, but only when the job reaches the clip's
   end. `sign` for neon leaf signs, `box` with keyframes for a leaf painted on a wall — only when the user wants signs
   blurred at all (Halloween: «оставить только закрытие косяков» — the signs went). Run
   `work/venv/bin/python -I $S/censor_track.py <project>` and look at EVERY `work/stills/censor/track_*.jpg`. Then in
   `gen_reel.py`: `body = R.censor_blurs() + body` (BlurPatch layers, `scenes/Censor.tsx`, a 28 px blur inside soft
   ellipses; tracks in `reel/src/censorData.ts`). Find the scenes first: a 1 s contact sheet of the uncensored render over
   every scene the transcript flags, plus a 3 s sheet of the whole video for what nobody talks about (signs, wall art).
5. **QA on the rendered file, densely.** Mid-patch stills passed v5 while six joints showed. Diff the censored render against
   the uncensored one (same cut, same captions → the difference IS the blur) and crop around it every 0.2 s from 1.5 s
   before to 1.5 s after each patch: `assets/examples/blur_sweep.example.py` (also takes a partial check render with
   `--offset`). Look at every tile for a joint outside the blur, at the dissolve frames too, then render only the fixed
   ranges (`npx remotion render Reel2K out/demo/x.mp4 --frames=a-b`) and sweep them before the full render. Render to
   `<name>_censored.mp4`; both versions go to the user.
