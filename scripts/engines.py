#!/usr/bin/env python3
"""One adapter for every picture / sound model the skill uses: the engine is chosen per capability, on every platform.

Usage: <venv python> -I engines.py [--json]                 → table: capability, chosen engine (and why), engines that run here
       python3 -I engines.py set <cap> <engine|default>    → remember the choice in ~/.cache/reel-studio/config.json
       python3 -I engines.py set-model vlm <folder|.gguf|hf-id|default>   → another scene-description model (vlm_model())
       <venv python> -I engines.py <cap> <file> [--engine X] [--lang en] [--out mask.png]   → JSON on stdout
         caps for the CLI: faces people hands ocr labels feature_print aesthetics sound_events person_mask cutout whisper decode
         (cutout: <in> <out.png> [--crop]; person_mask: --out writes the mask as a PNG; whisper: --lang, --model)
Library:  sys.path.insert(0, <reel-studio>/scripts); import engines; engines.faces("f.jpg") → [{"x","y","w","h","c"}]
Run from a system python3 (no venv active), the CLI re-runs itself under ~/.cache/reel-studio/venv, where the engines live.

Choosing (first that is set wins): the script's --engine flag → env REEL_STUDIO_ENGINE_<CAP> (e.g. REEL_STUDIO_ENGINE_FACES=yunet)
→ config.json {"engines": {"<cap>": "<engine>"}} → the platform default (Apple frameworks on macOS; open models elsewhere).
Capabilities, engines, defaults, licences and what differs in quality: references/engines.md.
Every box is normalised 0–1 with a TOP-LEFT origin: {"x", "y", "w", "h", "c"} (c = confidence 0–1).
Standard library at import time; every backend is imported inside its function. Weights download once: Hugging Face models at
pinned revisions into ~/.cache/huggingface, small ONNX / task files (pinned URL + sha256) into ~/.cache/reel-studio/models.
"""
import hashlib, importlib.util, json, os, platform, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
CACHE = os.path.expanduser("~/.cache/reel-studio")
MODELS = os.path.join(CACHE, "models")
VENV_PY = os.path.join(CACHE, "venv", "bin", "python")
MAC = sys.platform == "darwin"
LABELS_FILE = os.path.join(HERE, "engines_labels.txt")

# Hugging Face models: (repo, pinned revision) — a repo update never changes results under a running project
BIREFNET = ("ZhengPeng7/BiRefNet", "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4")          # MIT; ships its own model code
RTDETR = ("PekingU/rtdetr_v2_r18vd", "5650961749fa93567c0d46fc7f43ea4f9e914107")        # Apache-2.0, COCO (person = class 0)
DINOV2 = ("facebook/dinov2-small", "ed25f3a31f01632728cabb09d1542f84ab7b0056")          # Apache-2.0
SIGLIP = ("google/siglip2-base-patch16-224", "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2")  # Apache-2.0
AST = ("MIT/ast-finetuned-audioset-10-10-0.4593", "f826b80d28226b62986cc218e5cec390b1096902")  # BSD-3-Clause, AudioSet 527 classes
# Single files: name → (url, sha256)
FILES = {
    "yunet.onnx": ("https://github.com/opencv/opencv_zoo/raw/f12e12798e8314f7c074a6656816c048dcc95b7a/models/face_detection_yunet/"
                   "face_detection_yunet_2023mar.onnx", "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),   # MIT
    "hand_landmarker.task": ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
                             "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"),                                    # Apache-2.0
    # PP-OCRv5 East Slavic recogniser (Russian, Ukrainian, Belarusian, Bulgarian + Latin), ONNX export of PaddleOCR (Apache-2.0)
    "ocr_eslav_rec.onnx": ("https://huggingface.co/monkt/paddleocr-onnx/resolve/7b02d0a30a07ba2b92ad1ff5a8941ae2c633de65/languages/eslav/rec.onnx",
                           "dc6bf0e855247decce214ba6dae5bc135fa0ad725a5918a7fcfb59fad6c9cdee"),
    "ocr_eslav_dict.txt": ("https://huggingface.co/monkt/paddleocr-onnx/resolve/7b02d0a30a07ba2b92ad1ff5a8941ae2c633de65/languages/eslav/dict.txt",
                           "3e95f1581557162870cacdba5af91a4c6be2890710d395b0c3c7578e7ee5e6eb"),
}

ENGINES = {   # capability → engines, in the order the table lists them
    "faces": ("vision", "yunet"),
    "people": ("vision", "rtdetr", "yolo"),
    "hands": ("vision", "mediapipe", "none"),
    "ocr": ("vision", "rapidocr"),
    "feature_print": ("vision", "dinov2"),
    "labels": ("vision", "siglip"),
    "aesthetics": ("vision", "none"),
    "person_mask": ("vision", "birefnet"),
    "cutout": ("vision", "birefnet"),
    "sound_events": ("soundanalysis", "ast"),
    "whisper": ("mlx", "faster", "openai"),
    "vlm": ("mlx", "transformers", "llamacpp"),
    "decode": ("videotoolbox", "cuda", "none"),
}
WHAT = {"faces": "face boxes (face_zones, seams, name_tracks, censor_track, ref_analyze)", "people": "person boxes (people_zones, seams)",
        "hands": "hand boxes (censor_track)", "ocr": "on-screen text (ref_analyze)", "feature_print": "scene change print (video map)",
        "labels": "what is in the frame (video map)", "aesthetics": "frame score (video map)", "person_mask": "matte (person_matte)",
        "cutout": "subject cut-out (cutout)", "sound_events": "sounds in 3 s windows (video map)", "whisper": "speech, not Russian (transcribe)",
        "vlm": "frame descriptions (vlm_describe)", "decode": "ffmpeg hardware decode (common.HWACCEL)"}
TORCH = ("torch", "transformers")
NEEDS = {   # (cap, engine) → python modules it imports; "vision" also needs macOS
    "vision": ("Vision", "Quartz", "Foundation"), "yunet": ("cv2", "numpy"), "rtdetr": TORCH, "yolo": ("ultralytics",),
    "mediapipe": ("mediapipe", "numpy"), "rapidocr": ("rapidocr_onnxruntime", "numpy"), "dinov2": TORCH, "siglip": TORCH,
    "birefnet": (*TORCH, "timm", "kornia", "einops"), "ast": TORCH, "faster": ("faster_whisper",), "openai": ("whisper",),
}
FIX = {   # engine → the command that makes it available
    "vision": "python3 -I deps.py --install (pyobjc Vision in the venv)", "soundanalysis": "xcode-select --install (swiftc)",
    "yunet": "python3 -I deps.py --install (macOS: add --with linux-vision)", "rapidocr": "python3 -I deps.py --install (macOS: add --with linux-vision)",
    "mediapipe": "python3 -I deps.py --install (macOS: add --with linux-vision; installs libEGL / libGLES too; no mediapipe wheel for every platform)",
    "rtdetr": "python3 -I deps.py --install", "dinov2": "python3 -I deps.py --install", "siglip": "python3 -I deps.py --install",
    "ast": "python3 -I deps.py --install", "birefnet": "python3 -I deps.py --install",
    "yolo": "install ultralytics into the venv yourself (AGPL-3.0: uv pip install --python ~/.cache/reel-studio/venv/bin/python ultralytics)",
    "faster": "python3 -I deps.py --install --with fast-asr", "openai": "python3 -I deps.py --install",
    "mlx": "Apple Silicon only: python3 -I deps.py --install", "llamacpp": "llama.cpp with llama-mtmd-cli on PATH, a GGUF model + mmproj",
    "transformers": "python3 -I deps.py --install", "cuda": "an NVIDIA GPU and an ffmpeg built with CUDA", "videotoolbox": "macOS ffmpeg",
}
YOLO_NOTE = "people engine yolo: Ultralytics is AGPL-3.0 — a reel made with it is fine, shipping software that embeds it is not (references/engines.md)"
_ONCE = set()


