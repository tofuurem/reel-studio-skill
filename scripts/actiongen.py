#!/usr/bin/env python3
"""The action-reel generator: a list of shots → pieces cut straight from the camera files (people-aware crop, LUT, grade,
speed ramps, slow motion), punchline voices, text-behind-person cutouts → reel/src/shotsData.ts for the template's Action.tsx.

Used from the project's work/gen_action.py (copy assets/examples/gen_action.example.py):
    import actiongen as ag
    R = ag.Project(".", sources=["<folder with your clips>"])       # clip ids resolve like everywhere (clipid.py: DJI_…_0121_D → "0121")
    shots = [R.shot("0121b", 16.0, beats=2, note="подруга нарезает круги"),
             R.shot("0122b", [R.piece(72.4, 21), R.piece(73.1, 15, 0.4), R.piece(73.3, 15, 0.4), R.piece(73.5)], beats=4,
                    x=0.78, note="удар на дропе", sync=(36, "drop"), punch=[1.06, 1.22], punchAt=34, flashAt=36, shake=True, shakeAt=36,
                    sfx=[(36, "hit")]),
             R.shot("0091", 25.9, frames=62, voice=(25.9, 27.7), caption="…и просто стоит фоткает", captionAt=3),
             R.shot("0087", 95.0, beats=1, behind={"title": "ХЭЛЛОУИН", "kicker": "31.10"})]
    R.build(shots, end_frames=25, hook={"kicker": "31.10", "title": "ХЭЛЛОУИН", "from": 1, "to": 5})   # hook over shots 1–4 (0-based, to exclusive)
Length: `beats=N` puts the cut exactly on the track's beat grid (work/track_beats.json from track_beats.py --start …): shot
ends are computed on the continuous grid, so rounding never drifts; `frames=N` is a plain length. Pieces: R.piece(src_s, frames,
speed) — the last piece may leave frames out and takes the rest of the shot. speed < actionSlowmo is retimed with
motion-compensated interpolation (minterpolate), the browser would only repeat frames; > 1 is a plain speed-up.
Crop: x="auto" (default) = Apple Vision people boxes (people_zones.py: main person + big neighbours that fit, sticky,
smoothed, a pan when they move), x=0.4 a fixed centre, x=(0.65, 0.30) one value per piece, x=[0.6, 0.3] a linear pan over the
shot; a vertical source is used as is. sync=(frame in shot, "drop" | "phrase" | reel frame) checks that the moment lands there.
Effects (frames inside the shot): whip "left"/"right" (silent, directional blur — put them on phrase starts), punch [from, to],
punchAt, flashAt (≤ 0.45), shake, shakeAt, hold (freeze frames after the shot, desaturated), caption (+ captionAt,
captionTail; "\\n" = new line), voice (src_from, src_to) → a cleaned punchline (dualmic.py chain: declip, DeepFilterNet,
automix) + voiceAt/voiceGain, sfx [(frame, kind)] — sound only where something happens (no whoosh on every cut: the user
called it strange), battery (a camera-battery % top right; ≤ 9 blinks red), behind {"title", "kicker", "at", "until",
"mode": "person"|"subject"} → the title sits BEHIND the person (person_matte.py cuts them out of the same piece).
Writes reel/public/shots/s<NN><k>.mp4 (2K: the canvas × 4/3), reel/public/voice/v<NN>.wav, reel/public/shots/*.matte.webm,
work/shots.json, reel/src/shotsData.ts, work/action/sheet.jpg (the middle frame of every shot — look at the framing) and a
sync table: every cut's frame and its distance to the nearest beat. Re-runs rebuild only shots whose spec changed.
Prints ACTION_OK.
"""
import glob, hashlib, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N, atomic_json, canvas_size, clip_id, crop_expr, load_json, load_lut_map, lut_for, probe, title_place

SK = os.path.dirname(os.path.abspath(__file__))
# after the D-Log LUT the night footage is flat and grey; a camera without D-Log needs less
GRADE_LUT = "eq=contrast=1.12:saturation=1.22:gamma=1.04,curves=all='0/0 0.06/0.09 0.5/0.55 1/1'"
GRADE_REC709 = "eq=contrast=1.06:saturation=1.12"
VOICE_AF = "highpass=f=90,acompressor=threshold=-22dB:ratio=3:attack=8:release=150,afade=t=in:d=0.03,areverse,afade=t=in:d=0.08,areverse"
FX_KEYS = {"whip", "punch", "punchAt", "flashAt", "shake", "shakeAt", "hold", "caption", "captionAt", "captionTail", "voiceAt", "voiceGain", "sfx", "battery"}


