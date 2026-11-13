# Render and QA

Traps in Chrome rendering, the 2K pass and QA habits.

- **2K** → the `Reel2K` composition (CSS ×4/3) with `REMOTION_FOOTAGE_DIR=footage2k` (`render.sh` sets it; ad-hoc stills need it too). A 2K-only intake has no 1080 proxies: `doctor.py --comp Reel2K`.
- **16:9 video** → write `"canvas": "16:9"` into `work/intake.json` before `scaffold.sh` (it sets W/H in theme.ts) and before `cut_from_transcript.py` (it writes the cut list's canvas); a later change → re-run both. Reel2K renders 2560×1440. Set `punchCenterY` ≈ 430 in the project's `numbers.ts` (the default 730 is for 1920-high frames); captions switch to the wide layout themselves.
- **Renders time out with «Waiting for root component to load»**; even `chrome-headless-shell --dump-dom` hangs at 0 % CPU with `CVDisplayLinkCreateWithCGDisplay failed` → macOS has a virtual display (Screen Sharing in high-performance mode, DisplayLink, Sidecar; `system_profiler SPDisplaysDataType`). The headless shell never draws; installed Google Chrome works (the template prefers it). Kill stuck shells: `pkill -9 -f chrome-headless-shell`.
- **Keep the Mac awake** during long renders (`caffeinate -dis`); a sleeping display stalls Chrome.
- **Single-frame dropouts** (a card's text or panel missing for one frame) → never `backdrop-filter` or `mix-blend-mode` (each promotes a compositor layer; `lint_reel.py` fails on them): solid rgba panels, opacity gradients for light. Keep `gl: "angle"` (swiftshader drops stamps every other frame) and `CONC=1` (four tabs are not faster and drop frames). Read `glitch_scan.py`'s verdict on the final file before delivering.
- **Stills or a render while `make_proxies` runs** → a proxy not there yet is a 404 mid-render: wait for `PROXIES_DONE`.
- **`@remotion/effects` on a `<Video>`** → an effect added mid-clip (`effects` going from `[]` to `[zoomBlur]`) is never drawn: keep it mounted from the first frame with `disabled: true` until needed. A single `npx remotion still` can show what the sequence render lacks: check effects with `render --frames`.
- **Remotion's `lightLeak` preset** goes solid yellow at its peak → use the `leak` seam.
- **QA before the full render** → contact sheets (`qa_sheet.sh`) at the cold open, each chapter tag, each card mid-animation, every b-roll in/out and the outro, against `face_zones.json`. After the render: loudness, glitch scan, a few frames of the final file.
- **Censor blur misses a face half out of frame** (the hand tracker loses it) → check every frame where a hand meets the mouth and fill the gap with a `box` job.
- **`motion_gate.py` FROZEN on an event vlog** is mostly tripod shots of people talking — designed, not dead.