def _say(msg):
    if msg not in _ONCE: _ONCE.add(msg); print(msg, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ platform
_FACTS = {}
def apple_silicon():
    if "as" not in _FACTS:
        _FACTS["as"] = MAC and (platform.machine() == "arm64" or subprocess.run(["sysctl", "-n", "sysctl.proc_translated"], capture_output=True,
                                                                                text=True).stdout.strip() == "1")
    return _FACTS["as"]

HW_CACHE = os.path.join(CACHE, "hwaccels.json")   # probes that would otherwise spawn a process on every import of common

def _bin_key(path):
    st = os.stat(path); return f"{os.path.realpath(path)}:{st.st_size}:{int(st.st_mtime)}"

def _probe_cached(field, key, probe):
    """probe() once per key (a binary's path + size + mtime), kept under `field` in HW_CACHE (atomic write)."""
    try: c = json.load(open(HW_CACHE))
    except (OSError, ValueError): c = {}
    c = {k: v for k, v in c.items() if isinstance(v, dict)} if isinstance(c, dict) else {}   # drops the old flat format
    got = c.get(field)
    if isinstance(got, dict) and got.get("key") == key: return got.get("value")
    val = probe(); c[field] = {"key": key, "value": val}
    try:
        os.makedirs(CACHE, exist_ok=True); tmp = HW_CACHE + f".{os.getpid()}"
        json.dump(c, open(tmp, "w")); os.replace(tmp, HW_CACHE)
    except OSError: pass
    return val

def nvidia():
    """An NVIDIA GPU visible to `nvidia-smi -L` — cached per nvidia-smi binary and GPU device set in HW_CACHE."""
    if "nv" not in _FACTS:
        smi = shutil.which("nvidia-smi")
        if not smi: _FACTS["nv"] = False
        else:
            devs = ",".join(sorted(d for d in os.listdir("/dev") if d.startswith("nvidia"))) if os.path.isdir("/dev") else ""
            _FACTS["nv"] = bool(_probe_cached("nvidia", f"{_bin_key(smi)}|{devs}",
                                              lambda: subprocess.run([smi, "-L"], capture_output=True).returncode == 0))
    return _FACTS["nv"]

def hwaccels():
    """What `ffmpeg -hwaccels` lists — cached per ffmpeg binary in HW_CACHE (it runs on every import of common)."""
    if "hw" in _FACTS: return _FACTS["hw"]
    ff = shutil.which("ffmpeg"); out = []
    if ff:
        def probe():
            r = subprocess.run([ff, "-hide_banner", "-hwaccels"], capture_output=True, text=True)
            return [l.strip() for l in r.stdout.splitlines()[1:] if l.strip()]
        out = _probe_cached("hwaccels", _bin_key(ff), probe) or []
    _FACTS["hw"] = out
    return out


# ------------------------------------------------------------------ choosing
def _has(mods): return all(importlib.util.find_spec(m) is not None for m in mods)

def missing(cap, engine):
    """Why `engine` cannot run here for `cap` ('' = it can)."""
    if engine == "none": return ""
    if engine == "vision":
        if not MAC: return "Apple Vision is macOS only"
        return "" if _has(NEEDS["vision"]) else "pyobjc Vision is not in this python"
    if engine == "soundanalysis":
        if not MAC: return "Apple SoundAnalysis is macOS only"
        return "" if os.path.exists(_sound_bin()) or shutil.which("xcrun") else "no swiftc (Xcode Command Line Tools)"
    if engine == "mlx":
        if not apple_silicon(): return "MLX needs Apple Silicon"
        if cap == "vlm":   # mlx-vlm lives in its own env (vlmvenv); vlm_describe.py switches to it
            return "" if _has(("mlx_vlm",)) or os.path.exists(os.path.join(CACHE, "vlmvenv", "bin", "python")) else "no mlx-vlm (vlmvenv)"
        return "" if _has(("mlx_whisper",)) else "mlx-whisper is not in this python"
    if engine == "transformers": return "" if _has(TORCH) else "torch + transformers are not in this python"
    if engine == "llamacpp": return "" if shutil.which("llama-mtmd-cli") else "llama-mtmd-cli is not on PATH"
    if engine == "videotoolbox": return "" if MAC and "videotoolbox" in hwaccels() else "ffmpeg here has no videotoolbox"
    if engine == "cuda":
        if not nvidia(): return "no NVIDIA GPU visible (nvidia-smi)"
        return "" if "cuda" in hwaccels() else "ffmpeg here has no cuda hwaccel"
    lack = [m for m in NEEDS.get(engine, ()) if importlib.util.find_spec(m) is None]
    if lack: return "not in this python: " + ", ".join(lack)
    if engine == "mediapipe" and sys.platform.startswith("linux"):   # its tasks library dlopens EGL / GLES even on the CPU
        import ctypes.util
        gl = [n for n in ("EGL", "GLESv2") if not ctypes.util.find_library(n)]
        if gl: return "mediapipe needs " + " + ".join(f"lib{n}" for n in gl) + " (apt: libegl1 libgles2)"
    return ""

def available(cap):
    """Engines for `cap` that can run in this python on this machine."""
    return [e for e in ENGINES[cap] if not missing(cap, e)]

def default(cap):
    """The platform default: Apple frameworks on macOS, open models elsewhere (references/engines.md)."""
    if cap == "decode":
        if MAC: return "videotoolbox" if "videotoolbox" in hwaccels() else "none"
        return "cuda" if not missing(cap, "cuda") else "none"
    if cap == "whisper":
        if apple_silicon(): return "mlx"
        if MAC: return "openai"
        return "faster" if _has(("faster_whisper",)) else "openai"   # NVIDIA or CPU: faster-whisper only when it is installed
    if cap == "vlm": return "mlx" if apple_silicon() else "transformers"
    if MAC: return ENGINES[cap][0]
    if cap == "hands": return "none" if missing(cap, "mediapipe") else "mediapipe"
    return {"sound_events": "ast"}.get(cap) or ENGINES[cap][1]

def _check(cap, name, where):
    if cap not in ENGINES: sys.exit(f"engines: unknown capability {cap!r} — one of: {', '.join(ENGINES)}")
    if name not in ENGINES[cap]: sys.exit(f"engines: {where} names {name!r} for {cap} — valid: {', '.join(ENGINES[cap])}")
    return name

def _config():
    import projects_dir
    return projects_dir.load()

def choose_why(cap, override=None):
    """(engine, where the choice came from: flag / env / config / default)."""
    if override: return _check(cap, override, "--engine"), "flag"
    env = os.environ.get(f"REEL_STUDIO_ENGINE_{cap.upper()}")
    if env: return _check(cap, env.strip(), f"REEL_STUDIO_ENGINE_{cap.upper()}"), "env"
    cfg = (_config().get("engines") or {}).get(cap)
    if cfg: return _check(cap, cfg, "config.json"), "config"
    return default(cap), "default"

def choose(cap, override=None):
    """The engine for `cap`: override (--engine) → env REEL_STUDIO_ENGINE_<CAP> → config.json → platform default."""
    return choose_why(cap, override)[0]

def require(cap, script, override=None):
    """The chosen engine, or exit with one line: what is missing and the command that fixes it (or how to choose another)."""
    name, why = choose_why(cap, override)
    if name == "yolo": _say(YOLO_NOTE)
    miss = missing(cap, name)
    if not miss: return name
    others = [e for e in available(cap) if e != name]
    alt = f"; or pick another: --engine {others[0]} / engines.py set {cap} {others[0]} (runs here: {', '.join(others)})" if others else ""
    sys.exit(f"{script}: {cap} engine {name} ({why}) cannot run — {miss}. Fix: {FIX.get(name, 'python3 -I deps.py --install')}{alt}")

def set_engine(cap, name):
    import projects_dir
    cfg = projects_dir.load(); eng = cfg.setdefault("engines", {})
    if name in ("default", "auto", ""): eng.pop(cap, None)
    else: eng[cap] = _check(cap, name, "set")
    if not eng: cfg.pop("engines", None)
    projects_dir.save(cfg)

def vlm_model():
    """The scene-description model the user picked instead of vlm_describe.py's default, or None: env REEL_STUDIO_VLM_MODEL →
    config.json {"models": {"vlm": ...}} (engines.py set-model vlm <x>; video-library's deps.py --vlm-model writes it). A folder,
    a .gguf (llamacpp) or a Hugging Face id; an id whose copy is in ~/.cache/reel-studio/models/<last part, lower case> resolves
    to that folder (deps.py downloads it there), else it downloads on first use."""
    m = (os.environ.get("REEL_STUDIO_VLM_MODEL") or (_config().get("models") or {}).get("vlm") or "").strip()
    if not m: return None
    if os.path.exists(os.path.expanduser(m)): return os.path.expanduser(m)
    local = os.path.join(MODELS, m.rstrip("/").split("/")[-1].lower())
    return local if os.path.isfile(os.path.join(local, "config.json")) else m

def set_vlm_model(m):
    import projects_dir
    cfg = projects_dir.load(); mod = cfg.setdefault("models", {})
    if m in ("default", "auto", ""): mod.pop("vlm", None)
    else: mod["vlm"] = m
    if not mod: cfg.pop("models", None)
    projects_dir.save(cfg)


# ------------------------------------------------------------------ shared helpers
def _fetch(name):
    """A pinned single file (FILES) in ~/.cache/reel-studio/models, downloaded once and checked by sha256."""
    url, sha = FILES[name]; dst = os.path.join(MODELS, name)
    if os.path.exists(dst): return dst
    os.makedirs(MODELS, exist_ok=True); part = dst + f".{os.getpid()}.part"
    import urllib.request
    _say(f"engines: downloading {name} (once) from {url.split('/')[2]}")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(part, "wb") as f: shutil.copyfileobj(r, f)
    except OSError as e:
        if os.path.exists(part): os.remove(part)
        sys.exit(f"engines: cannot download {name} ({e}) — offline? Put the file at {dst} (sha256 {sha}) from {url}")
    got = hashlib.sha256(open(part, "rb").read()).hexdigest()
    if got != sha: os.remove(part); sys.exit(f"engines: {name} from {url} has sha256 {got}, expected {sha} — not used")
    os.replace(part, dst)
    return dst

def device():
    """torch device: $REEL_STUDIO_DEVICE, else cuda → mps → cpu."""
    import torch
    d = os.environ.get("REEL_STUDIO_DEVICE")
    if d: return d
    return "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

def pil(img):
    """Path / PIL image / HxWx3 uint8 array → PIL RGB (no EXIF rotation: frames from ffmpeg carry none, and Vision ignores it too)."""
    from PIL import Image
    if isinstance(img, Image.Image): return img.convert("RGB")
    if isinstance(img, (str, os.PathLike)):
        with Image.open(img) as im: return im.convert("RGB")
    return Image.fromarray(img).convert("RGB")

def rgb(img):
    import numpy as np
    if hasattr(img, "shape") and getattr(img, "ndim", 0) == 3: return np.ascontiguousarray(img[..., :3], dtype=np.uint8)
    return np.asarray(pil(img))

def resize(m, w, h):
    """Bilinear resize of a float mask with numpy (no PIL needed)."""
    import numpy as np
    if m.shape == (h, w): return m
    ys = np.clip((np.arange(h) + .5) * m.shape[0] / h - .5, 0, m.shape[0] - 1); xs = np.clip((np.arange(w) + .5) * m.shape[1] / w - .5, 0, m.shape[1] - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int); y1, x1 = np.minimum(y0 + 1, m.shape[0] - 1), np.minimum(x0 + 1, m.shape[1] - 1)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    top = m[y0][:, x0] * (1 - fx) + m[y0][:, x1] * fx; bot = m[y1][:, x0] * (1 - fx) + m[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy

def _size(img):
    if hasattr(img, "shape"): return img.shape[1], img.shape[0]
    return pil(img).size

_M = {}
def _model(key, load, hf=False):
    if key not in _M:
        _quiet(hf); _M[key] = load()
    return _M[key]

def _quiet(hf):
    """No progress bars or backend chatter on stderr (the CLI's stdout is JSON; scripts print their own progress)."""
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1"); os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2"); os.environ.setdefault("GLOG_minloglevel", "2")
    try:
        if hf:
            from transformers.utils import logging as tl
            tl.set_verbosity_error(); tl.disable_progress_bar()
        if "cv2" in sys.modules:
            import cv2; cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception: pass


# ------------------------------------------------------------------ Apple Vision (macOS)
_CS = []
def _cg(img):
    """CGImage of a path (read by ImageIO, as the scripts always did) or of an RGB array; None when unreadable."""
    import Quartz
    from Foundation import NSURL
    if isinstance(img, (str, os.PathLike)):
        src = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(os.fspath(img)), None)
        return None if src is None else Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
    a = rgb(img); h, w = a.shape[:2]; buf = a.tobytes()
    if not _CS: _CS.append(Quartz.CGColorSpaceCreateDeviceRGB())
    prov = Quartz.CGDataProviderCreateWithData(None, buf, len(buf), None)
    return Quartz.CGImageCreate(w, h, 8, 24, w * 3, _CS[0], Quartz.kCGImageAlphaNone, prov, None, False, Quartz.kCGRenderingIntentDefault)

