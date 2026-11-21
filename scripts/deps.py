#!/usr/bin/env python3
"""Check — and with --install, install — everything the skill needs, for the OS it runs on. Standard library only: it runs
before any venv exists, on a bare machine. setup_env.sh calls it first; on Linux run it yourself first (zsh may be missing).

Usage: python3 -I deps.py [--install] [--dry-run] [--with covers] [--with sound] [--with linux-vision] [--with fast-asr]
  (no flag)   report: platform, every tool / library / python env with its version, what is missing and the command that fixes
              it, and which parts of the skill this platform cannot run
  --install   install what is missing: system packages (brew / apt / dnf / pacman), uv, then the shared python envs in
              ~/.cache/reel-studio (venv, dfvenv, gigvenv, vlmvenv on Apple Silicon). Root-only commands run through sudo only when it needs no
              password (sudo -n); otherwise they are printed for the user to run, and the check stays MISSING
  --dry-run   with --install: print the commands, run nothing
  --with covers  also the Codex CLI for generated cover plates (ask the user first: it needs their ChatGPT login)
  --with sound   also earshot (ask the user first: ≈ 1.6 GB with its two listening models, CPU only): designed sound effects
              instead of the synthesized ones (make_sfx.sh → sfx_bank.py), ranking of real sounds found on Openverse
              (sfx_find.py), a listening check of the render (ears.py), moments found by sound (earshot find)
  --with linux-vision  the open picture engines into the venv (engines.py; always part of the install on Linux — no flag
              needed there; optional on macOS): OpenCV
              (YuNet faces), RapidOCR + onnxruntime (onnxruntime-gpu with an NVIDIA GPU), MediaPipe hands when a wheel exists
              for this platform, transformers + timm when missing (RT-DETR people, DINOv2, SigLIP 2, AST sounds, BiRefNet)
  --with fast-asr      faster-whisper into the venv: Whisper on the CPU (int8) or CUDA (fp16), several times faster than openai-whisper
The report ends with the engines table (engines.py): per capability the chosen engine and the engines that run here.
Speech: GigaAM v3 for Russian (gigvenv), Whisper for every other language (venv).
Prints DEPS_OK (the pipeline can run here) or DEPS_MISSING <n> (exit 1).

Platforms (picture and sound models: one engine per capability, engines.py; references/engines.md)
  macOS, Apple Silicon   everything; Apple Vision / SoundAnalysis / MLX by default, the open engines with --with linux-vision
  macOS, Intel           no MLX: Whisper runs as openai-whisper (CPU, slower), frame descriptions through transformers
  Linux (and WSL2)       CPU, optionally NVIDIA CUDA: YuNet faces, RT-DETR people, MediaPipe hands, RapidOCR, DINOv2 prints, SigLIP 2
                         labels, BiRefNet masks and cut-outs, AST sounds (linux-vision, installed by default); Whisper as faster-whisper (--with
                         fast-asr) or openai-whisper; no aesthetic score; hardware decode only with NVIDIA (cuda), else software
  Speech recognition     Russian: GigaAM v3 (gigvenv, onnxruntime on the CPU, every platform); other languages: Whisper (venv)
  Windows                not native (zsh scripts, POSIX paths): install WSL2 + Ubuntu and run the skill inside it
"""
import argparse, json, os, platform, re, shutil, subprocess, sys

