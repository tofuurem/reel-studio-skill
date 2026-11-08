# Blocks: ready-made motion pieces (`reel/src/blocks/`)

Six components for devlog beats that keep coming back: code that changes, code being written, a list of repositories, incoming notifications, a name plate, a before/after. The ideas (timing, layout) come from HeyGen's HyperFrames registry (Apache-2.0: `registry/blocks/code-diff`, `code-typing`, `x-post`, `notification-cascade`, `macos-notification`, `lt-mask-reveal`, `lt-kicker-name`, `lt-clean-bar`, `registry/components/before-after-wipe`). They are rewritten as Remotion components driven by frames: no GSAP, no CSS animations, no vendor logos. HyperFrames itself is not part of the pipeline.

Same conventions as the rest of the kit (`src/README.md`): cues are LOCAL frames of the Sequence (`R.L(word, start)`), `at` = lands, `until` = starts leaving (default: the last 8 frames of the Sequence, so a block placed with `rg.seq` leaves on its own), `x`/`y` = left/top in 1080-wide coordinates (`Reel2K` scales everything by 4/3), colours from the palette. Defaults: `x = safe.x`, `y = N.bandTop` (300), `w = 952`. Entrances are springs (heavy: damping 16, mass 1.3; small: damping 12), exits 8 frames, a group of items lands within 15 frames unless each item has its own `at`.

`BlocksDemo` (registered in `Root.tsx`) shows all six; render a still to see one: `npx remotion still BlocksDemo /tmp/x.png --frame=120`.

| block | use it when the speaker… | props |
|---|---|---|
| `CodeDiff` | says what changed in the code («добавил премаунт», «убрал лишний вызов») | `before`, `after` (strings), `file`, `lang` (`ts`/`py`/`sh`), `size` (≥ 30, default 32), `at`, `delAt` (default at + 20), `addAt` (default: as the removed lines start collapsing, so rows swap in place), `keepRemoved`, `x`, `y`, `w`, `until` |
| `CodeTyping` | writes or dictates a snippet, or a beat needs "this is the line" | `code`, `file`, `lang`, `size`, `at`, `typeAt` (default at + 14), `cps` (30 = a character per frame), `linePause` (4), `maxLines` (scrolls with the caret), `caretHold` (24), `x`, `y`, `w`, `until`; `typingFrames(code, cps, linePause)` = the length of the typing |
| `RepoCard` / `RepoList` | names tools or repositories, «у каждого столько-то звёзд» | card: `owner`, `name`, `desc?`, `stars`, `lang?`, `langColor?`, `at`, `starsAt` (default at + 6, counts 22 frames), `short` (31.2k), `dim`, `pick`, `x`, `y`, `w`, `until`; list: `items` (`{at, …Repo}`), `gap` (18), `pick` + `pickAt` (rim on one card, the others fade back), `short`, `at`, `until`; `repoCardH(r)` = 222 with a description, 166 without |
| `Notify` / `NotifyStack` | «прилетает уведомление», a build finishing, messages piling up | note: `app`, `title`, `text?` (≤ 2 lines), `time?`, `icon?` (a letter), `iconBg?` (palette token); `Notify` adds `x`, `y`, `w`, `at`, `until`; `NotifyStack`: `items` (`{at, …Note}`), `order` (`top`: the newest lands on top and pushes the others down; `bottom`: appends), `max` (4, older ones fade as they are pushed past it), `gap`, `at`, `until`; `notifyH(note, w)` |
| `LowerThird` | introduces themselves or a guest in a talking-head shot | `name`, `kicker?`, `variant` (`mask`: accent sweep over the name, kicker pill rises; `bar`: dark plate with an accent tab), `x`, `y` (default 1130: under a medium-shot face, above the captions), `size` (shrinks to fit), `accent`, `at`, `kickerAt` (default at + 10), `until` |
| `BeforeAfter` | compares two states of the same thing (old / new UI, raw / graded, slow / fast) | `a`, `b` (image path under `public/` or JSX), `labelA` («До»), `labelB` («После»), `x`, `y`, `w`, `h` (952), `fit`, `at`, `wipeAt` (default at + 12), `wipeFrames` (32), `rest` (0.5; 0 = all "after"), `moves` (`[[frame, pos], …]`), `until` |

## Placing them from `work/gen_reel.py`
```python
import reelgen as rg; from reelgen import tag, js
a = R.fw("добавил"); b = R.fw("рендер", after=a); t = R.fw("премаунт", after=a)
top, bottom = R.free_bottom(a, b)               # over a talking head: the face-free band
body += [
    rg.seq(a - 6, b + 20, tag("CodeDiff", file="scripts/reelgen.py", lang="py", before=OLD, after=NEW,
                              y=top, at=0, addAt=R.L(t, a - 6)), "diff · premount"),
    rg.seq(r0, r1, tag("RepoList", short=True, items=[
        {"at": R.L(R.fw("remotion", after=r0), r0), "owner": "remotion-dev", "name": "remotion", "stars": 71559, "lang": "TypeScript",
         "langColor": js("colors.accent2")},
        {"at": R.L(R.fw("ffmpeg", after=r0), r0), "owner": "FFmpeg", "name": "FFmpeg", "stars": 66723, "lang": "C"},
    ]), "repos"),
    rg.seq(R.seg(0) + 20, R.seg(0) + 110, tag("LowerThird", name="Алексей", kicker="разработчик · lofiroom", at=0), "lower third"),
]
```
Code goes in as plain Python strings (`before`, `after`, `code`): `tag()` puts any multi-line string into braces (`{"…\n…"}`) — a plain JSX attribute would keep `\n` as a backslash and an n.

`R.write` finds the blocks by their `export const` like any scene (it walks all of `reel/src`, `blocks/` included). Inside a `R.board(...)` the blocks sit on the board like `Win`; over a talking head pass `y=top` from `R.free_top` / `R.free_bottom` and check the block's height against the band (`repoCardH`, `notifyH`, code: 76 + 48 + lines × 1.5 × size).

## Rules of thumb
- **Code is short.** At size 32 a line holds ~40 characters, at 30 ~44; 5–8 lines per window. Cut the snippet down to the lines being spoken about; a long file is a screen recording, not a block.
- **Anchor every item to its word.** List items without `at` land as one group (≤ 15 frames). A cascade (`NotifyStack`) reads as events only when the arrivals are ≥ 12 frames apart.
- **Lists fit the band:** 4 repo cards with descriptions or 5–6 compact ones in y 300–1350; 3–4 notifications.
- **One accent move per block:** the strike-and-collapse, the caret, the star count, the sweep. Do not stack a Stamp or a Pill on top of a block.
- **Sound:** a `softwhoosh` on a BeforeAfter wipe or a LowerThird, `pop` on each notification, `tick`s while stars count (`R.ticks`), `done` when a diff's added lines land.
- `LowerThird` `mask` is white text straight over footage (with `shadows.text`); over a busy or bright shot use `bar`.
