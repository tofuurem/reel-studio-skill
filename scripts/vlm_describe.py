#!/usr/bin/env python3
"""Scene descriptions with a local Qwen3-VL — optional, the heaviest thing in the skill (≈ 6–10 GB of memory).

    <python> -I vlm_describe.py jobs.json answers.jsonl [--engine mlx|transformers|llamacpp] [--model DIR|FILE] [--max-gb 12]

It re-runs itself under mem_guard.py (the guard kills it with exit 137 when it passes --max-gb or the computer has less than
--min-free-gb left; --no-guard skips that — never do).

Engines (--engine, else engines.choose("vlm") — engines.py next to this file —, else mlx on Apple Silicon and transformers
elsewhere):
  mlx           mlx-vlm, run with ~/.cache/reel-studio/vlmvenv/bin/python; default model
                ~/.cache/reel-studio/models/qwen3-vl-8b-4bit. MLX limits: memory --mem-gb (10 GB), cache 1 GB.
  transformers  Qwen3-VL through transformers + torch, run with ~/.cache/reel-studio/venv/bin/python. CUDA: 8B in bf16 (fp16
                where bf16 is not supported); CPU: 4B in bf16 (≈ 9 GB of RAM; --dtype fp32 doubles it). Default model: the local
                copy ~/.cache/reel-studio/models/qwen3-vl-{8b|4b} for the device (else the other size), else the Hugging Face
                id Qwen/Qwen3-VL-8B-Instruct / Qwen/Qwen3-VL-4B-Instruct (downloaded on first use).
  Another model for any engine (e.g. Qwen/Qwen3-VL-2B-Instruct, ≈ 4.5 GB — smaller and weaker, for a machine with little
                memory): --model, else env REEL_STUDIO_VLM_MODEL, else engines.py set-model vlm <folder|hf-id> (video-library's
                deps.py --with descriptions --vlm-model <hf-id> downloads it and remembers it).
  llamacpp      llama-mtmd-cli (llama.cpp) on PATH, one call per job: --model is a .gguf or a folder with the model and its
                mmproj .gguf (default ~/.cache/reel-studio/models/qwen3-vl-gguf); --mmproj when it lies elsewhere;
                --llama-args passes more flags (e.g. "-ngl 99" for a GPU build).
jobs.json: [{"id": "...", "images": ["frame1.jpg", ...], "context": "what is said in the scene, camera, time"}, ...]
answers.jsonl: one line per job {"id", "text", "sec", "peak_gb", "engine", "model"}; finished ids are skipped (a run can be
continued).
The model loads once (llamacpp: per job). Pictures are shrunk to 448 px on the long side. peak_gb: MLX's own peak on mlx;
elsewhere the peak resident memory of the process and its children (ru_maxrss).
"""
import argparse
import glob
import json
import os
import platform
import resource
import shlex
import shutil
import subprocess
import sys
import time

MODELS = os.path.expanduser("~/.cache/reel-studio/models")
DEFAULT_MODEL = os.path.join(MODELS, "qwen3-vl-8b-4bit")                     # mlx
TF_LOCAL = {"8b": os.path.join(MODELS, "qwen3-vl-8b"), "4b": os.path.join(MODELS, "qwen3-vl-4b")}
TF_HUB = {"8b": "Qwen/Qwen3-VL-8B-Instruct", "4b": "Qwen/Qwen3-VL-4B-Instruct"}
GGUF_DIR = os.path.join(MODELS, "qwen3-vl-gguf")
REEL_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REEL_SCRIPTS)
from common import add_guard_args, guard_reexec  # noqa: E402
ENGINES = ("mlx", "transformers", "llamacpp")
PROMPT = (
    "Это кадры одной сцены из личного видео, по порядку времени. "
    "{context}\n"
    "Опиши сцену по-русски для каталога видео. Ответь строго JSON без пояснений:\n"
    '{{"что": "1–2 предложения: что происходит, что делают люди", '
    '"где": "место коротко (улица, рынок, лодка, кафе…)", '
    '"кадр": "крупность и ракурс: селфи / от первого лица / общий план / деталь", '
    '"теги": ["3–8 коротких тегов"], '
    '"годится": "да / нет — можно ли взять кадр в ролик (резкий, нормально видно)"}}'
)