CACHE = os.path.expanduser("~/.cache/reel-studio")
NODE_MIN, PY_MIN = 18, (3, 9)
FF_ENCODERS = {"libx264": True, "aac": True, "libvpx-vp9": False}            # True = required; libvpx-vp9 → mattes (title behind the person)
FF_FILTERS = ("lut3d", "minterpolate", "adeclip", "alimiter", "acompressor", "ebur128", "loudnorm", "astats", "atempo", "xfade")
FONTS = ("Unbounded.ttf", "Montserrat.ttf", "JetBrainsMono.ttf")
EARSHOT = "v0.4.1"   # pinned: a skill update moves it after the bank ids in sfx_bank.py were checked against the new version
EARSHOT_SPEC = f"earshot[mcp] @ git+https://github.com/Leonxlnx/earshot@{EARSHOT}"
EARSHOT_HF = os.path.join(os.environ.get("EARSHOT_HOME") or os.path.expanduser("~/.cache/earshot"), "hf")
# Remotion's headless Chrome on Linux: soname → package per manager (apt names get the "t64" suffix on Ubuntu 24.04+)
CHROME_LIBS = {
    "libnss3.so": ("libnss3", "nss", "nss"), "libgbm.so.1": ("libgbm1", "mesa-libgbm", "mesa"),
    "libasound.so.2": ("libasound2", "alsa-lib", "alsa-lib"), "libatk-bridge-2.0.so.0": ("libatk-bridge2.0-0", "at-spi2-atk", "at-spi2-core"),
    "libxkbcommon.so.0": ("libxkbcommon0", "libxkbcommon", "libxkbcommon"), "libcups.so.2": ("libcups2", "cups-libs", "libcups"),
    "libpango-1.0.so.0": ("libpango-1.0-0", "pango", "pango"), "libXcomposite.so.1": ("libxcomposite1", "libXcomposite", "libxcomposite"),
    "libXdamage.so.1": ("libxdamage1", "libXdamage", "libxdamage"), "libXrandr.so.2": ("libxrandr2", "libXrandr", "libxrandr"),
    "libdrm.so.2": ("libdrm2", "libdrm", "libdrm"), "libdbus-1.so.3": ("libdbus-1-3", "dbus-libs", "dbus"),
}
LIB_COL = {"apt": 0, "dnf": 1, "pacman": 2}
PKG = {   # tool → package per manager (None: comes with the OS)
    "zsh": {"brew": None, "apt": "zsh", "dnf": "zsh", "pacman": "zsh"},
    "ffmpeg": {"brew": "ffmpeg", "apt": "ffmpeg", "dnf": "ffmpeg", "pacman": "ffmpeg"},
    "node": {"brew": "node", "apt": "nodejs npm", "dnf": "nodejs npm", "pacman": "nodejs npm"},
    "rsync": {"brew": None, "apt": "rsync", "dnf": "rsync", "pacman": "rsync"},
    "curl": {"brew": None, "apt": "curl ca-certificates", "dnf": "curl", "pacman": "curl"},
    "uv": {"brew": "uv", "pacman": "uv"},                                     # elsewhere: astral's user-level installer
    "heif-convert": {"apt": "libheif-examples", "dnf": "libheif-tools", "pacman": "libheif"},
    "yt-dlp": {"brew": "yt-dlp"},
    "egl": {"apt": "libegl1 libgles2", "dnf": "mesa-libEGL mesa-libGLES", "pacman": "libglvnd"},   # MediaPipe's tasks library dlopens them                                             # brew brings deno (YouTube); distro packages lag behind the sites
}

def run(cmd, **kw):
    try: return subprocess.run(cmd, capture_output=True, text=True, **kw)
    except (OSError, subprocess.TimeoutExpired) as e: return subprocess.CompletedProcess(cmd, 127, "", str(e))

