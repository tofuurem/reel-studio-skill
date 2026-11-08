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
   - the report shows what the cleanup did to the voice (1/3-octave transfer over the speech frames); a band moved > 2 dB is a WARNING — listen, lower `--atten-lim-db`.
   - `--lav <folder|wav…>`: the DJI transmitter's own 32-bit float recording replaces the camera track (found and synced by cross-correlation, clock drift resampled; uncovered parts keep the camera track). Use it whenever the user has the TX files: it skips the radio link, the receiver's processing and one AAC encode.
   - Two lavs on the camera's L/R: `dualmic.py` instead (each mic restored alone, then automixed — below).
   - Never: ffmpeg `afftdn`, `agate`, `anlmdn` — rejected after listening.
2. **Proxies** carry the restored voice (`make_proxies.py --voice-dir work/voice/out`) — for Studio scrubbing and Whisper; the render does not use their sound.
3. **Dialogue stem** — after `gen_timeline.py`: `work/dfvenv/bin/python -I $S/dialogue.py <project>` → `reel/public/audio/dialogue.wav` (48 kHz 24-bit, timeline time), `reel/src/dialogueSrc.ts` (`DIALOGUE`: `Clip` mutes the proxies, `<Dialogue />` plays the stem; `reelgen.write` places it), `work/voice/dialogue.json` (`DIALOGUE_DONE`). Any re-cut → re-run (doctor.py says when it is stale). What it does:
   - **assembly** on the cut list's frames: each segment's source range from the restored voice, with handles; every jump cut gets an equal-power crossfade of `cutXfadeMs` (no click, no hole), two segments continuing one take a `joinXfadeMs` linear join; speed changes time-stretched like Remotion (`atempo`); `audioFadeIn` honoured; CapCut voiceovers placed where the draft put them;
   - **levels**: each take's active speech to `voiceTargetDb` (≤ `voiceMaxGain` up), each segment nudged into [`voiceSegLo`, `voiceSegHi`] (± `voiceSegMax`); `"amb"` segments add the camera's own sound at `ambDb` kept out from under every word, `"raw"` ones use the camera sound at `rawDb` instead of the restored voice;
   - **room tone**: gaps and muted slivers between the first and the last word get the quietest stretch of the neighbouring take, looped — never digital silence;
   - **one chain** over the whole stem (`voicelib.voice_chain`): high-pass `hpfHz` + phase rotator (lowers the lopsided speech peaks ≈ 2.5 dB, spectrum unchanged) → measured cuts at 315 Hz (mud) / 900 Hz (box) → ONE soft-knee compressor (`compOverDb` over the leveled speech, `compRatio`, `compWindowMs` RMS) → measured presence (3.5 kHz) / air (9 kHz shelf) → de-esser (dynamic cut at 6.5 kHz, only on dominant sibilants) → static gain to `stemLufs` → look-ahead limiter at `stemPeakDb`. The EQ moves are bounded (`eqMaxCut`, `eqMaxBoost`, `eqMaxAir`) and correct `eqAmount` of the measured deviation from the target speech spectrum (LTASS + a little presence and air) — the speaker keeps their timbre;
   - **bleeps** from `work/bleeps.json` go into the stem (word muted, soft boop); `bleep.py` on the render is then a no-op;
   - `--keep-raw` writes `work/voice/dialogue_raw.wav` (assembly + levels, no chain) for an A/B by ear.
4. **Mix in Remotion**: `<Dialogue />` at volume 1; the bed via `MusicBed` (0.3 in the cold open, wordless pauses and the tail, 0.18 under speech ≈ 20 LU down, short ramps, an end fade — `reel/public/audio/lofi_bed.wav` from `make_bed.sh <project> [seconds] <preset>`, or the user's track: `ffmpeg -i assets/music/<track> -ar 48000 -c:a pcm_s16le reel/public/audio/lofi_bed.wav`). SFX: `Sfx kind="tick|pop|done|whoosh|softwhoosh"` from `make_sfx.sh` (WAV, synthesised locally), one kind of sound per kind of action, levels in `numbers.md`. Music beds: `lofi.py` presets warm / night / bright / dusk, a different one per video. Everything stays PCM until the end.
5. **Master** (`render.sh`): Remotion renders the sound as PCM (`--audio-codec=pcm-16`, a `.mov` intermediate); then the integrated LUFS of the whole mix → a static gain to `targetLufs` → a 4× oversampled limiter at `truePeakDb` (a true-peak limiter; `level=false`) → the ONLY AAC encode (`aac_at`, Apple's encoder, when ffmpeg has it), `aacBitrate`. One corrective pass if > 0.2 LU off; the render fails beyond ±`lufsTolerance`. Never single-pass `loudnorm` (dynamic: pumps the bed in every pause).
6. **QA** — `audio_qa.py <file> --project <dir>` (render.sh runs it; warnings only): loudness, LRA in [`lraMin`, `lraMax`], true peak, digital silence inside the speech, pause floor under the speech, spectrum vs the target shape (mud / presence / air), tonal noise in the pauses (insects, hum), clicks at the dialogue cuts, codec and bitrate. Read the line before delivering. If the user says "music too loud", halve the bed (`R.music_bed(under=0.09)`), never touch the gain.

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

## Action reel sound
No music in the file — the user adds the track in Instagram (`inputs/action-reel.md`); the render is voices + a few SFX at −16 LUFS. Sound only where something happens: the hit on the drop, a beep, the power-down at the end; never the same whoosh on every cut (whips are silent). `make_sfx.sh` makes three variants of whoosh / softwhoosh / pop / hit and `R.sfx` cycles them. The punchline voices come from `actiongen.py` (dualmic's restoration), mastered by render.sh like everything else.
