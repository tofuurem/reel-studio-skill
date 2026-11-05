#!/bin/zsh
# Contact sheet of every clip in a footage folder (one LUT-corrected frame per clip, 10 per row).
# Usage: folder_sheet.sh "<folder>" <out.jpg> [lut.cube]
# Use it to scout b-roll in neighbouring shoot folders before transcoding anything. Tiles follow the printed order
# ("1 DJI_…_0005_D.MP4 …"); DJI reuses its 4-digit counter across days, so tiles are keyed by position, not by counter.
set -e; setopt null_glob
DIR=$1; OUT=$2; LUT=$3; TMP=$(mktemp -d)
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT";; esac   # the script cd's into the footage folder
cd "$DIR"; i=0
for f in *.MP4 *.mp4 *.MOV *.mov; do
  [ -f "$f" ] || continue; case "$f" in ._*) continue;; esac
  i=$((i+1)); echo "$i $f"
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  VF="scale=135:240:force_original_aspect_ratio=decrease,pad=135:240:(ow-iw)/2:(oh-ih)/2"; [ -n "$LUT" ] && VF="lut3d=file='$LUT',$VF"
  t="$TMP/$(printf %04d $i).jpg"
  ffmpeg -v error -nostdin -y -ss $(python3 -c "print(min(5,${d:-0}/2))") -i "$f" -frames:v 1 -vf "$VF" "$t" 2>/dev/null || true
  [ -f "$t" ] || ffmpeg -v error -nostdin -y -f lavfi -i "color=c=0x555555:s=135x240:d=0.04" -frames:v 1 "$t"   # keep positions
done
python3 - "$TMP" "$OUT" <<'PY'
import subprocess, glob, os, sys
tmp, out = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(f"{tmp}/*.jpg"))
rows = [files[i:i+10] for i in range(0, len(files), 10)]; outs = []
for ri, row in enumerate(rows):
    args = []
    for f in row: args += ["-i", f]
    o = f"{tmp}/row{ri}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *args, "-filter_complex", (f"hstack={len(row)}," if len(row) > 1 else "") + "pad=1350:240:0:0:black", o], check=True); outs.append(o)
for k in range(0, len(outs), 4):
    ch = outs[k:k+4]; args = []
    for o in ch: args += ["-i", o]
    dst = out if len(outs) <= 4 else out.replace(".jpg", f"_{k//4}.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *args, "-filter_complex", f"vstack={len(ch)}" if len(ch) > 1 else "null", dst], check=True); print(dst)
PY
rm -rf "$TMP"; echo FOLDER_SHEET_DONE
