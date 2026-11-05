#!/bin/zsh
# One-time setup for the pipeline (idempotent), on macOS or Linux / WSL2. Ends with ENV_OK.
# Usage: setup_env.sh <project-dir>
# 1. deps.py --install: system tools (ffmpeg, node, uv, …) and the shared python envs in ~/.cache/reel-studio, per platform:
#    venv (Whisper — mlx-whisper on Apple Silicon, openai-whisper elsewhere; numpy; Apple Vision on macOS), dfvenv (DeepFilterNet,
#    torch 2.4.1), pkvenv (Parakeet, Apple Silicon only). On a bare Linux run `python3 -I deps.py --install` first (zsh may be missing).
# 2. links the envs into <project>/work, converts Parakeet from the Handy app's GGUF (never a fresh ASR download), LUTs, fonts.
# First run downloads: the env packages (≈ 1 GB with torch), the three template fonts (≈ 2 MB, Google Fonts on GitHub);
# later, on first use: the Whisper model (1.6 GB, first transcribe.py) and the DeepFilterNet model (≈ 8 MB, first voice_isolate.sh).
set -e; setopt null_glob
P=${1:-.}; mkdir -p "$P/work"
CACHE=$HOME/.cache/reel-studio; mkdir -p "$CACHE"
python3 -I "$(dirname "$0")/deps.py" --install || { echo "SETUP STOPPED — install what deps.py lists under 'run yourself', then re-run"; exit 1; }
export PATH="$HOME/.local/bin:$PATH"   # uv from astral's installer
# envs are shared across projects (torch alone is ~200 MB); each project gets symlinks in work/
for v in venv dfvenv pkvenv; do [ -x "$CACHE/$v/bin/python" ] && ln -sfn "$CACHE/$v" "$P/work/$v"; done
# Parakeet (first-pass map of raw clips, Apple Silicon) — the weights come from the Handy app's GGUF, never a fresh download
PK=$CACHE/models/parakeet-v3-handy
g=("$HOME"/.cache/huggingface/hub/models--handy-computer--parakeet-tdt-0.6b-v3-gguf/snapshots/*/*.gguf(N)); GGUF=${g[1]-}   # not `ls …`: with null_glob an empty glob made ls list the cwd
if [ -x "$CACHE/pkvenv/bin/python" ] && [ ! -f "$PK/model.safetensors" ]; then
  if [ -n "$GGUF" ]; then
    mkdir -p "$PK"; [ -f "$PK/config.json" ] || curl -sSL -o "$PK/config.json" https://huggingface.co/mlx-community/parakeet-tdt-0.6b-v3/resolve/main/config.json
    "$CACHE/pkvenv/bin/python" -I "$(dirname "$0")/gguf2mlx.py" "$GGUF" "$PK"
  else
    echo "  parakeet: Handy's GGUF not found — select Parakeet V3 in Handy once, or use transcribe.py (whisper) for the first pass"
  fi
fi
# camera LUTs: whatever .cube is in assets/luts (not in git — assets/luts/README.md), ~/Downloads and CapCut's LUT folder
mkdir -p "$CACHE/luts"; for L in "$(dirname "$0")"/../assets/luts/*.cube; do cp "$L" "$CACHE/luts/"; done
for L in "$HOME/Downloads"/*.cube "$HOME/Movies/CapCut/User Data/Resources/Lut"/*/*.cube; do [ -f "$L" ] && [ ! -f "$CACHE/luts/$(basename "$L")" ] && cp "$L" "$CACHE/luts/" || true; done  # cp -n exits 1 on macOS when the file exists → with set -e the script died on every second run
ls "$CACHE/luts" | sed "s/^/  lut: /"
# template fonts (variable TTFs, all weights, Latin + Cyrillic): renders load them from reel/public/fonts — no network at render time
mkdir -p "$CACHE/fonts"; GF=https://raw.githubusercontent.com/google/fonts/main/ofl
for pair in unbounded/Unbounded montserrat/Montserrat jetbrainsmono/JetBrainsMono; do
  f=${pair#*/}.ttf
  if [ -s "$CACHE/fonts/$f" ]; then echo "  font: $f"; continue; fi
  echo "  font: downloading $f"; curl -fsSL --max-time 120 -o "$CACHE/fonts/$f.part" "$GF/$pair%5Bwght%5D.ttf" && mv "$CACHE/fonts/$f.part" "$CACHE/fonts/$f" || { rm -f "$CACHE/fonts/$f.part"; echo "  font: $f FAILED (offline?) — renders will fail until it is in $CACHE/fonts"; }
done
# a scaffold that finished before the fonts were here: put them into the project too
if [ -d "$P/reel/public" ]; then mkdir -p "$P/reel/public/fonts"; for f in "$CACHE"/fonts/*.ttf(N); do [ -s "$P/reel/public/fonts/${f:t}" ] || cp "$f" "$P/reel/public/fonts/"; done; fi
echo ENV_OK
