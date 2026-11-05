#!/usr/bin/env bash
# Generate (or edit) a raster image via Codex CLI's built-in image_gen tool
# and copy the result(s) into a target directory.
#
# Usage:
#   codex_image.sh -o <out_dir> -n <basename> [-r ref.png]... [-c count] [-t] "<prompt>"
#
#   -o  output directory (created if missing)
#   -n  base filename without extension (default: image); never overwrites,
#       appends -v2, -v3... if the name is taken
#   -r  reference / source image to attach (repeatable)
#   -c  number of variants to generate (default 1)
#   -t  request a transparent background (PNG with alpha)
#   -m  override Codex model
#
# Prints the absolute path of every saved image, one per line, on stdout.
set -euo pipefail

out_dir=""; name="image"; count=1; transparent=0; model=""
refs=()
while getopts "o:n:r:c:tm:" opt; do
  case "$opt" in
    o) out_dir="$OPTARG" ;;
    n) name="$OPTARG" ;;
    r) [[ -f "$OPTARG" ]] || { echo "reference not found: $OPTARG" >&2; exit 2; }
       refs+=("$(cd "$(dirname "$OPTARG")" && pwd)/$(basename "$OPTARG")") ;;
    c) count="$OPTARG" ;;
    t) transparent=1 ;;
    m) model="$OPTARG" ;;
    *) echo "bad option" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
prompt="${*:-}"
[[ -z "$out_dir" || -z "$prompt" ]] && { sed -n 2,16p "$0" >&2; exit 2; }
command -v codex >/dev/null || { echo "codex CLI not found" >&2; exit 1; }

codex_home="${CODEX_HOME:-$HOME/.codex}"
gen_root="$codex_home/generated_images"
mkdir -p "$out_dir" "$gen_root"
out_dir="$(cd "$out_dir" && pwd)"

log="$(mktemp "${TMPDIR:-/tmp}/codex-imagegen-log.XXXXXX")"

instr="Use your built-in image_gen tool (not the CLI fallback, not code) to generate exactly $count image(s)."
if ((${#refs[@]})); then
  instr+=" The attached image(s) are references/source: follow them for style, subject and composition (or edit them if the prompt asks for an edit)."
fi
((transparent)) && instr+=" The image must have a genuinely transparent background (alpha channel), no backdrop, no shadow plate."
instr+=" Do not write any files or run shell commands. Do not ask questions. After generating, reply with one short line: done.

Image prompt:
$prompt"

args=(exec --json --skip-git-repo-check --sandbox read-only --color never -C "$out_dir")
[[ -n "$model" ]] && args+=(-m "$model")
# -i takes multiple values, so the prompt goes through stdin, not as a positional arg.
for r in ${refs[@]+"${refs[@]}"}; do args+=(-i "$r"); done

if ! printf '%s' "$instr" | codex "${args[@]}" >"$log" 2>&1; then
  echo "codex exec failed, log: $log" >&2
  tail -20 "$log" >&2
  exit 1
fi

# Images land in generated_images/<thread_id>/, so parallel runs don't mix results.
thread_id="$(grep -m1 -o '"thread_id":"[^"]*"' "$log" | cut -d'"' -f4 || true)"
found=()
if [[ -n "$thread_id" && -d "$gen_root/$thread_id" ]]; then
  while IFS= read -r f; do found+=("$f"); done < <(
    find "$gen_root/$thread_id" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) -print0 \
      | xargs -0 ls -tr 2>/dev/null)
fi

if ((${#found[@]} == 0)); then
  echo "no image produced, codex log: $log" >&2
  tail -20 "$log" >&2
  exit 1
fi

for src in "${found[@]}"; do
  ext="${src##*.}"
  dest="$out_dir/$name.$ext"; v=2
  while [[ -e "$dest" ]]; do dest="$out_dir/$name-v$v.$ext"; v=$((v + 1)); done
  cp "$src" "$dest"
  echo "$dest"
done
rm -f "$log"
