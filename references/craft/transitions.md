# Seams and accents: how two shots meet

Read before giving any cut a transition (calm reels, vlogs) and before adding accents to an action reel. Built on
2026-11-09 from HeyGen HyperFrames, video-shotcraft and motionmaxxing (Apache-2.0, rules rewritten in our words), OpenMontage
(AGPL — ideas only) and Remotion's own packages; everything here was rendered on the user's footage before it went in.
Numbers: `numbers.md` «Seams». How a scene moves inside itself: `motion-design.md`.

## 0. The rule: alternate (the user, 2026-11-09 — non-negotiable)

«Слишком много переходов, вжух на каждое действие, миллионы RGB-сдвигов — получится ужасное видео. Видео нужно чередовать.»

- **Most cuts are plain**: the 7-frame dissolve on talking heads, a hard cut on the beat in an action reel. An effect seam is
  the exception that marks something — a new place, a new topic, the payoff, the drop. Write that reason in the plan note
  of the range; no reason → plain.
- **Budget** (checked by the generators, `SEAM BUDGET` / `FX BUDGET` lines — treat them as errors unless the user asked for
  more): calm reel ≤ `seamFxPerMin` effect seams per minute, ≥ `seamFxGapCuts` plain cuts between two of them; action reel
  ≥ `seamFxGapShots` plain shots between two accents (whips on phrase starts excepted); a kind never returns within
  `seamRepeatSec`; ≤ `transitionKindsMax` kinds per reel; one light leak; ≤ `rgbMax` RGB splits, ≤ `crashMax` crash zooms,
  ≤ `impactMax` full-frame impacts `impactGapBeats` beats apart.
- **Never**: a whoosh, whip or flash on every action; two effect seams back to back; a trick repeated as a pattern; an
  effect to "make it dynamic" — fake energy reads as cheap. Nothing bright: no white-out, no full-frame colour flash
  (flashes stay ≤ 0.45, the leak ≤ `seamLeakPeak`).
- When unsure, plain. A reel with three well-placed seams beats one with twelve.

## 1. Calm seams — the cut list's `"transition"` (plan.json opts of the incoming range)

