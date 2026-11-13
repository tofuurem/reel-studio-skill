#!/usr/bin/env python3
"""Find a REAL recorded sound effect (Openverse: ≈ 5 M openly licensed sounds, mostly Freesound) and add it to the reel.

Usage: python3 -I sfx_find.py <project> "camera shutter" [--license cc0|by] [--n 8] [--min-s 0.1] [--max-s 12]
       python3 -I sfx_find.py <project> "camera shutter" --pick 3 --name shutter_film [--trim 0.4-1.1]
1. Search: api.openverse.org (no key; ≈ 20 requests a minute, 200 a day). Only licences that allow commercial use and
   changes are offered: CC0 (default, nothing to credit) or, with --license by, CC0 + CC BY (credit the author in the post
   description). Never CC BY-NC / ND / SA — a reel on a monetised account is commercial, and an SA licence would bind the
   whole video.
2. The top --n previews (MP3) go to work/sfx_search/<query>/NN.mp3 with work/sfx_search/<query>/candidates.json + .md:
   title, author, licence, length, link. With earshot installed (deps.py --with sound) the candidates are RANKED by how
   well they sound like the query (`earshot rank`, CLAP) and every long one gets its best moment (`earshot find`) — Claude
   cannot hear, earshot can. Without it the order is Openverse's.
3. --pick K --name X: candidate K → reel/public/audio/sfx/real_X.wav (48 kHz stereo; the best moment or --trim A-B; leading
   silence cut; a 20 ms fade out; −20 LUFS, so N.sfxReal sets its level like any other kind) + assets/sfx/real_X.json (the
   source, licence, attribution); a CC BY sound also goes into work/credits.md, the lines for the post description.
   In gen_reel.py: R.sfx(at, "real_X").
Use a real recording when the picture shows a real event the camera did not capture (a shutter, fireworks far away, a
crowd) — the camera's own sound comes first (`amb` beats, event-vlog.md). Prints SFX_FIND_DONE.
"""
import argparse, json, os, re, shutil, subprocess, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import add_guard_args, guard_reexec

API = "https://api.openverse.org/v1/audio/"
OK = {"cc0": ["cc0"], "by": ["cc0", "by"]}
LIC_URL = {"cc0": "https://creativecommons.org/publicdomain/zero/1.0/", "by": "https://creativecommons.org/licenses/by/{v}/"}


def curl_json(url):
    """HTTP through curl: Python's own TLS stack failed on some setups (proxies, filtered networks) where curl works."""
    r = subprocess.run(["curl", "-sSL", "--max-time", "30", "-H", "User-Agent: reel-studio-skill", url], capture_output=True, text=True)
    if r.returncode: sys.exit(f"Openverse did not answer ({r.stderr.strip()[:200]})")
    try: return json.loads(r.stdout)
    except ValueError: sys.exit(f"Openverse: not JSON — {r.stdout[:200]}")


def slug(s):
    return re.sub(r"[^a-z0-9а-яё]+", "_", s.lower()).strip("_")[:40] or "sound"


