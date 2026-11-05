#!/bin/zsh
# Voice isolation (CapCut "voice isolation" equivalent) with DeepFilterNet3.
# Usage: voice_isolate.sh <project-dir> [--atten-lim-db N] [--no-declip] <source-file> [more files…]   (camera originals, not proxies)
# Writes work/voice/out/<clipId>_DeepFilterNet3.wav; make_proxies.py --voice-dir picks them up. Re-runs skip finished files
# and still print VOICE_DONE. --atten-lim-db N limits the noise reduction to N dB (mixes some room back: try 25 when the voice
# sounds "underwater"); it is passed to deepFilter under whatever name its --help shows.
# Do NOT substitute ffmpeg afftdn/agate: on this footage it left the voice sounding dirty.
# Every source is declipped first (adeclip, input halved so the rebuilt peaks fit): a lav held at the mouth clips in the
# transmitter and the flat tops crackle after the gain («колонки хрипят», Halloween vlog). --no-declip skips it.
# Two lav mics on the camera's L/R channels: use dualmic.py instead (each mic cleaned on its own, then automixed).
set -e -o pipefail; setopt null_glob
P=${1:?project}; shift; SK=$(cd "$(dirname "$0")" && pwd); ATT=""
DECLIP=",adeclip,volume=0.5"
while [ "${1#--}" != "$1" ]; do
  case "$1" in --atten-lim-db) ATT=$2; shift 2;; --no-declip) DECLIP=""; shift;; *) echo "unknown option $1"; exit 1;; esac
done
[ $# -gt 0 ] || { echo "no source files given"; exit 1; }
python3 -I "$SK/clipid.py" "$@" >/dev/null   # aborts on DJI counter collisions
mkdir -p "$P/work/voice/in" "$P/work/voice/out"
DF="$P/work/dfvenv/bin/deepFilter"
for src in "$@"; do
  id=$(python3 -I "$SK/clipid.py" "$src")
  [ -f "$P/work/voice/out/${id}_DeepFilterNet3.wav" ] && { echo "skip $id (done)"; continue; }
  [ -x "$DF" ] || { echo "DeepFilterNet missing: run setup_env.sh $P first"; exit 1; }
  ffmpeg -hide_banner -loglevel error -nostdin -y -i "$src" -map 0:a:0 -vn -af "aformat=channel_layouts=mono$DECLIP" -ar 48000 -c:a pcm_s16le "$P/work/voice/in/$id.wav"
done
todo=("$P"/work/voice/in/*.wav)
if (( ${#todo} )); then
  extra=()
  if [ -n "$ATT" ]; then flag=$("$DF" --help 2>&1 | grep -o -- '--atten-lim[-a-z]*' | head -1); [ -n "$flag" ] && extra=("$flag" "$ATT") || echo "deepFilter has no attenuation-limit flag; running without it"; fi
  "$DF" "${extra[@]}" "${todo[@]}" -o "$P/work/voice/out" 2>&1 | grep -v -i warn | tail -3
fi
for src in "$@"; do id=$(python3 -I "$SK/clipid.py" "$src"); [ -s "$P/work/voice/out/${id}_DeepFilterNet3.wav" ] || { echo "FAILED: no output for $id"; exit 1; }; done
rm -f "${todo[@]}"   # 48 kHz mono copies of 7-min takes are big; the outputs are what matters
echo VOICE_DONE "$(ls "$P/work/voice/out" | tr "\n" " ")"  # ≈ 4 s per minute of audio
