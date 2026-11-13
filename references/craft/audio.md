# Audio pipeline

The voice is restored once, assembled once, processed once and encoded once. Every number is in `numbers.md`
(«Voice chain», «Audio levels»). Why it is built this way: `pitfalls/audio.md` (2026-11-07 audit).

```
camera track ─┐                      ┌─ cut list (frames) ─┐
or DJI TX     ├─ voice_clean.py ──── work/voice/out ─ dialogue.py ─ reel/public/audio/dialogue.wav ─┐
32-bit float ─┘  (declip if clipped,   (float, source    assembly · crossfades · room tone ·          │
                  limited denoise)      time, no EQ)     levels · ONE chain · bleeps                  │
music bed (WAV), SFX (WAV) ───────────────────────────────────────────── Remotion mix (PCM) ─ render.sh:
                                                                         static gain · 4× true-peak limiter · ONE AAC 320k · audio_qa
```

1. **Restore each source** — `voice_isolate.sh <project> <speech sources…>` (= `work/dfvenv/bin/python -I $S/voice_clean.py`) → `work/voice/out/<clipId>_DeepFilterNet3.wav` + `<clipId>.voice.json`. Per source it measures the speech level, pause floor, SNR and clipped samples, then does only what is needed:
   - `adeclip` only around clipped samples (± 20 ms) — on clean audio it still rewrites the waveform;
   - DeepFilterNet limited to `noiseTargetDb − SNR` dB (`dfnMinAtten` … `dfnMaxAtten`), none when the room is already quiet. The residual room stays ≈ 48 dB under the voice: inaudible under speech, but the pauses keep their air instead of dropping to digital silence (which makes the voice «breathe» and sound gated);
   - the report shows what the cleanup did to the voice (1/3-octave transfer over ALL speech frames — exact since 2026-11-13; the old 1500-frame sample was ±2 dB noisy at 5–8 kHz); a band moved > 2 dB is a WARNING — listen, lower `--atten-lim-db`.
   - `--lav <folder|wav…>`: the DJI transmitter's own 32-bit float recording replaces the camera track (found and synced by cross-correlation, clock drift resampled; uncovered parts keep the camera track). Use it whenever the user has the TX files: it skips the radio link, the receiver's processing and one AAC encode.
   - Two lavs on the camera's L/R: `dualmic.py` instead (each mic restored alone, then automixed — below).
   - Never: ffmpeg `afftdn`, `agate`, `anlmdn` — rejected after listening.
2. **Proxies** carry the restored voice (`make_proxies.py --voice-dir work/voice/out`) — for Studio scrubbing and the transcript; the render does not use their sound.
3. **Dialogue stem** — after `gen_timeline.py`: `work/dfvenv/bin/python -I $S/dialogue.py <project>` → `reel/public/audio/dialogue.wav` (48 kHz 24-bit, timeline time), `reel/src/dialogueSrc.ts` (`DIALOGUE`: `Clip` mutes the proxies, `<Dialogue />` plays the stem; `reelgen.write` places it), `work/voice/dialogue.json` (`DIALOGUE_DONE`). Any re-cut → re-run (doctor.py says when it is stale). What it does:
   - **assembly** on the cut list's frames: each segment's source range from the restored voice, with handles; every jump cut gets an equal-power crossfade of `cutXfadeMs` (no click, no hole), two segments continuing one take a `joinXfadeMs` linear join; speed changes time-stretched like Remotion (`atempo`); `audioFadeIn` honoured; CapCut voiceovers placed where the draft put them;
   - **levels**: each take's active speech to `voiceTargetDb` (≤ `voiceMaxGain` up), each segment nudged into [`voiceSegLo`, `voiceSegHi`] (± `voiceSegMax`); `"amb"` segments add the camera's own sound at `ambDb` kept out from under every word, `"raw"` ones use the camera sound at `rawDb` instead of the restored voice;
   - **room tone**: gaps and muted slivers between the first and the last word get the quietest stretch of the neighbouring take, looped — never digital silence;
   - **one chain** over the whole stem (`voicelib.voice_chain`): high-pass `hpfHz` + phase rotator (lowers the lopsided speech peaks ≈ 2.5 dB, spectrum unchanged) → measured cuts at 315 Hz (mud) / 900 Hz (box) → ONE soft-knee compressor (`compOverDb` over the leveled speech, `compRatio`, `compWindowMs` RMS) → measured presence (3.5 kHz) / air (9 kHz shelf) → de-esser (dynamic cut at 6.5 kHz, only on dominant sibilants) → static gain to `stemLufs` → look-ahead limiter at `stemPeakDb`. The EQ moves are bounded (`eqMaxCut`, `eqMaxBoost`, `eqMaxAir`) and correct `eqAmount` of the measured deviation from the target speech spectrum (LTASS + a little presence and air) — the speaker keeps their timbre;
   - **bleeps** from `work/bleeps.json` go into the stem (word muted, soft boop); `bleep.py` on the render is then a no-op;
   - `--keep-raw` writes `work/voice/dialogue_raw.wav` (assembly + levels, no chain, no leveler) for an A/B by ear and for `eq_test.py`;
   - **optional voice tools** from `work/voice_tune.json` — all off without the file (the stem stays bit-identical; checked on «Покупка байка» 2026-11-13). Below.
