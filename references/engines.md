# Engines: one model per capability, on every platform

Every picture and sound model goes through `scripts/engines.py`. A capability (faces, people, OCR …) has several engines;
macOS keeps Apple's frameworks by default, Linux (CPU, optionally NVIDIA CUDA) gets open models. The user can pick any engine
that runs on the machine, per capability.

## Table

| capability | engines | macOS default | Linux (CPU) | Linux + NVIDIA | used by |
|---|---|---|---|---|---|
| faces | `vision`, `yunet` | vision | yunet | yunet | face_zones, seams (match), name_tracks, censor_track, ref_analyze, actiongen circle |
| people | `vision`, `rtdetr`, `yolo` | vision | rtdetr | rtdetr (cuda) | people_zones, actiongen crop, seams (bodywipe) |
| hands | `vision`, `mediapipe`, `none` | vision | mediapipe if installed, else none | same | censor_track (hands, follow snap) |
| ocr | `vision`, `rapidocr` | vision | rapidocr | rapidocr | ref_analyze |
| feature_print | `vision`, `dinov2` | vision | dinov2 | dinov2 (cuda) | video map (scene cuts) |
| labels | `vision`, `siglip` | vision | siglip | siglip (cuda) | video map |
| aesthetics | `vision`, `none` | vision | none | none | video map |
| person_mask | `vision`, `birefnet` | vision | birefnet | birefnet | person_matte |
| cutout | `vision`, `birefnet` | vision | birefnet | birefnet | cutout |
| sound_events | `soundanalysis`, `ast` | soundanalysis | ast | ast (cuda) | video map |
| whisper | `mlx`, `faster`, `openai` | mlx (Apple Silicon), openai (Intel) | faster if installed, else openai | faster | transcribe (languages other than ru) |
| vlm | `mlx`, `transformers`, `llamacpp` | mlx (Apple Silicon) | transformers | transformers | vlm_describe |
| decode | `videotoolbox`, `cuda`, `none` | videotoolbox | none | cuda | `common.HWACCEL` (proxies, people_zones) |

`decode` uses an accelerator only when `ffmpeg -hwaccels` lists it (and, for cuda, `nvidia-smi` sees a GPU). person_matte's
`--mode auto` keeps BiRefNet on macOS when torch is in the venv (better edges than Vision); an explicit choice wins.

## Choosing

First that is set wins:
1. the script's flag: `--engine` (face_zones, people_zones, name_tracks, censor_track = hands, ref_analyze, seams = faces,
   cutout, person_matte, transcribe = whisper); second capabilities: `--faces-engine` (people_zones, censor_track),
   `--ocr-engine` (ref_analyze), `--people-engine` (seams);
2. env `REEL_STUDIO_ENGINE_<CAP>`, e.g. `REEL_STUDIO_ENGINE_FACES=yunet`;
3. `python3 -I $S/engines.py set <cap> <engine>` → `~/.cache/reel-studio/config.json` `{"engines": {...}}`
   (`set <cap> default` forgets it);
4. the platform default above.

`python3 -I $S/engines.py` prints the table for this machine: the chosen engine, where the choice came from, which engines run
here, and what to install for one that cannot run. `deps.py` prints the same table and lists what runs degraded.
A script whose engine cannot run stops with one line: what is missing and the command that fixes it.
Other skills call `<venv python> -I $S/engines.py faces|people|hands|ocr|labels|feature_print|aesthetics|sound_events <file>
[--engine X]` (JSON on stdout) or `import engines` with `sys.path.insert(0, $S)`.

