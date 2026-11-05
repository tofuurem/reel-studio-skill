# Motion design for boards and scenes (making it look directed, not templated)

Read before writing scenes for chapters, the cold open and the payoff. Distilled on 2026-10-21 from reading `vizavi_motion` v1.6.1 (a free claude.ai skill, text only) and tested on lofiroom ep2 (chapter «Tripo», `assets/examples/TripoStory.example.tsx`). The rules are rewritten for vertical reels and this user's taste: calm lo-fi tempo, smooth transitions, no blinking, quiet SFX.

## 1. One object carries the chapter
- Keep the hero on screen and change its *state* on each spoken beat instead of fading one board out and another in. In the Tripo chapter the picture is scanned into the 3D model in the same box, the model moves aside for the price, slides right for the comparison and comes back to be inspected — one figure, five states.
- Show a property **on the object**: an outline for "всё одним куском", a triangle mesh masked by the figure's alpha for "1,5 млн треугольников", a scan line for "из картинки получаешь меш". A fact card next to it only names what the viewer already sees.
- A board that only lists text rows is the fallback, not the default.

## 2. Plan the key scenes before coding
For the cold open, every chapter change and the payoff: write three short options that differ by action, composition or transition (a colour change is not an option), pick one, and fill a card:

| field | what to decide |
|---|---|
| meaning | the one thing this beat must say (the spoken clause) |
| state change | what the object was, what triggers the change, what it becomes |
| layers | background / floor / hero / labels / screen overlay |
| text | exact words, how they move (roll, count, land), reading window |
| camera | lean in on the detail being spoken, pull back for context |
| in / out | which object or position carries the cut from the previous scene and into the next |
| sound | which action gets a sound, and which sound |
| risk | what may break (alignment of two images, unreadable small text) and the frame to check it on |

Routine boards (a list, a screenshot) do not need the full card.

## 3. Camera and depth
- `scenes/Motion.tsx`: `<Camera cam={{x, y, s, r}}>` + `<Layer depth>`; depth 0 is a screen overlay (brand pill, fact cards), 0.35 background glow, 0.8 floor grid, 1 the hero plane, 1.15 labels near the hero. Moves are slow (`steps(..., {damping: 30, mass: 3})`) and never stop dead between two beats.
- Lean in (scale 1.05–1.13) while the detail is spoken, pull back to 1.0 for a new element, a slight roll (±0.6°) is enough to feel handheld. No constant shaking, no zoom on a flat board as the only motion.

## 4. Weight and timing
- `steps(frame, fps, initial, [[atFrame, target], …], cfg)` moves a value to each new target on its word; consecutive moves overlap (the next starts before the previous one settles) — this is what makes it feel animated instead of keyframed.
- Heavy things (figures, windows): `damping 16–17, mass 1.2–1.4`. Small things (pills, tags): `damping 11–13` with a little overshoot. Exits are faster than entrances.
- Numbers count (`countUp`, ≈16–26 frames, ease-out), labels roll (`RollPill`), price tags and fact cards land flat with a spring (`PriceTag`, `FactCard`) — the only rotated element is a `Stamp`. Text never just appears where it could act.

## 5. Transitions
- Prefer a hand-off: the same object at the same place, or the new scene opening from an element of the old one. A plain board cross-fade (12 frames) is for unrelated scenes.
- A whip or push only where the speaker changes place or topic; the user disliked harsh cuts — keep them rare.

## 6. Sound for motion
- Give different actions different sounds: a soft whoosh for a scan or a slide, `done` when a result lands, ticks while a number counts, `pop` for small marks (`<Sfx kind>` plays each at its level from `numbers.md`; `R.ticks(a, b)` spaces the ticks). The same pop on every chip reads as a template.
- The lo-fi bed stays 0.18 under speech; chapter starts may sit on a bar start of the bed when it does not shift the speech.

