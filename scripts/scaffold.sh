#!/bin/zsh
# Create the Remotion project in <project>/reel and lay the skill template over it (idempotent). Ends with SCAFFOLD_OK.
# Usage: scaffold.sh <project-dir>        ≈ 3–4 min the first time (npm install); start it in the background right after
#        new_project.sh; gen_timeline.py may run before it finishes (Timeline.tsx is kept), tsc / renders wait for SCAFFOLD_OK.
# Pinned: Remotion and every @remotion/* package at REMOTION_VERSION (default 4.0.534, the version the template is tested
# with — `create-video@latest` once gave a project 4.0.537). create-video refuses a non-empty folder and make_proxies may already
# have written reel/public/footage — so the blank project is created in a temp dir and moved in around whatever is there.
# Template files never overwrite what exists: a re-run (or a scaffold that finishes after gen_timeline.py) keeps Timeline.tsx,
# Reel.tsx and scenes; only the blank project's own entry files (Root.tsx, index.ts, Composition.tsx) are replaced.
# Canvas: work/intake.json "canvas" ("9:16" default, "16:9", "4:5", "1:1") sets W / H in src/theme.ts on every run.
# Fonts: copied from ~/.cache/reel-studio/fonts (setup_env.sh) to reel/public/fonts — renders do not fetch Google Fonts.
# External volume (another device than $HOME, e.g. exFAT): node_modules in ~/.cache/reel-studio/npmroot/<name>-<hash>, linked;
#   never run npm inside reel/ there — it swaps the link for a real folder.
set -e; setopt null_glob
RV=${REMOTION_VERSION:-4.0.534}
P=${1:-.}; P=$(cd "$P" && pwd); T=$(cd "$(dirname "$0")/../assets/remotion-template" && pwd); FONTS=$HOME/.cache/reel-studio/fonts
# node_modules lives on the volume of $HOME. A project on an external volume (exFAT: 1 MB clusters, so 24k files ≈ 24 GB;
# and npm replaces a symlinked node_modules with a real folder) keeps it in ~/.cache/reel-studio/npmroot/<name>-<hash>/
# behind the link reel/node_modules; npm runs THERE on a copy of reel/package*.json that is copied back (hermes-worker, 2026-11-06).
EXT=$(python3 -I -c "import os,sys; print(1 if os.stat(sys.argv[1]).st_dev != os.stat(os.path.expanduser('~')).st_dev else 0)" "$P")
NMROOT=""
if [ "$EXT" = 1 ]; then
  if [ -L "$P/reel/node_modules" ]; then NMROOT=$(dirname "$(readlink "$P/reel/node_modules")")
  else NMROOT=$HOME/.cache/reel-studio/npmroot/$(basename "$P")-$(python3 -I -c "import hashlib,sys; print(hashlib.md5(sys.argv[1].encode()).hexdigest()[:8])" "$P"); fi
  mkdir -p "$NMROOT"; echo "external volume: node_modules → $NMROOT/node_modules"
fi
if [ ! -f "$P/reel/package.json" ]; then
  TMP=$(mktemp -d); (cd "$TMP" && npx --yes create-video@$RV --yes --blank --no-tailwind reel >/dev/null)
  mkdir -p "$P/reel"
  if [ -n "$NMROOT" ]; then   # the blank project's own install moves to the internal disk instead of being copied over
    if [ -d "$TMP/reel/node_modules" ] && [ ! -e "$NMROOT/node_modules" ]; then mv "$TMP/reel/node_modules" "$NMROOT/node_modules"; fi
    rsync -a --exclude node_modules "$TMP/reel/" "$P/reel/"
  else
    cp -R "$TMP/reel/." "$P/reel/"
  fi
  rm -rf "$TMP"; BLANK=1
