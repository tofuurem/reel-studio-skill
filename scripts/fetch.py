#!/usr/bin/env python3
"""Download a video or a track by link (yt-dlp) into the project — for analysis and the beat grid, never as footage of someone else.

Usage: python3 -I fetch.py <project> <url> [--as ref|music|own] [--name NAME] [--section START-END]
  --as ref    (default) a reel to learn the style from → assets/refs/<name>.mp4; then ref_analyze.py measures it
                        (inputs/reference-reel.md). Its picture, sound, text and people never go into the user's video.
  --as music  the audio of a track → assets/music/<name>.m4a: track_beats.py finds its beat grid for an action reel (the
                        published reel has no music; the user adds the same track in Instagram). A bed rendered INTO the
                        file only with a track the user has the rights to.
  --as own    the user's own published episode → assets/refs/own/<name>.mp4 (series continuity: look, covers, rhythm).
  --section   only that part, e.g. 0:30-1:15 (long videos).
Writes <file>.source.json next to the file (url, title, uploader, duration, date fetched) — what it is and where it came from.
A site that wants a sign-in (Instagram often does) fails with a clear message: ask the user to download the file themselves
and drop it into assets/refs/ (or assets/music/). Never pass the user's browser cookies or passwords to yt-dlp.
Needs yt-dlp (+ deno for YouTube): deps.py --install. Prints FETCH_DONE <path>.
"""
import argparse, datetime, glob, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ascii_stem, atomic_json

DEST = {"ref": "assets/refs", "music": "assets/music", "own": "assets/refs/own"}
LOGIN = re.compile(r"log ?in|sign ?in|cookies|private|rate-limit|age-restricted|confirm you.re not a bot", re.I)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("url")
    ap.add_argument("--as", dest="kind", choices=list(DEST), default="ref"); ap.add_argument("--name"); ap.add_argument("--section")
    a = ap.parse_args()
    if not shutil.which("yt-dlp"): sys.exit("yt-dlp is missing: python3 -I deps.py --install (or brew install yt-dlp)")
    if not re.match(r"^https?://", a.url): sys.exit("give a link (https://…); a local file needs no fetch — ref_analyze.py takes it directly")
    meta = subprocess.run(["yt-dlp", "--no-playlist", "--no-warnings", "-J", a.url], capture_output=True, text=True)
    if meta.returncode:
        err = meta.stderr.strip().splitlines()[-1] if meta.stderr.strip() else "unknown error"
        if LOGIN.search(meta.stderr): sys.exit(f"the site wants a sign-in or blocks downloads ({err}).\nAsk the user to download it themselves and put the file into {DEST[a.kind]}/")
        sys.exit(f"yt-dlp could not read the link: {err}")
    info = json.loads(meta.stdout)
    name = ascii_stem(a.name or f"{info.get('uploader') or info.get('extractor', 'web')}_{info.get('id', 'clip')}")[:60]
    out_dir = os.path.join(os.path.abspath(a.project), DEST[a.kind]); os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, name)
    for f in glob.glob(stem + ".*"):
        if f.endswith((".part", ".ytdl")): os.remove(f)
    cmd = ["yt-dlp", "--no-playlist", "--no-warnings", "--quiet", "--progress", "--no-mtime", "-o", stem + ".%(ext)s"]
    if a.kind == "music":
        cmd += ["-f", "bestaudio[ext=m4a]/bestaudio", "-x", "--audio-format", "m4a"]; ext = ".m4a"
    else:   # vertical reels are ≤ 1920 tall; a 4K landscape original is not needed to measure rhythm and framing
        cmd += ["-f", "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/bv*[height<=1920]+ba/b[height<=1920]/b", "--merge-output-format", "mp4"]; ext = ".mp4"
    if a.section: cmd += ["--download-sections", "*" + a.section, "--force-keyframes-at-cuts"]
    r = subprocess.run(cmd + [a.url])
    path = stem + ext
    if r.returncode or not os.path.exists(path):
        got = [f for f in glob.glob(stem + ".*") if not f.endswith(".json")]
        if r.returncode == 0 and len(got) == 1: path = got[0]
        else: sys.exit(f"download failed (yt-dlp exit {r.returncode}) — try again later or ask the user for the file")
    atomic_json({"url": a.url, "kind": a.kind, "title": info.get("title"), "uploader": info.get("uploader"), "duration": info.get("duration"),
                 "uploaded": info.get("upload_date"), "section": a.section, "fetched": datetime.date.today().isoformat()}, path + ".source.json")
    print(f"{info.get('title')!r} by {info.get('uploader')} ({info.get('duration')} s)")
    print("FETCH_DONE", path)


if __name__ == "__main__":
    main()