4. **Mix in Remotion**: `<Dialogue />` at volume 1; the bed via `MusicBed` (0.3 in the cold open, wordless pauses and the tail, 0.18 under speech ≈ 20 LU down, short ramps, an end fade — `reel/public/audio/lofi_bed.wav` from `make_bed.sh <project> [seconds] <preset>`, or the user's track: `ffmpeg -i assets/music/<track> -ar 48000 -c:a pcm_s16le reel/public/audio/lofi_bed.wav`). SFX: `Sfx kind="tick|pop|done|whoosh|softwhoosh"` from `make_sfx.sh` (WAV, local), one kind of sound per kind of action, levels in `numbers.md` — see «Sound effects» below. Music beds: `lofi.py` presets warm / night / bright / dusk, a different one per video. Everything stays PCM until the end.
5. **Master** (`render.sh`): Remotion renders the sound as PCM (`--audio-codec=pcm-16`, a `.mov` intermediate); then the integrated LUFS of the whole mix → a static gain to `targetLufs` → a 4× oversampled limiter at `truePeakDb` (a true-peak limiter; `level=false`) → the ONLY AAC encode (`aac_at`, Apple's encoder, when ffmpeg has it), `aacBitrate`. One corrective pass if > 0.2 LU off; the render fails beyond ±`lufsTolerance`. Never single-pass `loudnorm` (dynamic: pumps the bed in every pause).
6. **QA** — `audio_qa.py <file> --project <dir>` (render.sh runs it; warnings only): loudness, LRA in [`lraMin`, `lraMax`], true peak, digital silence inside the speech, pause floor under the speech, spectrum vs the target shape (mud / presence / air), tonal noise in the pauses (insects, hum), clicks at the dialogue cuts, codec and bitrate. Read the line before delivering. If the user says "music too loud", halve the bed (`R.music_bed(under=0.09)`), never touch the gain.

## Optional voice tools (`work/voice_tune.json`)

Learned on a podcast edit (2026-11-13), where an hour of one voice exposed what a 40-s reel hides. Off by default;
switch one on only when the user hears the problem or `voice_probe.py` shows it, and only after an A/B on a stretch
(`craft/ab.md`): `voice_probe.py` → `eq_test.py --try …` → the user picks → the file → `dialogue.py`.

```json
{"_why": "c0018 гудит, c0051 в комнате с эхом — A/B 13.11: 2 бипа",
 "notches": "auto", "expander": true, "leveler": {"amount": 0.6, "max_db": 5}}
```

| key | what it does | when | numbers |
|---|---|---|---|
| `notches` | `"auto"`: narrow cuts (Q 3) on the resonances under 500 Hz that stick out ≥ `notchMinDb` over the 1-octave trend, depth = the bump ≤ `notchMaxCut`; or your own ffmpeg `equalizer=…` string | «гудит», «бубнит», a hum (bike reel: 61 Hz +6.5 dB) — narrow peaks, not a broad 315 Hz hump (that one the chain already cuts) | podcast ep. 1 host: 108 / 214 / 320 Hz, centroid 396 → 693 Hz |
| `expander` | frames more than `expBelowDb` under the voice's own speech level pulled down 1:`expRatio`, ≤ `expRangeDb` (opens in 5 ms with look-ahead, closes in 60 ms) | room tails after words («эхо»), DeepFilterNet leftovers, a fan between phrases | it also lowers the room tone in the gaps by the same amount — continuity is kept, the pauses get cleaner |
| `leveler` | the speech level around each moment (400 ms, speech frames only) pulled `amount` of the way to `voiceTargetDb`, ≤ `max_db`; 0.25 s down / 0.9 s up, held through pauses | a voice that drifts inside one take (turning away, walking, a far phrase); LRA > 9 LU or a 3-s spread > 8 dB | runs on the placed speech before room tone — never on amb / raw camera sound or bridges; podcast ep. 1: LRA 9.9 → 5.8; bike reel: 6.9 → 5.4 |
| `extraEq` | any ffmpeg filters after the automatic cuts, before the compressor | a decided correction that the measured EQ does not make (presence for a dark lav, a de-honk) | test it with `eq_test.py` first |
| `hpf` | replaces the high-pass (`highpass=f=90:poles=2,highpass=f=90:poles=2` = 24 dB/oct at 90 Hz) | wind, handling, traffic rumble the default 80 Hz 12 dB/oct lets through | — |

Keys starting with `_` are notes for people. The file is part of the dialogue signature (`dialogue.py` re-runs when it
changes; `doctor.py` calls the stem stale). One tune applies to the whole stem: with two different voices (`dualmic.py`
event vlogs) `"auto"` measures their mix — give explicit `notches` per the louder problem instead, from
`voice_probe.py --clip <id>` on each take.

`voice_probe.py` numbers: centroid of the louder frames (male voice ≈ 600–700 Hz; < 500 dark / boomy, > 900 thin), the
1/3-octave deviation from LTASS + FINISH (exact LTAS, every speech frame), resonances, the 3-s spread of the speech level,
the quiet 10 % of frames under the speech (< 45 dB under → noise or room between words), hiss above 6 kHz.

## What each part of the voice's spectrum does

What to listen for, and what the chain does there (male voice; a female voice sits about an octave higher below 1 kHz):

| band | name | heard as | the chain |
|---|---|---|---|
| < 80 Hz | sub | rumble, wind, lav handling and cable thumps, traffic | high-pass at `hpfHz` |
| 85–180 Hz | fundamental | the weight of the voice, the «chest» | kept (proximity and close lavs exaggerate it) |
| 150–250 Hz | body | fullness, warmth; too much = boomy | kept |
| 250–500 Hz | mud / box | muffled, «in a box», «through a blanket»; a lav under clothing piles up here | measured cut at 315 Hz, up to `eqMaxCut` |
| 700 Hz–1.5 kHz | nasal / honk | «telephone», nasal, cheap speaker | measured cut at 900 Hz when it sticks out |
| 2–5 kHz | presence | consonants, intelligibility — the ear is most sensitive here; too much = harsh, shouty | measured boost at 3.5 kHz, up to `eqMaxBoost` |
| 5–9 kHz | sibilance | «с», «ш», «ц», «ч»; too much = piercing esses | de-esser at 6.5 kHz (only where an «s» dominates) |
| 10–16 kHz | air | openness, «expensive» sound; too much = hiss | measured shelf at 9 kHz, up to `eqMaxAir` |

Loudness words: **LUFS** — perceived loudness of the whole file (target −16 here; platforms normalise to −14…−16). **LRA** — how much the loudness moves between quiet and loud phrases (speech on a phone: 4–7 LU; < 3 = squashed and noisy, > 9 = quiet lines get lost). **True peak** — the real top of the waveform between samples (≤ −1 dBTP, or the platform's encoder distorts it).

## Recording (tell the user before a shoot; it decides more than any processing)

DJI Mic 2 / Mini / 3 on a talking head:
- **Internal recording ON, 32-bit float** on the transmitter; bring the TX files (`voice_clean.py --lav`) — the camera's track is the same mic after a radio link, the receiver's processing and AAC.
- **Noise cancellation OFF** on the mic (it gates like full-strength DeepFilterNet and cannot be undone); voice tone **Regular**; low-cut only outdoors in wind.
- The receiver's output level so the camera's meter peaks around −12 dBFS (safety track on if offered); not at the top of the camera's input range.
- The lav **15–25 cm below the mouth**, on the chest, outside the clothing or taped so nothing rubs; the windscreen outdoors.
- A quiet room beats any filter: no fan, fridge, AC, open window; record 5 s of silence at the start (room tone).
- Night outdoors near grass = insects at 3–4 kHz and 16 kHz (audio_qa «tonal noise») — they sit inside the voice's presence band and cannot be removed cleanly.

## Voice bus for event vlogs (two lavs, many clips)
Halloween vlog, 2026-11-02 … 04:
- **Two lavs on L/R → `dualmic.py`.** Restore each channel alone (declip where clipped, DeepFilterNet limited to `dualmicAtten` dB — full strength sounded hollow), then a Dugan-style automix: each channel's gain is its share of the smoothed power. A downmix first doubles the room noise and adds the far mic's late copy of every voice (comb filter, «из толчка»). `--test START DUR <clip>` writes L / R / mix / downmix for an A/B by ear.
- Levels, `"amb"` / `"raw"` beats and the chain are dialogue.py's (above). A vlog with no music: the event's own sound carries the picture beats; digital silence under a dance reads as a broken file.

## Sound effects: designed, real, and heard

- **Designed (default when earshot is installed — `deps.py --install --with sound`, ask the user: ≈ 1.6 GB).** `make_sfx.sh`
  synthesizes the set, then `sfx_bank.py` replaces every kind with a sound from earshot's bank (252 sounds stored as code,
  MIT, rendered locally, no models) at the SAME loudness, so the `numbers.md` levels still hold; the synthesized ones stay in
  `audio/sfx/synth/` for an A/B (`SFX=synth make_sfx.sh` keeps them). Why: earshot itself heard our synthesized shutter as
  «crisp hi-hats» (a weak match for «camera shutter»); real shutters scored strong. `--set whoosh=whoosh_big/cape` picks
  another bank sound (`earshot sfx list`).
- **Real recordings** when the picture shows an event the camera did not capture (a shutter, distant fireworks, a crowd):
  `python3 -I $S/sfx_find.py <project> "camera shutter"` searches Openverse (≈ 5 M openly licensed sounds, mostly Freesound;
  CC0 by default, `--license by` adds CC BY — never NC / ND / SA), downloads the top candidates, and with earshot RANKS them
  by how well they sound like the words and finds the best moment in long ones; `--pick K --name shutter_film` →
  `audio/sfx/real_shutter_film.wav` (−20 LUFS, level `sfxReal`) + `assets/sfx/real_shutter_film.json` (source, licence) and,
  for CC BY, a credit line in `work/credits.md` for the post description. English queries work best. The camera's own sound
  still comes first (`amb` beats).
- **Heard**: after the render, `python3 -I $S/ears.py <project> <render>` → `EARS_DONE` lets earshot listen: every SFX cue
  of the reel that is not heard (masked by the voice or bed, too quiet) or off its frame, tagged events, sections, loudness;
  `work/qa/ears.png` is the annotated sheet (frames, spectrogram, events, loudness, cue markers). ≈ 30 s per minute of
  render on an M-series CPU; `--from / --to` for a part of a long vlog.
- **Moments by sound** (event vlogs): `earshot find <camera clip> "people laughing" --top 5` lists the best moments of a
  long take for a description (laughter, a cheer, a splash, fireworks) — candidates for picture beats; confirm each in
  the transcript or the picture (a talking head's breath can read as «a man laughing»).
- Taste stays ours: one kind of sound per kind of action, quiet, never a whoosh on every cut (`transitions.md` §0).

## Action reel sound
No music in the file — the user adds the track in Instagram (`inputs/action-reel.md`); the render is voices + a few SFX at −16 LUFS. Sound only where something happens: the hit on the drop, a beep, the power-down at the end; never the same whoosh on every cut (whips are silent). `make_sfx.sh` makes three variants of whoosh / softwhoosh / pop / hit and `R.sfx` cycles them. The punchline voices come from `actiongen.py` (dualmic's restoration), mastered by render.sh like everything else.
