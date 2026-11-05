#!/usr/bin/env python3
"""Helpers for a project's work/gen_reel.py: spoken words → frames → reel/src/Reel.tsx (start from assets/examples/gen_reel*.example.py).

    import os, sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/reel-studio/scripts")); import reelgen as rg
    R = rg.Project(".")                      # work/tl_words.txt, cutlist.json, face_zones.json, beats.json, proxy_offsets.json
    t = R.fw("тело"); u = R.fw("кофта", after=t)
    body = [R.chapter(R.seg(3), "01", "Задача"), R.board(a, b, [rg.tag("Win", src="screens/x.png", x=64, y=300, w=952, h=952)])]
    R.write(body)                           # → reel/src/Reel.tsx with auto imports, SPEECH_END, REEL_FRAMES, captions

Why: anchors are words, never typed frame numbers — a re-cut is a re-run. Every cue inside a scene is LOCAL to its Sequence
(R.L(f, start)); cutaways and boards are widened around timeline cuts by N.coverBefore / N.coverAfter (R.cover); media
Sequences get premountFor; imports are found by scanning `export const` in reel/src, so an example never imports a scene
that the project does not have. Numbers come from references/craft/numbers.json (rg.N).
"""
import difflib, json, os, re, subprocess, sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = {r["key"]: r["value"] for s in json.load(open(os.path.join(SKILL, "references/craft/numbers.json")))["sections"] for r in s["rows"]}

_PUNCT = ".,!?…:;«»\"'()[]—–-“”„"


def norm(word):
    """Lower case, ё → е, outer punctuation off («Tripo,» → tripo, «включение-выключение» keeps its inner hyphen)."""
    return word.strip().lower().replace("ё", "е").strip(_PUNCT)


# ---------------------------------------------------------------- JSX building

class js(str):
    """A raw JS/JSX expression for tag(): rg.js("colors.accent"), rg.js("[1, 2]")."""


def _val(v):
    if isinstance(v, js): return "{" + v + "}"
    if isinstance(v, bool): return "{true}" if v else "{false}"
    if isinstance(v, (int, float)): return "{" + (str(round(v, 4)) if isinstance(v, float) else str(v)) + "}"
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False) if '"' not in v and "\\" not in v else "{" + json.dumps(v, ensure_ascii=False) + "}"
    return "{" + _jsonish(v) + "}"


def _key(k):
    return k if re.match(r"^[A-Za-z_$][\w$]*$", k) else json.dumps(k)


def _jsonish(v):
    """Python lists/dicts → a JS literal (keys unquoted when they are identifiers, js() kept raw)."""
    if isinstance(v, js): return str(v)
    if isinstance(v, bool): return "true" if v else "false"
    if v is None: return "undefined"
    if isinstance(v, (int, float, str)): return json.dumps(round(v, 4) if isinstance(v, float) else v, ensure_ascii=False)
    if isinstance(v, (list, tuple)): return "[" + ", ".join(_jsonish(x) for x in v) + "]"
    if isinstance(v, dict): return "{ " + ", ".join(_key(k) + ": " + _jsonish(x) for k, x in v.items()) + " }"
    raise TypeError(f"cannot write {type(v)} into JSX")


def tag(component, children=None, /, **props):
    """<Component a={1} b="text" /> from Python values (children: a JSX string or a list of them); `from_`-style names drop
    the trailing underscore; None props are skipped."""
    attrs = " ".join(f"{k.rstrip('_')}={_val(v)}" for k, v in props.items() if v is not None)
    head = f"<{component}{' ' + attrs if attrs else ''}"
    if not children: return head + " />"
    kids = children if isinstance(children, (list, tuple)) else [children]
    inner = "\n".join("  " + line for k in kids if k for line in str(k).splitlines())
    return f"{head}>\n{inner}\n</{component}>"


def seq(a, b, children, name, premount=False):
    """<Sequence name from durationInFrames [premountFor]> around children (frames are reel frames)."""
    a, b = int(round(a)), int(round(b))
    if b - a < 1: raise SystemExit(f"empty sequence «{name}»: {a}..{b}")
    return tag("Sequence", children, name=name, from_=a if a else None, durationInFrames=b - a, premountFor=N["premount"] if premount else None)


# ---------------------------------------------------------------- the project

