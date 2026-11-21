#!/usr/bin/env python3
"""Where a new video project goes. Default: the folder Claude Code is open in (the cwd); always confirmed with the user.

Usage: python3 -I projects_dir.py [--name video_<topic>] [--source <clip or folder> …]   → SUGGEST <path> + SOURCE drive|cwd|saved
       python3 -I projects_dir.py --set <dir>              → remember <dir> as the folder for all new projects
       python3 -I projects_dir.py --unset                  → forget it (back to the cwd)
Library drive first: when the cwd or a --source path lies on one of the video-library skill's drives
(https://github.com/tofuurem/video-library-skill; the drive root has `Source Video/_catalog.csv` and `Video Production/`),
the project goes to <drive>/Video Production/<YYYY-MM name> — month of
the shoot (from a Source Video/<year>/<YYYY-MM …>/ path, else this month), name from --name without the video_ prefix. The
clips stay where they are and are used by path; nothing is ever created inside Source Video/. Also prints DRIVE <root> and
READ <root>/CLAUDE.md when the drive has one (its rules come first). The drive wins over $REEL_STUDIO_PROJECTS and a
--set folder on purpose — the drive keeps its projects next to the clips they use — and the SOURCE line says so.
Otherwise: a remembered folder ($REEL_STUDIO_PROJECTS, else "projects" in ~/.cache/reel-studio/config.json) → <dir>/<name>;
otherwise the cwd itself when it is empty (the user opened Claude in a fresh folder for this video; never the home folder), next to it when the cwd is
a previous project (work/, reel/ or NOTES.md in it), else <cwd>/<name>.
Ask the user before creating it (the suggestion first, "another folder" as the alternative); --set only when they ask to
keep projects somewhere for good.
"""
import argparse, datetime, json, os, re, sys

CONFIG = os.path.expanduser("~/.cache/reel-studio/config.json")

def load():
    try: return json.load(open(CONFIG))
    except (OSError, ValueError): return {}

def save(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"; json.dump(cfg, open(tmp, "w"), indent=2, ensure_ascii=False); os.replace(tmp, CONFIG)

def saved():
    d = os.environ.get("REEL_STUDIO_PROJECTS") or load().get("projects")
    return os.path.abspath(os.path.expanduser(d)) if d else None

def library_root(path):
    """The library drive `path` lies on (a folder with Source Video/_catalog.csv and Video Production/ next to it), or None."""
    p = os.path.abspath(os.path.expanduser(path))
    while True:
        if os.path.isfile(os.path.join(p, "Source Video", "_catalog.csv")) and os.path.isdir(os.path.join(p, "Video Production")):
            return p
        up = os.path.dirname(p)
        if up == p: return None
        p = up

def shoot_month(paths):
    """YYYY-MM of the earliest Source Video/<year>/<YYYY-MM …>/ folder among `paths`, else None."""
    got = [m.group(1) for p in paths for m in [re.search(r"/Source Video/\d{4}/(\d{4}-\d{2})\b", os.path.abspath(p))] if m]
    return min(got) if got else None

def drive_name(name, paths):
    """«video_dive_reel» → «2026-11 dive reel» (the user's words for the video, the month of the shoot)."""
    words = re.sub(r"^video_", "", name).replace("_", " ").strip() or "new video"
    return f"{shoot_month(paths) or datetime.date.today().strftime('%Y-%m')} {words}"

def suggest(name, cwd=None, sources=()):
    """(path, source) for a new project called `name`; source = drive | saved | cwd."""
    cwd = os.path.abspath(cwd or os.getcwd())
    for where in [*sources, cwd]:
        root = library_root(where)
        if root: return os.path.join(root, "Video Production", drive_name(name, [*sources, cwd])), "drive"
    d = saved()
    if d: return os.path.join(d, name), "saved"
    if os.path.realpath(cwd) in (os.path.realpath(os.path.expanduser("~")), "/"):
        return os.path.join(cwd, name), "cwd"          # the home folder (only dotfiles on a fresh Linux user) is never a project
    entries = [e for e in os.listdir(cwd) if not e.startswith(".")]
    if not entries: return cwd, "cwd"
    if {"work", "reel", "NOTES.md"} & set(entries):   # the cwd is a previous video's project: the new one goes next to it
        return os.path.join(os.path.dirname(cwd), name), "cwd"
    return os.path.join(cwd, name), "cwd"

def main():
    ap = argparse.ArgumentParser(description="Suggest, remember or forget the folder for new video projects.")
    ap.add_argument("--name", default="video_new", help="the new project's folder name (video_<topic>)")
    ap.add_argument("--source", nargs="*", default=[], metavar="PATH", help="where the material is (clips or folders): a library drive wins")
    ap.add_argument("--set", metavar="DIR", help="remember DIR for all new projects (created if missing)")
    ap.add_argument("--unset", action="store_true", help="forget the remembered folder")
    a = ap.parse_args()
    if a.set:
        d = os.path.abspath(os.path.expanduser(a.set)); os.makedirs(d, exist_ok=True)
        cfg = load(); cfg["projects"] = d; save(cfg); print(f"PROJECTS_DIR_SET {d}"); return
    if a.unset:
        cfg = load(); cfg.pop("projects", None); save(cfg); print("PROJECTS_DIR_UNSET"); return
    p, src = suggest(a.name, sources=a.source)
    if src != "drive": print(f"SUGGEST {p}\nSOURCE {src}")
    if src == "drive":
        root = os.path.dirname(os.path.dirname(p)); d = saved()
        print(f"SUGGEST {p}\nSOURCE drive (the material is on a video-library drive: its projects live in its Video Production/"
              + (f"; this wins over the projects folder {d}" if d else "") + ")")
        print(f"DRIVE {root}")
        if os.path.isfile(os.path.join(root, "CLAUDE.md")): print(f"READ {os.path.join(root, 'CLAUDE.md')}")

if __name__ == "__main__":
    main()