def default_engine():
    try:
        if REEL_SCRIPTS not in sys.path:
            sys.path.insert(0, REEL_SCRIPTS)
        import engines
        return engines.choose("vlm")
    except Exception:                       # no engines.py (an older reel-studio): the platform default
        return "mlx" if sys.platform == "darwin" and platform.machine() == "arm64" else "transformers"


def picked_model():
    """The model the user picked (engines.vlm_model(): env REEL_STUDIO_VLM_MODEL → config.json {"models": {"vlm"}}), else None."""
    try:
        if REEL_SCRIPTS not in sys.path:
            sys.path.insert(0, REEL_SCRIPTS)
        import engines
        return engines.vlm_model()
    except Exception:                       # no engines.py, or an older one without vlm_model()
        return (os.environ.get("REEL_STUDIO_VLM_MODEL") or "").strip() or None


def rss_peak_gb():
    """Peak resident memory of this process and of its finished children (ru_maxrss: KB on Linux, bytes on macOS)."""
    unit = 1 if sys.platform == "darwin" else 1024
    return max(resource.getrusage(w).ru_maxrss for w in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN)) * unit / 2**30


class MLX:
    def __init__(self, a):
        import mlx.core as mx
        mx.set_memory_limit(int(a.mem_gb * 2**30))
        mx.set_cache_limit(1 * 2**30)
        from mlx_vlm import load, generate
        from mlx_vlm.prompt_utils import apply_chat_template
        self.mx, self.generate, self.template, self.max_tokens = mx, generate, apply_chat_template, a.max_tokens
        t0 = time.time()
        self.name = a.model or DEFAULT_MODEL
        self.model, self.processor = load(self.name)
        print("model loaded in %.1f s, memory %.1f GB" % (time.time() - t0, mx.get_active_memory() / 2**30), flush=True)

    def describe(self, imgs, text):
        mx = self.mx
        prompt = self.template(self.processor, self.model.config, text, num_images=len(imgs))
        mx.reset_peak_memory()
        r = self.generate(self.model, self.processor, prompt, imgs, max_tokens=self.max_tokens, temperature=0.0, verbose=False)
        return getattr(r, "text", r), mx.get_peak_memory() / 2**30

    def after(self):
        self.mx.clear_cache()


class Transformers:
    def __init__(self, a):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.torch, self.max_tokens = torch, a.max_tokens
        cuda = torch.cuda.is_available()
        size, other = ("8b", "4b") if cuda else ("4b", "8b")
        model = a.model or next((TF_LOCAL[s] for s in (size, other) if os.path.isfile(os.path.join(TF_LOCAL[s], "config.json"))),
                                TF_HUB[size])
        if a.dtype == "auto":
            dtype = (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if cuda else torch.bfloat16
        else:
            dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[a.dtype]
        t0 = time.time()
        self.name = model
        self.processor = AutoProcessor.from_pretrained(model)
        self.model = AutoModelForImageTextToText.from_pretrained(model, torch_dtype=dtype, device_map="cuda" if cuda else None)
        self.model.eval()
        print("model %s loaded in %.1f s on %s (%s), RAM peak %.1f GB" % (model, time.time() - t0, "cuda" if cuda else "cpu",
              str(dtype).replace("torch.", ""), rss_peak_gb()), flush=True)

    def describe(self, imgs, text):
        torch = self.torch
        msgs = [{"role": "user", "content": [{"type": "image", "image": p} for p in imgs] + [{"type": "text", "text": text}]}]
        inputs = self.processor.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_dict=True,
                                                    return_tensors="pt").to(self.model.device)
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=self.max_tokens, do_sample=False)
        return self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0], rss_peak_gb()

    def after(self):
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()