class Project:
    def __init__(self, root=".", words="work/tl_words.txt", cutlist="work/cutlist.json"):
        self.root = os.path.abspath(root); self._sfx_n = {}
        p = lambda rel: os.path.join(self.root, rel)
        self.words = []
        if os.path.exists(p(words)):
            for line in open(p(words), encoding="utf-8"):
                parts = line.split(None, 1)
                if len(parts) == 2 and parts[0].lstrip("-").isdigit(): self.words.append((int(parts[0]), norm(parts[1]), parts[1].strip()))
        self.cl = json.load(open(p(cutlist)))
        self.segs = self.cl["main"]
        self.END = self.cl["totalFrames"]
        self.silent = bool(self.cl.get("silent"))
        self.offsets = json.load(open(p("work/proxy_offsets.json"))) if os.path.exists(p("work/proxy_offsets.json")) else {}
        self.zones = json.load(open(p("work/face_zones.json"))) if os.path.exists(p("work/face_zones.json")) else []
        self.beatfile = json.load(open(p("work/beats.json"))) if os.path.exists(p("work/beats.json")) else None
        self.cuts = self._cuts()
        self.log = []
        if not self.words and not self.silent: print("WARNING: no work/tl_words.txt — run tl_words.py (or mark the cut list silent)")

    # ---- words
    def fw(self, word, after=0, nth=1, before=None):
        """Frame of the nth occurrence of `word` at or after `after` (and before `before`). Missing → stop with the nearest words."""
        w = norm(word)
        hits = [f for f, x, _ in self.words if x == w and f >= after and (before is None or f < before)]
        if len(hits) >= nth: return hits[nth - 1]
        near = difflib.get_close_matches(w, sorted({x for f, x, _ in self.words if f >= after}), n=5)
        raise SystemExit(f"word not found: «{word}» (#{nth}) after {after}{'' if before is None else f' before {before}'}; close: {near} — fix the cut, brands.json or the anchor, never type a frame")

    def fw_any(self, cands, after=0, before=None):
        """First frame among several spellings («28», «двадцать», «двадцати»)."""
        ws = {norm(c) for c in cands}
        hits = sorted(f for f, x, _ in self.words if x in ws and f >= after and (before is None or f < before))
        if hits: return hits[0]
        raise SystemExit(f"none of {cands} after {after}")

    def words_between(self, a, b):
        return [(f, raw) for f, _, raw in self.words if a <= f < b]

    # ---- cut list
    def seg(self, i):
        """Start frame of main-track segment i (the segment map lives in the generator's header comment)."""
        return self.segs[i]["fromFrame"]

    def seg_end(self, i):
        s = self.segs[i]; return s["fromFrame"] + s["durFrames"]

    def _cuts(self):
        """Visual cuts: segment starts where the source changes or the trim jumps (mute slivers are merged by gen_timeline)."""
        out = []
        for p, s in zip(self.segs, self.segs[1:]):
            same = p.get("path") == s.get("path") and abs(p.get("trimBeforeFrames", 0) + p["durFrames"] - s.get("trimBeforeFrames", 0)) <= 1
            if not same: out.append(s["fromFrame"])
        return out

    def trim(self, cid, src_sec):
        """trimBefore (proxy frames) that shows second `src_sec` of the source in footage/<cid>.mp4 (trimmed proxies have offsets)."""
        return int(round((src_sec - self.offsets.get(cid, 0)) * 30))

    def cover(self, a, b, name="layer"):
        """Widen a full-frame layer [a, b) so no timeline cut shows through: a cut inside gets N.coverBefore / N.coverAfter
        around it; a fade-out that would end right before a cut, or a fade-in during a cut's dissolve, straddles the cut instead."""
        a0, b0 = a, b
        for _ in range(10):
            pa, pb = a, b
            for c in self.cuts:
                if a < c < b:
                    a = min(a, c - N["coverBefore"]); b = max(b, c + N["coverAfter"])
                elif 0 <= c - b < N["layerFade"]:
                    b = c + N["coverAfter"]
                elif 0 <= a - c < N["xfade"] + 2:
                    a = c - N["coverBefore"]
            if (a, b) == (pa, pb): break
        a = max(0, a)
        if (a, b) != (a0, b0): self.log.append(f"cover «{name}»: {a0}..{b0} → {a}..{b}")
        return a, b

    # ---- layout
    def _zones(self, a, b):
        return [z for z in self.zones if z.get("fromFrame", 0) < b and z.get("fromFrame", 0) + z.get("durFrames", 0) > a]

    def free_top(self, a, b, default=(N["cardTop"], N["bandBottom"])):
        """Free band above the face over frames [a, b) (face_zones.json is already in screen coordinates, punch included)."""
        zs = [z["freeTop"] for z in self._zones(a, b) if z.get("freeTop")]
        return (max(z[0] for z in zs), min(z[1] for z in zs)) if zs else default

    def free_bottom(self, a, b, default=(N["cardTop"], N["bandBottom"])):
        """Free band under the face (card band) over frames [a, b)."""
        zs = [z["freeBottom"] for z in self._zones(a, b) if z.get("freeBottom")]
        return (max(z[0] for z in zs), min(z[1] for z in zs)) if zs else default

    def beats(self, every=1, start=0, end=None):
        """Beat frames of the music bed (work/beats.json from silent_timeline.py / make_bed.sh): {"frames": [...]} or {"bpm", "offsetFrames"}."""
        end = self.END if end is None else end
        bf = self.beatfile or {}
        if "frames" in bf: fr = bf["frames"]
        elif "bpm" in bf: step = 30 * 60 / bf["bpm"]; fr = [round(bf.get("offsetFrames", 0) + i * step) for i in range(int(end / step) + 2)]
        else: raise SystemExit("no work/beats.json — silent reels place pictures on the bed's beat grid")
        return [f for f in fr if start <= f < end][::every]

    @staticmethod
    def L(f, start):
        """Reel frame → local frame of a Sequence that starts at `start` (every component reads local frames)."""
        return int(round(f - start))

    # ---- layers
    def cutaway(self, cid, src_sec, a, b, name, zoom=(1, 1.08), fade=(None, None), cover=True, behind=None):
        """Full-frame b-roll from footage/<cid>.mp4 showing source second `src_sec` at reel frame `a`; widened by cover().
        behind={"title": "ХЭЛЛОУИН", "kicker": "31.10", "at": 6, "until": 80, "mode": "person"|"subject"} puts the title
        BEHIND the person: person_matte.py cuts them out of the 2K proxy for exactly these frames (cached in public/mattes)."""
        na, nb = self.cover(a, b, name) if cover else (a, b)
        tb = self.trim(cid, src_sec) - (a - na)
        if tb < 0: raise SystemExit(f"cutaway «{name}»: the proxy starts too late for the widened range (trimBefore {tb}) — re-run make_proxies with a wider window")
        bh = None
        if behind:
            bh = {k: v for k, v in behind.items() if k != "mode"}; bh["matte"] = self.matte(cid, tb, nb - na, behind.get("mode", "person"))
            if "y" not in bh:
                from common import title_y
                bh["y"] = title_y(os.path.join(self.root, "reel/public", bh["matte"].replace(".webm", ".mask.json")))
        return seq(na, nb, tag("BRoll", src=f"footage/{cid}.mp4", trimBefore=tb, zoomFrom=zoom[0], zoomTo=zoom[1], fadeIn=fade[0], fadeOut=fade[1], behind=bh), name, premount=True)

    def matte(self, cid, trim, frames, mode="person"):
        """reel/public/mattes/<cid>_<trim>_<frames>_<mode>.webm: the people of footage2k/<cid>.mp4 (or footage/) from proxy frame
        `trim`, `frames` long, transparent elsewhere — made once, reused on re-runs while the proxy is older than it."""
        rel = f"mattes/{cid}_{trim}_{frames}_{mode}.webm"; out = os.path.join(self.root, "reel/public", rel)
        src = next((p for p in (os.path.join(self.root, "reel/public/footage2k", cid + ".mp4"), os.path.join(self.root, "reel/public/footage", cid + ".mp4")) if os.path.exists(p)), None)
        if not src: raise SystemExit(f"matte: no proxy for {cid}")
        if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
            os.makedirs(os.path.dirname(out), exist_ok=True)
            py = os.path.join(self.root, "work/venv/bin/python")
            r = subprocess.run([py, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "person_matte.py"), src, out, "--from", f"{trim / 30:.4f}",
                                "--to", f"{(trim + frames) / 30:.4f}", "--mode", mode], cwd=self.root, capture_output=True, text=True)
            if r.returncode: raise SystemExit(f"person_matte failed for {cid}: {r.stdout[-400:]}{r.stderr[-400:]}")
            print("   ", r.stdout.strip().splitlines()[-1] if r.stdout.strip() else rel, file=sys.stderr)
        return rel

    def board(self, a, b, children, name, fade=(None, None), cover=True):
        """A full-frame Board [a, b) (widened by cover()); children use LOCAL frames: R.L(t, start) with start = returned .start."""
        na, nb = self.cover(a, b, name) if cover else (a, b)
        self.last = (na, nb)
        kids = children(na) if callable(children) else children
        return seq(na, nb, tag("Board", kids, fadeIn=fade[0], fadeOut=fade[1]), name, premount=True)

    def chapter(self, cut, n, title, flash=True):
        """Flash on the cut, tag + whoosh N.chapterLead frames later."""
        k = self._sfx_n.get("whoosh", 0); self._sfx_n["whoosh"] = k + 1; w = "whoosh" if k % N["sfxVariants"] == 0 else f"whoosh{k % N['sfxVariants'] + 1}"
        return seq(cut, cut + N["chapterLead"] + N["tagFrames"], tag("Chapter", n=n, title=title, flash=None if flash else False, whoosh=None if w == "whoosh" else w), f"chapter {n}")

    VARIED = ("whoosh", "softwhoosh", "pop", "hit")

    def sfx(self, at, kind, name=None, volume=None, vary=True):
        """One sound at `at`. whoosh / softwhoosh / pop / hit cycle through their N.sfxVariants versions (whoosh, whoosh2,
        whoosh3, whoosh …) in placement order, so two in a row are never the same sample; vary=False pins the base one."""
        file = kind
        if vary and kind in self.VARIED:
            k = self._sfx_n.get(kind, 0); self._sfx_n[kind] = k + 1
            file = kind if k % N["sfxVariants"] == 0 else f"{kind}{k % N['sfxVariants'] + 1}"
        return seq(at, at + N["sfxFrames"], tag("Sfx", kind=file, volume=volume), name or f"sfx {file}")

    def sfx_many(self, frames, kind, name=None):
        return "\n".join(self.sfx(f, kind, f"{name or 'sfx ' + kind} {i}") for i, f in enumerate(frames))

    def ticks(self, a, b, kind="tick"):
        """A tick every N.sfxTickEvery frames while a number counts from a to b."""
        return self.sfx_many(list(range(int(a), int(b), N["sfxTickEvery"])), kind, "sfx ticks")

    def music_bed(self, src="audio/lofi_bed.m4a", speech_start=None, speech_end=None, pauses=(), under=None, open_=None):
        """The bed over the whole reel: bedOpen before the first word, in `pauses` and after speech_end, bedUnder under
        speech (`under=0.09` when the user says the music is too loud), ramps and an end fade from N."""
        if self.silent: speech_start, speech_end = 0, 0  # no speech: the bed carries the reel at bedOpen
        first = self.words[0][0] if self.words else 0
        return tag("MusicBed", src=src, speechStart=first if speech_start is None else speech_start, speechEnd=self.END if speech_end is None else speech_end,
                   pauses=[list(p) for p in pauses] or None, under=under, open=open_)

    def capcut_voiceovers(self):
        """Sequences for the voiceovers the user recorded inside a CapCut draft, where the draft put them (levelled
        reel/public/audio/<name>.m4a from match_loudness.py)."""
        out = []
        vo = set(self.cl.get("voiceovers", []))
        for t in self.cl.get("tracks", []):
            if t.get("type") != "audio": continue
            for sg in t.get("segments", []):
                if sg.get("path") not in vo or sg.get("volume", 1) < 0.01: continue
                stem = os.path.splitext(os.path.basename(sg["path"]))[0]
                aud = tag("Audio", src=js(f'staticFile("audio/{stem}.m4a")'), trimBefore=sg["trimBeforeFrames"], volume=sg.get("volume", 1))
                out.append(seq(sg["fromFrame"], sg["fromFrame"] + sg["durFrames"], aud, f"vo {stem}"))
        return out

    # ---- write
    def write(self, body, path="reel/src/Reel.tsx", stage=None, speech_end=None, tail=None, end_card=True, captions=None, imports=None):
        """Write Reel.tsx: stage (default <Stage windows={[]}><Timeline/></Stage>), body layers in order, the end card in the
        `tail` frames after speech_end (end_card=False: put your own closing layer there), captions over the whole reel
        (off for silent cut lists). `imports` overrides auto-import: {"Name": "./scenes/X"}. Returns REEL_FRAMES."""
        speech_end = self.END if speech_end is None else speech_end
        tail = N["endTail"] if tail is None else tail
        reel = speech_end + tail  # the tail holds the end card (or your own closing layer with end_card=False)
        layers = [stage or tag("Stage", tag("Timeline"), windows=js("[]"))]
        layers += [x for x in body if x]
        if end_card: layers.append(seq(speech_end, reel, tag("EndCard"), "end"))
        if captions is None: captions = not self.silent
        if captions: layers.append(seq(0, reel, tag("Captions", src="captions/timeline.json"), "captions"))
        jsx = "\n".join(layers)
        src_dir = os.path.join(self.root, os.path.dirname(path))
        head = _imports(jsx, src_dir, os.path.join(self.root, path), imports or {})
        inner = "\n".join("    " + line for line in jsx.splitlines())
        tsx = (f"{head}\n\n/* Generated by work/gen_reel.py (scripts/reelgen.py) from word timestamps — edit the generator, not this file. */\n"
               f"export const SPEECH_END = {speech_end};\nexport const REEL_FRAMES = {reel};\n\n"
               f"export const Reel: React.FC = () => (\n  <AbsoluteFill style={{{{ backgroundColor: colors.bg }}}}>\n{inner}\n  </AbsoluteFill>\n);\n")
        out = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w").write(tsx)
        for line in self.log: print(line)
        print(f"wrote {path}: SPEECH_END {speech_end}, REEL_FRAMES {reel} ({reel / 30:.1f} s), {len(body)} layers")
        return reel


