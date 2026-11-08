"""The action reel's shot list → reel/public/shots, voices, mattes, reel/src/shotsData.ts (scripts/actiongen.py).

Copy to work/gen_action.py. Before: track_beats.py <project> <track> --start S --len 45 (the grid; the user picked the
track and the second it starts at in Instagram). Run: work/venv/bin/python -I work/gen_action.py [--only 3,10] → ACTION_OK, then
`(cd reel && npx tsc --noEmit -p .)`, look at work/action/sheet.jpg, render ActionTrack as a preview with the music.
Distilled from the Halloween reel (2026-11-04, 45 s, «Pursuit Of Happiness (Nightmare)» from 2:47.6, drop at frame 218).
"""
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts"))
import actiongen as ag

R = ag.Project(".", sources=["<folder with your clips>"])   # clip ids as clipid.py: DJI_…_0121_D.MP4 → "0121"
P = R.piece

shots = [
    # build-up (track 2:47.6 → the drop at frame 218): one strong picture per 1–2 beats, people framed by Vision
    R.shot("0121b", 16.0, beats=2, note="подруга нарезает круги вокруг камеры"),
    R.shot("0084", 74.0, beats=1, x=0.47, note="банан танцует"),
    R.shot("0087", 95.0, beats=1, note="друг в костюме греческого бога", punch=[1.0, 1.1],
           behind={"title": "ЗЕВС", "kicker": "ГРЕЧЕСКИЙ БОГ", "at": 0}),            # the title behind the person
    R.shot("0121b", 27.0, beats=2, note="подруга уезжает"),
    R.shot("0090", [P(68.6, None, 1.5)], beats=2, note="друг бежит за байком"),          # 1.5× speed-up
    R.shot("0122b", 71.0, frames=58, x=0.78, note="рука к груди друга"),                    # off the grid on purpose: the hit below must land ON the drop
    # the drop: a speed ramp — 100 %, two 40 % slow-motion pieces (motion-interpolated), back to 100 %; the hit lands ON the drop
    R.shot("0122b", [P(72.4, 21), P(73.1, 15, 0.4), P(73.3, 15, 0.4), P(73.5)], frames=60, x=0.78, note="удар на дропе",
           sync=(36, "drop"), punch=[1.06, 1.22], punchAt=34, flashAt=36, shake=True, shakeAt=36, sfx=[(36, "hit")]),
    R.shot("0122b", 78.0, beats=1.5, x=0.8, note="второй друг согнулся", shake=True, shakeAt=0),   # beats= snaps back onto the grid
    # talk punchlines: the cleaned voice of the line + one caption, censored wording
    R.shot("0091", 25.9, frames=62, x=0.41, voice=(25.9, 27.7), note="«и просто стоит фоткает»", caption="…и просто стоит фоткает", captionAt=3),
    # accents (craft/transitions.md §3) are rare and alternate with plain shots — FX BUDGET lines say when they crowd:
    #   bump=True on a strong beat, crashAt=f + punch=[1, 1.25] on a reaction, rgbAt=f on a hit, stutterUntil=<drop frame>,
    #   black=6 after a 3 × 9-frame cold-open bumper, hold=50 + circle="auto" for «вот он»
    # phrase starts get the rare silent whips; the battery gag counts the night down
    R.shot("0125b", [P(15.0, None, 1.6)], beats=2, x=0.6, note="банан на мотоцикле в фарах", whip="left", battery=19),
    R.shot("0115", 113.5, beats=1, x=0.6, note="морда банана в 7-Eleven", battery=9, sfx=[(3, "beep")]),
    R.shot("0132", [P(0.9, 36), P(2.1)], frames=108, x=(0.65, 0.30), voice=(0.9, 4.5), note="1% — дошли до байков",
           whip="right", battery=1, caption="1% последний — и мы дошли до байков", captionAt=4, sfx=[(5, "beep")]),
]

only = {int(x) for x in sys.argv[sys.argv.index("--only") + 1].split(",")} if "--only" in sys.argv else None
R.build(shots, end_frames=25, hook={"kicker": "31.10", "title": "ХЭЛЛОУИН", "from": 0, "to": 2}, only=only)   # over shots 1–2 (0-based, to exclusive)
