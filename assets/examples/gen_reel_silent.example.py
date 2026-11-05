"""EXAMPLE · images only, no voice (cut list from silent_timeline.py: one silent carrier, "silent": true, work/beats.json).
Pictures land on the music bed's beat grid; no captions, no bleeps, no face zones. Offer to record a few voice lines first
(references/inputs/voiceover.md) — a silent reel is the fallback.
Copy to work/gen_reel.py:  python3 -I work/gen_reel.py && (cd reel && npx tsc --noEmit -p .)"""
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts"))
import reelgen as rg
from reelgen import N, js, tag

R = rg.Project(".")
assert R.silent, "this generator is for silent cut lists"
SHOTS = ["screens/shot_1.png", "screens/shot_2.png", "screens/shot_3.png", "screens/shot_4.png"]
BEATS_PER_SHOT = 4
grid = R.beats(every=BEATS_PER_SHOT)  # one picture every 4 beats
assert len(grid) >= len(SHOTS) + 1, f"the bed is too short for {len(SHOTS)} pictures: {grid}"
X = N["layerFade"]

def shot(src, i):
    def kids(start):
        return [tag("Win", src=src, x=64, y=300, w=952, h=1050, zoomFrom=1.0, zoomTo=1.06),
                tag("Pill", text=f"{i + 1} / {len(SHOTS)}", x=64, y=1380, at=R.L(grid[i] + 4, start), size=30)]
    return kids

body = [rg.seq(grid[0], grid[0] + N["chapterLead"] + N["tagFrames"], tag("TitleCard", title="lofiroom", pill="как это выглядит", top=N["cardTop"] - 50), "title")]
for i, src in enumerate(SHOTS):
    body.append(R.board(grid[i], grid[i + 1] + X, shot(src, i), f"board · shot {i + 1}", fade=(0 if i == 0 else None, None), cover=False))
body += [
    rg.seq(grid[len(SHOTS)], R.END, tag("Plate", src="screens/plate_end.png"), "closing plate"),
    R.music_bed(),
    R.sfx_many(grid[1:len(SHOTS)], "softwhoosh", "sfx · picture change"),
]
R.write(body, speech_end=R.END, tail=N["endTail"])
print(dict(grid=grid[: len(SHOTS) + 1], END=R.END))
