#!/bin/zsh
# Voice restoration of speech sources — a wrapper of voice_clean.py (kept because every guide and series calls this name).
# Usage: voice_isolate.sh <project-dir> [--atten-lim-db N] [--lav <dir|wav>]… <source-file> [more files…]   (camera originals, not proxies)
# → work/voice/out/<clipId>_DeepFilterNet3.wav (+ .voice.json) and VOICE_DONE. Per source it measures the SNR and clipping and
# does only what is needed: adeclip around clipped samples, DeepFilterNet limited so the room stays ≈ 48 dB under the voice
# (never digital silence), or nothing in a quiet room. --atten-lim-db N forces the limit (0 = no DeepFilterNet). --lav takes
# the DJI transmitter's own 32-bit float recordings (found and synced by cross-correlation). Do NOT substitute ffmpeg
# afftdn/agate/anlmdn (rejected by ear). Two lav mics on the camera's L/R channels: dualmic.py instead.
set -e -o pipefail
P=${1:?project}; shift; SK=$(cd "$(dirname "$0")" && pwd); ARGS=()
while [ "${1#--}" != "$1" ]; do
  case "$1" in
    --atten-lim-db) ARGS+=(--atten "$2"); shift 2;;
    --no-declip) echo "--no-declip is obsolete: declip runs only where the source clipped"; shift;;
    --lav) ARGS+=(--lav "$2"); shift 2;;   # a TX folder or one WAV; repeat the flag for more
    *) echo "unknown option $1"; exit 1;;
  esac
done
[ $# -gt 0 ] || { echo "no source files given"; exit 1; }
PY="$P/work/dfvenv/bin/python"; [ -x "$PY" ] || { echo "DeepFilterNet environment missing: run setup_env.sh $P first"; exit 1; }
exec "$PY" -I "$SK/voice_clean.py" "$P" "${ARGS[@]}" "$@"
