#!/usr/bin/env python3
"""Find a REAL recorded sound effect (Openverse: ≈ 5 M openly licensed sounds, mostly Freesound) and add it to the reel.

Usage: python3 -I sfx_find.py <project> "camera shutter" [--license cc0|by] [--n 8] [--min-s 0.1] [--max-s 12]
       python3 -I sfx_find.py <project> "camera shutter" --pick 3 --name shutter_film [--trim 0.4-1.1]
1. Search: api.openverse.org (no key; ≈ 20 requests a minute, 200 a day). Only licences that allow commercial use and
   changes are offered: CC0 (default, nothing to credit) or, with --license by, CC0 + CC BY (credit the author in the post
   description). Never CC BY-NC / ND / SA — a reel on a monetised account is commercial, and an SA licence would bind the
   whole video.
2. The top --n files go to work/sfx_search/<query>/cNN.<ext> (the file's real type: mp3, ogg, wav, flac …) with work/sfx_search/<query>/candidates.json + .md:
   title, author, licence, length, link. With earshot installed (deps.py --with sound) the candidates are RANKED by how
   well they sound like the query (`earshot rank`, CLAP) and every long one gets its best moment (`earshot find`) — Claude
   cannot hear, earshot can. Without it the order is Openverse's.
3. --pick K --name X: candidate K → reel/public/audio/sfx/real_X.wav (48 kHz stereo; the best moment or --trim A-B; leading
   silence cut; a 20 ms fade out; −20 LUFS, so N.sfxReal sets its level like any other kind) + assets/sfx/real_X.json (the
   source, licence, attribution); a CC BY sound also goes into work/credits.md, the lines for the post description.
   In gen_reel.py: R.sfx(at, "real_X").
Use a real recording when the picture shows a real event the camera did not capture (a shutter, fireworks far away, a
crowd) — the camera's own sound comes first (`amb` beats, event-vlog.md). Prints SFX_FIND_DONE.

MUSIC MODE (--music): a real openly licensed TRACK for a bed instead of the procedural lofi.py one, a different one per video.
  python3 -I sfx_find.py <project> "lofi chill|chillhop|jazzy piano" --music --mood "calm warm lo-fi, slow, sunset by the sea"
  python3 -I sfx_find.py <project> "lofi chill|chillhop|jazzy piano" --music --pick 2 --name sea_lofi
- Openverse with a length filter (30 s–10 min; Freesound loops and tracks, Jamendo, Wikimedia — mostly CC BY, so the
  licence defaults to by), 60–600 s, page 1 plus random other pages per query and several queries split by «|»: one query
  on page 1 always returns the same handful of tracks, so every video would get the same music. (Openverse's
  category=music finds almost nothing, so it is not used; some queries get a 500 — retried once, then that page is skipped.)
- Variety: at most one track per author; every track already picked in ANY project (~/.cache/reel-studio/used_music.json)
  is skipped (--allow-used to keep them); candidates alternate between the queries. earshot ranks them by --mood (a short
  English description of the feel), not by the search words.
- --pick K --name X: the full track → assets/music/X.<ext> + assets/music/X.json (source, licence), remembered in the
  used list, a CC BY credit line in work/credits.md. Then the usual track path: track_beats.py for the tempo and the grid,
  ffmpeg → reel/public/audio/lofi_bed.wav (craft/audio.md step 4). When the platform lets the user add its own music, the
  upload is the version WITHOUT the bed unless they ask otherwise — the found track is for the preview / the variant with music.
"""
import argparse, json, os, random, re, shutil, subprocess, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import add_guard_args, guard_reexec

API = "https://api.openverse.org/v1/audio/"
USED = os.path.expanduser("~/.cache/reel-studio/used_music.json")   # tracks picked in any project (music mode)
OK = {"cc0": ["cc0"], "by": ["cc0", "by"]}
LIC_URL = {"cc0": "https://creativecommons.org/publicdomain/zero/1.0/", "by": "https://creativecommons.org/licenses/by/{v}/"}


