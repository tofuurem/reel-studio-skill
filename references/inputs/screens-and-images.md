# Input: screen recordings, screenshots, images, renders

They are pictures, not speech; they arrive with every other kind of project.

**Bring them in with safe names:** `python3 -I $S/ingest.py <project> <folders…> --dry-run`, check the mapping, then without `--dry-run`. macOS names carry U+00A0 / U+202F and NFD letters (Russian and English «Screen Recording … at …» names both work), the external volume has `._name` sidecars next to every file, HEIC photos do not show in Chrome — `ingest.py` handles all of it (HEIC → JPG) and logs the mapping in `assets/ingest_log.json`. Other video lands in `assets/video/`. Then `inventory.py` for the sheets (rotation and VFR are flagged).

**Screen recordings**
- Silent ones (`inventory.md` says "no sound") are never transcribed.
- 120 fps recordings are fine as `--extra` b-roll (retimed to 30); `--extra rec.mov@12-20` encodes just that window. The proxy of `work/broll/rec_x.mov` is `footage/crec_x.mp4` (`clipid.py`: `c` + ASCII basename).
- A landscape recording is shown either in a `Win` on a board (the proxy keeps its aspect at canvas width) or as a full-frame vertical: pre-crop it into `work/broll/<name>.mov` (`crop=<w>:<h>:<x>:<y>`, `-r 30`, crf 15). For a small UI detail pre-crop just that region. Check the crop over time — menus and the cursor sit in the first seconds, speech bubbles pop above characters later.
- Recordings of Claude Code / Codex sessions can show keys and passwords: look at every frame range you use; paraphrase instead of showing a secret.

**Images and renders** (from the user's game or app repo, Codex sheets, Blender renders)
- Copy into `reel/public/screens/` with short names; crop with ffmpeg into the part you show.
- Facts written on screen come from the files (docs, configs, counted files) — note the source of each in `NOTES.md`. When docs and files disagree, count the files. A research subagent may collect facts with file:line references; re-check the ones you put on screen.
- Floating heroes: `work/venv/bin/python -I $S/cutout.py <in> <out.png> --crop` (macOS subject lifting) → RGBA PNG for `Figure` / `ScanSwap` / covers.
- GIFs become video for windows: `ffmpeg -stream_loop 5 -i x.gif -vf "scale=1200:-2:flags=lanczos,fps=30" -t 14 -c:v libx264 -crf 15 -pix_fmt yuv420p work/broll/x.mov`, then `--extra`.
- Pictures from the internet (a store page, an official artwork) only with the user's OK; say where each one came from.

**3D models, rigs, FBX** are not rendered by this pipeline; show them through the user's recordings or renders.

Traps: `pitfalls/sources-and-footage.md`.