def vision_run(img, reqs, url=False):
    """Perform Vision requests on one image; returns the handler (None when the image cannot be read). url=True hands Vision
    the file itself (initWithURL) instead of a CGImage read by ImageIO: the two paths decode differently, so scores differ in
    the 2nd–3rd decimal. Each capability keeps the path its scripts always used: CGImage for faces / people / hands / ocr
    (reel-studio), the URL for feature_print / labels / aesthetics (the video map)."""
    import Vision
    if url and isinstance(img, (str, os.PathLike)):
        from Foundation import NSURL
        if not os.path.exists(img): return None
        h = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(os.fspath(img)), None)
        h.performRequests_error_(reqs, None)
        return h
    cg = _cg(img)
    if cg is None: return None
    h = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    h.performRequests_error_(reqs, None)
    return h

def _vbox(r):
    b = r.boundingBox()
    return {"x": b.origin.x, "y": 1 - b.origin.y - b.size.height, "w": b.size.width, "h": b.size.height, "c": float(r.confidence())}

def _vision_hands(obs):
    import Vision
    out = []
    for o in obs or []:
        pts, _ = o.recognizedPointsForJointsGroupName_error_(Vision.VNHumanHandPoseObservationJointsGroupNameAll, None)
        xy = [(p.location().x, 1 - p.location().y) for p in (pts or {}).values() if p.confidence() > 0.3]
        if len(xy) >= 4:
            xs, ys = zip(*xy); out.append((min(xs), min(ys), max(xs), max(ys)))
    return out