def curl_json(url, soft=False):
    """HTTP through curl: Python's own TLS stack failed on some setups (proxies, filtered networks) where curl works."""
    r = subprocess.run(["curl", "-sSL", "--max-time", "30", "-H", "User-Agent: reel-studio-skill", url], capture_output=True, text=True)
    if r.returncode:
        if soft: return {"detail": f"no answer ({r.stderr.strip()[:120]})"}
        sys.exit(f"Openverse did not answer ({r.stderr.strip()[:200]})")
    try: return json.loads(r.stdout)
    except ValueError:   # Openverse answers some queries with an HTML «Server Error (500)» page
        if soft: return {"detail": "server error (an HTML page instead of JSON)"}
        sys.exit(f"Openverse: not JSON — {r.stdout[:200]}")


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


def load_used():
    try: return json.load(open(USED))
    except (OSError, ValueError): return []


AUDIO_EXT = {"mp3", "ogg", "oga", "opus", "wav", "flac", "m4a", "aac", "aif", "aiff", "webm"}


def audio_ext(r):
    """The real extension of an Openverse result's file: its filetype, else the URL's, else .mp3."""
    for e in ((r.get("filetype") or "").lower().lstrip("."), os.path.splitext(urllib.parse.urlparse(r.get("url") or "").path)[1].lower().lstrip(".")):
        if e in AUDIO_EXT: return "." + e
    return ".mp3"


def atomic_json(obj, path):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f: json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def search_dir(a, P):
    return os.path.join(P, "work/music_search" if a.music else "work/sfx_search", slug(a.query))


