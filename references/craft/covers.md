# Covers

Few words: a white brand plate, a giant translucent episode number behind the hero, one word on a coloured plate. The hero carries the cover: a cut-out person or object with a soft shadow, or a contrast pair (the failed first version behind the good one, the user and the character in the same pose).

- Cut-outs: `work/venv/bin/python -I $S/cutout.py <frame or render> <covers>/public/covers/<name>.png --crop`; check the edge on a coloured background.
- Where: `<covers>` = `<project>/covers` for one video, `<series>/covers` for a series (`public/covers/` holds the cut-outs and plates, `src/` the source frames).
- Layout: `src/Cover.tsx` (`CoverFrame`, `Cut`, `Badge`, `FloorShadow`, `ArtCover` for generated plates); copy `assets/examples/Covers.example.tsx` to `reel/src/Covers.tsx`, set `brand` / the plate colours, and register each cover in `Root.tsx` as a `<Still id="Cover1" component={Cover1} width={W} height={H} defaultProps={{ guides: false }} />` (the commented block in the template's Root shows it). The word plate's default `wordTop` keeps it inside the 1:1 crop; text on the plate follows `inkOn(plate)`.
- Instagram shows the centre in the profile grid: 3:4 → y 240–1680, old 1:1 → y 420–1500. Faces and the word inside y 420–1500; the brand plate may sit at y 300.
- One background colour per episode of a series (night blue, coral, green …) so the grid reads as a set.
- Render: `$S/cover.sh <project> <covers>/public <abs out prefix> Cover1 Cover2 …` → 1440×2560 JPGs + a check sheet with both crops; look at the sheet before sending. `--public-dir` keeps the bundler from copying the footage; `cover.sh` copies the fonts into `<covers>/public/fonts` itself.
- Delivery: the JPGs are small enough for the phone; in Instagram the cover is set at publishing: «Обложка» → «Добавить из галереи».

## Covers on generated art (2026-10-22, birthday reel)
When the Codex CLI is set up (`deps.py`: `codex (covers)`), make generated covers too, not only cut-outs on flat colour, and offer the choice. `$S/codex_image.sh -o <dir> -n <name> [-r ref.png] [-t] "<prompt>"` prints the saved paths; one image ≈ 1 min; `codex CLI not found` / auth errors → `deps.py --install --with covers` and `codex login` (the user does that).
- Give a real frame of the reel as the `-r` reference (`covers/src/*.png`) and ask for a 9:16 plate **without text** (image models garble Cyrillic): the scene, the hero, the one object of the reel (a gold number standing in the pool, the bike lit at a night shop).
- Copy the result into `covers/public/covers/gen/`; keep prompts and variants next to it in `covers/gen/`.
- Lay the brand plate and the one word over it in Remotion with `ArtCover` (`src/Cover.tsx`, same typography as `CoverFrame`, a shade at the bottom for the word) and render with `cover.sh`.
- The same plate can close the reel (`Plate` in `scenes/Board.tsx`: full-bleed image with a slow push-in; `R.write(..., end_card=False)` when the plate is the ending) so the cover and the last frame match.