fi
cd "$P/reel"
npmi() {   # npm install in the right folder: reel/ itself, or NMROOT with package*.json copied there and back
  if [ -z "$NMROOT" ]; then npm i --no-audit --no-fund "$@" >/dev/null; return; fi
  cp package.json "$NMROOT/"; [ -f package-lock.json ] && cp package-lock.json "$NMROOT/"
  (cd "$NMROOT" && npm i --no-audit --no-fund "$@" >/dev/null)
  cp "$NMROOT/package.json" package.json; [ -f "$NMROOT/package-lock.json" ] && cp "$NMROOT/package-lock.json" package-lock.json
  return 0
}
if [ -n "$NMROOT" ]; then
  if [ -d node_modules ] && [ ! -L node_modules ]; then echo "WARNING: reel/node_modules is a real folder on an external volume (an older scaffold or npm run inside reel/) — delete it and re-run scaffold.sh"; fi
  [ -L node_modules ] || [ -e node_modules ] || ln -s "$NMROOT/node_modules" node_modules
  [ -d "$NMROOT/node_modules" ] || npmi
else
  [ -d node_modules ] || npmi
fi
PKGS=(remotion @remotion/cli @remotion/media @remotion/captions @remotion/fonts @remotion/effects @remotion/bundler @remotion/renderer @remotion/eslint-config-flat)   # what the template imports + what render.sh / stills.mjs need
need=()
for p in $PKGS; do v=$(node -p "try{require('./node_modules/$p/package.json').version}catch(e){''}" 2>/dev/null); [ "$v" = "$RV" ] || need+=("$p@$RV"); done
if (( ${#need} )); then echo "installing ${need[*]}"; npmi --save-exact "${need[@]}"; fi
# a blank create-video src (no Clip.tsx yet): its entry files are replaced, everything else from the template is added
if [ ! -f src/Clip.tsx ]; then mkdir -p src; cp -f "$T/src/Root.tsx" "$T/src/index.ts" src/; rm -f src/Composition.tsx; fi
rsync -a --ignore-existing "$T/src/" src/
# AppleDouble sidecars (._X.tsx — macOS writes one next to every file on exFAT / network volumes) must not be compiled
python3 -I - tsconfig.json <<'PY'
import json, sys
p = sys.argv[1]
try: c = json.load(open(p))
except ValueError: sys.exit(0)   # a tsconfig with comments: leave it
ex = c.setdefault("exclude", [])
for e in ("**/._*", "node_modules"):
    if e not in ex: ex.append(e)
open(p, "w").write(json.dumps(c, indent=2) + "\n")
PY
# canvas from work/intake.json "canvas" (9:16 default; "16:9" for a horizontal vlog): theme.ts W / H follow it
SK=$(cd "$(dirname "$0")" && pwd)
WH=$(python3 -I -c "import json,os,sys; sys.path.insert(0,'$SK'); from common import canvas_size, load_json; c=(load_json('$P/work/intake.json',{}) or {}).get('canvas'); print(*canvas_size(c)) if c else print('')")
if [ -n "$WH" ]; then CW=${WH% *}; CH=${WH#* }
  sed -E "s/^export const W = [0-9]+;/export const W = $CW;/; s/^export const H = [0-9]+;/export const H = $CH;/" src/theme.ts > src/theme.ts.tmp && mv src/theme.ts.tmp src/theme.ts; echo "canvas ${CW}x${CH} (work/intake.json)"; fi
[ -f remotion.config.ts ] && grep -q setChromiumOpenGlRenderer remotion.config.ts || cp "$T/remotion.config.ts" .
mkdir -p scripts public/footage public/footage2k public/screens public/audio public/captions public/fonts; [ -f scripts/stills.mjs ] || cp "$T/scripts/stills.mjs" scripts/
for f in Unbounded Montserrat JetBrainsMono; do
  [ -s "public/fonts/$f.ttf" ] || cp "$FONTS/$f.ttf" public/fonts/ 2>/dev/null || echo "WARNING: $f.ttf missing in $FONTS — run setup_env.sh (renders fail without the fonts)"
done
[ -f "$P/assets/brands.json" ] || { mkdir -p "$P/assets/screens" "$P/assets/music"; cp "$T/../brands.example.json" "$P/assets/brands.json"; }
echo SCAFFOLD_OK "$P/reel  remotion $RV  (next: gen_timeline.py → Timeline.tsx; the template Reel.tsx renders captions + end card until gen_reel writes it)"