def _vision_ocr_req(langs):
    import Vision
    tr = Vision.VNRecognizeTextRequest.alloc().init(); tr.setRecognitionLevel_(0); tr.setUsesLanguageCorrection_(False)
    tr.setRecognitionLanguages_([{"ru": "ru-RU", "en": "en-US"}.get(l, l) for l in langs]); return tr

def _vision_ocr(obs, min_conf):
    out = []
    for r in obs or []:
        c = r.topCandidates_(1)
        if not c or c[0].confidence() < min_conf: continue
        b = r.boundingBox()
        out.append({"text": str(c[0].string()).strip(), "x": b.origin.x, "y": 1 - b.origin.y - b.size.height, "w": b.size.width, "h": b.size.height,
                    "c": float(c[0].confidence())})
    return out

def vision_detect(img, faces=False, people=False, hands=False, ocr=False, langs=("ru", "en"), max_hands=6, ocr_min_conf=0.4,
                  upper_body=False, url=False):
    """Several Vision requests in ONE pass over the image (people_zones, censor_track, ref_analyze ask two at a time).
    Returns {"faces", "people", "hands", "ocr"} for what was asked; boxes as in faces()/people()/hands()/ocr()."""
    import Vision
    reqs = {}
    if faces: reqs["faces"] = Vision.VNDetectFaceRectanglesRequest.alloc().init()
    if people: reqs["people"] = Vision.VNDetectHumanRectanglesRequest.alloc().init(); reqs["people"].setUpperBodyOnly_(upper_body)
    if hands: reqs["hands"] = Vision.VNDetectHumanHandPoseRequest.alloc().init(); reqs["hands"].setMaximumHandCount_(max_hands)
    if ocr: reqs["ocr"] = _vision_ocr_req(langs)
    out = {k: [] for k in reqs}
    if vision_run(img, list(reqs.values()), url) is None: return out
    for k, r in reqs.items():
        res = r.results() or []
        out[k] = _vision_hands(res) if k == "hands" else _vision_ocr(res, ocr_min_conf) if k == "ocr" else [_vbox(x) for x in res]
    return out


# ------------------------------------------------------------------ faces
def faces(img, engine=None):
    """Face boxes [{"x","y","w","h","c"}] (0–1, top-left)."""
    e = engine or choose("faces")
    if e == "vision": return vision_detect(img, faces=True)["faces"]
    if e == "yunet": return _yunet(img)
    raise ValueError(f"faces engine {e}")

YUNET_TOP, YUNET_H = 0.18, 0.78

def _yunet(img, score=0.7):
    """OpenCV YuNet (MIT, 2023mar) at two scales: the long side ≤ 1280 (small faces) and 480 (a face filling the frame — at
    full size YuNet then boxes the nose and mouth only). Overlapping boxes (IoU > 0.3, or the smaller one mostly inside) keep
    the higher score. score 0.7: Vision finds small and turned faces; YuNet's demo threshold 0.9 misses them."""
    import cv2
    a = cv2.cvtColor(rgb(img), cv2.COLOR_RGB2BGR); H, W = a.shape[:2]; L = max(W, H)
    det = _model("yunet", lambda: cv2.FaceDetectorYN.create(_fetch("yunet.onnx"), "", (320, 320), score, 0.3, 5000))
    det.setScoreThreshold(score); found = []
    for side in sorted({min(L, 1280), 480} if L > 640 else {L}, reverse=True):
        k = side / L; w, h = max(1, round(W * k)), max(1, round(H * k))
        x = a if (w, h) == (W, H) else cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
        det.setInputSize((w, h)); _, res = det.detect(x)
        for r in (res if res is not None else []):
            x0, y0 = max(0.0, float(r[0]) / w), max(0.0, float(r[1]) / h)
            x1, y1 = min(1.0, (float(r[0]) + float(r[2])) / w), min(1.0, (float(r[1]) + float(r[3])) / h)
            if x1 > x0 and y1 > y0: found.append({"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "c": float(r[-1])})
    keep = []
    for b in sorted(found, key=lambda q: -q["c"]):
        def clash(q):
            iw = max(0.0, min(b["x"] + b["w"], q["x"] + q["w"]) - max(b["x"], q["x"])); ih = max(0.0, min(b["y"] + b["h"], q["y"] + q["h"]) - max(b["y"], q["y"]))
            i = iw * ih; ab, aq = b["w"] * b["h"], q["w"] * q["h"]
            return i / (ab + aq - i) > 0.3 or i / min(ab, aq) > 0.6
        if not any(clash(q) for q in keep): keep.append(b)
    # YuNet's box runs from the hairline; Vision's (which every threshold here was set on) from the brows: on matched faces
    # Vision's top sits 0.18 of YuNet's height lower and its height is 0.78 of it (x and width agree within noise)
    return [dict(b, y=b["y"] + YUNET_TOP * b["h"], h=YUNET_H * b["h"]) for b in keep]


# ------------------------------------------------------------------ people
def people(img, engine=None, upper_body=False):
    """Person boxes [{"x","y","w","h","c"}]; callers keep c ≥ numbers.json peopleMinConf. upper_body (Vision only: its own
    default, what the video map counted) finds people cut off at the waist; False = whole bodies (people_zones' crop)."""
    e = engine or choose("people")
    if e == "vision": return vision_detect(img, people=True, upper_body=upper_body)["people"]
    if e == "rtdetr": return _rtdetr(img)
    if e == "yolo": return _yolo(img)
    raise ValueError(f"people engine {e}")

def _rtdetr(img, floor=0.25):
    import torch
    from transformers import AutoImageProcessor, AutoModelForObjectDetection
    def load():
        dev = device(); proc = AutoImageProcessor.from_pretrained(RTDETR[0], revision=RTDETR[1])
        return proc, AutoModelForObjectDetection.from_pretrained(RTDETR[0], revision=RTDETR[1]).eval().to(dev), dev
    proc, model, dev = _model("rtdetr", load, hf=True)
    im = pil(img); w, h = im.size
    with torch.no_grad():
        out = model(**{k: v.to(dev) for k, v in proc(images=im, return_tensors="pt").items()})
    r = proc.post_process_object_detection(out, threshold=floor, target_sizes=[(h, w)])[0]
    person = next((int(k) for k, v in model.config.id2label.items() if v == "person"), 0)
    res = []
    for s, l, b in zip(r["scores"].tolist(), r["labels"].tolist(), r["boxes"].tolist()):
        if l != person: continue
        x0, y0, x1, y1 = max(0, b[0]), max(0, b[1]), min(w, b[2]), min(h, b[3])
        if x1 > x0 and y1 > y0: res.append({"x": x0 / w, "y": y0 / h, "w": (x1 - x0) / w, "h": (y1 - y0) / h, "c": float(s)})
    return sorted(res, key=lambda q: -q["c"])

def _yolo(img, floor=0.25):
    _say(YOLO_NOTE)
    from ultralytics import YOLO
    model = _model("yolo", lambda: YOLO(os.environ.get("REEL_STUDIO_YOLO_MODEL", "yolo11n.pt")))
    im = pil(img); w, h = im.size
    r = model(im, verbose=False, conf=floor, classes=[0])[0]
    return [{"x": b[0] / w, "y": b[1] / h, "w": (b[2] - b[0]) / w, "h": (b[3] - b[1]) / h, "c": float(c)}
            for b, c in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist())]


# ------------------------------------------------------------------ hands
def hands(img, engine=None, max_hands=6):
    """Hand boxes [(x0, y0, x1, y1)] (0–1, top-left) from the joints seen with confidence > 0.3 (Vision; at least 4 joints)."""
    e = engine or choose("hands")
    if e == "vision": return vision_detect(img, hands=True, max_hands=max_hands)["hands"]
    if e == "mediapipe": return _mediapipe_hands(img, max_hands)
    if e == "none": _say("hands engine none: hand-based censor boxes are skipped (follow keys / box jobs still work)"); return []
    raise ValueError(f"hands engine {e}")

def _mediapipe_hands(img, max_hands):
    _quiet(False)   # before the import: MediaPipe reads its log level from the environment once
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision as mpv
    det = _model(("mp_hands", max_hands), lambda: mpv.HandLandmarker.create_from_options(mpv.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=_fetch("hand_landmarker.task")), num_hands=max_hands,
        min_hand_detection_confidence=0.3, min_hand_presence_confidence=0.3)))
    res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb(img)))
    out = []
    for lm in res.hand_landmarks or []:
        xs = [min(1.0, max(0.0, p.x)) for p in lm]; ys = [min(1.0, max(0.0, p.y)) for p in lm]
        if len(xs) >= 4: out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


