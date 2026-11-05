# Input: raw camera takes (no edit)

Use for one-shot monologues, several takes of the same talk, over-the-shoulder footage, acting/mocap takes — anything from the camera that nobody has cut yet. Claude proposes the cut; the user approves it.

1. **Look first.** `python3 -I $S/inventory.py <project> <clips or folders>` → table (duration, orientation, sound level, notes) + `camera.jpg` with one graded frame per clip. Classify each clip: talking head, b-roll, acting, unusable.
2. **Map the speech.** `work/pkvenv/bin/python -I $S/transcribe_parakeet.py <clips with sound>` → `work/pk/c<id>.json` (≈50× realtime, clean in pauses; drop short English lines on silent clips). Use what the machine has: Parakeet when `deps.py` lists `env pkvenv` (the Handy app's model is there, `setup_env.sh` converted it), otherwise the first pass is `transcribe.py --sources` (Whisper) — never download an ASR model just for this. Whisper stays for exact cut seconds and for the captions on the timeline. Read it like an editor: who says what where, which takes repeat a point, what the ending is.
3. **What can be made of it.** Count the usable speech: up to ≈ 2:30 is one reel; more is a series (`inputs/series.md`) or a reel plus shorts. Offer the options with lengths, then **propose the structure** to the user: chapters, the source ranges (clip + seconds) for each, the ending, what is left out. For a series, write it into `PLAN.md` (`inputs/series.md`). Wait for the OK.
4. **Exact words and boundaries.** `$S/voice_isolate.sh <project> <takes…>`, then `work/venv/bin/python -I $S/transcribe.py --sources <takes…>` → `work/new/c<id>.json` (or `pk2whisper.py` for a plan-only pass). Measure real pauses with `python3 -I $S/pauses.py work/voice/out/c<id>_DeepFilterNet3.wav <start> <dur> [thr_db] [min_s]`; cut at the pause, about 0.1 s before speech and 0.15 s after.
5. **The plan.** `work/plan.json`:
   ```json
   {"files": {"0171": "/abs/DJI_…_0171_D.MP4", "0137": "/abs/DJI_…_0137_D.MP4"}, "words": {"0171": "work/new/c0171.json"},
    "voice": {"0171": "work/voice/out/c0171_DeepFilterNet3.wav"}, "exact": true,
    "plan": [["0171", 156.10, 164.50, "cold open", {"audioFadeIn": 4}],
             ["0137", 28.0, 34.0, "silent wide shot tail", {"transition": "whip", "mute": true, "punch": 1.0}]],
    "broll": ["work/broll/DJI_…_0141b_D.MP4"]}
   ```
   Options per range: `exact`, `transition: "whip"` (only where the speaker changes place or topic), `audioFadeIn` (frames, when a cut lands inside a word), `mute` (a picture-only segment; always exact, needs no transcript), `punch` (framing scale; `gen_timeline.py --punch 1.2` for small figures in wide shots), `cropX` (the 9:16 crop centre of a landscape clip, 0–1 of its width, or `[from, to]` for a pan — only where `people_zones.py` picked the wrong person). `amb` (a picture beat with the camera's own sound under it, via voice_mix.py), `raw` (camera sound instead of the cleaned voice), `speed` (≥ 1 for picture beats), `snap: false` / `gaps: true` (no sentence growth / no pause split for this range). Plan-level `lead`, `tail`, `snap` (default on), `splitPauses`, `splitWindows`, `canvas` — see `cut_from_transcript.py --help`. Only the takes the plan uses become sources (unused takes are not encoded).
6. `python3 -I $S/cut_from_transcript.py work/plan.json [--lut "$LUT"]` → `work/cutlist.json` + `work/bleeps.json` (swears snapped to the voice); an empty, backwards or sub-frame range stops it with `PLAN ERRORS` and nothing is written. Continue with the core pipeline: the takes are isolated already (step 4 here), so start at `match_loudness.py` when several takes or mics meet, else at people → crop (step 2).

Footage specifics:
- Long takes: proxies with `--trim-to-cutlist 2` encode only the used window. B-roll from the unused part: `--extra "<take>@<start>-<end>"` encodes just that window (muted; `BRoll` trims by `proxy_offsets.json`); a stream-copied snippet in `work/broll/` (`new_project.sh` creates it) works too — keeping the `DJI_` prefix keeps the LUT.
- Horizontal camera clips (`DJI_*` 3840×2160): `make_proxies.py` centre-crops them to 9:16 with the LUT; for another crop position grade and crop by hand into `work/broll/<name>.mov` (`lut3d=file='$LUT',crop=1215:2160:<x>:0,scale=1440:2560`) without the `DJI_` prefix.
- Acting / mocap takes shown next to their result: measure the moment of the action in every source (frames every 0.5 s) and set each window's `trimBefore` from it (`pitfalls/cut-and-timeline.md`, synced windows). Clip ids must be unique in a project: when two clips share a DJI counter, `ingest.py --camera link` gives the second link a `b` suffix.
- When asked to shorten: cut whole clauses at real pauses and list what was cut with timecodes in `NOTES.md`.