def plat():
    s, m = platform.system(), platform.machine().lower()
    p = {"system": s, "arch": m, "wsl": False, "pm": None, "distro": ""}
    if s == "Darwin":
        # python under Rosetta reports x86_64 on an M-series Mac
        p["apple_silicon"] = m == "arm64" or run(["sysctl", "-n", "sysctl.proc_translated"]).stdout.strip() == "1"
        p["name"] = f"macOS {platform.mac_ver()[0]} " + ("Apple Silicon" if p["apple_silicon"] else "Intel")
        for d in ("/opt/homebrew/bin", "/usr/local/bin"):   # a fresh Homebrew is not on PATH until `brew shellenv` runs in the shell profile
            if os.path.exists(os.path.join(d, "brew")) and d not in os.environ["PATH"].split(os.pathsep): os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
        p["pm"] = "brew" if shutil.which("brew") else None
    elif s == "Linux":
        p["apple_silicon"] = False
        try: p["wsl"] = "microsoft" in open("/proc/version").read().lower()
        except OSError: pass
        try: osr = dict(l.rstrip().split("=", 1) for l in open("/etc/os-release") if "=" in l); p["distro"] = osr.get("PRETTY_NAME", "").strip('"')
        except OSError: pass
        p["pm"] = next((k for k, b in (("apt", "apt-get"), ("dnf", "dnf"), ("pacman", "pacman")) if shutil.which(b)), None)
        p["name"] = f"Linux {p['distro'] or ''} {m}" + (" (WSL2)" if p["wsl"] else "")
    else:
        p["apple_silicon"] = False; p["name"] = f"{s} {m}"
    p["mac"] = s == "Darwin"; p["nvidia"] = bool(shutil.which("nvidia-smi")) and run(["nvidia-smi", "-L"]).returncode == 0
    return p

def venv_specs(p):
    """name → (python version, import check, pip packages, extra index for torch, what it is for). Per platform."""
    cpu_torch = None if (p["mac"] or p["nvidia"]) else "https://download.pytorch.org/whl/cpu"   # Linux without a GPU: CPU wheels (≈ 200 MB, not 2.5 GB)
    # Whisper: speech in languages other than Russian (transcribe.py --lang en …); Russian goes to GigaAM (gigvenv)
    if p["mac"]:
        asr = (["mlx_whisper"], ["mlx-whisper"]) if p["apple_silicon"] else (["whisper"], ["openai-whisper"])
        vis = (["Vision", "Quartz", "Foundation"], ["pyobjc-framework-Vision", "pyobjc-framework-Quartz"])
    else:
        asr, vis = (["whisper"], ["openai-whisper"]), ([], [])
    # person_matte.py --mode birefnet (title behind a person WITH headphones / glasses / props): BiRefNet through transformers
    mat = (["torch", "torchvision", "transformers", "timm", "kornia", "einops"], ["torch", "torchvision", "transformers", "timm", "kornia", "einops"])
    specs = {
        "venv": ("3.12", ["numpy", *asr[0], *vis[0], *mat[0]], ["numpy", *asr[1], *vis[1], *mat[1]], None if p["apple_silicon"] or p["mac"] else cpu_torch,
                 "numpy scripts, Whisper (speech other than Russian), person_matte.py (BiRefNet)" + (", Apple Vision" if p["mac"] else "")),
        "dfvenv": ("3.11", ["df", "torchaudio", "soundfile"], ["deepfilternet", "soundfile", "torch==2.4.1", "torchaudio==2.4.1"], cpu_torch,
                   "voice_clean.py, dualmic.py, dialogue.py"),
    }
    # GigaAM v3 (Russian ASR, ONNX on the CPU) + Silero VAD: Russian speech (transcribe_gigaam.py, transcribe.py --lang ru);
    # the models download from Hugging Face on first use (≈ 1 GB + 2 MB)
    specs["gigvenv"] = ("3.12", ["onnx_asr", "onnxruntime", "soundfile", "huggingface_hub"], ["onnx-asr[hub]", "onnxruntime", "soundfile"], None,
                        "transcribe_gigaam.py / transcribe.py (GigaAM v3 + Silero VAD, Russian)")
    if p["apple_silicon"]:
        # Qwen3-VL-8B 4-bit (optional frame descriptions, vlm_describe.py); the model (≈ 5.4 GB) is fetched by hand, see SKILL.md
        specs["vlmvenv"] = ("3.12", ["mlx_vlm", "PIL"], ["mlx-vlm"], None, "vlm_describe.py (optional: describe frames with Qwen3-VL)")
    return specs

def ver(cmd, rx):
    r = run(cmd, timeout=20); m = re.search(rx, r.stdout + r.stderr)
    return m.group(1) if r.returncode == 0 and m else None