| kind | what the viewer sees | use it for | sound |
|---|---|---|---|
| `dissolve` (default) | 7-frame cross-fade | every ordinary cut, jump cuts | none |
| `cut` | hard cut | stepped jump-ins (below), an intentional jolt | none |
| `whip` | slide out left / in from the right, blurred along the move | the speaker changes place or topic | none or a soft whoosh |
| `push` | the shot accelerates into a radial zoom blur, the next one keeps pushing in as the blur clears | «deeper into the same thought», into a detail, into the payoff | a soft whoosh at most |
| `blur` | defocus out, the next shot resolves from the same blur | a change of time («later that night»), a dreamy beat | none |
| `leak` | warm light drifts across the frame and hides the cut | a change of place in a warm vlog — once per reel | none |
| `wipe` | a soft-edged reveal sweeping right → left (the reel's current) | a list of places / days, a before → after | none |
| `bodywipe` | someone walking across the outgoing shot reveals the next one behind them | when a person (or a big object) crosses close to the camera | the crossing's own sound |
| `match` | the next shot starts moved and zoomed so the head lands where the previous head was, then settles | the same person in two places / outfits / times | none |

- `push` keeps the zoom moving the same way across the cut (motion-design.md «the sign of a zoom»); its blur is
  `@remotion/effects` `zoomBlur` on the video (WebGL, renders in the installed Chrome). `leak` is our own warm gradients at
  a capped opacity plus a lighter, flatter picture — Remotion's `lightLeak` preset fills the frame with solid yellow at its
  peak and is not used.
- `match` and `bodywipe` are measured from the picture: `gen_timeline.py` → `work/venv/bin/python -I $S/seams.py <project>`
  → `SEAMS_DONE` (Apple Vision: faces at the cut for `match`, the crossing person's trailing edge for `bodywipe`) →
  `gen_timeline.py` again. A match that needs more than `seamMatchMaxScale` zoom, or a crossing that is not one, falls
  back to a dissolve / plain wipe with a WARNING — pick another frame. For `bodywipe` put the cut on the frame the person
  ENTERS the shot; the outgoing clip keeps playing over the cut while they cross.
- Stepped jump-in (a calm accent on a strong line): split one range into three exact ranges with `"punch"` 1.0 / 1.3 / 1.6
  and `"transition": "cut"`, each step held ≥ 35 frames, the face as the pivot — steps under 1.25× read as a glitch, and
  2K proxies soften beyond ≈ 1.8×. Once per reel.

## 2. Sound bridges (J / L cuts)

`dialogue.py --bridge` (every cut between two different takes) or `"bridge": true` on a range: the outgoing scene's own sound
carries `bridgeTail` s under the next picture, the incoming one starts `bridgeLead` s early, at `ambDb`, never under a word.
The place changes in the ear a moment before or after the eye — the event vlog's scene changes stop feeling like a
slideshow. Use it on the hardest 3–5 scene changes of an event vlog (`event-vlog.md`), not on talking-head jump cuts.

## 3. Action accents (`actiongen.py` shot effects)

| effect | what | where |
|---|---|---|
| `bump=True` (+ `bumpAt`) | the shot pushes in `bumpScale` over `bumpFrames` with a 2-frame flash ≤ `bumpFlash` | a cut on a strong beat that needs a kick; not every beat |
| `crashAt=f`, `punch=[from, to]` | pull back 3.5 % (the wind-up), then a 6-frame ease-in push that lands ON frame f and stops dead | a reaction, the drop; ≤ `crashMax` |
| `rgbAt=f` | a `rgbFrames`-frame RGB split, `rgbPx` at its peak, fading out | on a hit only, ≤ `rgbMax`; never as a look |
| `stutterUntil=f` | the picture steps every `stutterStep` frames, real time from f | the last beat or two before the drop — each step must move visibly |
| `black=N` | N pure black frames after the shot | the cold-open bumper: 3 shots × 9 frames, each with `punch=[1, 1.04]`, then `black=6`, then the hook title |
| `hold=N, circle="auto"` | freeze (desaturated) + a hand-drawn marker loop around the biggest face | «вот он» — ≤ 2 per 30 s, hold ≥ 45 frames, one `shutter` sound |
| `shake=True` | `shakePx` with an e^(−t/`shakeTau`) decay, gone in ≈ 6 frames | the impact itself, on the same frame as the flash and the hit sound |

- **Pin accents to real hits**: `track_beats.py` writes the strongest kick / snare transients as grid `hits`; actiongen
  reports a flash / crash / RGB / shake more than 2 frames off the nearest hit. Cause and effect on one frame: flash, shake,
  stamp and sound start together — one frame apart reads as broken.
- **Paparazzi triple** (a group photo moment): the same instant as three shots cropped 1.0 / 1.4 / 1.8 (`punch`), cut after
  22 / 18 / 18 frames, `flashAt=0` + `sfx=[(0, "shutter")]` on each, then hold ≥ 70 frames. Once per reel.
- **Cut on motion**: actiongen's `STILL CUTS` line lists cuts where neither side moves — move the cut onto a movement or
  give the next shot `bump=True`.
- Busy hi-hats (the bar map's `hat`) leave room for small moves; sparse bars want the picture to hold still.

## 4. Taste rules (rewritten from motionmaxxing / video-shotcraft)

- **One belief per beat**: each beat must make the viewer believe one thing («the viewer now knows ___»); a beat that buys
  nothing is cut, not decorated.
- **One star per trick**: a technique stars once per reel; shine on one hero, not on every card.
- **Exits are new motion**, not the entrance played backwards; an exit is faster (`exitShare`).
- **Adjacent shots differ**: three cuts in a row with the same subject, the same scale and the same movement direction read as
  a loop — change one of them (a cutaway, a punch, the other camera).
- **Overlays**: 3–6 graphic overlays per minute of talking head, 3–5 s each; more is a slideshow over a face.
- **Lead the word**: a pop lands 0–2 frames before its word; a reveal that must be finished when the word is said starts
  ≈ 5 frames early; a seam starts 3–6 frames before the line ends.
- **Batches accelerate**: a group of items enters with shrinking gaps, then rests ≈ 0.5 s; identical timing reads as a
  slide deck.
- **No beat-locked camera**: a camera pulse on every beat reads as shake; pulse on the accents only.
- **Self-check**: describe each frame of the cut sheet in one sentence and ask «would this pass as a slide?» — and let a
  fresh reviewer (below) look, never self-certify.

## 5. Review the seams

- `work/venv/bin/python -I $S/motion_gate.py <project> <render.mp4>` → `MOTION_GATE_DONE`: `work/qa/cuts_NN.jpg` (frames cut−2 … cut+1
  of every cut), `FROZEN` stretches, the seam count. Look at the sheet: the eye should land where it was, something should
  move across a cut, no effect seam right after another.
- A **fresh reviewer** for the first full render: start a subagent with no production history — give it only the render, the
  cut sheet, the style brief and this file's §0 — and ask for findings as «timecode → what is wrong → why → fix», each
  citing a frame. Fix what is real; the user decides on taste calls.

## 6. Not used, and why

- Remotion's shader transitions (`crossZoom`, `filmBurn`, `ripple`, …) need `<HtmlInCanvas>` and a Chrome flag the
  installed Chrome (`remotion.config.ts`) does not have; `TransitionSeries` would fight the transcript-cut timeline.
- Glitch, tear, pixelate, checkerboard, starburst, film burn, venetian blinds, 3D cube on footage: dated and usually done
  badly. A 3D card flip is fine on a graphic card (a before → after) once; never on footage.
- `@remotion/noise` «living» motion and `CameraMotionBlur`: idle wobble and ×5–10 render time; `DirBlur` covers whips.