# ------------------------------------------------------------------ text
def ocr(img, langs=("ru", "en"), engine=None, min_conf=0.4):
    """Lines of text [{"text","x","y","w","h","c"}] with confidence ≥ min_conf (0–1, top-left box of the line)."""
    e = engine or choose("ocr")
    if e == "vision": return vision_detect(img, ocr=True, langs=langs, ocr_min_conf=min_conf)["ocr"]
    if e == "rapidocr": return _rapidocr(img, langs, min_conf)
    raise ValueError(f"ocr engine {e}")

def _rapidocr(img, langs, min_conf):
    """RapidOCR (PP-OCRv4 detector shipped with rapidocr-onnxruntime); the recogniser: PP-OCRv5 East Slavic (Cyrillic + Latin)
    when ru / uk / be / bg is asked, else the package's own Chinese + English one."""
    from rapidocr_onnxruntime import RapidOCR
    cyr = bool({"ru", "uk", "be", "bg"} & set(langs))
    def load():
        kw = {"rec_model_path": _fetch("ocr_eslav_rec.onnx"), "rec_keys_path": _fetch("ocr_eslav_dict.txt")} if cyr else {}
        if nvidia() and importlib.util.find_spec("onnxruntime") and "CUDAExecutionProvider" in __import__("onnxruntime").get_available_providers():
            kw.update(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)
        return RapidOCR(**kw)
    eng = _model(("rapidocr", cyr), load)
    a = rgb(img); h, w = a.shape[:2]
    res, _ = eng(a[..., ::-1].copy())   # RapidOCR takes BGR arrays (cv2 order)
    out = []
    for box, text, conf in res or []:
        conf = float(conf); text = str(text).strip()
        if conf < min_conf or not text: continue
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        x0, y0, x1, y1 = max(0, min(xs)), max(0, min(ys)), min(w, max(xs)), min(h, max(ys))
        out.append({"text": text, "x": x0 / w, "y": y0 / h, "w": (x1 - x0) / w, "h": (y1 - y0) / h, "c": conf})
    return out


# ------------------------------------------------------------------ feature print
SCENE_THRESHOLD = {"vision": 0.95, "dinov2": 0.25}   # vision: Euclidean; dinov2: cosine distance — calibrate with video-library's vm_frames.py --calib

def feature_print(img, engine=None):
    """(engine, vector) — a print to compare frames by; never compare prints of different engines."""
    e = engine or choose("feature_print")
    if e == "vision":
        import Vision
        r = Vision.VNGenerateImageFeaturePrintRequest.alloc().init()
        if vision_run(img, [r], url=True) is None or not r.results(): return e, None
        o = r.results()[0]
        # pyobjc does not return computeDistance's out-parameter: the distance is the Euclidean one between the raw vectors
        import numpy as np
        dt = np.float32 if o.elementType() == 1 else np.float64
        return e, np.frombuffer(bytes(o.data()), dtype=dt).astype(np.float32).tolist()
    if e == "dinov2":
        import torch
        from transformers import AutoImageProcessor, AutoModel
        def load():
            dev = device()
            return AutoImageProcessor.from_pretrained(DINOV2[0], revision=DINOV2[1]), AutoModel.from_pretrained(DINOV2[0], revision=DINOV2[1]).eval().to(dev), dev
        proc, model, dev = _model("dinov2", load, hf=True)
        with torch.no_grad():
            v = model(**{k: t.to(dev) for k, t in proc(images=pil(img), return_tensors="pt").items()}).last_hidden_state[0, 0].float()
        return e, torch.nn.functional.normalize(v, dim=0).cpu().tolist()
    raise ValueError(f"feature_print engine {e}")

def distance(a, b, engine_name):
    """Distance between two prints of the SAME engine: vision Euclidean, dinov2 cosine (1 − dot of unit vectors)."""
    if a is None or b is None: return 0.0
    import numpy as np
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    if engine_name == "vision": return float(np.linalg.norm(a - b))
    return float(1.0 - np.dot(a, b) / max(1e-12, float(np.linalg.norm(a) * np.linalg.norm(b))))

def scene_threshold(engine_name):
    return SCENE_THRESHOLD[engine_name]


# ------------------------------------------------------------------ labels
# SigLIP 2 zero-shot over engines_labels.txt (Vision's own identifiers, so both engines speak one vocabulary). Its sigmoid
# scores are small for a true label (0.01–0.3), so they are mapped onto Vision's scale before min_conf:
# conf = sigmoid(SIGLIP_K * (logit − SIGLIP_AT)): min_conf 0.3 then keeps ≈ 6 labels a frame, as many as Vision gives (50 camera frames).
SIGLIP_AT, SIGLIP_K = -5.3, 1.2

def labels(img, min_conf=0.3, top=10, engine=None):
    """[[identifier, conf]] best first, conf ≥ min_conf, at most `top`."""
    e = engine or choose("labels")
    if e == "vision":
        import Vision
        r = Vision.VNClassifyImageRequest.alloc().init()
        if vision_run(img, [r], url=True) is None: return []
        return [[str(o.identifier()), float(o.confidence())] for o in (r.results() or []) if o.confidence() >= min_conf][:top]
    if e == "siglip":
        import torch
        ids, txt, model, proc, dev = _siglip()
        with torch.no_grad():
            f = model.get_image_features(**{k: v.to(dev) for k, v in proc(images=[pil(img)], return_tensors="pt").items()})
            f = getattr(f, "pooler_output", f)
            f = torch.nn.functional.normalize(f.float(), dim=-1)
            logit = (f @ txt.T)[0] * model.logit_scale.exp().float() + model.logit_bias.float()
            conf = torch.sigmoid(SIGLIP_K * (logit - SIGLIP_AT)).cpu().tolist()
        best = sorted(range(len(ids)), key=lambda i: -conf[i])
        return [[ids[i], conf[i]] for i in best if conf[i] >= min_conf][:top]
    raise ValueError(f"labels engine {e}")

