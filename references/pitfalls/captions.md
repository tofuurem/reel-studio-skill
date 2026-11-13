# Captions and transcription

Russian goes through GigaAM v3 + Silero VAD (`transcribe.py --lang ru`; raw takes `transcribe_gigaam.py`), other languages through Whisper (`transcribe.py --lang <code>`). Page limits, the soft swap and patch syntax are owned by `craft/captions.md`.

- **Whisper invents text on silence** («Продолжение следует…», «Субтитры сделал…», «Спасибо за субтитры» on a silent tail) → never feed it a silent recording; check `ffmpeg -af volumedetect` first (mean ≈ −91 dB = silence; `inventory.py` notes «no sound»). GigaAM writes nothing on silence.
- **GigaAM drops a quiet word after a long pause** and spells foreign brands phonetically («Tripo» → «трипо») → read the page list against the audio; fix in `assets/brands.json` / `work/caption_patches.json`.
- **GigaAM word ends are the last token + 0.12 s (±0.1–0.26 s)**; starts are good → never cut or bleep on a bare word end, measure with `pauses.py`.
- **Narration misreads** («Итого» → «Год», «Ходьба» → «Сходьба») → read every take against the script; fix one occurrence with `replace_at`, never a global `replace`.
- **`replace_at` / `drop_at` hit every token with that text within ±1.5 s** → when the word repeats within 3 s, move the patch time away from the neighbour so only one token is in the window; re-read the page list.
- **Words under 0.4 confidence** are usually fillers or misheard → check them against the audio before trusting the caption.
