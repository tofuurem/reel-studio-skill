# Sources and footage

Traps in camera files, colour, file names, screen recordings and crops. This file owns the LUT rule.

- **LUT (owner)** → Chrome cannot colour-manage, so log footage gets its LUT burned into the camera proxies. `make_proxies.py` picks it per clip: a `--lut-map` glob, else the DJI colour profile in the file's `djmd` track (Normal → none, D-Log / D-Log M → that camera's cube), else `--lut` / the draft's LUT. A folder or file name proves nothing about the camera: `python3 -I $S/common.py lut <clip>` prints the choice and its reason; on a mixed shoot read the LUT column of `inventory.py`. Files without the djmd track (re-encoded in Mimo) or a new DJI model fall back to a guess → set `--lut-map` (`"none"` for Rec.709 cameras). Action 4 D-Log M is unverified: check its first such clip. HLG / PQ sources get the `hdr_lut.py` cube automatically; in ad-hoc ffmpeg re-tag after `lut3d` (`setparams` bt709), or Chrome tone-maps a second time.
- **DJI files carry a second (preview) video stream** → every explicit mapping uses `-map 0:v:0` («Could not find tag for codec h264 in stream #1»).
- **DJI shoots 29.97 fps; `-r 30` duplicates a frame a second** — a visible hitch on slow pans. `make_proxies.py --extra` retimes b-roll itself; in ad-hoc ffmpeg use `setpts=PTS/1.001` + `-r 30 -fps_mode cfr` on muted b-roll. Speech clips keep the duplicate (sync first).
- **HEVC 10-bit sources** → H.264 yuv420p proxies. Pocket 3K is 1728×3072: 2K is a downscale, 4K an upscale.
- **Landscape camera clip on a 9:16 canvas** → `make_proxies.py` refuses to crop without `work/people_zones.json` (`people_zones.py --sheet`) unless `--centre-crop`. Look at `work/people/sheet_*.jpg`: in a static wide shot the biggest person is often not the action. Override a range with `cropX` in plan.json (`0.3`, or `[from, to]` for a pan).
- **External volume unmounted** (`capcut_export.py` warns, `make_proxies` exits 1) → stop and ask; never render black.
- **Sources in CapCut's temp folder** (`/var/folders/…/NSIRD_screencaptureui_*`) are unreadable → ask the user to put the screenshots into `assets/screens/`.
- **Long takes** → never proxy in full: `--trim-to-cutlist 2`; cutaways from unused parts via `--extra "<take>@<start>-<end>"`.
- **DJI counters repeat across days** (`_0005_` on two dates) → never key by the number; `clipid.py` aborts on a collision: `ingest.py --camera link` names the second `…_0005b_D.MP4`.
- **Non-ASCII names** (macOS «Запись экрана …», «Снимок экрана …») are NFD on external volumes; a pasted NFC path does not open → run `ingest.py` before any other script touches them (ASCII copies under `assets/`).
- **macOS screenshot / recording names contain U+00A0** (and U+202F before AM/PM) → regexes use `\s+`, not a literal space.
- **ffmpeg here has no `drawtext`** → no labels on tiles; keep the table order equal to the tile order.
- **Landscape screen recording as full-frame vertical** → pre-crop it (`crop=876:1558:<x>:0`) into `work/broll/` and pass that as `--extra`. macOS leaves Control Center and the cursor in the first ≈ 6 s: trim. Check any screen crop over time, not on one frame (a bubble appears later and gets cut; UI text at both edges needs `zoom 1.0`).
- **Voiceovers recorded in CapCut** → the draft holds the user's trims (`capcut_export.py --draft <name>` → audio tracks with `srcStart` / `dur`): they mark the good part of each take.
- **Night clips almost black after the LUT** → `night_lift.py`; re-run it after `make_proxies` re-encodes a clip (doctor warns).
- **No screen recording of an event** → record the public site with `site_capture.mjs` (`inputs/screens-and-images.md`). Check every used range for login codes, e-mails, card digits and phone notifications; cut them.
- **Session transcripts** (`~/.claude/projects/*/*.jsonl`) can hold passwords the user pasted → recreating a chat on screen, paraphrase and never render credentials; prefer the user's own screenshots.
