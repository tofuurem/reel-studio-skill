#!/usr/bin/env python3
"""One clip-id rule for every script (proxies, voice, transcripts, timeline, face zones must agree).

DJI_20261009183139_0001_D.MP4 → c0001 ; anything else → c<basename>, made ASCII: NFC first (a macOS NFD name and the
same name typed in NFC give one id), U+00A0/U+202F count as spaces, Cyrillic is transliterated, anything outside
[A-Za-z0-9._-] becomes "_". ASCII names without spaces keep their old ids byte for byte (rec_day_v → crec_day_v).
DJI reuses the 4-digit counter across days, so the id is only safe within one project: `check_unique(paths)` aborts
with a clear message when two inputs collide (copy/rename one of the files, e.g. DJI_..._0005b_D.MP4).
CLI: clipid.py <path> [more paths]  → prints ids (used by voice_isolate.sh)
     clipid.py --stem <path>…        → prints the ASCII file stem (vo_carriers.sh names its carriers with it)
"""
import os, re, sys, unicodedata

TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))

def nfc(s):
    """NFC + the two macOS non-breaking spaces (U+00A0, U+202F before AM/PM) as plain spaces."""
    return unicodedata.normalize("NFC", s).replace(" ", " ").replace(" ", " ")

def translit(s):
    out = []
    for ch in s:
        t = TR.get(ch.lower())
        out.append(ch if t is None else (t[:1].upper() + t[1:] if ch.isupper() else t))
    return "".join(out)

def ascii_stem(stem, lower=False, keep="._-"):
    """Transliterate to a safe ASCII name. Plain ASCII without spaces comes back unchanged (unless lower=True)."""
    s = translit(nfc(stem).lower() if lower else nfc(stem))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(rf"[^A-Za-z0-9{re.escape(keep)}]+", "_", s).strip("_")
    return s or "file"

def clip_id(p):
    b = nfc(os.path.splitext(os.path.basename(p))[0]); parts = b.split("_")
    return "c" + (ascii_stem(parts[2]) if b.startswith("DJI_") and len(parts) > 2 else ascii_stem(b))

def check_unique(paths):
    seen = {}
    for p in paths:
        i = clip_id(p)
        if i in seen and nfc(os.path.abspath(seen[i])) != nfc(os.path.abspath(p)):
            sys.exit(f"clip id collision: {i} ← {seen[i]} and {p}. Copy one file under a new name (…_{i[1:]}b_D.MP4) and re-run.")
        seen[i] = p
    return seen

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--stem"]: print("\n".join(ascii_stem(os.path.splitext(os.path.basename(p))[0]) for p in args[1:])); raise SystemExit
    check_unique(args); print("\n".join(clip_id(p) for p in args))
