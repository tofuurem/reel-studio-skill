# Audio

Traps around the voice, loudness, bed and bleeps. The chain, its never-rules and its numbers are owned by `craft/audio.md`.

- **Ad-hoc loudness fix** → measure integrated LUFS, then a static `volume=XdB` + `alimiter=…:level=false`. Never single-pass `loudnorm` (pumps the bed in every pause); `alimiter`'s default `level=true` lifts the output ≈ 1.5 dB.
- **`render.sh` loudness** → read its `measured I=… → final …` line; `LOUDNESS OFF TARGET` fails the render.
- **`make_proxies` prints `NOTE: no isolated voice for …`** → those proxies carry camera sound: run `voice_isolate.sh` on them and re-run.
- **Music**: nothing licensed on the machine (no Apple Loops; CapCut cache tracks are CapCut-only). Offer the user's own track first; the procedural `make_bed.sh` bed is recognisable across videos — a different preset each time. Bed level → `craft/audio.md`.
- **ffmpeg `sine` peaks at ≈ −21 dBFS**, not 0 → in ad-hoc beeps, set the gain by measured peak. `bleep.py --gain` is the true peak; check `astats` Peak inside a bleep window after any change.
- **The same whoosh on every cut** → sound marks events only: `craft/transitions.md` §0.
- **Bleeps** → after every cut read the bleep list against the transcript. A missed or wrongly caught word → extend `swear.py` (owner: `craft/captions.md`).
- **`ffmpeg -ac 1` on a lav sent to both channels adds +3 dB** (false «clipping» in analysis) → average the channels (`voicelib.read` does).
- **A picture beat from source second 0 of a cleaned clip** → DeepFilterNet leaves ≈ 0.6 s of silence at the file start: begin the beat at ≥ 0.7 s.
- **Picture beats with no voice** → mark them `"amb"` in plan.json so `dialogue.py` plays the camera sound. `audio_qa.py` lists digital silence inside the speech: read it — a wireless-mic dropout with no packets cannot be recovered, cut around it.
- **Remotion writes PCM only into `.mov` / `.mkv`** (`--audio-codec=pcm-16` with an `.mp4` name fails).
- **Two files whose names differ only in case** (`dialogue.ts` next to `Dialogue.tsx`) break `tsc` on macOS → pick another name (`dialogueSrc.ts`).
- **«Гудит», «эхо», a voice drifting inside a take** → `work/voice_tune.json` (`craft/audio.md`), only after a 30-s A/B (`craft/ab.md`).
