# Pitfalls — index

Traps the scripts cannot catch for you, grouped by area in `references/pitfalls/`. Read the file of the area you are about to touch.

| file | covers |
|---|---|
| `pitfalls/sources-and-footage.md` | the LUT rule, DJI streams and 29.97 fps, HEVC, landscape crops, external volume, NFD / U+00A0 names, screen recordings, CapCut voiceovers, night clips, secrets on screen |
| `pitfalls/cut-and-timeline.md` | the user's edit is final, cutaways at cuts, cold open, exact cut points, whole scenes, punch, synced windows |
| `pitfalls/audio.md` | ad-hoc loudness, bleeps, music, mono downmix, DeepFilterNet start silence, picture beats, PCM container |
| `pitfalls/captions.md` | GigaAM vs Whisper on silence, dropped words, word-end accuracy, misreads, `replace_at` windows |
| `pitfalls/layout-and-graphics.md` | glyphs, text width, `interpolate` clamps, contrast, close-up split, behind-title stacks, facts |
| `pitfalls/render-and-qa.md` | Reel2K, 16:9 setup, virtual-display Chrome hang, single-frame dropouts, proxies mid-write, `@remotion/effects`, QA habit |
| `pitfalls/environment-and-shell.md` | zsh globs and modifiers, `pgrep`, background jobs, disk space, Remotion pins, `coverage/`, `python3 -I`, exFAT, AppleDouble `._*`, yt-dlp |

Add an item only when it changes what the agent does: one "symptom → action" line in the right file, no dates or production names. A bug a script now prevents by itself needs no item.
