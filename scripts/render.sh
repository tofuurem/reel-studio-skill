#!/bin/zsh
# Render a composition and set loudness with a STATIC gain (never single-pass loudnorm: it is a dynamic
# normaliser and pumps the music bed up in speech pauses).
# Usage: [CONC=1] [FORCE=1] render.sh <project-dir> <Reel|Reel2K|Action2K|ActionTrack> <out.mp4> [target LUFS = numbers.json targetLufs]
# CONC=1 by default: with 4 tabs the GPU occasionally leaves a card half-rasterised on a single frame ("blinking");
# 1 tab is not slower here (GPU-bound).
# Gates and checks (each failure exits 1 with the reason):
#   before — doctor.py --pre-render (proxies of this resolution match the cut list, Timeline newer than the cut list, fonts, lint…);
#            FORCE=1 renders anyway;
#   render — a Remotion failure prints the tail of work/render_<out>.log;
#   mux    — volume + alimiter with level=false (the default level=true auto-levelled every reel to ≈ −14.9 instead of −16);
#            written to a temp file and moved over <out> only when the frame count equals the raw render's;
#   level  — the final integrated loudness must be within numbers.json lufsTolerance of the target (one corrective pass first);
#   glitch — glitch_scan.py: exit 2 (broken/truncated) fails the render, exit 1 (dropouts) is a WARNING to look at.
set -e
SCRIPTS=$(cd "$(dirname "$0")" && pwd)
P=$(cd "${1:?project}" && pwd); COMP=${2:?Reel|Reel2K|Action2K}; OUT=${3:?out.mp4}
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT";; esac
T=${4:-$(python3 -I "$SCRIPTS/common.py" N targetLufs)}; TOL=$(python3 -I "$SCRIPTS/common.py" N lufsTolerance)
mkdir -p "$P/work" "$(dirname "$OUT")"; LOG="$P/work/render_$(basename "$OUT").log"
python3 -I "$SCRIPTS/doctor.py" "$P" --pre-render --comp "$COMP" || { if [ "${FORCE:-0}" = 1 ]; then echo "FORCE=1: rendering despite doctor errors"; else echo "RENDER REFUSED — fix the errors above (or FORCE=1)"; exit 1; fi; }
cd "$P/reel"
if [ "$COMP" = "Reel2K" ]; then export REMOTION_FOOTAGE_DIR=footage2k; fi
RAW="$OUT.raw.mp4"; rm -f "$RAW"
# caffeinate (macOS) / systemd-inhibit (Linux): a sleeping display stalls headless Chrome (see references/pitfalls/render-and-qa.md)
mkdir -p "$P/work/tmp"; export TMPDIR="$P/work/tmp"   # the bundle lives in the project: nothing else can sweep it away mid-render
KEEP=(); if command -v caffeinate >/dev/null; then KEEP=(caffeinate -dis); elif command -v systemd-inhibit >/dev/null; then KEEP=(systemd-inhibit --what=sleep:idle --why=render); fi
$KEEP npx remotion render "$COMP" "$RAW" --codec=h264 --crf=17 --concurrency=${CONC:-1} > "$LOG" 2>&1 || { echo "RENDER FAILED (remotion exit) — last lines of $LOG:"; tail -30 "$LOG"; exit 1; }
[ -s "$RAW" ] || { echo "RENDER FAILED — no output; see $LOG"; tail -30 "$LOG"; exit 1; }
FR=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$RAW" | tr -dc 0-9)
lufs(){ ffmpeg -hide_banner -nostdin -i "$1" -af ebur128 -f null - 2>&1 | grep -A1 "Integrated" | tail -1 | awk '{print $2}'; }
I=$(lufs "$RAW")
case "$I" in -[0-9]*) ;; *) echo "loudness measurement failed (I='$I'): is there an audio track?"; exit 1;; esac
mux(){  # $1 = gain dB → "$OUT.tmp.mp4"
  ffmpeg -hide_banner -loglevel error -nostdin -y -i "$RAW" -c:v copy -af "volume=${1}dB,alimiter=limit=0.84:level=false:attack=5:release=50" -c:a aac -b:a 192k "$OUT.tmp.mp4" || { echo "FINAL MUX FAILED"; rm -f "$OUT.tmp.mp4"; exit 1; }
}
G=$(python3 -c "print(round($T-($I),2))"); mux $G; F=$(lufs "$OUT.tmp.mp4")
if python3 -c "import sys; sys.exit(0 if abs(($F)-($T)) > 0.2 else 1)"; then   # the limiter ate some level: one corrective pass
  G=$(python3 -c "print(round($G+($T)-($F),2))"); mux $G; F=$(lufs "$OUT.tmp.mp4"); fi
FR2=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$OUT.tmp.mp4" | tr -dc 0-9)
[ "$FR2" = "$FR" ] || { echo "FINAL MUX BROKEN: $FR2 frames instead of $FR"; rm -f "$OUT.tmp.mp4"; exit 1; }
mv -f "$OUT.tmp.mp4" "$OUT"; rm -f "$RAW"
echo "measured I=$I LUFS, gain=$G dB → final $F LUFS (target $T ±$TOL), $FR frames"
python3 -c "import sys; sys.exit(0 if abs(($F)-($T)) <= $TOL else 1)" || { echo "LOUDNESS OFF TARGET: $F LUFS (target $T ±$TOL) — $OUT kept for inspection"; exit 1; }
PY="$P/work/venv/bin/python"; [ -x "$PY" ] || PY=python3   # needs numpy
set +e; "$PY" -I "$SCRIPTS/glitch_scan.py" "$OUT" --expect "$FR"; GS=$?; set -e
[ $GS -eq 2 ] && { echo "RENDER FAILED: the final file is broken (see above)"; exit 1; }
[ $GS -eq 1 ] && echo "WARNING: single-frame dropouts found — look at the frames (references/pitfalls/render-and-qa.md: backdrop-filter? mix-blend-mode? CONC>1?) and re-render before delivering"
echo RENDER_DONE "$OUT"
