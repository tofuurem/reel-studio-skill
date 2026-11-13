#!/bin/zsh
# Render only a stretch of a composition — a few seconds of each variant for an A/B (ab_video.py), never the whole reel per idea.
# Usage: [MAX_GB=12] render_part.sh <project-dir> <Reel|Reel2K|Action2K|ActionTrack> <from s> <dur s> <out.mp4>
# Seconds are timeline seconds (frames = seconds × FPS of reel/src/theme.ts). No gates, no mastering: the sound is Remotion's
# raw mix (ab_video.py matches the loudness of the versions); the file is a draft — out/ab/ (re-creatable) is the place.
# Same safety as render.sh: one Chrome tab, the memory guard, caffeinate, the bundle in work/tmp.
set -e
SCRIPTS=$(cd "$(dirname "$0")" && pwd)
P=$(cd "${1:?project}" && pwd); COMP=${2:?composition}; FROM=${3:?from seconds}; DUR=${4:?duration seconds}; OUT=${5:?out.mp4}
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT";; esac
FPS=$(sed -nE 's/^export const FPS = ([0-9.]+).*/\1/p' "$P/reel/src/theme.ts" 2>/dev/null | head -1); FPS=${FPS:-30}
A=$(python3 -c "print(round($FROM*$FPS))"); B=$(python3 -c "print(round(($FROM+$DUR)*$FPS)-1)")
mkdir -p "$P/work/tmp" "$(dirname "$OUT")"; export TMPDIR="$P/work/tmp"; LOG="$P/work/render_part_$(basename "$OUT").log"
cd "$P/reel"
if [ "$COMP" = "Reel2K" ]; then export REMOTION_FOOTAGE_DIR=footage2k; fi
KEEP=(); if command -v caffeinate >/dev/null; then KEEP=(caffeinate -dis); elif command -v systemd-inhibit >/dev/null; then KEEP=(systemd-inhibit --what=sleep:idle --why=render); fi
GUARD=(); [ "$(uname)" = Darwin ] && GUARD=(python3 -I "$SCRIPTS/mem_guard.py" --max-gb "${MAX_GB:-12}" --min-free-gb "${MIN_FREE_GB:-4}" --)
"${GUARD[@]}" $KEEP npx remotion render "$COMP" "$OUT" --frames=$A-$B --codec=h264 --crf=17 --audio-codec=aac --audio-bitrate=320k --concurrency=1 > "$LOG" 2>&1 || {
  echo "RENDER_PART FAILED — last lines of $LOG:"; tail -20 "$LOG"; exit 1; }
[ -s "$OUT" ] || { echo "RENDER_PART FAILED — no output; see $LOG"; exit 1; }
echo "RENDER_PART_DONE $OUT (frames $A–$B at $FPS fps)"
