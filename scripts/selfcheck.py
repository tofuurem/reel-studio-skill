#!/usr/bin/env python3
"""Skill-level checks — run after editing the skill (no project needed, nothing is downloaded or installed).

Usage: python3 -I selfcheck.py [--verbose]
  numbers     references/craft/numbers.json → numbers.md / template numbers.ts are up to date (numbers_gen.py --check)
  python      every script compiles; every argparse script answers --help (SKIP when it needs a venv module: mlx_whisper, Vision …)
  shell       zsh -n on every .sh
  swear       swear.py self-test
  flags       every `--flag` written after `<script>.py|.sh` in SKILL.md and references/**/*.md exists in that script
  contracts   the template's Timeline.tsx stub exports the names gen_timeline.py writes (Timeline, TOTAL_FRAMES)
  lint        lint_reel.py on assets/remotion-template/src (errors fail, warnings are listed)
Prints SELFCHECK_OK or the problems (exit 1).
"""
import glob, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.dirname(HERE)
verbose = "--verbose" in sys.argv
probs, notes = [], []
VENV_MODULES = ("soundfile", "mlx_whisper", "Vision", "Quartz", "Foundation", "parakeet_mlx", "gguf", "mlx", "torch", "df", "objc", "whisper")

def run(cmd, **kw): return subprocess.run(cmd, capture_output=True, text=True, **kw)

r = run([sys.executable, "-I", os.path.join(HERE, "numbers_gen.py"), "--check"])
if r.returncode: probs.append("numbers: " + (r.stdout + r.stderr).strip())
helps = {}
for p in sorted(glob.glob(os.path.join(HERE, "*.py"))):
    name = os.path.basename(p)
    r = run([sys.executable, "-m", "py_compile", p])
    if r.returncode: probs.append(f"python: {name} does not compile: {r.stderr.strip()[-200:]}"); continue
    if name == "selfcheck.py" or not re.search(r"^import .*\bargparse\b|^\s*import argparse", open(p).read(), re.M): continue
    try: r = run([sys.executable, "-I", p, "--help"], cwd="/tmp", timeout=30)
    except subprocess.TimeoutExpired: probs.append(f"python: {name} --help hangs (work before argparse?)"); continue
    if r.returncode == 0: helps[name] = r.stdout
    elif any(f"No module named '{m}" in r.stderr for m in VENV_MODULES): notes.append(f"python: {name} --help SKIP (needs a venv module)"); helps[name] = open(p).read()
    else: probs.append(f"python: {name} --help failed: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else r.returncode}")
for p in sorted(glob.glob(os.path.join(HERE, "*.sh"))):
    r = run(["zsh", "-n", p])
    if r.returncode: probs.append(f"shell: {os.path.basename(p)}: {r.stderr.strip()}")
r = run([sys.executable, "-I", os.path.join(HERE, "swear.py")])
if "SWEAR_SELFTEST OK" not in r.stdout: probs.append("swear: " + r.stdout.strip())

docs = [os.path.join(SKILL, "SKILL.md")] + glob.glob(os.path.join(SKILL, "references/**/*.md"), recursive=True)
scripts = {os.path.basename(p): p for p in glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(HERE, "*.sh"))}
SCRIPT = re.compile(r"\b([a-z_0-9]+\.(?:py|sh))\b"); checked = 0
for d in docs:
    for n, line in enumerate(open(d, encoding="utf-8"), 1):
        ms = list(SCRIPT.finditer(line))
        for k, m in enumerate(ms):
            name = m.group(1)
            if name not in scripts: continue
            end = ms[k + 1].start() if k + 1 < len(ms) else len(line)
            chunk = line[m.end():end]; tick = chunk.find("`")
            if tick >= 0: chunk = chunk[:tick]
            chunk = re.split(r"\s(?:→|&&|\|\||;|then)\s", chunk)[0]
            for flag in re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", chunk):
                checked += 1
                text = helps.get(name) if name.endswith(".py") else open(scripts[name]).read()
                if text is None: text = open(scripts[name]).read()
                if flag not in text: probs.append(f"flags: {os.path.relpath(d, SKILL)}:{n}: {name} has no {flag}")

notes.append(f"flags: {checked} documented flags checked")
stub = os.path.join(SKILL, "assets/remotion-template/src/Timeline.tsx")
if not os.path.exists(stub): probs.append("contracts: assets/remotion-template/src/Timeline.tsx (stub) missing — a fresh scaffold does not compile")
else:
    t = open(stub).read()
    for nm in ("Timeline", "TOTAL_FRAMES"):
        if not re.search(rf"export const {nm}\b", t): probs.append(f"contracts: Timeline.tsx stub does not export {nm}")
r = run([sys.executable, "-I", os.path.join(HERE, "lint_reel.py"), os.path.join(SKILL, "assets/remotion-template/src")])
if r.returncode: probs.append("lint: " + " | ".join(l for l in r.stdout.splitlines() if "ERROR" in l or l.startswith("LINT")))
elif "warnings=" in r.stdout: notes.append("lint (template): " + r.stdout.strip().splitlines()[-1] + ("\n  " + "\n  ".join(r.stdout.strip().splitlines()[:-1]) if verbose else ""))

for x in notes: print("note:", x)
for x in probs: print("PROBLEM:", x)
print("SELFCHECK_OK" if not probs else f"SELFCHECK_FAILED {len(probs)}")
sys.exit(1 if probs else 0)