class Report:
    def __init__(s): s.rows, s.fix, s.missing = [], [], 0
    def add(s, ok, name, info="", fix=None, required=True):
        state = "OK" if ok else ("MISSING" if required else "optional")
        if not ok and required: s.missing += 1
        s.rows.append((state, name, info))
        if not ok and fix: s.fix.append(fix)

def apt_name(n):
    """Ubuntu 24.04 renamed some libs to <name>t64 and keeps the old name only as a virtual package."""
    for c in (n + "t64", n):
        out = run(["apt-cache", "policy", c]).stdout
        if "Candidate:" in out and "(none)" not in out: return c
    return n

def earshot_state():
    """(installed version or None, listening models downloaded)."""
    exe = shutil.which("earshot") or (os.path.expanduser("~/.local/bin/earshot") if os.path.exists(os.path.expanduser("~/.local/bin/earshot")) else None)
    v = None
    if exe:
        uvx = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
        m = re.search(r"^earshot v(\S+)", run([uvx, "tool", "list"]).stdout, re.M) if os.path.exists(uvx) or shutil.which("uv") else None
        v = m.group(1) if m else "?"
    size = 0
    for root, _, files in os.walk(EARSHOT_HF):
        size += sum(os.path.getsize(os.path.join(root, f)) for f in files if not os.path.islink(os.path.join(root, f)))
    return v, size > 800 * 2 ** 20


def extra_specs(p):
    """--with extras that go into the shared venv: name → (import check, pip packages, optional packages (may have no wheel), what)."""
    return {
        "linux-vision": (["cv2", "rapidocr_onnxruntime", "onnxruntime", "transformers", "timm"],
                         ["opencv-python-headless", "rapidocr-onnxruntime", "onnxruntime-gpu" if p["nvidia"] else "onnxruntime", "transformers", "timm"],
                         ["mediapipe"], "open picture engines: YuNet faces, RapidOCR, MediaPipe hands (engines.py)"),
        "fast-asr": (["faster_whisper"], ["faster-whisper"], [], "faster-whisper (Whisper on CPU int8 / CUDA fp16)"),
    }

def engine_rows():
    """engines.py --json from the venv python (where the engines live), else from this python."""
    py = os.path.join(CACHE, "venv", "bin", "python")
    r = run([py if os.path.exists(py) else sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "engines.py"), "--json"], timeout=120)
    try: return json.loads(r.stdout)
    except ValueError: return []

