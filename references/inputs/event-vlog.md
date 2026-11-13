# Input: an event vlog (many people, two cameras, lav mics, long uncut takes)

Use for a day or an evening filmed as it happened — a party, a trip, a holiday — cut into a long vlog (5–25 min), usually
horizontal for YouTube or a private archive, plus maybe an action reel from the same material (`inputs/action-reel.md`).
Distilled from the Halloween vlog (2026-11-01 … 04: 52 clips, two DJI Pockets, two wireless lavs on L/R, 21 min, three
rounds of feedback). It is the raw-takes entry (`inputs/raw-takes.md`) with these differences.

## What the user wants from it (v1 was 4/10)
- **Whole scenes, not sound bites.** v1 cut every scene into 3–5 s quotes; the user wants the scene to play: the setup, the
  joke, the laugh, the reaction. Short pauses stay (≤ 2.4 s), only dead air goes.
- **No phrase cut in the middle, no silent fragments** («обрезанные пару секунд кадры без звука», «фразы без смысла
  обрезанные по середине»): every speech range ends on a sentence end; a picture beat without words needs a reason (it shows
  something) and gets the camera's own sound.
- **Gentle voice cleanup**, levels even between people and cameras, no crackle when someone holds the mic at their mouth.
- Uncensored for the vlog (the user's own channel/archive) unless they say otherwise; the reel cut from it is censored.
  A censored long version (YouTube, family) keeps the whole cut: bleeps, masked captions, tracked blur — `craft/censor.md`.
- Music: usually none («тут не получится ничего хорошего») — the event's own sound carries it. Ask.
- **Captions: all speech or none** (v5 review, 2026-11-09): key lines only («ключевые фразы») read as captions that come and
  go — «только к ним привыкаешь, потом их нету»; the user chose calm captions on every line (both versions).
- **Who is who**: a name on the person the first time each one appears (`NameTag`, a pill riding on the tracked head), not
  only a card later in the costume — the user did not know who was talking.
- **The ending is the user's**: they wanted the vlog to stop on a line («закончить на вопросе… больше ничего не вставлять»);
  a coda added after the last line (v4: a time-lapse ride home) was cut. Ask before adding anything after the last word.
- **Seams with a reason** (v5): whip = another place the same day, blur = a jump in time, one leak into a sunset, push =
  deeper into the night, a stepped jump-in once on a punchline («Во всём.»); dissolves everywhere else. The user asked for
  «более прикольные переходы» — more kinds than `transitionKindsMax`, each with its reason, still alternating.

## Steps (on top of raw-takes)
1. **Intake**: `"canvas": "16:9"` in `work/intake.json` (scaffold.sh sets the template's W × H from it; cut_from_transcript
   writes it into the cut list; nothing is cropped). Captions: ask — a vlog in the user's own language often goes without.
2. **Voice per mic.** Two lavs on the camera's L/R → `work/dfvenv/bin/python -I $S/dualmic.py <project> --cutlist work/cutlist.json <clips…>`
   (after the first cut; `--test START DUR <clip>` writes L / R / mix / downmix for an A/B by ear first). One mic →
   `voice_isolate.sh` (declips too). DeepFilterNet stays mild (`dualmicAtten` 12 dB): full strength sounded hollow.
3. **Plan as beats.** Write the plan as scenes in the order of the evening, chapters by place/time (`"chapter"` + whip on the
   first range). Plan-level `"lead": 0.2, "tail": 0.45, "splitPauses": 2.4` and the default `"snap": true`; picture beats
   (`"exact": true, "amb": true`) only where the picture tells something (a dance, a ride, a view). `cut_from_transcript.py`
   prints `GROWN` (ranges extended to the sentence edge) and `MID-SENTENCE` (what is still cut inside a sentence) — fix those.
   Far-apart ranges of one long take become alias clips (`splitWindows`), so the proxies stay short.
4. **Voice.** `dualmic.py --cutlist` restores each lav clip (proxies take `--voice-dir work/voice/out`); after the timeline,
   `work/dfvenv/bin/python -I $S/dialogue.py <project>` builds the vlog's one dialogue stem: per-clip level, per-segment
   leveling, camera sound under `amb` beats, crossfaded cuts, room tone, one chain (`craft/audio.md`). Re-run after every re-cut.
   Scene changes: `--bridge` (or `"bridge": true` on the 3–5 hardest ones) lets each place's own sound run a moment across the
   cut (J/L, `craft/transitions.md` §2). Looking for the moments in long takes: with earshot, `earshot find <clip> "people
   laughing" --top 5` (a cheer, a splash, fireworks) lists candidates by sound — confirm them in the transcript or the picture. Seams between places: mostly dissolves; one `leak`, a `match` when the same person is
   in two places, a `bodywipe` when someone crosses close to the camera — within the seam budget (`transitions.md` §0).
5. **Night.** After the proxies: `work/venv/bin/python -I $S/night_lift.py <project>` lifts the shadows of dark clips (per clip, by mean
   luma); re-run after make_proxies re-encodes one (doctor warns).
6. **Graphics**: chapter tags and a title, few cards — the people and the event are the content. A title behind a person
   (`R.cutaway(..., behind={...})`) works for the opening.
7. Render `Reel2K` (2560×1440 for 16:9). A 20-minute vlog renders ≈ 40 min; check the loudness line and the glitch scan.

## Review rounds
The user watches the whole thing and lists problems by kind (silent fragments, cut phrases, crackle, music). Fix by kind:
`MID-SENTENCE` list → plan; crackle → declip / tame numbers; music → intake. Keep `gen_plan_vN.py` / `cutlist_vN.json`
backups and a v-section in `NOTES.md` per round.
