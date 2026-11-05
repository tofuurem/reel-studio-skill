#!/bin/zsh
# QA frames as readable pages: 16 per page (9:16 → 8 per row of 405x720; 16:9 → 4 per row of 640x360) — easier to read than one long strip.
# Usage: qa_sheet.sh <project-dir> <name> <frame> [frame…]   → <project>/work/stills/<name>_<page>.jpg  (comp id: Reel)
# make_proxies.py now encodes into work/tmp and moves finished files in, so QA can run while proxies are being made (older
# versions wrote .tmp.mp4 into public/ and the bundler died on a vanishing file).
set -e -o pipefail
P=$(cd "$1" && pwd); NAME=$2; shift 2
# «2K only» intake: there are no 1080 proxies — render the stills from footage2k (reel-studio reel, 2026-11-05: 404 on footage/)
p1080=("$P"/reel/public/footage/*.mp4(N)); if [ -z "${REMOTION_FOOTAGE_DIR:-}" ] && (( ${#p1080} == 0 )); then export REMOTION_FOOTAGE_DIR=footage2k; fi
cd "$P/reel" && node scripts/stills.mjs Reel "$@" | tail -1
cd "$P/work/stills"; page=0; args=(); n=0
# tile size follows the composition: 405x720, 8 per row for 9:16; 640x360, 4 per row for a landscape (16:9) video
dims=$(ffprobe -v error -show_entries stream=width,height -of csv=p=0 "f$(printf %04d $1).jpg"); TW=405; TH=720; COLS=8
[ "${dims%%,*}" -gt "${dims##*,}" ] && { TW=640; TH=360; COLS=4; }
flush(){ [ $n -eq 0 ] && return; lay=""; for k in $(seq 0 $((n-1))); do lay="$lay|$(( (k%COLS)*TW ))_$(( (k/COLS)*TH ))"; done; lay=${lay#|}
  if [ $n -eq 1 ]; then ffmpeg -v error -y "${args[@]}" -vf scale=${TW}:${TH} "${NAME}_$page.jpg"
  else ffmpeg -v error -y "${args[@]}" -filter_complex "$(for k in $(seq 0 $((n-1))); do printf "[%d:v]scale=${TW}:${TH}[v%d];" $k $k; done)$(for k in $(seq 0 $((n-1))); do printf "[v%d]" $k; done)xstack=inputs=${n}:layout=${lay}:fill=black[o]" -map "[o]" "${NAME}_$page.jpg"; fi
  echo "$P/work/stills/${NAME}_$page.jpg"; page=$((page+1)); args=(); n=0; }
for f in "$@"; do args+=(-i "f$(printf %04d $f).jpg"); n=$((n+1)); [ $n -eq 16 ] && flush; done; flush
