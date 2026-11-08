#!/usr/bin/env python3
"""Static checks of a Remotion src tree against the skill's render and style rules.

Usage: python3 -I lint_reel.py <project | reel dir | src dir> [--quiet]     (doctor.py and selfcheck.py run it)
ERROR (exit 1):
  backdrop-filter / backdropFilter       single-frame dropouts in the render ("blinking cards")
  mix-blend-mode / mixBlendMode          the same: blend modes promote the element to its own compositor layer
WARN:
  emoji in strings / JSX text            no emoji in UI text (✓ ✕ → ← ↑ ↓ ≈ × · • … are marks, allowed)
  hex colour literal outside theme.ts / palettes.ts / numbers.ts   colours come from the palette
  fontSize below numbers.json minTextPx  unreadable on a phone
  coloured glow (0 0 Npx <colour>)       one shadow per kind, no glows (shadows in theme.ts)
A line ending with `// lint-ok` (or a JSX comment {/* lint-ok */}) is skipped — write why next to it.
Prints file:line: LEVEL rule — snippet, then LINT_OK or LINT errors=N warnings=M.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import N

args = [x for x in sys.argv[1:] if not x.startswith("--")]; quiet = "--quiet" in sys.argv
if not args: sys.exit(__doc__)
root = os.path.abspath(args[0])
for sub in ("reel/src", "src"):
    if os.path.isdir(os.path.join(root, sub)): root = os.path.join(root, sub); break
PALETTE_FILES = {"theme.ts", "palettes.ts", "numbers.ts"}
ALLOWED = set("✓✔✕✖→←↑↓≈×·•…—–№°±")
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")
HEX = re.compile(r"""(["'`])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|[ (,]#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b(?=[^"'`]*["'`])""")
FONT = re.compile(r"fontSize\s*[:=]\s*\{?\s*(\d+(?:\.\d+)?)\b")
GLOW = re.compile(r"(?:boxShadow|textShadow|drop-shadow)[^\n]*?\b0(?:px)?\s+0(?:px)?\s+(\d+)px\s+(?:\d+px\s+)?(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})")

def dark(col):
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", col)
    if m: return max(int(m[1]), int(m[2]), int(m[3])) < 60
    h = col.lstrip("#"); h = "".join(c * 2 for c in h[:3]) if len(h) in (3, 4) else h[:6]
    try: return max(int(h[i:i + 2], 16) for i in (0, 2, 4)) < 60
    except ValueError: return True

def code_part(line, in_block):
    """Strip // and /* */ comments (strings with // inside URLs are rare in this code)."""
    out, i = "", 0
    while i < len(line):
        if in_block:
            j = line.find("*/", i)
            if j < 0: return out, True
            i = j + 2; in_block = False; continue
        if line.startswith("/*", i): in_block = True; i += 2; continue
        if line.startswith("//", i) and not line[max(0, i - 1):i] == ":": break
        out += line[i]; i += 1
    return out, in_block

errors, warns = [], []
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d not in ("node_modules", ".git")]
    for f in sorted(fn):
        if f.startswith(".") or not f.endswith((".ts", ".tsx")): continue   # ._X.tsx: AppleDouble sidecars on external volumes
        p = os.path.join(dp, f); rel = os.path.relpath(p, root); blk = False
        for n, raw in enumerate(open(p, encoding="utf-8"), 1):
            if "lint-ok" in raw: continue
            line, blk = code_part(raw.rstrip("\n"), blk)
            if not line.strip(): continue
            def hit(lst, rule): lst.append(f"{rel}:{n}: {'ERROR' if lst is errors else 'WARN'} {rule} — {line.strip()[:110]}")
            if re.search(r"backdrop-?filter", line, re.I): hit(errors, "backdrop-filter")
            if re.search(r"mix-?blend-?mode", line, re.I): hit(errors, "mix-blend-mode")
            if any(ch not in ALLOWED for ch in EMOJI.findall(line)): hit(warns, "emoji in UI text")
            if f not in PALETTE_FILES and HEX.search(line): hit(warns, "hex colour outside the palette")
            for m in FONT.finditer(line):
                if float(m.group(1)) < N["minTextPx"]: hit(warns, f"fontSize {m.group(1)} < {N['minTextPx']}")
            for m in GLOW.finditer(line):
                if not dark(m.group(2)): hit(warns, "coloured glow")
if not quiet or errors:
    for x in errors + warns: print(x)
print("LINT_OK" if not errors and not warns else f"LINT errors={len(errors)} warnings={len(warns)}", f"({root})")
sys.exit(1 if errors else 0)