def label_vocabulary():
    return [l.strip() for l in open(LABELS_FILE, encoding="utf-8") if l.strip() and not l.startswith("#")]

def _siglip():
    def load():
        import numpy as np, torch
        from transformers import AutoModel, AutoProcessor
        dev = device(); proc = AutoProcessor.from_pretrained(SIGLIP[0], revision=SIGLIP[1])
        model = AutoModel.from_pretrained(SIGLIP[0], revision=SIGLIP[1]).eval().to(dev)
        ids = label_vocabulary(); key = hashlib.sha1(("\n".join(ids) + SIGLIP[1]).encode()).hexdigest()[:12]
        cp = os.path.join(MODELS, f"siglip_labels_{key}.npy")   # the text side of the vocabulary, computed once
        if os.path.exists(cp): txt = torch.from_numpy(np.load(cp)).to(dev)
        else:
            chunks = []
            with torch.no_grad():
                for i in range(0, len(ids), 64):
                    prompts = [f"a photo of {x.replace('_', ' ')}." for x in ids[i:i + 64]]
                    t = proc(text=prompts, padding="max_length", max_length=64, return_tensors="pt")
                    o = model.get_text_features(**{k: v.to(dev) for k, v in t.items()})
                    chunks.append(torch.nn.functional.normalize(getattr(o, "pooler_output", o).float(), dim=-1))
            txt = torch.cat(chunks)
            os.makedirs(MODELS, exist_ok=True); np.save(cp, txt.cpu().numpy())
        return ids, txt, model, proc, dev
    return _model("siglip", load, hf=True)


# ------------------------------------------------------------------ aesthetics
def aesthetics(img, engine=None):
    """{"aesthetic": overall score −1…1 | None, "utility": a document / screenshot rather than a memorable photo | None}."""
    e = engine or choose("aesthetics")
    if e == "vision":
        import Vision
        if not hasattr(Vision, "VNCalculateImageAestheticsScoresRequest"): return {"aesthetic": None, "utility": None}   # macOS 15+
        r = Vision.VNCalculateImageAestheticsScoresRequest.alloc().init()
        if vision_run(img, [r], url=True) is None or not r.results(): return {"aesthetic": None, "utility": None}
        o = r.results()[0]; return {"aesthetic": float(o.overallScore()), "utility": bool(o.isUtility())}
    if e == "none": return {"aesthetic": None, "utility": None}
    raise ValueError(f"aesthetics engine {e}")


# ------------------------------------------------------------------ person mask / cutout
def _pb_array(pb):
    """CVPixelBuffer (8-bit or float32 one-component) → float32 [0,1] array."""
    import numpy as np, Quartz
    Quartz.CVPixelBufferLockBaseAddress(pb, 1)
    try:
        w, h = Quartz.CVPixelBufferGetWidth(pb), Quartz.CVPixelBufferGetHeight(pb); bpr = Quartz.CVPixelBufferGetBytesPerRow(pb)
        raw = bytes(Quartz.CVPixelBufferGetBaseAddress(pb).as_buffer(bpr * h))
    finally: Quartz.CVPixelBufferUnlockBaseAddress(pb, 1)
    if Quartz.CVPixelBufferGetPixelFormatType(pb) == 0x4C303066:  # 'L00f'
        return np.frombuffer(raw, np.uint8).reshape(h, bpr)[:, :w * 4].copy().view(np.float32).reshape(h, w).clip(0, 1)
    return np.frombuffer(raw, np.uint8).reshape(h, bpr)[:, :w].astype(np.float32) / 255.0

def vision_mask(img, kind="person", quality="accurate"):
    """Apple Vision mask at the model's own size (None = nobody / no subject): kind person = person segmentation (low-res,
    people only), subject = foreground instance mask (macOS 14+)."""
    import Vision
    cg = _cg(img)
    if cg is None: return None
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    if kind == "person":
        req = Vision.VNGeneratePersonSegmentationRequest.alloc().initWithCompletionHandler_(None)
        req.setQualityLevel_(Vision.VNGeneratePersonSegmentationRequestQualityLevelAccurate if quality == "accurate"
                             else Vision.VNGeneratePersonSegmentationRequestQualityLevelBalanced)
        ok, err = handler.performRequests_error_([req], None)
        if not ok: sys.exit(f"vision failed: {err}")
        res = req.results()
        return _pb_array(res[0].pixelBuffer()) if res else None
    req = Vision.VNGenerateForegroundInstanceMaskRequest.alloc().init()
    ok, err = handler.performRequests_error_([req], None)
    if not ok: sys.exit(f"vision failed: {err}")
    res = req.results()
    if not res or len(res[0].allInstances()) == 0: return None
    pb, err = res[0].generateScaledMaskForImageForInstances_fromRequestHandler_error_(res[0].allInstances(), handler, None)
    return _pb_array(pb) if pb is not None else None

def birefnet_model():
    """(model, device, dtype) — BiRefNet at the pinned revision, fp16 on MPS / CUDA."""
    def load():
        import torch
        from transformers import AutoModelForImageSegmentation
        dev = device(); dtype = torch.float16 if dev != "cpu" else torch.float32
        m = AutoModelForImageSegmentation.from_pretrained(BIREFNET[0], revision=BIREFNET[1], trust_remote_code=True).eval().to(dev).to(dtype)
        return m, dev, dtype
    return _model("birefnet", load, hf=True)

BIREFNET_SIDE = 1024
def birefnet(img):
    """RGB HxWx3 → alpha HxW float32 0–1; the model runs at 1024² (BiRefNet's training size)."""
    import numpy as np, torch
    model, dev, dtype = birefnet_model(); a = rgb(img); h, w = a.shape[:2]
    mean = torch.tensor([0.485, 0.456, 0.406], device=dev).view(1, 3, 1, 1); std = torch.tensor([0.229, 0.224, 0.225], device=dev).view(1, 3, 1, 1)
    x = torch.from_numpy(np.array(a)).to(dev).permute(2, 0, 1)[None].float() / 255
    x = torch.nn.functional.interpolate(x, (BIREFNET_SIDE, BIREFNET_SIDE), mode="bilinear", align_corners=False, antialias=True)
    with torch.no_grad():
        p = model(((x - mean) / std).to(dtype))[-1].float().sigmoid()
    return torch.nn.functional.interpolate(p, (h, w), mode="bilinear", align_corners=False)[0, 0].clamp(0, 1).cpu().numpy()

def person_mask(img, engine=None, quality="accurate"):
    """Person alpha, HxW float32 0–1 at the image's size (zeros when nobody is found)."""
    import numpy as np
    e = engine or choose("person_mask"); w, h = _size(img)
    if e == "vision":
        m = vision_mask(img, "person", quality)
        return np.zeros((h, w), np.float32) if m is None else resize(m, w, h).astype(np.float32)
    if e == "birefnet": return birefnet(img).astype(np.float32)
    raise ValueError(f"person_mask engine {e}")