_EXTERNAL = {"Sequence": "remotion", "AbsoluteFill": "remotion", "Img": "remotion", "staticFile": "remotion", "interpolate": "remotion", "Easing": "remotion", "Audio": "@remotion/media", "Video": "@remotion/media"}


def _exports(src_dir, skip):
    """name → module ('./scenes/Board') for every `export const|function X` under reel/src (re-exports are ignored)."""
    found = {}
    for root, _, files in os.walk(src_dir):
        for f in files:
            full = os.path.join(root, f)
            if not f.endswith((".ts", ".tsx")) or os.path.abspath(full) == os.path.abspath(skip): continue
            mod = "./" + os.path.relpath(full, src_dir).rsplit(".", 1)[0].replace(os.sep, "/")
            for name in re.findall(r"^export (?:const|function) ([A-Za-z_]\w*)", open(full, encoding="utf-8").read(), re.M):
                found.setdefault(name, []).append(mod)
    return found


def _imports(jsx, src_dir, out_path, overrides):
    used = set(re.findall(r"<([A-Z][A-Za-z0-9]*)", jsx)) | {"AbsoluteFill"}
    used |= set(re.findall(r"\b(colors|shadows|safe|brand|N|staticFile|interpolate|Easing)\b(?=[.(])", jsx)) | {"colors"}
    ex = _exports(src_dir, out_path)
    by_mod, missing, clash = {}, [], []
    for name in sorted(used):
        mod = overrides.get(name) or _EXTERNAL.get(name)
        if not mod:
            mods = ex.get(name, [])
            if not mods: missing.append(name); continue
            if len(mods) > 1: clash.append(f"{name}: {mods}"); continue
            mod = mods[0]
        by_mod.setdefault(mod, []).append(name)
    if missing: raise SystemExit(f"components not found in {src_dir}: {missing} — copy the scene file in or fix the name")
    if clash: raise SystemExit("ambiguous names (pass imports={'Name': './path'}): " + "; ".join(clash))
    order = sorted(by_mod, key=lambda m: (not m.startswith("remotion"), not m.startswith("@"), m))
    return 'import React from "react";\n' + "\n".join(f'import {{ {", ".join(sorted(by_mod[m]))} }} from "{m}";' for m in order)


if __name__ == "__main__":
    R = Project(sys.argv[1] if len(sys.argv) > 1 else ".")
    print(f"{len(R.words)} words, {len(R.segs)} segments, cuts at {R.cuts}, END {R.END}, silent={R.silent}")
