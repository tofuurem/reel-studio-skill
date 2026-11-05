#!/bin/zsh
# Voiceover takes (audio only) become timeline sources: a dark 1080x1920 carrier video with the take's audio.
# Usage: vo_carriers.sh <project-dir> [--silence SEC] [audio files…]
#        → work/vo/<ascii name>.mp4 for each take + work/vo/silence.mp4 (30 s, or at least SEC with --silence; an existing
#          shorter one is rebuilt)
# Carrier names are ASCII (clipid.py --stem: «Голос 01.m4a» → Golos_01.mp4) so clip ids, proxies and plan keys stay simple;
# a take named DJI_… gets a "vo_" prefix (DJI_ names get the camera LUT).
# Then treat them like camera takes: voice_isolate.sh on work/vo/*.mp4 (not on silence.mp4), transcribe.py --sources,
# plan.json "files": {"vo01": "work/vo/vo_01_x.mp4", "sil": "work/vo/silence.mp4"}; wordless stretches (cold open, a breath
# after a punchline, the end) are ranges of the silent carrier with {"mute": true}. Every carrier frame must be covered
# by a Board / BRoll in Reel.tsx — the carrier itself is just a dark frame.
set -e -o pipefail; setopt null_glob
P=$(cd "${1:?project}" && pwd); shift; SK=$(cd "$(dirname "$0")" && pwd); mkdir -p "$P/work/vo"; SIL=30
if [ "$1" = "--silence" ]; then SIL=$2; shift 2; fi
for a in "$@"; do
  n=$(python3 -I "$SK/clipid.py" --stem "$a"); case "$n" in DJI_*) n="vo_$n";; esac
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$a")
  ffmpeg -v error -nostdin -y -f lavfi -i "color=c=0x0E0C0B:s=1080x1920:r=30:d=$d" -i "$a" -map 0:v -map 1:a -c:v libx264 -preset veryfast -crf 28 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -ac 1 -shortest "$P/work/vo/$n.mp4"
  echo "carrier $n.mp4 ${d}s  ← $(basename "$a")"
done
S="$P/work/vo/silence.mp4"
have=0; [ -f "$S" ] && have=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$S" | cut -d. -f1)
if [ "${have:-0}" -lt "${SIL%.*}" ] || [ ! -f "$S" ]; then
  ffmpeg -v error -nostdin -y -f lavfi -i "color=c=0x0E0C0B:s=1080x1920:r=30:d=$SIL" -f lavfi -i "anullsrc=r=48000:cl=mono" -t "$SIL" -c:v libx264 -preset veryfast -crf 28 -pix_fmt yuv420p -c:a aac -b:a 96k "$S"
  echo "silence.mp4 ${SIL}s"
fi
echo "VO_CARRIERS_DONE $P/work/vo"
