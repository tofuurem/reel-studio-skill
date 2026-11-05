"""EXAMPLE · camera only (raw takes or a CapCut draft): talking head + title, chapters, a card in the free band, a cutaway,
chips and a stamp. Copy to work/gen_reel.py, rewrite the anchors for your transcript, run after every re-cut:
    python3 -I work/gen_reel.py && (cd reel && npx tsc --noEmit -p .)
Anchors are words (R.fw), never typed frames; a missing word stops the script with the nearest spellings."""
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts"))
import reelgen as rg
from reelgen import N, js, tag

R = rg.Project(".")
# segment map (keep it in sync with work/cutlist.json): 0 cold open · 1 the idea · 2 the reference · 3 the prototype · 4 the character
assert len(R.segs) == 5, "the cut changed: re-check the segment map"
S = [R.seg(i) for i in range(5)]

# ---- anchors
title_a, title_b = R.fw("комната") - 4, S[1] - 6
ref_a = R.fw("референс"); ref_b = R.fw("короче", after=ref_a)
proto_a = R.fw("прототип") - 6; proto_b = R.fw("вечером", after=proto_a) + 20
tools = [R.fw(w, after=S[3]) for w in ["claude", "codex", "blender"]]
horror = R.fw("ужас", after=S[4])

band = R.free_bottom(ref_a, ref_b)  # card band under the face for these frames (face_zones.json)
body = [
    rg.seq(title_a, title_b, tag("TitleCard", title="lofiroom", pill="дневник разработки", pillNote="· 01", sub="idle-комната с живым персонажем"), "title"),
    R.chapter(S[1], "01", "Идея"),
    rg.seq(ref_a, ref_b, tag("ImageCard", src="screens/ref_island.png", ratio=16 / 9, caption="Idle Island — с этого всё началось", top=band[0], maxH=band[1] - band[0]), "card · reference"),
    R.cutaway("crec_day_v", 31.0, proto_a, proto_b, "broll · the prototype", zoom=(1.05, 1.0)),
    rg.seq(tools[0] - 2, S[4], tag("ChipBand", top=1180, chips=[{"at": R.L(t, tools[0] - 2), "text": w} for t, w in zip(tools, ["Claude Code", "Codex", "Blender MCP"])]), "chips · tools"),
    R.chapter(S[4], "02", "Персонаж"),
    rg.seq(horror, horror + 40, tag("Stamp", text="УЖАС", color=js("colors.badPlate"), rotate=-5), "stamp · ужас"),
    R.music_bed(),
    R.sfx_many(tools, "pop", "sfx pop · tools"),
    R.sfx(horror, "done", "sfx · stamp"),
]
R.write(body)
print(dict(title=(title_a, title_b), ref=(ref_a, ref_b), proto=(proto_a, proto_b), tools=tools, horror=horror, band=band))
