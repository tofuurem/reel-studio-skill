# Input: an event vlog (many people, two cameras, lav mics, long uncut takes)

Use for a day or an evening filmed as it happened — a party, a trip, a holiday — cut into a long vlog (5–25 min), usually
horizontal for YouTube or a private archive, plus maybe an action reel from the same material (`inputs/action-reel.md`).
It is the raw-takes entry (`inputs/raw-takes.md`) with these differences.

## What the user wants from it
- **Whole scenes, not sound bites.** Let each scene play: the setup, the joke, the laugh, the reaction. Short pauses stay
  (≤ 2.4 s); only dead air goes.
- **No phrase cut in the middle, no silent fragments.** Every speech range ends on a sentence end; a picture beat without
  words needs a reason (it shows something) and gets the camera's own sound.
- **Gentle voice cleanup**, levels even between people and cameras, no crackle when someone holds the mic at their mouth.
- Uncensored for the vlog (the user's own channel/archive) unless they say otherwise; the reel cut from it is censored.
  A censored long version (YouTube, family): `craft/censor.md`.
- Music: usually none — the event's own sound carries it. Ask.
- **Captions: all speech or none.** Key lines only come and go and read as broken; ask, and if captions, calm captions on
  every line.
- **Who is who**: a name on each person the first time they appear (`NameTag`, a pill riding on the tracked head), not only
  a card later.
- **The ending is the user's**: no coda after the last line (a time-lapse home, a montage). Ask before adding anything
  after the last word.
- **Seams with a reason** (step 4). The user may ask for more kinds than `transitionKindsMax`; each still needs its reason
  and the alternation of `craft/transitions.md` §0.

## Steps (on top of raw-takes)
1. **Intake**: `"canvas": "16:9"` in `work/intake.json` (scaffold.sh sets the template's W × H from it; cut_from_transcript
   writes it into the cut list; nothing is cropped). Captions: ask (above).
2. **Voice per mic.** Two lavs on the camera's L/R → `work/dfvenv/bin/python -I $S/dualmic.py <project> --cutlist work/cutlist.json <clips…>`
   after the first cut (`--test START DUR <clip>` first writes L / R / mix / downmix for an A/B by ear); proxies take
   `--voice-dir work/voice/out`. One mic → `voice_isolate.sh` (declips too). DeepFilterNet stays mild (`dualmicAtten`).
3. **Plan as beats.** Scenes in the order of the evening, chapters by place/time (`"chapter"` + a whip on the first range).
   Plan-level `"lead": 0.2, "tail": 0.45, "splitPauses": 2.4` and the default `"snap": true`; picture beats
   (`"exact": true, "amb": true`) only where the picture tells something (a dance, a ride, a view). `cut_from_transcript.py`
   prints `GROWN` (ranges extended to the sentence edge) and `MID-SENTENCE` (still cut inside a sentence) — fix those.
   Far-apart ranges of one long take become alias clips (`splitWindows`), so the proxies stay short.
   Moments in long takes: `earshot find` by sound (`craft/audio.md` «Sound effects») — confirm each in the transcript or the
   picture.
4. **Dialogue and seams.** After the timeline, `work/dfvenv/bin/python -I $S/dialogue.py <project>` builds the one dialogue
   stem (`craft/audio.md`); re-run after every re-cut. The 3–5 hardest scene changes get a sound bridge (`--bridge`, or
   `"bridge": true` on the range; `craft/transitions.md` §2). Seam per reason (`craft/transitions.md` §1): whip = another
   place the same day, blur = a jump in time, push = deeper into the night, one `leak` (into a sunset), `match` when the same
   person is in two places, `bodywipe` when someone crosses close to the camera, a stepped jump-in once on a punchline;
   dissolves everywhere else, within the seam budget (§0).
5. **Night.** After the proxies: `work/venv/bin/python -I $S/night_lift.py <project>` lifts the shadows of dark clips (per
   clip, by mean luma); re-run after make_proxies re-encodes one (doctor warns).
6. **Graphics**: chapter tags and a title, few cards — the people and the event are the content. A title behind a person
   (`R.cutaway(..., behind={...})`) works for the opening.
7. Render `Reel2K` (2560×1440 for 16:9). A 20-minute vlog renders ≈ 40 min; check the loudness line and the glitch scan.

## Review rounds
The user watches the whole thing and lists problems by kind (silent fragments, cut phrases, crackle, music). Fix by kind:
`MID-SENTENCE` list → plan; crackle → declip / tame numbers; music → intake. Keep `gen_plan_vN.py` / `cutlist_vN.json`
backups and a v-section in `NOTES.md` per round.