def cutout(src_path, dst_png, engine=None, crop=False):
    """The main subject(s) of an image → RGBA PNG. Returns (width, height, note)."""
    e = engine or choose("cutout")
    if e == "vision":
        import Vision, Quartz
        from Foundation import NSURL
        img = _cg(os.path.abspath(src_path))
        if img is None: sys.exit(f"cannot read {src_path}")
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
        req = Vision.VNGenerateForegroundInstanceMaskRequest.alloc().init()
        ok, err = handler.performRequests_error_([req], None)
        if not ok or not req.results(): sys.exit(f"no subject found in {src_path}: {err}")
        obs = req.results()[0]
        buf, err = obs.generateMaskedImageOfInstances_fromRequestHandler_croppedToInstancesExtent_error_(obs.allInstances(), handler, crop, None)
        if buf is None: sys.exit(f"mask failed: {err}")
        ci = Quartz.CIImage.imageWithCVPixelBuffer_(buf); ctx = Quartz.CIContext.contextWithOptions_(None)
        cs = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
        ok, err = ctx.writePNGRepresentationOfImage_toURL_format_colorSpace_options_error_(ci, NSURL.fileURLWithPath_(os.path.abspath(dst_png)), Quartz.kCIFormatRGBA8, cs, {}, None)
        if not ok: sys.exit(f"write failed: {err}")
        ex = ci.extent(); return int(ex.size.width), int(ex.size.height), f"instances={len(obs.allInstances())}"
    if e == "birefnet":
        import numpy as np
        from PIL import Image
        a = rgb(src_path); alpha = birefnet(a)
        if (alpha > 0.5).mean() < 0.002: sys.exit(f"no subject found in {src_path}")
        rgba = np.dstack([a, (alpha * 255 + .5).astype(np.uint8)])
        if crop:
            ys, xs = np.where((alpha > 0.5).any(1))[0], np.where((alpha > 0.5).any(0))[0]; rgba = rgba[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]
        Image.fromarray(rgba, "RGBA").save(dst_png); return rgba.shape[1], rgba.shape[0], f"coverage={float((alpha > 0.5).mean()):.2f}"
    raise ValueError(f"cutout engine {e}")


# ------------------------------------------------------------------ sound events
SOUND_SWIFT = r'''// Sounds in an audio file (Apple SoundAnalysis, built-in classifier, 303 classes) → JSON on stdout:
// [{"s": start, "e": end, "top": [["speech", 0.71], ...]}, ...] — windows of argv[2] s (default 3), no overlap.
import Foundation
import SoundAnalysis
import AVFoundation
final class Obs: NSObject, SNResultsObserving {
    var rows: [[String: Any]] = []
    func request(_ request: SNRequest, didProduce result: SNResult) {
        guard let r = result as? SNClassificationResult else { return }
        let top = r.classifications.prefix(4).filter { $0.confidence > 0.2 }.map { [$0.identifier, (Double($0.confidence) * 100).rounded() / 100] as [Any] }
        rows.append(["s": (r.timeRange.start.seconds * 10).rounded() / 10, "e": ((r.timeRange.start.seconds + r.timeRange.duration.seconds) * 10).rounded() / 10, "top": top])
    }
}
let win = CommandLine.arguments.count > 2 ? (Double(CommandLine.arguments[2]) ?? 3.0) : 3.0
let analyzer = try SNAudioFileAnalyzer(url: URL(fileURLWithPath: CommandLine.arguments[1]))
let req = try SNClassifySoundRequest(classifierIdentifier: .version1)
req.windowDuration = CMTime(seconds: win, preferredTimescale: 48000)
req.overlapFactor = 0.0
let obs = Obs()
try analyzer.add(req, withObserver: obs)
analyzer.analyze()
let data = try JSONSerialization.data(withJSONObject: obs.rows)
FileHandle.standardOutput.write(data)
'''

def _sound_bin():
    return os.path.join(CACHE, "bin", "sound_events_" + hashlib.sha1(SOUND_SWIFT.encode()).hexdigest()[:10])

def snake(label):
    """AudioSet display name → Apple-style identifier: «Wind noise (microphone)» → wind_noise_microphone."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")

def sound_events(wav, win=3.0, engine=None):
    """[{"s", "e", "top": [[label, conf]]}] per `win`-second window, no overlap; ≤ 4 labels with conf > 0.2, snake_case."""
    e = engine or choose("sound_events")
    if e == "soundanalysis":
        b = _sound_bin()
        if not os.path.exists(b):
            os.makedirs(os.path.dirname(b), exist_ok=True); src = b + ".swift"; open(src, "w").write(SOUND_SWIFT)
            r = subprocess.run(["xcrun", "swiftc", "-O", src, "-o", b + ".part"], capture_output=True, text=True)
            if r.returncode: sys.exit(f"engines: swiftc failed: {r.stderr.strip()[-300:]}")
            os.replace(b + ".part", b)
        r = subprocess.run([b, os.path.abspath(wav), str(win)], capture_output=True)
        return json.loads(r.stdout or b"[]")
    if e == "ast": return _ast(wav, win)
    raise ValueError(f"sound_events engine {e}")

def _pcm16k(path, sr=16000):
    """Mono float32 samples at 16 kHz, decoded by ffmpeg."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True)
    if r.returncode: sys.exit(f"engines: ffmpeg cannot read {path}: {r.stderr.decode(errors='replace')[-200:]}")
    return np.frombuffer(r.stdout, np.float32)

def _ast(wav, win, batch=8):
    import numpy as np, torch
    from transformers import ASTFeatureExtractor, ASTForAudioClassification
    def load():
        dev = device()
        return ASTFeatureExtractor.from_pretrained(AST[0], revision=AST[1]), ASTForAudioClassification.from_pretrained(AST[0], revision=AST[1]).eval().to(dev), dev
    fe, model, dev = _model("ast", load, hf=True)
    sr = 16000; x = _pcm16k(wav, sr); n = int(win * sr)
    starts = list(range(0, max(0, len(x) - n) + 1, n)) if len(x) >= n else []
    if len(x) - (starts[-1] + n if starts else 0) >= n / 2: starts.append(starts[-1] + n if starts else 0)   # a last window over half full
    names = [snake(model.config.id2label[i]) for i in range(len(model.config.id2label))]; rows = []
    for i in range(0, len(starts), batch):
        chunk = [x[s:s + n] for s in starts[i:i + batch]]
        feats = fe(chunk, sampling_rate=sr, return_tensors="pt")
        with torch.no_grad():
            p = torch.sigmoid(model(**{k: v.to(dev) for k, v in feats.items()}).logits).cpu().numpy()
        for s, pr in zip(starts[i:i + batch], p):
            top = [[names[j], round(float(pr[j]), 2)] for j in np.argsort(-pr)[:4] if pr[j] > 0.2]
            rows.append({"s": round(s / sr, 1), "e": round(min(len(x), s + n) / sr, 1), "top": top})
    return rows


# ------------------------------------------------------------------ whisper
def whisper_name(model):
    """A model id in any spelling → the bare name (mlx-community/whisper-large-v3-turbo → large-v3-turbo)."""
    return model.rsplit("/", 1)[-1].removeprefix("whisper-")

