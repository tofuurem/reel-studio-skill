"""EXAMPLE · camera + voiceover takes (lofiroom ep2 pattern): close-ups shrink into a left window with notes on the right
(SplitStage + SideList / SideBubble); every voiceover segment (dark carrier) is covered by a Board.
Copy to work/gen_reel.py, rewrite anchors, run after every re-cut:  python3 -I work/gen_reel.py && (cd reel && npx tsc --noEmit -p .)"""
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts"))
import reelgen as rg
from reelgen import N, js, tag

R = rg.Project(".")
# segments: 0 camera cold open · 1 camera close-up «из чего она» · 2 vo Tripo · 3 vo price · 4 camera outro
assert len(R.segs) == 5, "the cut changed: re-check the segment map"
S = [R.seg(i) for i in range(5)]
COL = {"x": 620, "y": 300, "w": 404}  # right column next to the shrunken head (window x 56–596, y 300–1260)

# ---- 01 · what she is made of (close-up → split)
split = (S[1], S[2] + N["coverAfter"])
parts = [(R.fw(w, after=S[1]), w) for w in ["тело", "причёска", "кофта", "наушники"]]
footer_at = R.fw("отдельными", after=S[1])
# ---- 02 · Tripo (voiceover: boards over the carrier)
t_brand = R.fw("tripo", after=S[2]); t_pic = R.fw("картинку", after=S[2]); t_res = R.fw("получаешь", after=S[2])
t_price = R.fw("55", after=S[3]); t_credits = R.fw("5000", after=S[3])
bubble_at = R.fw("лучше", after=S[4])

def tripo(start):  # children get LOCAL frames: L(t) = t - start
    L = lambda t: R.L(t, start)
    return [
        tag("Pill", text="Tripo", x=548, y=320, at=L(t_brand), bg=js("colors.ink"), size=64, font="display"),
        tag("Win", src="screens/codex_girl.png", x=64, y=300, w=440, h=440, at=L(t_pic), label="картинка"),
        tag("DownArrow", x=252, y=756, at=L(t_pic) + 20),
        tag("Win", src="screens/tripo_v1.png", x=64, y=850, w=952, h=480, at=L(t_res), label="3D-модель из Tripo", labelColor=js("colors.accent")),
        tag("BigFact", big="$55", sub="за 5000 кредитов", subAt=L(t_credits), x=548, y=540, w=442, at=L(t_price), bigSize=88),
    ]

body = [
    R.chapter(S[1], "01", "Задача"),
    rg.seq(S[1] + 2, S[2] + 6, tag("SideList", x=COL["x"], y=COL["y"], w=COL["w"], header="героиня — это",
                                   items=[{"at": R.L(t, S[1] + 2), "text": w} for t, w in parts],
                                   footer={"at": R.L(footer_at, S[1] + 2), "text": "и всё отдельными кусками"}), "side · parts"),
    R.board(S[2] - 8, S[4], tripo, "board · picture → Tripo → 3D"),
    R.chapter(S[2], "02", "Tripo"),
    rg.seq(bubble_at - 4, R.END, tag("SideBubble", x=COL["x"], y=420, w=COL["w"], text="Модель стала сильно лучше.", who="Claude, в той же сессии"), "side · verdict"),
    R.music_bed(),
    R.sfx_many([t for t, _ in parts], "pop", "sfx pop · parts"),
    R.sfx(t_price, "done", "sfx done · price"),
    R.ticks(t_price, t_price + 16),
]
stage = tag("SplitStage", tag("Timeline"), windows=[{"from": split[0], "to": split[1]}, {"from": bubble_at - 8, "to": R.END}])
R.write(body, stage=stage)
print(dict(split=split, parts=parts, tripo=R.last, price=t_price, bubble=bubble_at))
