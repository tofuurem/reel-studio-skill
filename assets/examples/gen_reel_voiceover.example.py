"""EXAMPLE · voiceover only (lofiroom ep3 pattern): no talking head — the voice takes sit on dark carriers and the picture is
boards end to end (crossfading into each other), a receipt that lands on the spoken numbers, tiles, a chat and a closing plate.
Copy to work/gen_reel.py, rewrite anchors, run after every re-cut:  python3 -I work/gen_reel.py && (cd reel && npx tsc --noEmit -p .)"""
import os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts"))
import reelgen as rg
from reelgen import N, js, tag

R = rg.Project(".")
# segments: 0 vo «анимации» · 1 vo «мокап» · 2 vo «чек» (each a carrier; the boards cover every cut)
assert len(R.segs) == 3, "the cut changed: re-check the segment map"
S = [R.seg(i) for i in range(3)]
X = N["layerFade"]  # boards overlap by one fade → a crossfade, never the carrier

moves = [(R.fw(w), w) for w in ["машет", "сидит", "печатает"]]
chat_at = R.fw("спросил"); reply_at = R.fw("ответил", after=chat_at)
rows = [("Tripo", R.fw("tripo", after=S[2]), "$55"), ("Rokoko", R.fw("rokoko", after=S[2]), "$12 / мес"), ("подписки", R.fw("подписки", after=S[2]), "$200")]

def tiles(start):
    return [tag("Tile", src=f"screens/move_{i}.png", label=w, x=64 + (i % 3) * 326, y=420, size=300, at=R.L(t, start)) for i, (t, w) in enumerate(moves)]

def chat(start):
    msgs = [{"at": R.L(chat_at, start), "from": "me", "text": "как снять анимации без студии?"}, {"at": R.L(reply_at, start), "from": "them", "text": "Rokoko Vision: камера телефона, костюм не нужен."}]
    return [tag("ChatCard", who="Claude", messages=msgs, top=360, height=560, typingFrom=R.L(chat_at, start) + 20)]

def receipt(start):
    return [tag("Ledger", x=64, y=380, w=952, title="Чек", sub="за два дня", rows=[{"at": R.L(t, start), "name": n, "value": v} for n, t, v in rows])]

body = [
    rg.seq(0, N["fadeFromBlack"], tag("FadeFromBlack"), "fade from black"),
    R.board(0, S[1] + X, tiles, "board · moves", fade=(0, None), cover=False),
    R.chapter(S[1], "01", "Мокап"),
    R.board(S[1], S[2] + X, chat, "board · chat", cover=False),
    R.board(S[2], R.END, receipt, "board · receipt", cover=False),
    rg.seq(R.END, R.END + N["endTail"], tag("Plate", src="screens/plate_end.png"), "closing plate"),
    R.music_bed(),
    R.sfx_many([t for t, _ in moves], "pop", "sfx pop · moves"),
    R.sfx_many([t for _, t, _ in rows], "done", "sfx done · receipt"),
]
R.write(body, end_card=False, speech_end=R.END, tail=N["endTail"])
print(dict(moves=moves, chat=(chat_at, reply_at), rows=rows))
