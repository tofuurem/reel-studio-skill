# A/B: let the user decide by ear and eye on a short stretch

When it is not clear which of two or three options is better — a voice setting, a look, a caption style, a cut point, the
music level — do not rebuild and render the whole reel per idea. Make one short file with every version of the SAME moment,
announced by beeps (and a numbered card in a video), send it, ask «1, 2 или 3?». The user decides; you write down the
decision (NOTES.md, `work/voice_tune.json`, plan.json) and only then rebuild.

Learned on a podcast edit (episodes 1–2, 2026-11): the user chose the voices, the stingers, the jingle and the guest's mic
from such files on the phone. Two lessons came with it:
- **Version 1 is always «как сейчас»** — what they already heard. Nothing they heard is replaced without an A/B.
- **A variant that wins in isolation can lose in context.** Ep. 3: the guest's voice variant the user picked from a 30-s
  A/B of four sounded doubled and far away in the episode — the A/B stretch had no fast exchanges, the episode was full of
  them. A decision that lives at a transition (a cut, the music under the first words, a voice next to another voice) is
  compared WITH the transition: pick a stretch that contains it, or `ab.py --after` (the next words after every version).

## Rules

- 2–4 versions. More and the first one is forgotten.
- The same moment in every version, same length: 20–40 s of speech for a voice, 4–10 s of picture for a look or a cut.
- Loudness matched (both tools do it): louder always «sounds better».
- The message says what each number is in plain words (the tools print the legend: «1 бип = как сейчас, 2 бипа = …»), and
  what to listen or look for («послушай паузы между словами», «смотри на лицо и небо»). Do not tell which one you prefer
  before they answer, unless asked.
- Files go to `out/ab/` (re-creatable: deleting them needs a separate «да» like `out/demo`). Name them by the question:
  `voice_echo.mp3`, `look_warm.mp4`.
- After the answer: write the decision down, rebuild that one thing, and say what changed. If the user hears no difference,
  keep version 1.

## Voice (no picture needed — small MP3, quick to make)

```
PY=work/dfvenv/bin/python
$PY -I $S/dialogue.py <project> --keep-raw                    # once: work/voice/dialogue_raw.wav, the assembly before the chain
$PY -I $S/voice_probe.py <project>                            # what is off: centroid, resonances, LRA, floor → SUGGEST {…}
$PY -I $S/eq_test.py <project> --at 42 --dur 30 \
    --try "срез резонансов" '{"notches": "auto"}' \
    --try "+ экспандер" '{"notches": "auto", "expander": true}' --ab out/ab/voice_boom.mp3
```
`eq_test.py` runs the same chain as `dialogue.py` (`voicelib.voice_chain`) on that stretch, version 1 = the project as it
is now. The winner goes into `work/voice_tune.json` (`craft/audio.md` «Optional voice tools»), then `dialogue.py` again.
Choose the stretch where the problem is heard (the boomy take, the echoey room, the line that drifts away from the mic).

Any other sound question (two music beds under the same words, bleep styles, SFX level, the bed under the hook):
```
$PY -I $S/ab.py out/ab/bed.mp3 out/a.wav@12:20 out/b.wav@12:20 --names "warm,night" [--after <file>@s:d]
```
`file@start:dur` reads any media (wav, mp3, mp4, mov).

## Picture (a few seconds of each version)

Rendering a stretch, not the reel:
```
$S/render_part.sh <project> Reel <from s> <dur s> <abs>/out/ab/v1.mp4     # variant 1 as it is now
# … change the one thing (gen_reel.py / plan opts / a component prop), regenerate …
$S/render_part.sh <project> Reel <from s> <dur s> <abs>/out/ab/v2.mp4
python3 -I $S/ab_video.py out/ab/captions.mp4 out/ab/v1.mp4 out/ab/v2.mp4 --names "как сейчас,крупнее"
```
`render_part.sh` = `npx remotion render --frames=a-b` with the memory guard, one tab, caffeinate; seconds are timeline
seconds. `Reel` (1080) is enough for a decision — `Reel2K` only when the question is about detail. After the decision, put
the project back to the chosen variant before the full render (`doctor.py` checks the usual staleness, not this).

Without rendering — the same source clip with different ffmpeg filters (LUT, night lift, crop, speed):
```
python3 -I $S/ab_video.py out/ab/look.mp4 "<clip>@63.2:5" "<clip>@63.2:5" --names "LUT,LUT + теплее" \
    --vf 1 "lut3d=file='<cube>'" --vf 2 "lut3d=file='<cube>',colorbalance=rm=0.04:bm=-0.04"
```
`--grid` puts the versions side by side (sound of `--audio K`): right for a look (colour, crop, exposure) where showing one
after the other makes the second look «different» rather than better; sequential (default) is right for anything that moves
— a cut, a transition, a caption animation, timing. `--af K "<filters>"` changes one version's sound.

Measured (2026-11-13, «Покупка байка», 4K D-Log clip): two 5-s versions → 29 s, 5 MB; the filters run after the downscale.
