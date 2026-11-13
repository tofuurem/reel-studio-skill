"""GigaAM v3 (Sber, ONNX via onnx-asr) + Silero VAD over whole source clips -> work/pk/c<id>.json (clipid.py rule).

Usage: cd <project>; work/gigvenv/bin/python -I $S/transcribe_gigaam.py [--force] [--max-gb 6] [--min-free-gb 4] <video|audio>...
The raw-take map (the format the old Parakeet script wrote), so pk2words.py / cut_from_transcript.py read it: each JSON is
[{start, end, text, words: [{w, s, e}]}] in source seconds, one entry per sentence (split at . ? !). Differences:
`w` is a whole word with its leading space (and its punctuation), not a sentencepiece token; `e` is the last token's time
+ 0.12 s (GigaAM gives token emission times on a 40 ms grid, no end times), clamped to the next word / the segment end.
Russian only (the default model gigaam-v3-e2e-rnnt writes punctuation and normalises numbers); another language: transcribe.py --sources --lang <code> (Whisper).
Silero VAD gates speech first, so wind / engine noise gives no invented text; segments without a Cyrillic letter are dropped.
Long clips are decoded to 16 kHz mono once and fed in ~10 min pieces cut at the quietest spot, so memory stays flat (~1.5 GB).
It re-runs itself under mem_guard.py (kills it when it passes --max-gb or the Mac has less than --min-free-gb left; exit 137);
MEM_GUARDED=1 or --no-guard skips that. Prints GIGAAM_DONE. Existing work/pk/c<id>.json are skipped unless --force.
First run downloads the model from Hugging Face (≈ 1 GB) and Silero VAD (≈ 2 MB).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clipid import check_unique, clip_id  # noqa: E402

OUT = Path("work/pk")
SR = 16000
CHUNK_S = 600          # feed the model ~10 min at a time
LOOKAHEAD_S = 20       # look for the quietest 0.2 s in the last 20 s of a piece to cut there
TAIL_S = 0.12          # word end = last token time + this (clamped)
SENT_END = re.compile(r"[.?!…]+[\"»)]*$")
PUNCT_ONLY = re.compile(r"^[\W_]+$")
CYR = re.compile(r"[А-Яа-яЁё]")
LETTER = re.compile(r"[^\W\d_]")


def reexec_guarded(args: argparse.Namespace) -> None:
    """Re-run this script under mem_guard.py (macOS only, once)."""
    if args.no_guard or os.environ.get("MEM_GUARDED") or sys.platform != "darwin":
        return
    guard = Path(__file__).with_name("mem_guard.py")
    env = {**os.environ, "MEM_GUARDED": "1"}
    cmd = [sys.executable, "-I", str(guard), "--max-gb", str(args.max_gb), "--min-free-gb", str(args.min_free_gb), "--",
           sys.executable, "-I", os.path.abspath(__file__), *sys.argv[1:]]
    os.execve(sys.executable, cmd, env)


def words_from_tokens(tokens: list[str], stamps: list[float], base: float, seg_end: float) -> list[dict]:
    """Join GigaAM tokens (a leading space starts a word, punctuation has its own tokens) into {w, s, e} words."""
    words: list[dict] = []
    cur: dict | None = None
    new_word = True
    for tok, ts in zip(tokens, stamps):
        if tok.strip() == "":
            new_word = True
            continue
        if tok.startswith(" "):
            new_word = True
        punct = bool(PUNCT_ONLY.match(tok.strip())) and not tok.strip().startswith(("-", "—")) or tok.strip() in ("-", "—")
        # opening quote after a space belongs to the next word, any other punctuation sticks to the previous one
        if new_word or cur is None:
            if cur is not None:
                words.append(cur)
            cur = {"w": " " + tok.strip(), "s": base + ts, "last": base + ts}
            new_word = False
        else:
            cur["w"] += tok
            if not punct:
                cur["last"] = base + ts
    if cur is not None:
        words.append(cur)
    for i, w in enumerate(words):
        nxt = words[i + 1]["s"] if i + 1 < len(words) else seg_end
        w["e"] = round(max(min(w["last"] + TAIL_S, nxt, seg_end), w["s"] + 0.04), 2)
        w["s"] = round(w["s"], 2)
        del w["last"]
    return words


def to_sentences(words: list[dict]) -> list[dict]:
    """Split a word list at sentence-final punctuation into map entries."""
    out: list[dict] = []
    buf: list[dict] = []
    for w in words:
        buf.append(w)
        if SENT_END.search(w["w"].strip()):
            out.append(buf)
            buf = []
    if buf:
        out.append(buf)
    return [{"start": b[0]["s"], "end": b[-1]["e"], "text": "".join(x["w"] for x in b).strip(), "words": b} for b in out]


def pieces(wav: Path):
    """Yield (offset_seconds, float32 mono array) pieces of ~CHUNK_S, each cut at the quietest 0.2 s near its end."""
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(str(wav)) as f:
        total, pos = len(f), 0
        while pos < total:
            end = min(pos + CHUNK_S * SR, total)
            if end < total:
                f.seek(max(end - LOOKAHEAD_S * SR, pos))
                tail = f.read(end - max(end - LOOKAHEAD_S * SR, pos), dtype="float32")
                step = SR // 5
                n = len(tail) // step
                if n > 1:
                    rms = np.sqrt((tail[: n * step].reshape(n, step) ** 2).mean(axis=1))
                    end = max(end - LOOKAHEAD_S * SR, pos) + (int(rms.argmin()) * step + step // 2)
            f.seek(pos)
            yield pos / SR, f.read(end - pos, dtype="float32")
            pos = end


def transcribe_clip(src: Path, model, vad) -> tuple[list[dict], int]:
    """Return (sentences, dropped segment count) for one source clip."""
    sentences: list[dict] = []
    dropped = 0
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:a:0", "-ac", "1",
                        "-ar", str(SR), str(wav)], check=True)
        for offset, audio in pieces(wav):
            for seg in model.recognize(audio, sample_rate=SR):
                text = (seg.text or "").strip()
                if not text or not seg.tokens or (LETTER.search(text) and not CYR.search(text)):
                    dropped += bool(text)    # empty VAD hits are not worth a mention; Latin-only garbage is
                    continue
                base = offset + seg.start
                words = words_from_tokens(seg.tokens, seg.timestamps, base, offset + seg.end)
                sentences += to_sentences(words)
    return sentences, dropped


def main() -> None:
    ap = argparse.ArgumentParser(description="GigaAM v3 + Silero VAD -> work/pk/c<id>.json")
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--model", default="gigaam-v3-e2e-rnnt", help="onnx-asr model name (gigaam-v3-rnnt: no punctuation)")
    ap.add_argument("--lang", default="ru", help="only ru is supported")
    ap.add_argument("--force", action="store_true", help="overwrite existing work/pk/c<id>.json")
    ap.add_argument("--vad-threshold", type=float, default=0.5, help="Silero speech threshold (raise for windy takes)")
    ap.add_argument("--max-gb", type=float, default=6.0, help="mem_guard: the run's memory ceiling")
    ap.add_argument("--min-free-gb", type=float, default=4.0, help="mem_guard: memory always left to the Mac")
    ap.add_argument("--no-guard", action="store_true")
    args = ap.parse_args()
    if args.lang != "ru":
        sys.exit("GigaAM is Russian only — for another language: transcribe.py --sources --lang <code> <clips> (Whisper, → work/new/c<id>.json)")
    check_unique(args.sources)
    reexec_guarded(args)
    OUT.mkdir(parents=True, exist_ok=True)
    import onnx_asr   # here, so --help works without the venv
    # CPU only: CoreMLExecutionProvider fails on this model's dynamic shapes; CPU runs ≈ 20x realtime on an M4 Pro
    model = onnx_asr.load_model(args.model, providers=["CPUExecutionProvider"]).with_vad(
        onnx_asr.load_vad("silero"), threshold=args.vad_threshold).with_timestamps()
    for src in map(Path, args.sources):
        target = OUT / f"{clip_id(str(src))}.json"
        if target.exists() and not args.force:
            print("skip", target)
            continue
        t0 = time.time()
        sentences, dropped = transcribe_clip(src, model, model)  # model carries the VAD adapter
        target.write_text(json.dumps(sentences, ensure_ascii=False, indent=1))
        n = sum(len(s["words"]) for s in sentences)
        print(f"{target}: {len(sentences)} sentences, {n} words, {dropped} non-Russian segments dropped, {time.time() - t0:.0f}s")
    print("GIGAAM_DONE")


if __name__ == "__main__":
    main()
