# From transcript to storyboard (the creative pass)

Read the transcript segments and mark:
1. **Hook** (first 3 s): the strongest sentence or picture — a cold open on the payoff, a question bubble (`ChatCard` / `Bubble`) over a muted shot when the user recorded one, or a stamp.
2. **Chapters** — every topic change gets a `Chapter` ("01 · Фотоархив": flash on the cut, tag, whoosh). 3–5 chapters for 2–3 minutes.
3. **Cards** — one per concrete claim: a process (diagram with nodes/arrows), a before/after (glitching dates), a list (dupes grid, criteria chips), a dialogue (chat bubbles that appear on the spoken clause), a number (count-up chip timed to the spoken number).
4. **Proof** — real screenshots and renders the user supplied (copied to `reel/public/screens/`). Show them with a slow push-in and large count-up chips on top; a 1x screenshot is unreadable at 1080 wide, the chips carry the numbers.
5. **Cutaways** — pick from the b-roll clips on the inventory sheets (or the draft's `brollCandidates`): hands typing, back view at the laptop, walking to the pool. Use them on sentences that describe doing/waiting ("оставляю на ночь", "пойти заниматься своими делами"), never on the sentence that carries the key claim.
6. **Stamps** — one-word emotional peaks ("ПОЛНЫЙ АД", "основной кайф"), max 2–3 per video.
7. **End** — a quiet end card (channel pill, fade to black); a CTA card only when the user asks for one.

Fabrication rule: invented placeholders (store names, prices, mail subjects) must be clearly generic ("магазин 1", "Акция недели") and listed in the hand-off note so the user can swap in real material. Never invent numbers the speaker did not say.

## Placing graphics by words, not numbers
Everything above is placed in `work/gen_reel.py` on top of `scripts/reelgen.py` (`craft/scenes.md`): anchors are spoken words (`R.fw("слово")`), never typed frame numbers. Anchor cards to the clause that carries the claim (card in 8–10 frames before the word), chips to the spoken noun, chapters to segment starts, payoffs ON the word that names them. When the user asks to shorten the video, edit the plan and re-run the chain (SKILL.md "Re-cut = re-run"); only then touch anything by hand.

## What the user does not want in the video
- Cards or tiles that point to other videos ("начало истории — в прошлом ролике"); they add the link in Instagram.
- Karaoke captions, progress bars, persistent UI chrome, loud SFX, a 1 kHz censor beep, emoji in UI text, clip-art objects.
- A cutaway that shows the wrong people: a friend on a couch over «мы с девушкой» was rejected («не тот человек») — a cutaway must show who or what the sentence is about.
- Repeated information: when two takes make the same point, keep the better delivery and list the cut one with timecodes in NOTES.md.