def earshot_json(args):
    if not shutil.which("earshot"): return None
    r = subprocess.run(["earshot", *args, "--json"], capture_output=True, text=True)
    if r.returncode: print(f"  (earshot {args[0]} failed: {(r.stderr or r.stdout).strip()[-160:]})"); return None
    try: return json.loads(r.stdout)
    except ValueError: return None


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", path, "-af", "apad=pad_dur=0.6,ebur128", "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def search(a, P):
    q = urllib.parse.urlencode({"q": a.query, "license": ",".join(OK[a.license]), "page_size": 20})
    d = curl_json(f"{API}?{q}")
    if d.get("detail"): sys.exit(f"Openverse: {d['detail']}")
    rows = [r for r in d.get("results", []) if r.get("license") in OK[a.license] and r.get("url")
            and a.min_s <= (r.get("duration") or 0) / 1000 <= a.max_s][: a.n]
    if not rows: sys.exit(f"nothing under {'/'.join(OK[a.license])} between {a.min_s} and {a.max_s} s for «{a.query}» — try other words (English works best) or --license by")
    out = os.path.join(P, "work/sfx_search", slug(a.query)); os.makedirs(out, exist_ok=True)
    for i, r in enumerate(rows, 1):
        f = os.path.join(out, f"{i:02d}.mp3")
        if not os.path.exists(f):   # --fail: an HTTP error page must not be saved as an .mp3
            if subprocess.run(["curl", "-sSLf", "--max-time", "60", "-o", f, r["url"]]).returncode or not os.path.getsize(f):
                print(f"  skip «{r.get('title')}»: the file did not download"); os.path.exists(f) and os.remove(f); r["file"] = None; continue
        r["file"] = f
    rows = [r for r in rows if r.get("file")]
    if not rows: sys.exit("no candidate downloaded — Openverse / Freesound did not answer; try again later")
    rank = earshot_json(["rank", a.query, *[r["file"] for r in rows]])
    if rank:
        by = {os.path.realpath(x.get("path", "")): x for x in (rank.get("results") or rank.get("ranked") or [])}
        for r in rows:
            x = by.get(os.path.realpath(r["file"]), {})
            r["match"] = f"{x.get('verdict')} (z {x.get('z'):+.1f})" if x.get("verdict") else None   # strong / plausible / weak / no match
            r["score"] = x.get("z") or 0
        rows.sort(key=lambda r: -float(r["score"] or 0))
        for r in rows:
            if (r.get("duration") or 0) > 2500:   # a long recording: where in it is the sound?
                fd = earshot_json(["find", r["file"], a.query, "--top", "1"])
                seg = ((fd or {}).get("segments") or (fd or {}).get("results") or [{}])[0]
                if "start" in seg: r["best"] = [round(seg["start"], 2), round(seg["end"], 2)]
    for i, r in enumerate(rows, 1):   # the numbers follow the final order
        n = os.path.join(out, f"c{i:02d}.mp3"); os.replace(r["file"], n) if r["file"] != n else None; r["file"] = n
    for f in os.listdir(out):
        if re.fullmatch(r"\d\d\.mp3", f): os.remove(os.path.join(out, f))
    keep = ["title", "creator", "license", "license_version", "duration", "foreign_landing_url", "url", "attribution", "source", "file", "match", "best"]
    json.dump([{k: r.get(k) for k in keep} for r in rows], open(os.path.join(out, "candidates.json"), "w"), ensure_ascii=False, indent=1)
    md = [f"# «{a.query}» — Openverse, {'/'.join(OK[a.license])}", "", "| # | title | author | licence | s | earshot | best moment |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        md.append(f"| {i} | {r.get('title', '')[:40]} | {r.get('creator') or '?'} | {r['license']} | {(r.get('duration') or 0) / 1000:.1f} | {r.get('match') or ''} | {r.get('best') or ''} |")
    open(os.path.join(out, "candidates.md"), "w").write("\n".join(md) + "\n"); print("\n".join(md))
    print(f"\n{len(rows)} previews in {os.path.relpath(out, P)}/ — listen or let earshot judge, then --pick K --name <kind>"
          + ("" if rank else "\n(earshot not installed: no ranking — deps.py --install --with sound)"))


def pick(a, P):
    out = os.path.join(P, "work/sfx_search", slug(a.query)); cands = json.load(open(os.path.join(out, "candidates.json")))
    if not 1 <= a.pick <= len(cands): sys.exit(f"--pick 1…{len(cands)}")
    r = cands[a.pick - 1]; name = "real_" + slug(a.name or a.query)
    t0, t1 = (map(float, a.trim.split("-")) if a.trim else (r.get("best") or [None, None]))
    D = os.path.join(P, "reel/public/audio/sfx"); os.makedirs(D, exist_ok=True); dst = os.path.join(D, name + ".wav"); tmp = dst + ".part.wav"
    cut = ["-ss", str(t0), "-to", str(t1)] if t0 is not None else []
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *cut, "-i", r["file"], "-af",
                    "silenceremove=start_periods=1:start_threshold=-50dB,areverse,afade=t=in:d=0.02,areverse,aformat=sample_rates=48000:channel_layouts=stereo",
                    "-c:a", "pcm_s24le", tmp], check=True)
    l = lufs(tmp); g = -20 - l if l is not None else 0
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", tmp, "-af", f"volume={g:.2f}dB,alimiter=limit=0.89:level=false", "-c:a", "pcm_s24le", dst], check=True); os.remove(tmp)
    v = r.get("license_version") or "4.0"
    meta = {"name": name, "query": a.query, "title": r.get("title"), "creator": r.get("creator"), "license": r["license"], "licenseUrl": LIC_URL[r["license"]].format(v=v),
            "page": r.get("foreign_landing_url"), "file": r.get("url"), "trim": [t0, t1] if t0 is not None else None, "attribution": r.get("attribution")}
    os.makedirs(os.path.join(P, "assets/sfx"), exist_ok=True); json.dump(meta, open(os.path.join(P, "assets/sfx", name + ".json"), "w"), ensure_ascii=False, indent=1)
    if r["license"] == "by":
        line = f"- Звук «{r.get('title')}» — {r.get('creator')}, CC BY {v} ({r.get('foreign_landing_url')}), обрезан и выровнен по громкости"   # CC BY: say it was changed
        cp = os.path.join(P, "work/credits.md"); old = open(cp).read() if os.path.exists(cp) else "# Credits for the post description\n\n"
        if line not in old: open(cp, "w").write(old + line + "\n")
        print(f"CC BY: credit it in the post description — work/credits.md:\n{line}")
    print(f"{os.path.relpath(dst, P)} ({r.get('title')}, {r['license']}{', ' + str(t0) + '–' + str(t1) + ' s' if t0 is not None else ''}) — R.sfx(at, \"{name}\")")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("query")
    ap.add_argument("--license", choices=sorted(OK), default="cc0"); ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--min-s", type=float, default=0.1); ap.add_argument("--max-s", type=float, default=12.0)
    ap.add_argument("--pick", type=int); ap.add_argument("--name"); ap.add_argument("--trim", help="A-B seconds of the candidate")
    add_guard_args(ap, 4.0)   # earshot rank / find (CLAP) over a handful of short candidates
    a = ap.parse_args(); guard_reexec(a); P = os.path.abspath(a.project)
    pick(a, P) if a.pick else search(a, P)
    print("SFX_FIND_DONE")


if __name__ == "__main__":
    main()
