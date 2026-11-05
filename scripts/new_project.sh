#!/bin/zsh
# Create a project folder for one video or for a series of episodes made from one pool of material.
# Usage: new_project.sh <name|path> [episodes]   e.g. new_project.sh video_lofiroom 3
#   normally a full path the user confirmed (projects_dir.py suggests it); a bare name resolves the same way projects_dir.py
#   suggests: a remembered folder, else the cwd (the cwd itself when it is empty)
# One video:  <path>/{assets/{screens,screenrec,voiceover,music,models,video},work/broll,out}
# Series:     the same shared assets/ and work/ (inventory, transcripts of the whole pool, PLAN.md, NOTES.md) plus
#             <path>/epN/{work,out} with links into the pool:  epN/assets → ../assets,
#             epN/work/{voice,new,vo,pk,broll} → ../../work/{voice,new,vo,pk,broll}
#             — voice isolation, transcripts and carriers are made once for the pool; without the links an episode's
#             match_loudness / make_proxies silently fell back to the camera sound (audit 2026-10-22).
#             Each episode is then a normal project (scaffold.sh <path>/epN; its cutlist.json, proxies, reel/ are its own).
# Never reuses an existing folder's files: existing dirs and links are kept, nothing is overwritten.
set -e
P=${1:?name or path}; N=${2:-0}
if [[ $P != */* ]]; then
  P=$(python3 -I "$(dirname "$0")/projects_dir.py" --name "$P" | sed -n 's/^SUGGEST //p')
fi
mkdir -p "$P"/assets/{screens,screenrec,voiceover,music,models,video} "$P"/work/broll "$P"/out
[ -f "$P/NOTES.md" ] || printf '# %s\n\nMaterial, decisions, what was cut and how to re-run. Absolute dates only.\n' "$(basename "$P")" > "$P/NOTES.md"
if [ "$N" -gt 0 ]; then
  [ -f "$P/PLAN.md" ] || printf '# %s — series plan\n\n| episode | topic | status |\n|---|---|---|\n' "$(basename "$P")" > "$P/PLAN.md"
  mkdir -p "$P"/work/{voice/out,new,vo,pk,broll}
  for i in $(seq 1 $N); do
    mkdir -p "$P/ep$i/work" "$P/ep$i/out"; [ -e "$P/ep$i/assets" ] || ln -s ../assets "$P/ep$i/assets"
    # the pool's isolated voice, transcripts, carriers, Parakeet maps and b-roll are shared; work/voice/matched stays per episode
    # (match_loudness gains depend on the episode's own ranges — a shared folder let episodes overwrite each other)
    mkdir -p "$P/ep$i/work/voice"; [ -e "$P/ep$i/work/voice/out" ] || ln -s "../../../work/voice/out" "$P/ep$i/work/voice/out"
    for d in new vo pk broll; do [ -e "$P/ep$i/work/$d" ] || ln -s "../../work/$d" "$P/ep$i/work/$d"; done
  done
fi
echo "PROJECT_OK $P $( [ "$N" -gt 0 ] && echo "episodes=$N (epN/work/{voice/out,new,vo,pk,broll} → shared pool)" )"