def check(p, want_covers=False, want_sound=False, extras=()):
    R, pm = Report(), p["pm"]
    def pkg(tool): return (PKG.get(tool) or {}).get(pm)
    def sys_fix(tool): return ("pkg", tool) if pkg(tool) else None
    # --- system tools
    if not p["mac"] and p["system"] != "Linux":
        R.add(False, "platform", "Windows is not supported natively: `wsl --install -d Ubuntu`, then run the skill inside WSL2")
        return R
    if p["mac"] and not pm: R.add(False, "brew", "Homebrew installs ffmpeg / node / uv", ("manual", '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'))
    if not p["mac"] and not pm: R.add(False, "package manager", "no apt / dnf / pacman — install zsh ffmpeg nodejs npm rsync curl by hand")
    R.add(sys.version_info >= PY_MIN, "python3", platform.python_version(), required=True)
    v = ver(["zsh", "--version"], r"zsh (\S+)"); R.add(bool(v), "zsh", v or "the skill's shell scripts are zsh", sys_fix("zsh"))
    for t in ("curl", "rsync"):
        R.add(bool(shutil.which(t)), t, "", sys_fix(t))
    fv = ver(["ffmpeg", "-hide_banner", "-version"], r"ffmpeg version (\S+)")
    if fv and shutil.which("ffprobe"):
        enc, flt = run(["ffmpeg", "-hide_banner", "-encoders"]).stdout, run(["ffmpeg", "-hide_banner", "-filters"]).stdout
        lack = [f for f in FF_FILTERS if not re.search(rf"^\s*\S+\s+{re.escape(f)}\s", flt, re.M)]
        lack += [e for e, req in FF_ENCODERS.items() if req and not re.search(rf"\s{re.escape(e)}\s", enc)]
        hint = "a full build: brew install ffmpeg / apt ffmpeg / Fedora: ffmpeg from RPM Fusion (ffmpeg-free has no libx264)"
        R.add(not lack, "ffmpeg", fv + (f" — lacks {', '.join(lack)}: {hint}" if lack else ""), ("manual", hint) if lack else None)
        vp9 = bool(re.search(r"\slibvpx-vp9\s", enc))
        R.add(vp9, "ffmpeg libvpx-vp9", "" if vp9 else "person_matte.py (title behind the person) needs it", required=False)
        if p["mac"]:
            hw = "videotoolbox" in run(["ffmpeg", "-hide_banner", "-hwaccels"]).stdout
            R.add(hw, "ffmpeg videotoolbox", "" if hw else "decode falls back to software (slower)", required=False)
    else:
        R.add(False, "ffmpeg + ffprobe", "", sys_fix("ffmpeg"))
    nv = ver(["node", "--version"], r"v(\d+[\d.]*)")
    node_ok = bool(nv) and int(nv.split(".")[0]) >= NODE_MIN and bool(shutil.which("npx"))
    nfix = sys_fix("node") if not nv else ("manual", f"node ≥ {NODE_MIN}: " + ("brew upgrade node" if p["mac"] else
            "curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs" if pm == "apt" else f"install Node.js {NODE_MIN}+ from nodejs.org"))
    R.add(node_ok, "node + npx", (nv or "") + ("" if node_ok or not nv else f" — Remotion needs ≥ {NODE_MIN}"), nfix)
    uvv = ver(["uv", "--version"], r"uv (\S+)") or ver([os.path.expanduser("~/.local/bin/uv"), "--version"], r"uv (\S+)")
    R.add(bool(uvv), "uv", uvv or "builds the python envs", ("pkg", "uv") if pkg("uv") else ("uv", None))
    if p["system"] == "Linux":
        have = run(["ldconfig", "-p"]).stdout if shutil.which("ldconfig") or os.path.exists("/sbin/ldconfig") else ""
        if not have and os.path.exists("/sbin/ldconfig"): have = run(["/sbin/ldconfig", "-p"]).stdout
        miss = [so for so in CHROME_LIBS if so not in have]
        R.add(not miss, "chrome libs", "for Remotion's headless Chrome" + (f" — missing {', '.join(miss)}" if miss else ""), ("libs", miss) if miss else None)
        if "linux-vision" in extras:
            egl = [so for so in ("libEGL.so.1", "libGLESv2.so.2") if so not in have]
            R.add(not egl, "EGL / GLES libs", "MediaPipe hands" + (f" — missing {', '.join(egl)}" if egl else ""), sys_fix("egl") if egl else None, required=False)
        hc = bool(shutil.which("heif-convert") or shutil.which("magick"))
        R.add(hc, "heif-convert", "" if hc else "ingest.py converts iPhone HEIC photos with it", sys_fix("heif-convert"), required=False)
    yv = ver(["yt-dlp", "--version"], r"(\S+)")
    R.add(bool(yv), "yt-dlp", (yv + ("" if shutil.which("deno") else " — no deno: YouTube links fail")) if yv else "fetch.py: a reference reel or a track by link",
          sys_fix("yt-dlp") or ("manual", "uv tool install 'yt-dlp[default]' && curl -fsSL https://deno.land/install.sh | sh   (deno: YouTube)"), required=False)
    # --- python envs (shared, built by --install / setup_env.sh)
    for name, (pyv, mods, pkgs, idx, what) in venv_specs(p).items():
        py = os.path.join(CACHE, name, "bin", "python")
        ok = os.path.exists(py) and run([py, "-I", "-c", "import " + ", ".join(mods)], timeout=120).returncode == 0
        if ok and name == "dfvenv": ok = os.path.exists(os.path.join(CACHE, name, "bin", "deepFilter"))
        R.add(ok, f"env {name}", what, ("venv", name), required=name != "vlmvenv")   # vlmvenv: optional frame descriptions
    vpy = os.path.join(CACHE, "venv", "bin", "python")
    for name, (mods, pkgs, opt, what) in extra_specs(p).items():
        want = name in extras
        ok = os.path.exists(vpy) and run([vpy, "-I", "-c", "import " + ", ".join(mods)], timeout=120).returncode == 0
        if ok and opt:
            have = [m for m in opt if run([vpy, "-I", "-c", f"import {m}"], timeout=120).returncode == 0]
            what += "" if len(have) == len(opt) else f" — without {', '.join(m for m in opt if m not in have)} (no wheel here?)"
        R.add(ok, f"{name} (venv)", what if (ok or want) else f"optional: {what} — --install --with {name}", ("extra", name) if want else None, required=want)
    ev, models = earshot_state()
    es_ok = bool(ev) and ev.lstrip("v") == EARSHOT.lstrip("v") and models
    info = (f"{ev}" + ("" if models else " — listening models not downloaded") + ("" if not ev or ev.lstrip("v") == EARSHOT.lstrip("v") else f" — the skill wants {EARSHOT}")) if ev else \
        "optional: designed SFX, Openverse ranking, a listening check of the render — --install --with sound (≈ 1.6 GB)"
    R.add(es_ok, "earshot (sound)", info, ("sound", None) if want_sound else None, required=want_sound)
    cx = ver(["codex", "--version"], r"(\d+\.\d+[\w.\-]*)")
    R.add(bool(cx), "codex (covers)", cx or "optional: generated cover plates (scripts/codex_image.sh) — --install --with covers, then `codex login`",
          ("covers", None) if want_covers else None, required=want_covers)
    fonts = [f for f in FONTS if not (os.path.exists(fp := os.path.join(CACHE, "fonts", f)) and os.path.getsize(fp))]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import projects_dir; pd = projects_dir.saved()
    R.add(True, "projects folder", pd or "the folder Claude Code is open in (asked before each new project)", required=False)
    R.add(not fonts, "fonts", "template fonts in ~/.cache/reel-studio/fonts" + (" — setup_env.sh downloads them" if fonts else ""), required=False)
    return R

