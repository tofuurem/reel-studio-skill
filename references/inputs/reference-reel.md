# Input: a reel to learn the style from («сделай как тут», «вот так хочу»)

The user sends a link or a file of someone's reel (or their own earlier one) and wants the next video to feel like it. What is
taken is the **style** — rhythm, hook, framing, the caption rail, the loudness — measured, not guessed. The reference's
picture, sound, music, text, people, faces and logos never go into the user's video, and the video never mentions it.

1. **Get the file.** A link: `python3 -I $S/fetch.py <project> <url>` → `assets/refs/<name>.mp4` + `.source.json`
   (`--section 0:30-1:15` for a long video; `--as own` for the user's own published episode → `assets/refs/own/`). Instagram
   and some sites want a sign-in — the script says so: ask the user to download it themselves (the share menu, a screen
   recording) and drop it into `assets/refs/`. Never pass their browser cookies or passwords to yt-dlp. YouTube needs a
   working connection to Google (a VPN where it is throttled); an SSL «EOF» from yt-dlp while curl works is that.
2. **Measure.** `work/venv/bin/python -I $S/ref_analyze.py <project> assets/refs/<name>.mp4` → `work/refs/<name>/ref.md`,
   `ref.json`, `sheet.jpg` (≈ 20 s per minute on an M-series Mac). It lists every shot (hard cuts, short dissolves, dissolved jump
   cuts and the cutaways), the shot lengths, the hook, the
   framing per shot (Apple Vision faces), the on-screen text (OCR, ru + en): where the caption rail sits, letter height,
   words and lines per page, page length, ALL CAPS — and the loudness. Linux: no Vision → framing and text are skipped.
3. **Look.** Open `sheet.jpg` and watch the reference once at speed. Name what the numbers cannot: the transition kinds
   (a whip, a zoom, a hand-off — count them against `transitions.md` §1), the graphics (cards, stickers, a progress bar),
   the colour (warm / cold / contrasty), the music's role, the first sentence's shape.
4. **Write a style brief** into `NOTES.md` — 5–8 lines, each «reference → our knob»:

| reference measures | our knob |
|---|---|
| median shot < 1.6 s, cuts on the beat | the action profile (`inputs/action-reel.md`, `motion-design.md` «Two tempos») |
| median shot 1.6–3.5 s, jump cuts | `plan.json`: one clause per segment, breaths cut, `gen_timeline.py --punch` on the jump cuts |
| median shot > 3.5 s | the calm default (2–8 s per clause), cutaways carry the change |
| cuts in the first 3 s, text from the first second | the cold open (`storyboard.md`): a hook title or a `BehindTitle` from frame 0 |
| close-ups most of the time | `--punch` 1.2–1.35, close-ups get `Stage` / `SplitStage` instead of cards |
| caption rail y, letter height, words per page | `numbers.json` «Captions» (`capMaxWords`, `capFontPx`, `capBottomPad`) — inside the safe zones of `layout-rules.md` |
| ALL CAPS / word highlighting | caps are possible in a new caption preset; per-word highlighting is not (non-negotiable) — say so |
| a loudness far from −16 LUFS | ours stays −16 LUFS (platforms normalise); a quieter or louder reference is not a target |

5. Confirm the brief with the user in one message before building («беру ритм и подачу, не беру музыку и графику»), then
   continue with the entry for the user's own material (`SKILL.md` §1).

A whole series «in the style of» is the same brief kept in the series' `PLAN.md`. Never rebuild someone's video shot for shot
(that is copying, not style), never reuse their music, and never imitate a specific creator's face, voice, name or branding.
