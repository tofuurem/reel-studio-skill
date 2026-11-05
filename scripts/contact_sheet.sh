#!/bin/zsh
# Render frames of a composition into one contact sheet (half-size stills, 200 px grid lines).
# Usage: contact_sheet.sh <project-dir> <CompId> <out.jpg> <frame> [frame…]      (qa_sheet.sh pages many frames)
set -e -o pipefail   # 10–60 s per sheet (bundle copies public/ + Chrome start); batch all frames into one call
P=$(cd "${1:?project}" && pwd); COMP=$2; OUT=$3; shift 3
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT";; esac
cd "$P/reel" && node scripts/stills.mjs "$COMP" "$@" | tail -1
F=""; for y in 200 400 600 800 1000 1200 1400 1600; do F="$F,drawbox=y=$((y/2)):w=iw:h=1:color=yellow@0.7:t=fill"; done; F=${F#,}
args=(); n=0
for f in "$@"; do p="$P/work/stills/f$(printf %04d $f).jpg"; ffmpeg -v error -nostdin -y -i "$p" -vf "$F" "$p.g.jpg"; args+=(-i "$p.g.jpg"); n=$((n+1)); done
if [ $n -eq 1 ]; then cp "$P/work/stills/f$(printf %04d $1).jpg.g.jpg" "$OUT"; else ffmpeg -v error -nostdin -y "${args[@]}" -filter_complex "hstack=$n" "$OUT"; fi
echo "$OUT"
