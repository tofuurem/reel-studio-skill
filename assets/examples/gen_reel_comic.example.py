"""EXAMPLE · camera + comic panels (references/craft/styles.md «comic», or a calm reel with comic accents). A STYLE switch at
the top builds the same beat in two styles for an A/B (render_part.sh per variant → ab_video.py), then stays on the winner.
Plates are generated with scripts/codex_image.sh from real frames of this reel into reel/public/comic/ (no text in them);
every word is set here. Copy to work/gen_reel.py, rewrite the anchors for your transcript, run after every re-cut:
    python3 -I work/gen_reel.py && (cd reel && npx tsc --noEmit -p .)
Needs scenes/ComicPanel.tsx + scenes/Comic.tsx from the template (copy them into a project scaffolded before they existed).
The story here: «guys, I'll build it in a couple of days» → the game it was built for (real footage) → «…ten days»."""
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts"))
import reelgen as rg
from reelgen import N, js, tag

STYLE = "comic"   # "calm" | "comic" — the A/B switch; write the decision into work/intake.json "style" and NOTES.md

R = rg.Project(".")
# segment map (keep it in sync with work/cutlist.json): 0 the promise · 1 the attempt · 2 the reality · 3 the moral
assert len(R.segs) == 4, "the cut changed: re-check the segment map"
S = [R.seg(i) for i in range(4)]

# ---- anchors (spoken words)
promise_a, promise_b = R.fw("ребята"), R.fw("сделаю") + 30            # «ребята, сейчас за пару дней всё сделаю»
game_a = R.fw("игра"); game_b = R.fw("знак", after=game_a) + 12      # what the speaker talks about → real footage, credited
bang = R.fw("восклицательный", after=game_a)
days = R.fw("дней", after=S[2])                                        # «…десять дней»

body = [R.chapter(S[1], "01", "Попытка")]

# the promise: an inset panel above the face, the speaker's own line in a balloon pointing at the mouth (cy of the mouth
# from work/face_zones.json or a QA still), a narrator box with the spoiler
if STYLE == "comic":
    body.append(R.comic_panel(promise_a - 4, promise_b, "comic/p1_promise.png", "comic · the promise",
        ratio=4 / 5, focus="50% 40%",
        cues=lambda st: {
            "box": {"text": "спойлер: десять дней", "x": 90, "y": 260, "at": R.L(promise_b - 40, st), "bg": "yellow"},
            "balloon": {"lines": ["за пару дней", "всё сделаю"], "accent": [1], "cx": 560, "cy": 1180, "rx": 380, "ry": 150,
                        "tailX": 520, "tailY": 1480, "at": 6},
        }))
    body.append(R.sfx(promise_a - 4, "pop", "sfx · panel"))
else:
    band = R.free_top(promise_a, promise_b)
    body.append(rg.seq(promise_a, promise_b, tag("TitleCard", title="за пару дней", sub="спойлер: десять дней", top=band[0]), "title · the promise"))

# the game itself: REAL footage in every style (style 3 for this beat) — someone else's gameplay after the user's yes,
# fetched with fetch.py --as footage, cut into reel/public/<name>/ and credited on screen (the CREDIT line fetch.py printed)
body.append(rg.seq(game_a, game_b, tag("VideoCard", src="gameplay/edit1.mp4", trimBefore=0, ratio=1, label="the game",
                                       credit="gameplay: Author · YouTube", top=250, maxH=1000), "real · gameplay"))
body.append(R.sfx(bang, "pop", "sfx · the «!»"))

# the reality: a full panel instead of a cutaway on the punchline (counts as an effect seam), a shout balloon
if STYLE == "comic":
    body.append(R.comic_panel(days - 20, days + 70, "comic/p2_days.png", "comic · ten days", full=True,
        title={"text": "десять\nдней", "top": 300, "size": 120},
        cues=lambda st: {"balloon": {"lines": ["пу-пу-пу"], "kind": "shout", "cx": 560, "cy": 1300, "rx": 330, "ry": 130,
                                     "tailX": 700, "tailY": 1060, "at": R.L(days, st) + 6}}))
else:
    body.append(rg.seq(days, days + 50, tag("Stamp", text="ДЕСЯТЬ ДНЕЙ", color=js("colors.badPlate"), rotate=-5), "stamp · days"))

body.append(R.music_bed())
R.write(body)   # prints STYLE BUDGET when the reel has more comic panels than comicPanelsPerMin allows
print(dict(style=STYLE, promise=(promise_a, promise_b), game=(game_a, game_b), days=days))