def search(a, P):
    queries = [q.strip() for q in a.query.split("|") if q.strip()] if a.music else [a.query]
    used = {u.get("url") for u in load_used()} if a.music and not a.allow_used else set()
    per_q, seen, skipped = [], set(), 0

    def fetch(q, page):
        params = {"q": q, "license": ",".join(OK[a.license]), "page_size": 20, "page": page}
        if a.music: params["length"] = "short,medium" if a.min_s < 120 else "medium"   # Openverse: short 30 s–2 min, medium 2–10 min
        for attempt in range(2):
            if a.music: time.sleep(1.5)   # Openverse: ≈ 20 requests a minute, «Search is over capacity» when faster
            d = curl_json(f"{API}?{urllib.parse.urlencode(params)}", soft=a.music)
            if not d.get("detail") or not re.search(r"server error|capacity", d["detail"]): return d
            time.sleep(4)
        return d

    for q in queries:
        got, pages, done = [], [1], set()
        while pages:
            page = pages.pop(0); done.add(page)
            d = fetch(q, page)
            if d.get("detail"):
                if a.music: print(f"  «{q}» page {page}: Openverse — {d['detail']}, skipped"); continue
                if page > 1: break
                sys.exit(f"Openverse: {d['detail']}")
            for r in d.get("results", []):
                if r.get("license") not in OK[a.license] or not r.get("url") or r["url"] in seen: continue
                if not a.min_s <= (r.get("duration") or 0) / 1000 <= a.max_s: continue
                if r["url"] in used: skipped += 1; continue
                seen.add(r["url"]); got.append(r)
            if page == 1 and a.pages > 1:   # the other pages at random: not the same top results for every video
                rest = list(range(2, (d.get("page_count") or 1) + 1)); random.shuffle(rest); pages += rest[: a.pages - 1]
        random.shuffle(got) if a.music and a.pages > 1 else None
        per_q.append(got)
    rows, authors = [], set()
    for i in range(max((len(g) for g in per_q), default=0)):   # alternate between the queries
        for g in per_q:
            if i < len(g) and len(rows) < a.n:
                who = (g[i].get("creator") or "").strip().lower()
                if a.music and who and who in authors: continue   # one track per author
                authors.add(who); rows.append(g[i])
    if skipped: print(f"  skipped {skipped} track(s) already used in earlier projects ({USED})")
    if not rows: sys.exit(f"nothing under {'/'.join(OK[a.license])} between {a.min_s} and {a.max_s} s for «{a.query}» — try other words (English works best) or --license by")
    out = search_dir(a, P); os.makedirs(out, exist_ok=True)
    for i, r in enumerate(rows, 1):
        f = os.path.join(out, f"{i:02d}{audio_ext(r)}")
        if not os.path.exists(f):   # --fail: an HTTP error page must not be saved as audio
            if subprocess.run(["curl", "-sSLf", "--max-time", "180" if a.music else "60", "-o", f, r["url"]]).returncode or not os.path.getsize(f):
                print(f"  skip «{r.get('title')}»: the file did not download"); os.path.exists(f) and os.remove(f); r["file"] = None; continue
        r["file"] = f
    rows = [r for r in rows if r.get("file")]
    if not rows: sys.exit("no candidate downloaded — Openverse / Freesound did not answer; try again later")
    rank = earshot_json(["rank", a.mood or queries[0], *[r["file"] for r in rows]])
    if rank:
        by = {os.path.realpath(x.get("path", "")): x for x in (rank.get("results") or rank.get("ranked") or [])}
        for r in rows:
            x = by.get(os.path.realpath(r["file"]), {})
            r["match"] = f"{x.get('verdict')} (z {x.get('z'):+.1f})" if x.get("verdict") else None   # strong / plausible / weak / no match
            r["score"] = x.get("z") or 0
        rows.sort(key=lambda r: -float(r["score"] or 0))
        for r in rows:
            if not a.music and (r.get("duration") or 0) > 2500:   # a long recording: where in it is the sound?
                fd = earshot_json(["find", r["file"], a.query, "--top", "1"])
                seg = ((fd or {}).get("segments") or (fd or {}).get("results") or [{}])[0]
                if "start" in seg: r["best"] = [round(seg["start"], 2), round(seg["end"], 2)]
    for i, r in enumerate(rows, 1):   # the numbers follow the final order
        n = os.path.join(out, f"c{i:02d}{os.path.splitext(r['file'])[1]}"); os.replace(r["file"], n) if r["file"] != n else None; r["file"] = n
    for f in os.listdir(out):
        if re.fullmatch(r"\d\d\.\w+", f): os.remove(os.path.join(out, f))
    keep = ["title", "creator", "license", "license_version", "duration", "foreign_landing_url", "url", "attribution", "source", "file", "match", "best"]
    json.dump([{k: r.get(k) for k in keep} for r in rows], open(os.path.join(out, "candidates.json"), "w"), ensure_ascii=False, indent=1)
    md = [f"# «{a.query}» — Openverse{' music' if a.music else ''}, {'/'.join(OK[a.license])}", "", "| # | title | author | licence | source | s | earshot | best moment |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        md.append(f"| {i} | {r.get('title', '')[:40]} | {r.get('creator') or '?'} | {r['license']} | {r.get('source') or ''} | {(r.get('duration') or 0) / 1000:.1f} | {r.get('match') or ''} | {r.get('best') or ''} |")
    open(os.path.join(out, "candidates.md"), "w").write("\n".join(md) + "\n"); print("\n".join(md))
    print(f"\n{len(rows)} {'tracks' if a.music else 'previews'} in {os.path.relpath(out, P)}/ — listen or let earshot judge, then --pick K --name <kind>"
          + ("" if rank else "\n(earshot not installed: no ranking — deps.py --install --with sound)"))


def pick_music(a, P, r):
    name = slug(a.name or a.query); D = os.path.join(P, "assets/music"); os.makedirs(D, exist_ok=True)
    dst = os.path.join(D, name + (os.path.splitext(r["file"])[1] or ".mp3")); shutil.copyfile(r["file"], dst)
    v = r.get("license_version") or "4.0"
    meta = {"name": name, "query": a.query, "title": r.get("title"), "creator": r.get("creator"), "license": r["license"], "licenseUrl": LIC_URL[r["license"]].format(v=v),
            "page": r.get("foreign_landing_url"), "file": r.get("url"), "source": r.get("source"), "attribution": r.get("attribution")}
    json.dump(meta, open(os.path.join(D, name + ".json"), "w"), ensure_ascii=False, indent=1)
    used = load_used(); os.makedirs(os.path.dirname(USED), exist_ok=True)
    if r.get("url") not in {u.get("url") for u in used}:
        used.append({"url": r.get("url"), "title": r.get("title"), "creator": r.get("creator"), "project": P})
        atomic_json(used, USED)
    if r["license"] == "by":
        line = f"- Music \"{r.get('title')}\" by {r.get('creator')}, CC BY {v} ({r.get('foreign_landing_url')}), trimmed and mixed with the video"
        cp = os.path.join(P, "work/credits.md"); old = open(cp).read() if os.path.exists(cp) else "# Credits for the post description\n\n"
        if line not in old: open(cp, "w").write(old + line + "\n")
        print(f"CC BY: credit it in the post description — work/credits.md:\n{line}")
    print(f"{os.path.relpath(dst, P)} ({r.get('title')} — {r.get('creator')}, {r['license']}) — next: track_beats.py <project> {os.path.relpath(dst, P)}, "
          f"then ffmpeg -i {os.path.relpath(dst, P)} -ar 48000 -c:a pcm_s16le reel/public/audio/lofi_bed.wav (craft/audio.md step 4)")


def pick(a, P):
    out = search_dir(a, P); cands = json.load(open(os.path.join(out, "candidates.json")))
    if not 1 <= a.pick <= len(cands): sys.exit(f"--pick 1…{len(cands)}")
    r = cands[a.pick - 1]
    if a.music: return pick_music(a, P, r)
    name = "real_" + slug(a.name or a.query)
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
        line = f"- Sound \"{r.get('title')}\" by {r.get('creator')}, CC BY {v} ({r.get('foreign_landing_url')}), trimmed and loudness-matched"   # CC BY: say it was changed
        cp = os.path.join(P, "work/credits.md"); old = open(cp).read() if os.path.exists(cp) else "# Credits for the post description\n\n"
        if line not in old: open(cp, "w").write(old + line + "\n")
        print(f"CC BY: credit it in the post description — work/credits.md:\n{line}")
    print(f"{os.path.relpath(dst, P)} ({r.get('title')}, {r['license']}{', ' + str(t0) + '–' + str(t1) + ' s' if t0 is not None else ''}) — R.sfx(at, \"{name}\")")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("query")
    ap.add_argument("--music", action="store_true", help="find a music TRACK (Openverse length filter, 60–600 s, CC0 + CC BY, varied across queries and projects)")
    ap.add_argument("--mood", help="music mode: English description of the feel earshot ranks by (default: the first query)")
    ap.add_argument("--pages", type=int, help="result pages per query (default 1, music 3)")
    ap.add_argument("--allow-used", action="store_true", help="music mode: keep tracks already picked in earlier projects")
    ap.add_argument("--license", choices=sorted(OK)); ap.add_argument("--n", type=int)
    ap.add_argument("--min-s", type=float); ap.add_argument("--max-s", type=float)
    ap.add_argument("--pick", type=int); ap.add_argument("--name"); ap.add_argument("--trim", help="A-B seconds of the candidate")
    add_guard_args(ap, 4.0)   # earshot rank / find (CLAP) over a handful of short candidates
    a = ap.parse_args()
    for k, sfx, mus in (("license", "cc0", "by"), ("n", 8, 10), ("min_s", 0.1, 60.0), ("max_s", 12.0, 600.0), ("pages", 1, 3)):
        if getattr(a, k) is None: setattr(a, k, mus if a.music else sfx)
    guard_reexec(a); P = os.path.abspath(a.project)
    pick(a, P) if a.pick else search(a, P)
    print("SFX_FIND_DONE")


if __name__ == "__main__":
    main()
