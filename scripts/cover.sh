#!/bin/zsh
# Render cover stills (1080x1920 comps built with src/Cover.tsx) as 1440x2560 JPGs + a check sheet with Instagram crop guides.
# Usage: cover.sh <project-dir> <covers-public-dir> <out-prefix> <CompId> [CompId…]
#   e.g. cover.sh $PWD $PWD/covers/public $PWD/out/cover_ Cover          → out/cover_Cover.jpg, out/cover_check.jpg
# <covers-public-dir> holds only the cover images (public/covers/*.png): --public-dir keeps the bundler from copying all footage;
# the fonts are copied into <covers-public-dir>/fonts on every run.
# The comps must take a `guides` prop (CoverFrame guides={guides}); the check sheet shows the 3:4 (cyan) and 1:1 (yellow) crops —
# look at it before sending: the face and the word must sit inside the yellow box.
set -e -o pipefail
P=$(cd "$1" && pwd); PUB=$(cd "$2" && pwd); OUT=$3; shift 3; T=$(mktemp -d)
# the template loads its fonts from public/fonts (fonts.ts) — the covers public dir needs them too, or every still fails with a 404
mkdir -p "$PUB/fonts"; for f in "$P"/reel/public/fonts/*.ttf(N) "$HOME"/.cache/reel-studio/fonts/*.ttf(N); do [ -s "$PUB/fonts/${f:t}" ] || cp "$f" "$PUB/fonts/"; done
cd "$P/reel"; args=(); n=0
for c in "$@"; do
  npx remotion still "$c" "$T/$c.png" --public-dir="$PUB" --scale=2 >/dev/null 2>&1 || { npx remotion still "$c" "$T/$c.png" --public-dir="$PUB" --scale=2 | tail -5; exit 1; }
  ffmpeg -v error -y -i "$T/$c.png" -vf "scale=1440:2560:flags=lanczos" -q:v 2 -pix_fmt yuvj444p "${OUT}${c}.jpg"; echo "${OUT}${c}.jpg"
  npx remotion still "$c" "$T/${c}_g.png" --public-dir="$PUB" --props='{"guides":true}' >/dev/null 2>&1; args+=(-i "$T/${c}_g.png"); n=$((n+1))
done
if [ $n -gt 1 ]; then ffmpeg -v error -y "${args[@]}" -filter_complex "hstack=${n},scale=$((n*540)):-1" "${OUT}check.jpg"; else ffmpeg -v error -y "${args[@]}" -vf scale=540:-1 "${OUT}check.jpg"; fi
echo "${OUT}check.jpg"; rm -rf "$T"