def transcribe(wav, lang, model="mlx-community/whisper-large-v3-turbo", engine=None):
    """Whisper with word timestamps → the openai-whisper dict {text, segments:[{start, end, text, words:[{word, start, end,
    probability}]}], language} whatever the engine."""
    e = engine or choose("whisper")
    if e == "mlx":
        import mlx_whisper
        repo = model if "/" in model else f"mlx-community/whisper-{model}"
        return mlx_whisper.transcribe(wav, path_or_hf_repo=repo, language=lang, word_timestamps=True, verbose=False)
    if e == "openai":
        import whisper as ow
        m = _model(("openai", whisper_name(model)), lambda: ow.load_model(whisper_name(model)))
        return m.transcribe(wav, language=lang, word_timestamps=True, verbose=False)
    if e == "faster":
        from faster_whisper import WhisperModel
        def load():
            cuda = False
            try:
                import ctranslate2; cuda = ctranslate2.get_cuda_device_count() > 0
            except Exception: pass
            return WhisperModel(whisper_name(model), device="cuda" if cuda else "cpu", compute_type="float16" if cuda else "int8")
        m = _model(("faster", whisper_name(model)), load)
        segs, info = m.transcribe(_pcm16k(wav), language=lang, word_timestamps=True, vad_filter=False)   # decoded by ffmpeg: no PyAV pinning
        out = []
        for i, s in enumerate(segs):
            out.append({"id": i, "start": s.start, "end": s.end, "text": s.text,
                        "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability} for w in (s.words or [])]})
        return {"text": "".join(s["text"] for s in out), "segments": out, "language": info.language}
    raise ValueError(f"whisper engine {e}")


# ------------------------------------------------------------------ decode
def hwaccel(engine=None):
    """ffmpeg input args for hardware decode: ["-hwaccel", "videotoolbox" | "cuda"] or [] (software)."""
    try: e = engine or choose("decode")
    except SystemExit: e = "none"
    return [] if e == "none" or missing("decode", e) else ["-hwaccel", e]


# ------------------------------------------------------------------ CLI
def report():
    """[{cap, engine, why, available, missing, fix}] — the table as data (deps.py reads it with --json)."""
    rows = []
    for cap in ENGINES:
        try: name, why = choose_why(cap)
        except SystemExit as ex: rows.append({"cap": cap, "engine": None, "why": "error", "available": available(cap), "missing": str(ex), "fix": ""}); continue
        miss = missing(cap, name)
        rows.append({"cap": cap, "engine": name, "why": why, "available": available(cap), "missing": miss, "fix": FIX.get(name, "") if miss else ""})
    return rows

def table():
    print(f"python: {sys.executable}" + ("" if _has(("numpy",)) else "  (no numpy here: run it with ~/.cache/reel-studio/venv/bin/python)"))
    print(f"platform: {platform.system()} {platform.machine()}" + (" · Apple Silicon" if apple_silicon() else "") + (" · NVIDIA GPU" if nvidia() else ""))
    print(f"{'capability':<14}{'chosen':<15}{'from':<9}{'runs here':<34}note")
    for cap in ENGINES:
        try: name, why = choose_why(cap)
        except SystemExit as ex: print(f"{cap:<14}{'?':<15}{'error':<9}{'':<34}{ex}"); continue
        av = available(cap); miss = missing(cap, name)
        note = (f"CANNOT RUN: {miss} — {FIX.get(name, '')}" if miss else WHAT[cap]) + (" · AGPL-3.0" if name == "yolo" else "")
        print(f"{cap:<14}{name:<15}{why:<9}{', '.join(av) or '—':<34}{note}")
    vm = vlm_model()
    if vm: print(f"vlm model: {vm} (env REEL_STUDIO_VLM_MODEL / engines.py set-model vlm; default: the engine's own)")
    print("choose: engines.py set <cap> <engine|default> · env REEL_STUDIO_ENGINE_<CAP>=<engine> · a script's --engine (references/engines.md)")

def _save_mask(m, path):
    from PIL import Image
    Image.fromarray((m * 255 + .5).astype("uint8"), "L").save(path)

def _reexec_in_venv():
    """A bare system python (not inside any venv) answers for the skill's venv: re-run there once."""
    if sys.prefix != sys.base_prefix or os.environ.get("REEL_STUDIO_ENGINES_REEXEC") or not os.path.exists(VENV_PY): return
    sys.stdout.flush(); os.execve(VENV_PY, [VENV_PY, "-I", os.path.abspath(__file__), *sys.argv[1:]], {**os.environ, "REEL_STUDIO_ENGINES_REEXEC": "1"})

def main(argv):
    import argparse
    if argv[:1] == ["set"]:
        if len(argv) != 3: sys.exit("usage: engines.py set <cap> <engine|default>")
        set_engine(argv[1], argv[2]); print(f"ENGINE_SET {argv[1]} {choose(argv[1])}"); return
    if argv[:1] == ["set-model"]:
        if len(argv) != 3 or argv[1] != "vlm": sys.exit("usage: engines.py set-model vlm <folder|.gguf|hf-id|default>")
        set_vlm_model(argv[2]); print(f"MODEL_SET vlm {vlm_model() or 'default'}"); return
    _reexec_in_venv()
    if not argv: table(); return
    if argv == ["--json"]: print(json.dumps(report(), ensure_ascii=False)); return
    ap = argparse.ArgumentParser(description="Run one capability on a file and print JSON (see the module doc).")
    ap.add_argument("cap", choices=["faces", "people", "hands", "ocr", "labels", "feature_print", "aesthetics", "sound_events", "person_mask",
                                    "cutout", "whisper", "decode"])
    ap.add_argument("file", nargs="?"); ap.add_argument("dst", nargs="?", help="cutout: the output PNG")
    ap.add_argument("--engine"); ap.add_argument("--lang", default=None, help="ocr: ru,en (default); whisper: the language code")
    ap.add_argument("--min-conf", type=float, default=None); ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--win", type=float, default=3.0); ap.add_argument("--crop", action="store_true"); ap.add_argument("--out")
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo", help="whisper model")
    a = ap.parse_args(argv)
    if a.cap == "decode": print(json.dumps({"engine": choose("decode", a.engine), "args": hwaccel(a.engine), "ffmpeg_hwaccels": hwaccels()})); return
    if not a.file or not os.path.exists(a.file): sys.exit(f"engines.py {a.cap}: no such file {a.file!r}")
    e = require(a.cap, f"engines.py {a.cap}", a.engine)
    if a.cap == "faces": r = faces(a.file, e)
    elif a.cap == "people": r = people(a.file, e)
    elif a.cap == "hands": r = [list(h) for h in hands(a.file, e)]
    elif a.cap == "ocr": r = ocr(a.file, tuple((a.lang or "ru,en").split(",")), e, **({"min_conf": a.min_conf} if a.min_conf is not None else {}))
    elif a.cap == "labels": r = labels(a.file, 0.3 if a.min_conf is None else a.min_conf, a.top, e)
    elif a.cap == "feature_print":
        name, v = feature_print(a.file, e); r = {"engine": name, "dim": len(v or []), "threshold": scene_threshold(name), "vector": v}
    elif a.cap == "aesthetics": r = aesthetics(a.file, e)
    elif a.cap == "sound_events": r = sound_events(a.file, a.win, e)
    elif a.cap == "person_mask":
        m = person_mask(a.file, e); r = {"engine": e, "w": m.shape[1], "h": m.shape[0], "coverage": round(float((m > 0.5).mean()), 4)}
        if a.out: _save_mask(m, a.out); r["out"] = a.out
    elif a.cap == "cutout":
        if not a.dst: sys.exit("engines.py cutout <in> <out.png> [--crop]")
        w, h, note = cutout(a.file, a.dst, e, a.crop); r = {"engine": e, "out": a.dst, "w": w, "h": h, "note": note}
    else:
        if not a.lang: sys.exit("engines.py whisper <wav> --lang <code>")
        r = transcribe(a.file, a.lang, a.model, e)
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
