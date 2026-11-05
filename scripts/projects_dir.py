#!/usr/bin/env python3
"""Where a new video project goes. Default: the folder Claude Code is open in (the cwd); always confirmed with the user.

Usage: python3 -I projects_dir.py [--name video_<topic>]   → SUGGEST <path> + SOURCE cwd|saved
       python3 -I projects_dir.py --set <dir>              → remember <dir> as the folder for all new projects
       python3 -I projects_dir.py --unset                  → forget it (back to the cwd)
Suggestion: a remembered folder ($REEL_STUDIO_PROJECTS, else "projects" in ~/.cache/reel-studio/config.json) → <dir>/<name>;
otherwise the cwd itself when it is empty (the user opened Claude in a fresh folder for this video), next to it when the cwd is
a previous project (work/, reel/ or NOTES.md in it), else <cwd>/<name>.
Ask the user before creating it (the suggestion first, "another folder" as the alternative); --set only when they ask to
keep projects somewhere for good.
"""
import argparse, json, os, sys

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

def suggest(name, cwd=None):
    """(path, source) for a new project called `name`."""
    d = saved()
    if d: return os.path.join(d, name), "saved"
    cwd = os.path.abspath(cwd or os.getcwd())
    entries = [e for e in os.listdir(cwd) if not e.startswith(".")]
    if not entries: return cwd, "cwd"
    if {"work", "reel", "NOTES.md"} & set(entries):   # the cwd is a previous video's project: the new one goes next to it
        return os.path.join(os.path.dirname(cwd), name), "cwd"
    return os.path.join(cwd, name), "cwd"

def main():
    ap = argparse.ArgumentParser(description="Suggest, remember or forget the folder for new video projects.")
    ap.add_argument("--name", default="video_new", help="the new project's folder name (video_<topic>)")
    ap.add_argument("--set", metavar="DIR", help="remember DIR for all new projects (created if missing)")
    ap.add_argument("--unset", action="store_true", help="forget the remembered folder")
    a = ap.parse_args()
    if a.set:
        d = os.path.abspath(os.path.expanduser(a.set)); os.makedirs(d, exist_ok=True)
        cfg = load(); cfg["projects"] = d; save(cfg); print(f"PROJECTS_DIR_SET {d}"); return
    if a.unset:
        cfg = load(); cfg.pop("projects", None); save(cfg); print("PROJECTS_DIR_UNSET"); return
    p, src = suggest(a.name)
    print(f"SUGGEST {p}\nSOURCE {src}")

if __name__ == "__main__":
    main()