## 7. Review in motion
- After the first render, watch the scene at speed, then stills at every state change. Write notes as *interval → what is wrong → why → fix* and re-render only what changed.
- Check the decoded file: `glitch_scan.py` must print CLEAN (masks, `clip-path` and `drop-shadow` passed it on ep2).

## Two tempos: calm and action
The rules above are the **calm** profile: talking heads, devlogs, a lo-fi bed. An **action reel** (`inputs/action-reel.md`) is the other profile and turns several of them around:

| | calm reel | action reel |
|---|---|---|
| cut length | a clause, 2–8 s | 1–2 beats (≈ 0.5–1 s at 115 BPM), 2–4 s for a punchline |
| where cuts go | on pauses in the speech | on the track's beat grid (`track_beats.py`, `beats=` in actiongen) |
| transitions | 7-frame dissolve, a rare whip | hard cuts on the beat; silent whips (blurred along the move) on phrase starts |
| emphasis | lean-in camera, count-ups | speed ramp into the moment, slow motion, a hit + flash (≤ 0.45) + shake ON the drop, a freeze |
| sound | quiet SFX per kind of action | the track (added in Instagram) carries it; SFX only on events, no whoosh per cut |
| text | calm captions of everything | 2–4 punchline captions, a hook title, maybe one title behind a person |

- **Whips blur along the move only** (`ui/DirBlur.tsx`, an SVG filter): a CSS `blur()` smears in every direction and reads as a defocus. Clip.tsx and Action.tsx use it.
- **Title behind the person** (`scenes/BehindTitle.tsx`, `person_matte.py`): the word sits between the footage and a cutout of the same frames; the kicker stays in front. actiongen / reelgen place it just below the top of the person (the mask box), so the head covers the lower part of the letters and the word still reads. One per reel, on a shot where one person is big and fairly still — a crowd or a whip breaks it.
- **Speed ramps are pieces**, not playbackRate: 100 % → 40 % → 100 % of the same moment, cut at the source; slow pieces are motion-interpolated (`actionSlowmo`). The browser only repeats frames.

## What not to take from generic motion advice
- 60 fps landscape exports, nonstop camera movement, a motion-blur/DOF checklist on every shot, music cuts on every beat: they fight a calm talking-head reel (an action reel is the exception — see the table above). Use blur only on fast moves (`npx remotion add @remotion/motion-blur` in that project when a scene needs it — the template does not ship it), depth of field only when there is real depth.

## Learned on the birthday reel (2026-10-22)
- **Reaction cut on the spoken word.** When the speaker names something that is in another shot («фейерверки» → the wide pool), bring that shot in as a `BRoll` 4 frames before the word and let it run frame-continuously into the next timeline segment from the same clip (`trimBefore = segStartInProxy − (segStart − brollFrom)`): the timeline's own cut becomes invisible and the payoff lands on the word, not 1.5 s later.
- **Candles / clip-art objects read as childish**; a number lying on the real water as a squashed, masked, blurred reflection with three drifting highlights read as directed. Do not mirror digits — an upside-down «28» reads «58».
- **Shadow system, one per kind** (text over footage `0 2px 10px .6`, panels `0 20px 50px .35` + hairline border 8 %, bubbles and pills `0 8px 24px .3`), no glows, no tilt on landing pills, no emoji in UI text — this is what «тени и границы странные» meant. The template uses these values (`shadows` in `theme.ts`).
- **Payoff beats get their own frame**: «10 из 10» as a 132 px counter with the list dimmed, not a number in the header slot.
- **Empty panel ≥ 2 s is a bug**: anchor the answer header to the lead-in words («вот он дал мне чек-лист»), show «typing…» until then.
- One object can carry a whole reel, not only a chapter: the hero number lands as a title, parks as a badge, becomes a HUD number, rises above the head and ends as a reflection on the pool.
- Cues are LOCAL frames of the scene's Sequence everywhere (TripoStory was converted on 2026-10-22); the generator passes `R.L(word_frame, start)`.