The vlm **model** is chosen apart from the engine: `vlm_describe.py --model` → env `REEL_STUDIO_VLM_MODEL` →
`engines.py set-model vlm <folder|.gguf|hf-id|default>` (config.json `{"models": {"vlm": ...}}`) → the engine's default
(MLX: Qwen3-VL-8B 4-bit; transformers: 4B on a CPU, 8B with CUDA). A smaller one for a machine with little memory, e.g.
`Qwen/Qwen3-VL-2B-Instruct` (≈ 4.5 GB, ≈ 5 GB of RAM on a CPU; plainer descriptions): video-library's deps.py
(`--install --with descriptions --vlm-model Qwen/Qwen3-VL-2B-Instruct`; not this skill's deps.py) downloads it into `~/.cache/reel-studio/models/<name>`
and remembers it. The engine and model that wrote each description land in the answers (and in the video map's `engines`).

## Installing

- macOS: nothing to do for the defaults. The open engines: `python3 -I $S/deps.py --install --with linux-vision`.
- Linux: `python3 -I $S/deps.py --install` — the open engines (`linux-vision`) are part of the default install there (OpenCV, RapidOCR + onnxruntime — onnxruntime-gpu with an
  NVIDIA GPU —, MediaPipe when a wheel exists for the platform; torch + transformers come with the venv) and
  `--with fast-asr` (faster-whisper). Weights download on first use: Hugging Face models at pinned revisions into
  `~/.cache/huggingface` (RT-DETRv2 r18 ≈ 80 MB, DINOv2-small ≈ 90 MB, SigLIP 2 base ≈ 1.5 GB, AST ≈ 350 MB, BiRefNet ≈ 420 MB),
  small files (YuNet, the MediaPipe hand model, the Cyrillic OCR recogniser) pinned by URL + sha256 into `~/.cache/reel-studio/models`.
- YOLO: never installed by deps.py. A user who wants it installs `ultralytics` into the venv and sets `people` to `yolo`.

## Licences

| engine | model | licence |
|---|---|---|
| yunet | OpenCV Zoo YuNet 2023mar | MIT |
| rtdetr | PekingU/rtdetr_v2_r18vd | Apache-2.0 |
| yolo | Ultralytics YOLO11 | **AGPL-3.0** — fine for making a reel; shipping software that embeds it obliges you to publish that software's source (or buy their licence). engines.py prints a note whenever it is chosen. |
| mediapipe | HandLandmarker | Apache-2.0 |
| rapidocr | PP-OCRv4 detector, PP-OCRv5 East Slavic recogniser (ONNX) | Apache-2.0 |
| dinov2 | facebook/dinov2-small | Apache-2.0 |
| siglip | google/siglip2-base-patch16-224 | Apache-2.0 |
| ast | MIT/ast-finetuned-audioset-10-10-0.4593 | BSD-3-Clause |
| birefnet | ZhengPeng7/BiRefNet | MIT |
| faster / openai | Whisper weights | MIT |
| mlx / transformers / llamacpp (vlm) | Qwen3-VL | Apache-2.0 |
| GigaAM (Russian speech) | GigaAM v3 | MIT |
| Silero VAD | Silero VAD | MIT |
| DeepFilterNet (voice cleaning) | DeepFilterNet 3 | MIT / Apache-2.0 |
| earshot (optional sound) | earshot package | MIT (its package metadata; the listening models it fetches keep their own licences — see its repo) |

`scripts/engines_labels.txt` is the list of Apple Vision's label identifiers (names only, no model data) that SigLIP
scores against.

Not used: InsightFace / SCRFD face detectors — the code is MIT but the released weights are for non-commercial research only.

## What differs in quality

Measured on 50 camera frames against Vision (macOS, same frames). Speed per 1280 px frame, model loaded, 8-core ARM CPU
without a GPU: YuNet 0.03 s, MediaPipe hands 0.02 s, RT-DETR 0.32 s, RapidOCR 0.6 s, SigLIP 0.15 s, DINOv2 0.10 s,
BiRefNet 11.5 s; AST ≈ 1 s per 3 s window. The first call of a model adds its download and load (SigLIP: ≈ 1 min once,
including the vocabulary's text embeddings).
- **faces (yunet)**: found 59 of Vision's 67 faces; misses more small and turned faces, adds a few tiny ones (faces on a screen).
  YuNet's box starts at the hairline; engines.py maps it onto Vision's geometry (top + 0.18 h, height × 0.78), so head and
  mouth estimates keep working. A face filling the frame is found at a second, smaller scale.
- **people (rtdetr)**: more people in crowds (it finds the background too, plus low-score duplicates of one person);
  people_zones may pick another «main person» in a crowded frame — look at the `--sheet`.
- **hands (mediapipe)**: found 31 of Vision's 56 hands (misses small, blurred and partly hidden hands); **none** = no hand boxes at all (censor `hands`
  jobs come out empty, follow keys are not snapped — use `"snap": false` or box jobs).
- **ocr (rapidocr)**: comparable on captions and signs (it also reads small text Vision skips), more misreads on stylised fonts. Russian + English come from one
  East Slavic recogniser; other languages use the package's Chinese + English one.
- **feature_print (dinov2)**: cosine distance (0 same … 1), threshold 0.25 to start; never compare prints across engines.
- **labels (siglip)**: zero-shot over Vision's own vocabulary (`scripts/engines_labels.txt`), but flat — no parent words
  like «outdoor» or «structure» that Vision adds; about one label in five matches Vision's. Scores are rescaled
  (`SIGLIP_AT`, `SIGLIP_K`) so `min_conf` 0.3 keeps ≈ 6 labels a frame, as many as Vision.
- **aesthetics (none)**: no score; the video map picks frames by sharpness and the other signals.
- **sound_events (ast)**: AudioSet's 527 classes in snake_case (`wind_noise_microphone`), not SoundAnalysis' 303 — words in
  the map differ; speech, music, wind and laughter agree.
- **person_mask / cutout (birefnet)**: better edges than Vision (headphones, props kept), ≈ 0.7 s a frame on Apple Silicon,
  ≈ 12 s a frame on an 8-core ARM CPU (it always runs at 1024²): cut the range to the shot first.
- **whisper**: same model and dict on every engine; faster-whisper int8 is several times faster than openai-whisper on a CPU.

## Thresholds to recalibrate when an engine changes

Set on Vision; check on a few real shots after switching:
- `peopleMinConf` (numbers.json, 0.3) — RT-DETR scores run higher; raise it when posters and statues become people.
- face size bands: face_zones `close` > 300 px / `medium` > 180 px, ref_analyze `SIZES`, censor_track `minFace` 0.12.
- the scene threshold of the feature print (`engines.SCENE_THRESHOLD`; the video map's `--calib`).
- the SigLIP label scale (`SIGLIP_AT`, `SIGLIP_K`) and the YuNet geometry (`YUNET_TOP`, `YUNET_H`) in engines.py.
- caches keep their engine: people_zones / actiongen rescan a clip whose cached detections came from another engine.
