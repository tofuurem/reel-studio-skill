#!/bin/zsh
# Create a project folder for one video or for a series of episodes made from one pool of material.
# Usage: new_project.sh <name|path> [episodes]   e.g. new_project.sh video_devlog 3
#   normally a full path the user confirmed (projects_dir.py suggests it); a bare name resolves the same way projects_dir.py
#   suggests: <drive>/Video Production/<YYYY-MM name> on a library drive, else a remembered folder, else the cwd (the cwd
#   itself when it is empty)
# Library drive (the video-library skill's drives: Source Video/_catalog.csv + Video Production/ in the drive root): never inside
#   Source Video/ — it holds raw clips only; the project uses them by path from <drive>/Video Production/.
# One video:  <path>/{assets/{screens,screenrec,voiceover,music,models,video},work/broll,out}
# Series:     the same shared assets/ and work/ (inventory, transcripts of the whole pool, PLAN.md, NOTES.md) plus
#             <path>/epN/{work,out} with links into the pool:  epN/assets → ../assets,
#             epN/work/{voice,new,vo,pk,broll} → ../../work/{voice,new,vo,pk,broll}
#             — voice isolation, transcripts and carriers are made once for the pool; without the links an episode's
#             make_proxies silently falls back to the camera sound.
#             Each episode is then a normal project (scaffold.sh <path>/epN; its cutlist.json, proxies, reel/ are its own).
# Never reuses an existing folder's files: existing dirs and links are kept, nothing is overwritten.
[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0; }
set -e
P=${1:?name or path}; N=${2:-0}
if [[ $P != */* ]]; then
  P=$(python3 -I "$(dirname "$0")/projects_dir.py" --name "$P" | sed -n 's/^SUGGEST //p')
fi
python3 -I -c "
import os, sys; sys.path.insert(0, sys.argv[2]); import projects_dir as pd
p = os.path.abspath(sys.argv[1]); r = pd.library_root(p)
if r and (p + '/').startswith(os.path.join(r, 'Source Video') + '/'):
    sys.exit(f'refused: {p} is inside Source Video/ of a library drive (raw clips only) — use {os.path.join(r, \"Video Production\")}/<YYYY-MM name>; projects_dir.py suggests one')
" "$P" "$(dirname "$0")"
mkdir -p "$P"/assets/{screens,screenrec,voiceover,music,models,video} "$P"/work/broll "$P"/out
[ -f "$P/NOTES.md" ] || printf '# %s\n\nMaterial, decisions, what was cut and how to re-run. Absolute dates only.\n' "$(basename "$P")" > "$P/NOTES.md"
if [ "$N" -gt 0 ]; then
  [ -f "$P/PLAN.md" ] || printf '# %s — series plan\n\n| episode | topic | status |\n|---|---|---|\n' "$(basename "$P")" > "$P/PLAN.md"
  mkdir -p "$P"/work/{voice/out,new,vo,pk,broll}
  for i in $(seq 1 $N); do
    mkdir -p "$P/ep$i/work" "$P/ep$i/out"; [ -e "$P/ep$i/assets" ] || ln -s ../assets "$P/ep$i/assets"
    # the pool's restored voice, transcripts, carriers, GigaAM maps and b-roll are shared; work/voice/dialogue.json stays per
    # episode (dialogue.py's gains depend on the episode's own ranges — a shared folder let episodes overwrite each other)
    mkdir -p "$P/ep$i/work/voice"; [ -e "$P/ep$i/work/voice/out" ] || ln -s "../../../work/voice/out" "$P/ep$i/work/voice/out"
    for d in new vo pk broll; do [ -e "$P/ep$i/work/$d" ] || ln -s "../../work/$d" "$P/ep$i/work/$d"; done
  done
fi
# an external volume (another device than $HOME): say so — scaffold.sh keeps node_modules on the internal disk there
EXT=$(python3 -I -c "import os,sys; print('external volume' if os.stat(sys.argv[1]).st_dev != os.stat(os.path.expanduser('~')).st_dev else '')" "$P")
echo "PROJECT_OK $P $( [ "$N" -gt 0 ] && echo "episodes=$N (epN/work/{voice/out,new,vo,pk,broll} → shared pool)" ) ${EXT}"
