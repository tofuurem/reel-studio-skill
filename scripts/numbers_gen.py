#!/usr/bin/env python3
"""Regenerate the two derived copies of references/craft/numbers.json (the single source of numbers).

Usage: python3 -I numbers_gen.py [--check]
→ references/craft/numbers.md                 the table the docs point at
  assets/remotion-template/src/numbers.ts     `export const N = {...} as const` for the template
--check exits 1 if either file is out of date (the skill's selfcheck runs it).
"""
import argparse, json, os, sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(SKILL, "references/craft/numbers.json")
MD = os.path.join(SKILL, "references/craft/numbers.md")
TS = os.path.join(SKILL, "assets/remotion-template/src/numbers.ts")

ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); a = ap.parse_args()
data = json.load(open(SRC))
keys = [r["key"] for s in data["sections"] for r in s["rows"]]
dup = {k for k in keys if keys.count(k) > 1}
if dup: sys.exit(f"duplicate keys in numbers.json: {sorted(dup)}")

md = ["# Numbers in one place", "",
      "Generated from `numbers.json` by `scripts/numbers_gen.py` — edit the JSON, not this file. Timings are frames at 30 fps on the 1080×1920 canvas (Reel2K scales everything by 4/3). Scripts read the same values (`scripts/common.py`), the template imports them from `src/numbers.ts` (`N.<key>`).", ""]
for s in data["sections"]:
    md += [f"**{s['title']}**", "", "| key | value | what | why | used by |", "|---|---|---|---|---|"]
    for r in s["rows"]:
        md.append(f"| `{r['key']}` | {r['value']} | {r['what']} | {r.get('why', '')} | {r.get('used', '')} |")
    md.append("")
md_text = "\n".join(md)

ts = ["// Generated from references/craft/numbers.json by scripts/numbers_gen.py — edit the JSON, then re-run the script.", "export const N = {"]
for s in data["sections"]:
    ts.append(f"  // {s['title']}")
    for r in s["rows"]:
        ts.append(f"  {r['key']}: {json.dumps(r['value'])}, // {r['what']}")
ts.append("} as const;")
ts_text = "\n".join(ts) + "\n"

stale = [p for p, t in ((MD, md_text), (TS, ts_text)) if not os.path.exists(p) or open(p).read() != t]
if a.check:
    if stale: sys.exit("NUMBERS_STALE " + " ".join(os.path.relpath(p, SKILL) for p in stale) + " — run scripts/numbers_gen.py")
    print("NUMBERS_OK"); sys.exit(0)
for p, t in ((MD, md_text), (TS, ts_text)): open(p, "w").write(t)
print("NUMBERS_WRITTEN", os.path.relpath(MD, SKILL), os.path.relpath(TS, SKILL), f"({len(keys)} keys)")
