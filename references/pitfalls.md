# Pitfalls — index

The traps are grouped by area in `references/pitfalls/`. Read the file of the area you are about to touch; on a first run in a new kind of material read the sources and cut files completely.

| file | covers |
|---|---|
| `pitfalls/sources-and-footage.md` | DJI files and LUT, HDR (HLG / PQ) phone clips, external volume, 29.97 → 30, screen recordings, AppleDouble files, U+00A0 / NFD names, horizontal camera clips, voiceover files from CapCut, crops over time |
| `pitfalls/cut-and-timeline.md` | the user's edit is final, cutaway coverage, transitions, exact cut points, voiceover carriers, boards at cuts, synced windows, punch, whole scenes, mid-sentence cuts, beat grids |
| `pitfalls/audio.md` | DeepFilterNet, static loudness, music bed, bleeps and the swear matcher, levels between takes, lav crackle, two mics, SFX repetition |
| `pitfalls/captions.md` | caption pages and the soft swap, Whisper hallucinations and dropped words, voiceover misreads, Parakeet vs Whisper |
| `pitfalls/layout-and-graphics.md` | people-aware crop, face zones, safe areas, stamps, fonts, close-up split layout, board content band, facts on screen |
| `pitfalls/render-and-qa.md` | Reel2K, single-frame dropouts, GPU / virtual display, temp bundle loss, stills while proxies are written, QA habit, `@remotion/effects` on video |
| `pitfalls/environment-and-shell.md` | project folder = session folder, external exFAT volumes (node_modules, `._*` files), setup_env, scaffold order, zsh globs and modifiers, background jobs, disk space, Parakeet weights, `coverage/` folder, `python3 -I` on the iCloud Desktop, yt-dlp behind a filter |

When you hit a new trap, add one bullet to the right file: what happened, why, the fix, the date and the production.
