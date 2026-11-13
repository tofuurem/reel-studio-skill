# Input: screen recordings, screenshots, images, renders

They are pictures, not speech; they arrive with every other kind of project.

**Bring them in with safe names:** `python3 -I $S/ingest.py <project> <folders…> --dry-run`, check the mapping, then without `--dry-run`. macOS names carry U+00A0 / U+202F and NFD letters (Russian and English «Screen Recording … at …» names both work), the external volume has `._name` sidecars next to every file, HEIC photos do not show in Chrome — `ingest.py` handles all of it (HEIC → JPG) and logs the mapping in `assets/ingest_log.json`. Other video lands in `assets/video/`. Then `inventory.py` for the sheets (rotation and VFR are flagged).

**Screen recordings**
- Silent ones (`inventory.md` says "no sound") are never transcribed.
- 120 fps recordings are fine as `--extra` b-roll (retimed to 30; windowed extras: `inputs/raw-takes.md`). The proxy of `work/broll/rec_x.mov` is `footage/crec_x.mp4` (`clipid.py`: `c` + ASCII basename).
- A landscape recording is shown either in a `Win` on a board (the proxy keeps its aspect at canvas width) or as a full-frame vertical: pre-crop it into `work/broll/<name>.mov` (`crop=<w>:<h>:<x>:<y>`, `-r 30`, crf 15). For a small UI detail pre-crop just that region. Check the crop over time — menus and the cursor sit in the first seconds, speech bubbles pop above characters later.
- Recordings of Claude Code / Codex sessions can show keys and passwords: look at every frame range you use; paraphrase instead of showing a secret.

**A website URL instead of a recording** (a product landing page)
- `node $S/site_capture.mjs <project> <url> [--name site]` → `work/broll/<name>_hero.mp4` (the page loading from blank plus its own animations), `<name>_scroll.mp4` (an eased scroll, only when the page scrolls), `work/site/<name>_hero.png` / `<name>_full.png`; `SITE_CAPTURE_DONE`. Headless Chrome with a throwaway profile, CDP screencast frames with their own timestamps → CFR 30 fps by `frames2mp4.py`, 2560×1440 by default (a 16:9 Reel2K needs no upscale); a vertical reel records the mobile site with `--size 430x932 --scale 3 --mobile`. Frames stay in a temp folder on the internal disk.
- Public pages only: never sign in, type into forms or capture a cabinet behind a login — the user's own recording or screenshots carry those. Say in the hand-off that the page was recorded on the render day (it may differ from what the people in the video saw).
- Show it framed, not as a bare full frame: a browser window on the palette background (address bar with the domain, slow push-in, the page's content column scaled ≈ 1.6× from the top so its headline reads — a 1920-wide page has wide empty margins). Pick the palette from the page itself (sample the background and the button colour from `<name>_hero.png`).
- Then `make_proxies.py … --extra work/broll/<name>_hero.mp4` (non-DJI extras keep their aspect, no LUT); the proxy is `footage/c<name>_hero.mp4`.

**Images and renders** (from the user's game or app repo, Codex sheets, Blender renders)
- Copy into `reel/public/screens/` with short names; crop with ffmpeg into the part you show.
- Facts written on screen come from the files (docs, configs, counted files) — note the source of each in `NOTES.md`. When docs and files disagree, count the files. A research subagent may collect facts with file:line references; re-check the ones you put on screen.
- Floating heroes: `work/venv/bin/python -I $S/cutout.py <in> <out.png> --crop` (macOS subject lifting) → RGBA PNG for `Figure` / `ScanSwap` / covers.
- GIFs become video for windows: `ffmpeg -stream_loop 5 -i x.gif -vf "scale=1200:-2:flags=lanczos,fps=30" -t 14 -c:v libx264 -crf 15 -pix_fmt yuv420p work/broll/x.mov`, then `--extra`.
- Pictures from the internet (a store page, an official artwork) only with the user's OK; say where each one came from.

**3D models, rigs, FBX** are not rendered by this pipeline; show them through the user's recordings or renders.

Traps: `pitfalls/sources-and-footage.md`.
