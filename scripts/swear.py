#!/usr/bin/env python3
"""The one profanity matcher (used by cut_from_transcript.py, bleeps_from_timeline.py, make_captions.py, mask_captions.py,
doctor.py). Run it to self-test: python3 -I swear.py → prints FAIL lines if a known word is missed or an innocent word is caught.
The root list is matched at the start of the word after an optional prefix, so short prefixes ("с", "у", "о") glue onto
innocent roots: «себестоимость» = с + ебе… once merged with the next swear into a 1.55 s bleep (audit 2026-10-22).
INNOCENT_PREFIX lists word starts that are never swears; INNOCENT whole words."""
import re
SWEAR = re.compile(r"^[^а-яё]*(ни|нах|на|про|за|по|до|от|у|съ|въ|подъ|объ|разъ|отъ|с|вы|об|при|и|о|рас|раз|под|пере)?(бля|бляд|хуй|хуё|хуе|хуя|хуи|пизд|ёпт|епт|еба|ебу|ебё|ебе|ебы|ебл|ёб|заеб|наеб|охуе|охуи)", re.I)
INNOCENT = {"хуже"}
INNOCENT_PREFIX = ("себе", "себя", "усеб", "подсеб", "насеб", "хулиг", "хутор", "небе", "ребё", "ребе",
                   "убеж", "убед", "побед", "обед", "оглобл", "сабл", "рубл", "корабл", "оскорбл", "употребл", "истребл", "колебл", "стебел")

def is_swear(word):
    core = re.sub(r"^[^\wа-яё]+|[^\wа-яё]+$", "", word.strip(), flags=re.I).lower()
    if not core or core in INNOCENT or core.startswith(INNOCENT_PREFIX): return False
    return bool(SWEAR.search(core))

if __name__ == "__main__":
    yes = "блять блядь нихуя хуй хуйня проебываемся ебать заебись наебали пиздец охуеть охуенно распиздяй ёбаный ебло похуй нахуй ебучий выебываться съебаться".split()
    no = ("себе себя себестоимость себестоимости себялюбие тебе хуже обед победа работа пробел убедить убеждать сабля рубля корабля "
          "оскорбление употребление истребитель колеблется небеса стебель хулиган хутор застраховать требуется ребёнок ребенок оглобля подъезд объект съесть объездной").split()
    ok = True
    for w in yes:
        if not is_swear(w): print("FAIL missed:", w); ok = False
    for w in no:
        if is_swear(w): print("FAIL caught innocent:", w); ok = False
    print("SWEAR_SELFTEST", "OK" if ok else "FAILED")