DEGRADED = {   # engine → what is different from the macOS default (references/engines.md has the numbers)
    "yunet": "faces: YuNet — misses more small / turned faces than Vision; boxes mapped onto Vision's geometry",
    "rtdetr": "people: RT-DETR — finds more background people than Vision, slower on a CPU (lower people_zones --fps on long cuts)",
    "none": "{cap}: none — " + "{why}",
    "rapidocr": "ocr: RapidOCR (PP-OCRv5 Cyrillic) — more misreads on stylised captions than Vision",
    "dinov2": "feature_print: DINOv2 — cosine distances, its own scene threshold (calibrate with video-library's vm_frames.py --calib)",
    "siglip": "labels: SigLIP 2 zero-shot over Vision's vocabulary — flat labels (no parent categories like «outdoor»)",
    "ast": "sound_events: AST (AudioSet labels, not SoundAnalysis') — the video map's sound words differ",
    "openai": "whisper: openai-whisper — several times slower than mlx / faster-whisper (--with fast-asr)",
}
NONE_WHY = {"hands": "no hand boxes (MediaPipe not installed, or no wheel for this platform): censor hands jobs are empty, follow keys are not snapped",
            "aesthetics": "no aesthetic score in the video map", "decode": "software decode, proxies take longer"}

def limits(p, rows=None):
    """What runs degraded (or not at all) here, per capability, from the engines table."""
    out = []
    for r in rows if rows is not None else engine_rows():
        e, cap = r.get("engine"), r["cap"]
        if r.get("missing"):
            out.append(f"{cap}: {e} cannot run — {r['missing']}" + (f" ({r['fix']})" if r.get("fix") else "") +
                       (f"; runs here: {', '.join(r['available'])}" if r.get("available") else ""))
        elif e == "none": out.append(f"{cap}: none — {NONE_WHY.get(cap, '')}")
        elif e in DEGRADED and e != "none": out.append(DEGRADED[e])
    return out

