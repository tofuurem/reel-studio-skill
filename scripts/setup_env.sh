#!/bin/zsh
# One-time setup for the pipeline (idempotent), on macOS or Linux / WSL2. Ends with ENV_OK.
# Usage: setup_env.sh <project-dir>
# 1. deps.py --install: system tools (ffmpeg, node, uv, …) and the shared python envs in ~/.cache/reel-studio, per platform:
#    venv (numpy, Apple Vision on macOS, torch + BiRefNet deps), dfvenv (DeepFilterNet, torch 2.4.1), gigvenv (GigaAM v3 + Silero
#    VAD — the only speech recognizer, Russian), vlmvenv (Qwen3-VL, optional, Apple Silicon). On a bare Linux run `python3 -I deps.py --install` first (zsh may be missing).
# 2. links the envs into <project>/work, copies LUTs and fonts.
# First run downloads: the env packages (≈ 1 GB with torch), the three template fonts (≈ 2 MB, Google Fonts on GitHub);
# later, on first use: the GigaAM v3 ONNX model (≈ 1 GB) and Silero VAD (≈ 2 MB) from Hugging Face (first transcribe_gigaam.py), and the DeepFilterNet model (≈ 8 MB, first voice_isolate.sh).
set -e; setopt null_glob
P=${1:-.}; mkdir -p "$P/work"
CACHE=$HOME/.cache/reel-studio; mkdir -p "$CACHE"
python3 -I "$(dirname "$0")/deps.py" --install || { echo "SETUP STOPPED — install what deps.py lists under 'run yourself', then re-run"; exit 1; }
export PATH="$HOME/.local/bin:$PATH"   # uv from astral's installer
# envs are shared across projects (torch alone is ~200 MB); each project gets symlinks in work/
for v in venv dfvenv gigvenv vlmvenv; do [ -x "$CACHE/$v/bin/python" ] && ln -sfn "$CACHE/$v" "$P/work/$v"; done
# optional frame descriptions (vlm_describe.py): Qwen3-VL-8B 4-bit, ≈ 5.4 GB — never fetched automatically
if [ -x "$CACHE/vlmvenv/bin/python" ] && [ ! -d "$CACHE/models/qwen3-vl-8b-4bit" ]; then
  echo "  vlm: model missing (optional, ≈ 5.4 GB): $CACHE/vlmvenv/bin/python -c \"from huggingface_hub import snapshot_download as d; d('mlx-community/Qwen3-VL-8B-Instruct-4bit', local_dir='$CACHE/models/qwen3-vl-8b-4bit')\""
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