class Project:
    def __init__(self, project=".", sources=(), lut=None, lut_map=None, grade_lut=GRADE_LUT, grade_rec709=GRADE_REC709, canvas=None, fps=30):
        self.P = os.path.abspath(project); os.chdir(self.P)
        self.fps = fps; cw, ch = canvas_size(canvas, self.P); self.W, self.H = round(cw * 4 / 3 / 2) * 2, round(ch * 4 / 3 / 2) * 2
        if lut_map is None and os.path.exists("work/lut_map.json"): lut_map = "work/lut_map.json"
        self.lut = lut; self.lut_map = load_lut_map(lut_map) if isinstance(lut_map, str) else (lut_map or {})
        self.grade = (grade_lut, grade_rec709)
        self.files = {}
        for s in sources:
            for f in ([s] if os.path.isfile(s) else sorted(glob.glob(os.path.join(s, "**", "*"), recursive=True))):
                if os.path.isfile(f) and os.path.splitext(f)[1].lower() in (".mp4", ".mov", ".m4v") and not os.path.basename(f).startswith("._"):
                    self.files.setdefault(clip_id(f)[1:], f)
        tb = load_json("work/track_beats.json")
        self.grid = (tb or {}).get("grid"); self.track = tb
        if self.grid:
            self.bf = self.grid["beatFrames"]
            self.first = (tb["beats"][next(i for i, t in enumerate(tb["beats"]) if t >= tb["start"] - 1e-6)] - tb["start"]) * fps   # exact, unrounded
            self.k0 = round(-self.first / self.bf)
        self.infos = {}; self.caches = {}

    # ------------------------------------------------------------ shot spec
    def piece(self, a, frames=None, speed=1.0):
        return {"a": float(a), "frames": frames, "speed": float(speed)}

    def shot(self, clip, start, beats=None, frames=None, x="auto", note="", voice=None, sync=None, behind=None, **fx):
        bad = set(fx) - FX_KEYS
        if bad: raise SystemExit(f"shot {note!r}: unknown effect(s) {sorted(bad)} — one of {sorted(FX_KEYS)}")
        if beats is None and frames is None: raise SystemExit(f"shot {note!r}: give beats= (on the track grid) or frames=")
        if beats is not None and not self.grid: raise SystemExit("beats= needs work/track_beats.json with a grid: track_beats.py <project> <track> --start S")
        pieces = [self.piece(start)] if not isinstance(start, list) else start
        return {"clip": str(clip), "pieces": pieces, "beats": beats, "frames": frames, "x": x, "note": note, "voice": voice, "sync": sync, "behind": behind, "fx": fx}

    def src(self, clip):
        f = self.files.get(clip)
        if not f: raise SystemExit(f"clip {clip!r} not found in the sources (known: {', '.join(sorted(self.files)[:12])}…)")
        return f

    def info(self, f):
        return self.infos.get(f) or self.infos.setdefault(f, probe(f))

    # ------------------------------------------------------------ crop
    def auto_keys(self, f, a, b):
        import people_zones as pz
        info = self.info(f); span = info["h"] * self.W / self.H / info["w"]
        cid = clip_id(f); cp = f"work/people/{cid}.json"; os.makedirs("work/people", exist_ok=True)
        cache = self.caches.get(cid) or self.caches.setdefault(cid, load_json(cp, {}) or {})
        frames = pz.scan(f, a, b, max(N["peopleFps"], 6), cache); atomic_json(cache, cp)
        keys, found = pz.path(frames, a, b, span)
        if not keys: print(f"WARNING: nobody found in {cid} {a:.1f}–{b:.1f} s — centre crop (set x=…)"); return [[a, 0.5], [b, 0.5]]
        return keys

    def vf(self, f, a, b, speed, x):
        info = self.info(f); w, h = info["w"], info["h"]; out = []
        if w / h > self.W / self.H + 0.01:   # the source is wider than the canvas: choose WHERE (people), never squash
            sw = round(w * self.H / h / 2) * 2
            if x == "auto": keys = self.auto_keys(f, a, b)
            elif isinstance(x, list): keys = [[a, x[0]], [b, x[-1]]]
            else: keys = [[a, float(x)], [b, float(x)]]
            span = self.W / sw; keys = [[t, max(span / 2, min(1 - span / 2, c))] for t, c in keys]
            out.append(f"scale={sw}:{self.H}:flags=lanczos,crop={self.W}:{self.H}:{crop_expr(keys, a, sw, self.W)}:0")
        else:
            out.append(f"scale={self.W}:{self.H}:force_original_aspect_ratio=increase:flags=lanczos,crop={self.W}:{self.H}")
        out.append("setsar=1")
        lut = lut_for(f, self.lut, self.lut_map, info)[0]   # D-Log camera clips and HDR phone clips; None for Rec.709
        if lut: out.append(f"lut3d=file='{lut}':interp=tetrahedral,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709")   # Rec.709 from here on
        out.append(self.grade[0] if lut and not info.get("hdr") else self.grade[1])   # D-Log needs the stronger grade; HDR comes out Apple-graded
        if speed != 1: out.append(f"setpts=PTS/{speed}")
        out.append(f"minterpolate=fps={self.fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir" if speed < N["actionSlowmo"] else f"fps={self.fps}")
        return ",".join(out), lut

    def cut(self, f, a, frames, speed, x, out):
        b = a + frames / self.fps * speed
        vf, _ = self.vf(f, a, b, speed, x)
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a + 0.3:.3f}", "-i", f, "-an", "-vf", vf,
                        "-frames:v", str(frames), "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", out + ".part.mp4"], check=True)
        os.replace(out + ".part.mp4", out)

    def voice(self, f, a, b, out):
        py = os.path.join(self.P, "work/dfvenv/bin/python")
        subprocess.run([py, "-I", os.path.join(SK, "dualmic.py"), self.P, "--test", f"{a - 0.3:.2f}", f"{b - a + 0.6:.2f}", f], check=True, stdout=subprocess.DEVNULL)
        mix = f"work/voice/test/{clip_id(f)}_mix.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", "0.3", "-t", f"{b - a:.3f}", "-i", mix, "-af", VOICE_AF, "-ar", "48000", out + ".part.wav"], check=True)
        os.replace(out + ".part.wav", out)

    def matte(self, piece_file, mode):
        out = piece_file.replace(".mp4", ".matte.webm")
        subprocess.run([os.path.join(self.P, "work/venv/bin/python"), "-I", os.path.join(SK, "person_matte.py"), "reel/public/" + piece_file, "reel/public/" + out,
                        "--mode", mode or "auto", "--fps", str(self.fps)], check=True, stdout=subprocess.DEVNULL)
        return out

    # ------------------------------------------------------------ build
    def build(self, shots, end_frames=25, hook=None, only=None, out_ts="reel/src/shotsData.ts"):
        os.makedirs("reel/public/shots", exist_ok=True); os.makedirs("reel/public/voice", exist_ok=True); os.makedirs("work/action", exist_ok=True)
        old = load_json("work/shots.json", {"shots": []}) or {"shots": []}
        known = {p["file"]: p for s in old["shots"] for p in s["pieces"]}; known_v = {s.get("voice"): s.get("vspec") for s in old["shots"]}
        known_m = {p["file"]: p.get("mspec") for s in old["shots"] for p in s["pieces"]}
        res, pos, cum = [], 0, 0.0
        whips = [(i, s["fx"]["whip"]) for i, s in enumerate(shots, 1) if s["fx"].get("whip")]
        for (i, d), (j, e) in zip(whips, whips[1:]):   # the vector law (motion-design.md «Seams»): one current, no ping-pong
            if d != e: print(f"WARNING: whip {d} on shot {i}, then {e} on shot {j} — keep one direction unless something on screen causes the flip")
        for i, s in enumerate(shots, 1):
            f = self.src(s["clip"])
            if s["beats"] is not None:
                cum = round((cum + s["beats"]) * 2) / 2   # back on the grid (half beats) after a shot measured in frames
                end = round(self.first + (self.k0 + cum) * self.bf); n = end - pos
            else: n = int(s["frames"]); cum = (pos + n - self.first) / self.bf - self.k0 if self.grid else 0
            fixed = sum(p["frames"] or 0 for p in s["pieces"]); free = [p for p in s["pieces"] if not p["frames"]]
            if len(free) > 1 or (not free and fixed != n): raise SystemExit(f"shot {i} {s['note']!r}: pieces add up to {fixed} frames, the shot is {n} — leave the last piece's frames out")
            if free: free[0]["frames"] = n - fixed
            if any(p["frames"] <= 0 for p in s["pieces"]): raise SystemExit(f"shot {i} {s['note']!r}: a piece has no frames left ({n} frames in the shot)")
            out = []
            for k, p in enumerate(s["pieces"]):
                x = s["x"][k] if isinstance(s["x"], tuple) else s["x"]
                if isinstance(s["x"], list) and len(s["pieces"]) > 1: x = s["x"][0] + (s["x"][-1] - s["x"][0]) * k / (len(s["pieces"]) - 1)
                name = f"shots/s{i:02d}{'abcdefghij'[k] if len(s['pieces']) > 1 else ''}.mp4"
                b = p["a"] + p["frames"] / self.fps * p["speed"]
                keys = self.auto_keys(f, p["a"], b) if x == "auto" and self.info(f)["w"] / self.info(f)["h"] > self.W / self.H + 0.01 else None
                spec = hashlib.md5(json.dumps([f, p, x, keys, self.W, self.H, self.grade, self.lut, self.lut_map, N["actionSlowmo"]] + (["hdr", lut_for(f, self.lut, self.lut_map, self.info(f))[0]] if self.info(f).get("hdr") else []), default=str).encode()).hexdigest()[:10]
                prev = known.get(name)
                if prev and prev["spec"] == spec and os.path.exists("reel/public/" + name) and not (only and i in only):
                    entry = dict(prev)
                else:
                    self.cut(f, p["a"], p["frames"], p["speed"], x, "reel/public/" + name)
                    entry = {"file": name, "frames": p["frames"], "spec": spec, "speed": p["speed"], "src": [s["clip"], p["a"], round(b, 3)]}
                    print(f"piece {name}: {s['clip']} {p['a']:.2f}–{b:.2f} s ×{p['speed']} → {p['frames']} frames", flush=True)
                if s["behind"]:
                    mspec = spec + str((s["behind"] or {}).get("mode"))
                    mf = name.replace(".mp4", ".matte.webm")
                    if known_m.get(name) != mspec or not os.path.exists("reel/public/" + mf): mf = self.matte(name, s["behind"].get("mode")); print("matte", mf, flush=True)
                    entry.update(matte=mf, mspec=mspec)
                out.append(entry)
            v = vspec = None
            if s["voice"]:
                v = f"voice/v{i:02d}.wav"; vspec = hashlib.md5(json.dumps([f, s["voice"], VOICE_AF, N["dualmicAtten"]]).encode()).hexdigest()[:10]
                if known_v.get(v) != vspec or not os.path.exists("reel/public/" + v) or (only and i in only):
                    self.voice(f, *s["voice"], "reel/public/" + v); print("voice", v, flush=True)
            res.append({"n": i, "clip": s["clip"], "note": s["note"], "from": pos, "frames": n, "pieces": out, "voice": v, "vspec": vspec, "fx": s["fx"], "sync": s["sync"], "behind": s["behind"]})
            pos += n + int(s["fx"].get("hold", 0) or 0)
        atomic_json({"fps": self.fps, "size": [self.W, self.H], "shots": res}, "work/shots.json")
        keep = {p[k] for s in res for p in s["pieces"] for k in ("file", "matte") if p.get(k)} | {s["voice"] for s in res if s["voice"]}
        for d in ("shots", "voice"):   # pieces of shots that no longer exist (a shorter list, a re-split) would only confuse
            for fn in os.listdir(f"reel/public/{d}"):
                if fn.startswith("."): continue   # AppleDouble sidecars / .DS_Store
                rel = f"{d}/{fn}"
                if rel not in keep and not fn.endswith(".mask.json") and (fn.endswith((".mp4", ".webm", ".wav"))): os.remove(f"reel/public/{rel}")
                elif fn.endswith(".mask.json") and rel.replace(".mask.json", ".webm") not in keep: os.remove(f"reel/public/{rel}")
        self.report(res, pos, end_frames); self.sheet(res)
        self.write_ts(res, end_frames, hook, out_ts)
        print("ACTION_OK", len(res), "shots,", pos, "+", end_frames, "=", pos + end_frames, "frames", f"({(pos + end_frames) / self.fps:.1f} s)")

    def report(self, res, total, end_frames):
        g = self.grid; probs = []
        print(" #   from  len  cut→beat  note")
        for s in res:
            near = ""
            if g:
                k = round((s["from"] - self.first) / self.bf); d = s["from"] - (self.first + k * self.bf)
                near = f"{d:+5.1f}" + (" phrase" if s["from"] in g["phrases"] or any(abs(s["from"] - p) <= 1 for p in g["phrases"]) else "") + (" DROP" if g.get("drop") is not None and abs(s["from"] - g["drop"]) <= 1 else "")
            print(f"{s['n']:2d} {s['from']:6d} {s['frames']:4d}  {near:14s} {s['note']}")
            if s["sync"]:
                at, what = s["sync"]; want = g.get("drop") if what == "drop" else what if isinstance(what, int) else None
                if what == "phrase": want = min(g["phrases"], key=lambda p: abs(p - (s["from"] + at)))
                got = s["from"] + at
                if want is not None and abs(got - want) > 1: probs.append(f"shot {s['n']} {s['note']!r}: frame {at} lands at {got}, {what} is {want} ({got - want:+d}) — change a length before it")
                else: print(f"   sync ok: {s['note']!r} frame {at} = reel {got} ({what})")
        if g and total + end_frames > g["frames"] + 1: probs.append(f"the reel ({total + end_frames} frames) is longer than the track window ({g['frames']}) — track_beats.py --len")
        for p in probs: print("SYNC WARNING:", p)

    def sheet(self, res):
        with tempfile.TemporaryDirectory(dir="work") as tmp:
            for s in res:
                p = s["pieces"][len(s["pieces"]) // 2]
                subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{p['frames'] / self.fps / 2:.2f}", "-i", "reel/public/" + p["file"], "-frames:v", "1",
                                "-vf", "scale=-2:360", os.path.join(tmp, f"{s['n']:03d}.jpg")], check=True)   # tiles in shot order, left to right
            cols = 10 if self.H > self.W else 6
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-pattern_type", "glob", "-i", os.path.join(tmp, "*.jpg"), "-vf", f"tile={cols}x{-(-len(res) // cols)}:padding=4",
                            "-frames:v", "1", "work/action/sheet.jpg"], check=True)
        print(f"framing sheet: work/action/sheet.jpg (shots 1–{len(res)} left to right, {10 if self.H > self.W else 6} per row)")

    def write_ts(self, res, end_frames, hook, out_ts):
        shots = []
        for s in res:
            d = {"note": s["note"], "frames": s["frames"], "pieces": [{"file": p["file"], "frames": p["frames"], **({"matte": p["matte"]} if p.get("matte") else {})} for p in s["pieces"]]}
            if s["voice"]: d["voice"] = s["voice"]
            if s["behind"]:
                d["behind"] = {k: v for k, v in s["behind"].items() if k != "mode"}
                mt_ = next((p["matte"] for p in s["pieces"] if p.get("matte")), None)
                if "y" not in d["behind"] and mt_:   # x, y, scale from the matte's alpha (common.title_place)
                    d["behind"].update(title_place("reel/public/" + mt_.replace(".webm", ".mask.json"), d["behind"].get("title"),
                                                   canvas_size(None, self.P), kicker=bool(d["behind"].get("kicker"))) or {})
            d.update({k: (list(map(list, v)) if k == "sfx" else v) for k, v in s["fx"].items()})
            shots.append(d)
        g = self.grid or {}
        ts = ("// GENERATED by work/gen_action.py (scripts/actiongen.py) — do not edit by hand.\n"
              "import type { Shot } from \"./Action\";\n"
              f"export const TRACK_START = {json.dumps((self.track or {}).get('start'))};\n"
              f"export const END_FRAMES = {int(end_frames)};\n"
              f"export const HOOK: {{ kicker?: string; title: string; from: number; to: number }} | null = {json.dumps(hook, ensure_ascii=False)};\n"
              f"export const GRID = {json.dumps({'beat': g.get('beatFrames'), 'drop': g.get('drop'), 'phrases': g.get('phrases', [])})};\n"
              f"export const SHOTS: Shot[] = {json.dumps(shots, ensure_ascii=False, indent=1)};\n")
        open(out_ts, "w").write(ts)
