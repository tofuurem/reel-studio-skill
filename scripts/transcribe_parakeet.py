"""Parakeet TDT 0.6B v3 (Handy's weights, converted once by setup_env.sh → gguf2mlx.py) over whole source clips -> work/pk/c<id>.json (clipid.py rule).

Usage: cd <project>; work/pkvenv/bin/python -I $S/transcribe_parakeet.py <video|audio>...
Each JSON: [{start, end, text, words: [{w, s, e}]}] in source seconds. ~50x realtime on M4 Pro, no repetition loops
in pauses; language is auto-detected, so silent/noisy clips may yield short English phrases — drop Latin-only lines.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from parakeet_mlx import from_pretrained

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clipid import check_unique, clip_id  # noqa: E402

MODEL = Path.home() / ".cache/reel-studio/models/parakeet-v3-handy"
OUT = Path("work/pk")


def main(sources: list[str]) -> None:
    check_unique(sources)
    OUT.mkdir(parents=True, exist_ok=True)
    model = from_pretrained(str(MODEL))
    for src in map(Path, sources):
        target = OUT / f"{clip_id(str(src))}.json"
        if target.exists():
            print("skip", target)
            continue
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "a.wav"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(wav)], check=True)
            result = model.transcribe(str(wav), chunk_duration=120, overlap_duration=15)
        sentences = [
            {"start": s.start, "end": s.end, "text": s.text.strip(), "words": [{"w": t.text, "s": t.start, "e": t.end} for t in s.tokens]}
            for s in result.sentences
        ]
        target.write_text(json.dumps(sentences, ensure_ascii=False, indent=1))
        print(f"{target}: {len(sentences)} sentences")


if __name__ == "__main__":
    main(sys.argv[1:])
