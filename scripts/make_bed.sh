#!/bin/zsh
# Procedural lo-fi music bed → reel/public/audio/lofi_bed.wav (what the template's MusicBed references; PCM — the render
# encodes the sound once, at the end).
# Usage: make_bed.sh <project-dir> [seconds] [warm|night|bright|dusk|spooky]      (or make_bed.sh <project-dir> <preset>)
#        seconds default = work/cutlist.json totalFrames/30 + numbers.json bedTailSec (15 s: the end card and the fade)
# Offer the user's own track first (assets/music): the procedural bed is recognisably the same in every video («такой же как
# всегда», BRX promo 2026-10-10). Use a different preset per video. The bed is −29.7 LUFS at unity → volume 0.18 (numbers.json
# bedUnder) ≈ 20 LU under speech, 0.3 (bedOpen) in the cold open and the tail. Also writes work/beats.json (the beat grid).
set -e -o pipefail
P=$(cd "${1:?project}" && pwd); SEC=$2; PRESET=${3:-warm}; SK=$(cd "$(dirname "$0")" && pwd)
case "$SEC" in warm|night|bright|dusk|spooky) PRESET=$SEC; SEC="";; esac
if [ -z "$SEC" ]; then
  SEC=$(python3 -I -c "import json,sys; sys.path.insert(0,'$SK'); from common import N; c=json.load(open('$P/work/cutlist.json')); print(round(c['totalFrames']/c.get('fps',30) + N['bedTailSec'], 1))")
fi
PY="$P/work/venv/bin/python"; [ -x "$PY" ] || PY=python3   # needs numpy
mkdir -p "$P/reel/public/audio"
"$PY" -I "$SK/lofi.py" "$P/work/lofi_$PRESET.wav" "$SEC" "$PRESET"
ffmpeg -hide_banner -loglevel error -nostdin -y -i "$P/work/lofi_$PRESET.wav" -af "aecho=0.6:0.3:60:0.25" -ar 48000 -c:a pcm_s16le "$P/reel/public/audio/lofi_bed.wav"
# the bed's beat grid for gen_reel (cuts on a bar, pictures on beats): work/beats.json {"bpm", "preset", "frames", "bars"} — the bed starts at frame 0
python3 -I - "$SK/lofi.py" "$PRESET" "$SEC" "$P/work/beats.json" <<'PY'
import json, re, sys
src, preset, sec, out = open(sys.argv[1]).read(), sys.argv[2], float(sys.argv[3]), sys.argv[4]
m = re.search(rf"'{preset}':\s*dict\(bpm=(\d+)", src); bpm = int(m.group(1)) if m else 76; beat = 60 / bpm
frames = [int(round(k * beat * 30)) for k in range(int(sec / beat) + 1) if k * beat < sec]
json.dump({"bpm": bpm, "preset": preset, "frames": frames, "bars": frames[::4]}, open(out, "w"))
PY
echo BED_OK "$P/reel/public/audio/lofi_bed.wav ($SEC s, $PRESET) + work/beats.json"
