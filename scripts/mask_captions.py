"""Replace profanity (matcher in swear.py, shared with cut_from_transcript.py) in a Caption[] JSON with first letter + asterisks (timing untouched). Usage: mask_captions.py [captions.json]"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from swear import is_swear
caps_path = sys.argv[1] if len(sys.argv) > 1 else "reel/public/captions/timeline.json"
caps = json.load(open(caps_path)); n = 0
for c in caps:
    t = c["text"]; core = t.strip(); m = re.match(r"^([^\wа-яё]*)([\wа-яё-]+)(.*)$", core, re.I)
    if m and is_swear(m.group(2)):
        w = m.group(2); c["text"] = " " + m.group(1) + w[0] + "*" * (len(w) - 1) + m.group(3); n += 1
json.dump(caps, open(caps_path, "w"), ensure_ascii=False); print("masked", n)