def sh(cmd, dry):
    print("  $ " + (cmd if isinstance(cmd, str) else " ".join(cmd)))
    if dry: return True
    r = subprocess.run(cmd, shell=isinstance(cmd, str))
    return r.returncode == 0

def root_prefix(dry):
    """'' as root, 'sudo ' when sudo needs no password, None when the user must run it."""
    if os.geteuid() == 0: return ""
    if shutil.which("sudo") and (dry or run(["sudo", "-n", "true"]).returncode == 0): return "sudo "
    return None

def install(p, R, dry):
    pm, manual = p["pm"], []
    uv = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
    pkgs = []
    for kind, what in R.fix:
        if kind == "pkg": pkgs += PKG[what][pm].split()
        elif kind == "libs" and pm in LIB_COL: pkgs += [CHROME_LIBS[so][LIB_COL[pm]] for so in what]
        elif kind == "manual": manual.append(what)
    if pkgs and pm:
        if pm == "brew": ok = sh(["brew", "install", *dict.fromkeys(pkgs)], dry)
        else:
            pre = root_prefix(dry)
            if pm == "apt" and pre is not None and not dry: run((["sudo", "-n"] if pre else []) + ["apt-get", "update"])
            if pm == "apt": pkgs = [apt_name(x) if x.startswith("lib") and x != "libheif-examples" else x for x in pkgs]
            cmd = {"apt": "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends", "dnf": "dnf install -y",
                   "pacman": "pacman -S --needed --noconfirm"}[pm] + " " + " ".join(dict.fromkeys(pkgs))
            if pre is None:
                upd = "sudo apt-get update && " if pm == "apt" else ""
                manual.append(f"{upd}sudo {cmd}   # needs your password"); ok = False
            else: ok = sh(pre + cmd, dry)
        if not ok and not dry: print("  system packages: install failed")
    if any(k == "covers" for k, _ in R.fix):   # Codex CLI for generated cover plates; the user logs in once (`codex login`)
        npm_pre = "" if p["mac"] or root_prefix(dry) in ("", None) else "sudo "
        if not sh(npm_pre + "npm install -g @openai/codex", dry) and not dry: manual.append("npm install -g @openai/codex")
        manual.append("codex login   # once, with your ChatGPT account")
    if any(k == "sound" for k, _ in R.fix):   # earshot in its own uv tool env (torch CPU), then its two models (≈ 1 GB, Hugging Face)
        if sh([uv, "tool", "install", "--force", EARSHOT_SPEC], dry):
            es = shutil.which("earshot") or os.path.expanduser("~/.local/bin/earshot")
            print("  earshot: downloading the listening models (CLAP + AST, ≈ 1 GB) — a few minutes")
            if not sh([es, "doctor", "--fetch"], dry) and not dry: manual.append(f"{es} doctor --fetch   # the listening models")
        elif not dry: manual.append(f"uv tool install --force '{EARSHOT_SPEC}' && earshot doctor --fetch")
    if any(k == "uv" for k, _ in R.fix):
        sh("curl -LsSf https://astral.sh/uv/install.sh | sh", dry)          # user-level, no sudo (~/.local/bin)
    os.environ["PATH"] = os.pathsep.join([os.path.expanduser("~/.local/bin"), os.path.expanduser("~/.cargo/bin"), os.environ["PATH"]])
    uv = shutil.which("uv") or "uv"
    specs = venv_specs(p)
    for kind, name in R.fix:
        if kind != "venv": continue
        pyv, mods, pkgs_v, idx, what = specs[name]; d = os.path.join(CACHE, name); py = os.path.join(d, "bin", "python")
        print(f"  env {name}: {what}" + (" — torch makes it ≈ 1 GB, a few minutes" if any("torch" in x or "whisper" in x for x in pkgs_v) else ""))
        os.makedirs(CACHE, exist_ok=True)
        if not os.path.exists(py) and not sh([uv, "venv", d, "-p", pyv], dry): continue
        if idx:   # torch from the CPU index first, so openai-whisper / deepfilternet do not pull the CUDA build
            torch = [x for x in pkgs_v if x.startswith(("torch", "torchaudio"))] or ["torch"]
            sh([uv, "pip", "install", "--python", py, "--index-url", idx, *torch], dry)
        sh([uv, "pip", "install", "--python", py, *pkgs_v], dry)
    vpy = os.path.join(CACHE, "venv", "bin", "python")
    for kind, name in R.fix:   # extras go into the venv after it exists
        if kind != "extra": continue
        mods, pkgs_x, opt, what = extra_specs(p)[name]
        if not os.path.exists(vpy) and not dry: manual.append(f"--with {name}: build the venv first (deps.py --install)"); continue
        print(f"  {name}: {what}")
        sh([uv, "pip", "install", "--python", vpy, *pkgs_x], dry)
        for o in opt:   # mediapipe has no wheel for every platform / python: its engine then stays unavailable ("none")
            if not sh([uv, "pip", "install", "--python", vpy, o], dry) and not dry: print(f"  {o}: no wheel for this platform — that engine stays unavailable")
    return manual