class LlamaCpp:
    def __init__(self, a):
        self.cli = shutil.which("llama-mtmd-cli")
        if not self.cli:
            sys.exit("vlm_describe.py: llama-mtmd-cli is not on PATH (llama.cpp: https://github.com/ggml-org/llama.cpp)")
        src = a.model or GGUF_DIR
        if os.path.isdir(src):
            ggufs = sorted(glob.glob(os.path.join(src, "*.gguf")), key=os.path.getsize)
            models = [g for g in ggufs if "mmproj" not in os.path.basename(g).lower()]
            projs = [g for g in ggufs if "mmproj" in os.path.basename(g).lower()]
            self.model, self.mmproj = (models[-1] if models else None), (a.mmproj or (projs[-1] if projs else None))
        else:
            self.model, self.mmproj = src, a.mmproj
        if not (self.model and os.path.isfile(self.model) and self.mmproj and os.path.isfile(self.mmproj)):
            sys.exit("vlm_describe.py: llamacpp needs a Qwen3-VL .gguf and its mmproj .gguf (--model, --mmproj; default folder %s)"
                     % GGUF_DIR)
        self.max_tokens, self.extra, self.name = a.max_tokens, shlex.split(a.llama_args or ""), self.model
        print("llama.cpp: %s + %s" % (os.path.basename(self.model), os.path.basename(self.mmproj)), flush=True)

    def describe(self, imgs, text):
        cmd = [self.cli, "-m", self.model, "--mmproj", self.mmproj, "-c", "8192", "-n", str(self.max_tokens), "--temp", "0"]
        for p in imgs:
            cmd += ["--image", p]
        r = subprocess.run(cmd + self.extra + ["-p", text], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("llama-mtmd-cli failed: " + r.stderr.strip()[-400:])
        return r.stdout, rss_peak_gb()

    def after(self):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("out")
    ap.add_argument("--engine", choices=ENGINES, help="default: engines.choose('vlm'), else the platform's")
    ap.add_argument("--model", help="mlx / transformers: model folder or Hugging Face id; llamacpp: .gguf file or folder "
                    "(default: env REEL_STUDIO_VLM_MODEL / engines.py set-model vlm, else the engine's own default)")
    ap.add_argument("--mmproj", help="llamacpp: the mmproj .gguf (default: the one next to the model)")
    ap.add_argument("--llama-args", help="llamacpp: more llama-mtmd-cli flags, e.g. \"-ngl 99 -t 8\"")
    ap.add_argument("--dtype", default="auto", choices=["auto", "bf16", "fp16", "fp32"], help="transformers only")
    ap.add_argument("--max-tokens", type=int, default=260)
    ap.add_argument("--mem-gb", type=float, default=10.0, help="mlx only: MLX memory limit, GB")
    add_guard_args(ap, 12.0)
    a = ap.parse_args()
    guard_reexec(a)
    engine = a.engine or default_engine()
    a.model = a.model or picked_model()
    if engine not in ENGINES:
        sys.exit("vlm_describe.py: unknown vlm engine %r — one of %s" % (engine, ", ".join(ENGINES)))

    from PIL import Image

    jobs = json.load(open(a.jobs, encoding="utf-8"))
    done = set()
    if os.path.exists(a.out):
        for line in open(a.out, encoding="utf-8"):
            try:
                done.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                pass
    jobs = [j for j in jobs if j["id"] not in done]
    if not jobs:
        print("VLM_DONE (nothing to do)")
        return
    E = {"mlx": MLX, "transformers": Transformers, "llamacpp": LlamaCpp}[engine](a)
    tmpdir = os.path.join(os.path.dirname(os.path.abspath(a.out)), ".vlm_tmp")
    os.makedirs(tmpdir, exist_ok=True)
    with open(a.out, "a", encoding="utf-8") as f:
        for n, j in enumerate(jobs, 1):
            imgs = []
            for k, p in enumerate(j["images"]):
                im = Image.open(p).convert("RGB")
                im.thumbnail((448, 448))
                q = os.path.join(tmpdir, "%d.jpg" % k)
                im.save(q, quality=90)
                imgs.append(q)
            t = time.time()
            text, peak = E.describe(imgs, PROMPT.format(context=j.get("context", "")))
            rec = {"id": j["id"], "text": text.strip(), "sec": round(time.time() - t, 1), "peak_gb": round(peak, 2),
                   "engine": engine, "model": os.path.basename(str(E.name).rstrip("/"))}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            E.after()
            print("%d/%d %s — %.1f s, peak %.1f GB" % (n, len(jobs), j["id"], rec["sec"], rec["peak_gb"]), flush=True)
    print("VLM_DONE")


if __name__ == "__main__":
    main()
