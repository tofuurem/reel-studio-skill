#!/usr/bin/env python3
"""Listen to a finished render (optional: earshot — deps.py --with sound; ≈ 1 GB of models, CPU).

Usage: python3 -I ears.py <project> <render.mp4> [--from S] [--to S] [--detail low|normal|high]
Claude cannot hear; earshot can (github.com/Leonxlnx/earshot, MIT: CLAP + AST models, local). This hands it the render and
our own cue list — every sound effect the reel places (Sequences named «sfx …» in reel/src/Reel.tsx, nested boards
included; the action reel's work/shots.json sfx) — and reads back:
- every SFX cue that is NOT heard (no onset at its frame: masked by the voice or the bed, too quiet, a missing file) or
  lands more than one frame off;
- the listening transcript: tagged events (time, level, what it sounds like), sections, loudness, picture cuts (most of our
  cuts are silent by design — the count is information, not a fault);
→ work/qa/ears.json (earshot's full result), work/qa/ears.png (frames, spectrogram, events, loudness, cues), and the
  summary in the console. Look at the PNG next to motion_gate.py's cut sheet. A 24-minute vlog takes minutes; use
  --from / --to for a part. Prints EARS_DONE (or EARS_SKIP when earshot is not installed).
"""
import argparse, json, os, re, shutil, subprocess, sys


def reel_cues(P):
    """(frame, name) of every «sfx …» Sequence in Reel.tsx, nested Sequences' from= added up (boards use local frames)."""
    p = os.path.join(P, "reel/src/Reel.tsx")
    if not os.path.exists(p): return []
    s = open(p).read(); out = []; stack = []
    for m in re.finditer(r"<Sequence\b([^>]*?)(/?)>|</Sequence>", s):
        if m.group(0) == "</Sequence>":
            if stack: stack.pop()
            continue
        attrs = m.group(1); f = re.search(r"from=\{(-?\d+)\}", attrs); f = int(f.group(1)) if f else 0
        name = re.search(r'name="([^"]*)"', attrs); name = name.group(1) if name else ""
        if name.startswith("sfx"): out.append((sum(stack) + f, name))
        if not m.group(2): stack.append(f)
    return out


def action_cues(P):
    sh = json.load(open(os.path.join(P, "work/shots.json"))) if os.path.exists(os.path.join(P, "work/shots.json")) else {}
    return [(s["from"] + int(at), f"sfx {kind}") for s in sh.get("shots", []) for at, kind in (s["fx"].get("sfx") or [])]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("render")
    ap.add_argument("--from", dest="start", type=float); ap.add_argument("--to", dest="end", type=float)
    ap.add_argument("--detail", choices=["low", "normal", "high"], default="normal")
    a = ap.parse_args(); P = os.path.abspath(a.project); render = os.path.abspath(a.render)
    if not shutil.which("earshot"):
        print("EARS_SKIP earshot is not installed (python3 -I deps.py --install --with sound) — audio_qa.py and motion_gate.py still apply"); return
    qa = os.path.join(P, "work/qa"); os.makedirs(qa, exist_ok=True)
    fps = 30
    cues = action_cues(P) if "Action" in os.path.basename(render) or (os.path.exists(os.path.join(P, "work/shots.json")) and not os.path.exists(os.path.join(P, "reel/src/Reel.tsx"))) else reel_cues(P)
    if a.start is not None: cues = [c for c in cues if c[0] / fps >= a.start]
    if a.end is not None: cues = [c for c in cues if c[0] / fps <= a.end]
    cue_p = os.path.join(qa, "ears_cues.json")
    json.dump({"fps": fps, "events": [{"f": f, "kind": "sfx", "id": n} for f, n in cues]}, open(cue_p, "w"), ensure_ascii=False)
    zoom = (["--from", str(a.start)] if a.start is not None else []) + (["--to", str(a.end)] if a.end is not None else [])
    common = [render, "--cues", cue_p, "--detail", a.detail, *zoom]
    r = subprocess.run(["earshot", "timeline", *common, "--json", "--out", os.path.join(qa, "ears.json")], capture_output=True, text=True)
    if r.returncode: sys.exit(f"earshot timeline failed: {(r.stderr or r.stdout).strip()[-300:]}")
    d = json.load(open(os.path.join(qa, "ears.json")))
    subprocess.run(["earshot", "sheet", *common, "-o", os.path.join(qa, "ears.png")], capture_output=True, text=True)
    print(d.get("summary", "").strip())
    items = ((d.get("sync") or {}).get("cues") or {}).get("items") or []
    names = {round(f / fps, 3): n for f, n in cues}
    deaf = [i for i in items if i.get("status") == "no sound" or i.get("offset_ms") is None]
    off = [i for i in items if i.get("offset_ms") is not None and abs(i["offset_ms"]) > 1500 / fps]   # onsets are measured to about a frame
    for i in deaf: print(f"NOT HEARD  {i['t']:7.2f} s  {names.get(round(i['t'], 3), 'sfx')} — masked by the voice / bed, too quiet, or the file is missing")
    for i in off: print(f"OFF SYNC   {i['t']:7.2f} s  {names.get(round(i['t'], 3), 'sfx')} — the sound starts {i['offset_ms']:+.0f} ms from its frame")
    print(f"EARS_DONE {len(items)} SFX cues: {len(items) - len(deaf) - len(off)} heard on the frame, {len(deaf)} not heard, {len(off)} off sync — work/qa/ears.png, work/qa/ears.json")


if __name__ == "__main__":
    main()