def show(p, R):
    print(f"platform: {p['name']}" + (f" · package manager: {p['pm']}" if p["pm"] else "") + (" · NVIDIA GPU" if p["nvidia"] else ""))
    for state, name, info in R.rows: print(f"  {state:<8} {name:<20} {info}")
    rows = engine_rows()
    if rows:
        print("engines (engines.py; change: engines.py set <cap> <engine>):")
        for r in rows: print(f"  {r['cap']:<14} {str(r['engine']):<14} ({r['why']})  runs here: {', '.join(r['available']) or '—'}")
    lim = limits(p, rows)
    if lim: print("degraded or missing here:"); [print("  - " + x) for x in lim]

def main():
    sys.stdout.reconfigure(line_buffering=True)   # keep our lines in order with the installers' output
    ap = argparse.ArgumentParser(description="Check / install the skill's dependencies for this OS.")
    ap.add_argument("--install", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--with", dest="extras", action="append", default=[], choices=["covers", "sound", "linux-vision", "fast-asr"],
                    help="optional parts the user agreed to: covers = Codex CLI for generated cover plates; sound = earshot (designed SFX, listening checks; ≈ 1.6 GB); "
                         "linux-vision = open picture engines in the venv (OpenCV, RapidOCR, MediaPipe; automatic on Linux); fast-asr = faster-whisper")
    a = ap.parse_args()
    covers = "covers" in a.extras
    sound = "sound" in a.extras
    venv_extras = [x for x in a.extras if x in ("linux-vision", "fast-asr")]
    p = plat()
    if p["system"] == "Linux" and "linux-vision" not in venv_extras: venv_extras.append("linux-vision")   # Linux has no Apple Vision: required
    R = check(p, covers, sound, venv_extras)
    if a.install and R.fix and p["system"] in ("Darwin", "Linux"):
        show(p, R); print("installing:")
        manual = install(p, R, a.dry_run)
        if not a.dry_run: R = check(p, covers, sound, venv_extras); print("after install:")
        else: manual += [w for k, w in R.fix if k == "manual" and w not in manual]
        show(p, R)
        if manual: print("run yourself:"); [print("  " + m) for m in dict.fromkeys(manual)]
    else:
        show(p, R)
        if R.missing:
            print("fix: python3 -I " + os.path.abspath(__file__) + " --install")
            for k, w in R.fix:
                if k == "manual": print("  " + w)
    print("DEPS_OK" if not R.missing else f"DEPS_MISSING {R.missing}")
    sys.exit(1 if R.missing else 0)

if __name__ == "__main__":
    main()
