# From transcript to storyboard (the creative pass)

**0. Style first** (`styles.md`). Before marking anything, offer the user 2–3 styles that fit this material — one line
each: what the viewer sees and what it needs ("calm — captions, cards, your own cutaways", "comic — 3–4 drawn panels with
your own lines, plates generated from real frames", "real footage — we show the game itself, someone else's clips with the
author credited, if you say yes"). The default is calm (and the previous video's style for "same as last time"). Not sure
which works → build ONE beat (the hook or the key claim, 4–10 s) in each style with a `STYLE` switch in `gen_reel.py`,
`$S/render_part.sh` per variant, `ab_video.py` → "1 or 2?" — never a full render per style. Save the answer to
`work/intake.json` `style` and `NOTES.md`. Comic panels never go into a montage the user already approved unless they ask.
The style decides what the steps below use: in «real footage» proof and cutaways come from real footage first; in
«comic» the hook and the punchline may become panels (`R.comic_panel`, `assets/examples/gen_reel_comic.example.py`).

Read the transcript segments and mark:
1. **Hook** (first 3 s): the strongest sentence or picture — a cold open on the payoff, a question bubble (`ChatCard` / `Bubble`) over a muted shot when the user recorded one, or a stamp.
2. **Chapters** — every topic change gets a `Chapter` ("01 · <topic>": flash on the cut, tag, whoosh). 3–5 chapters for 2–3 minutes.
3. **Cards** — one per concrete claim: a process (diagram with nodes/arrows), a before/after, a list (a grid, criteria chips), a dialogue (chat bubbles that appear on the spoken clause), a number (count-up chip timed to the spoken number).
4. **Proof** — real screenshots and renders the user supplied (copied to `reel/public/screens/`). Show them with a slow push-in and large count-up chips on top; a 1x screenshot is unreadable at 1080 wide, the chips carry the numbers.
5. **Cutaways** — pick from the b-roll clips on the inventory sheets (or the draft's `brollCandidates`): hands typing, back view at the laptop, walking somewhere. Use them on sentences that describe doing or waiting, never on the sentence that carries the key claim. A cutaway shows who or what the sentence is about — never another person.
6. **Stamps** — one-word emotional peaks, max 2–3 per video.
7. **End** — a quiet end card (channel pill, fade to black); a CTA card only when the user asks for one.

Fabrication rule: invented placeholders (store names, prices, mail subjects) must be clearly generic ("магазин 1", "Акция недели") and listed in the hand-off note so the user can swap in real material. Never invent numbers the speaker did not say.

## Placing graphics by words, not numbers
Everything above is placed in `work/gen_reel.py` on top of `scripts/reelgen.py` (`craft/scenes.md`): anchors are spoken words (`R.fw("слово")`), never typed frame numbers. Anchor cards to the clause that carries the claim (card in 8–10 frames before the word), chips to the spoken noun, chapters to segment starts, payoffs ON the word that names them. When the user asks to shorten the video, edit the plan and re-run the chain (SKILL.md "Re-cut = re-run"); only then touch anything by hand.

## What the user does not want in the video
- Cards or tiles that point to other videos ("начало истории — в прошлом ролике"); they add the link in Instagram.
- Karaoke captions, progress bars, persistent UI chrome, loud SFX, a 1 kHz censor beep, emoji in UI text, clip-art objects.
- Repeated information: when two takes make the same point, keep the better delivery and list the cut one with timecodes in NOTES.md.
