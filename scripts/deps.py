#!/usr/bin/env python3
"""Check — and with --install, install — everything the skill needs, for the OS it runs on. Standard library only: it runs
before any venv exists, on a bare machine. setup_env.sh calls it first; on Linux run it yourself first (zsh may be missing).

Usage: python3 -I deps.py [--install] [--dry-run] [--with covers]
  (no flag)   report: platform, every tool / library / python env with its version, what is missing and the command that fixes
              it, and which parts of the skill this platform cannot run
  --install   install what is missing: system packages (brew / apt / dnf / pacman), uv, then the shared python envs in
              ~/.cache/reel-studio (venv, dfvenv, pkvenv — per platform). Root-only commands run through sudo only when it needs no
              password (sudo -n); otherwise they are printed for the user to run, and the check stays MISSING
  --dry-run   with --install: print the commands, run nothing
  --with covers  also the Codex CLI for generated cover plates (ask the user first: it needs their ChatGPT login)
Parakeet is set up only when the Handy app's model is on the machine; otherwise transcription uses Whisper.
Prints DEPS_OK (the pipeline can run here) or DEPS_MISSING <n> (exit 1).

Platforms
  macOS, Apple Silicon   everything
  macOS, Intel           no MLX: Whisper runs as openai-whisper (CPU, slower), no Parakeet (transcribe.py does the first pass)
  Linux (and WSL2)       no Apple Vision: face_zones / people_zones / person_matte / cutout do not run → no people-aware 9:16 crop
                         of landscape footage (use a 16:9 canvas or crop keys by hand), no title behind the person, no cut-out
                         covers; no Parakeet; no hardware decode (software decode, slower); Whisper as openai-whisper (CUDA if
                         an NVIDIA GPU is visible, else CPU)
  Windows                not native (zsh scripts, POSIX paths): install WSL2 + Ubuntu and run the skill inside it
"""
import argparse, json, os, platform, re, shutil, subprocess, sys

CACHE = os.path.expanduser("~/.cache/reel-studio")
NODE_MIN, PY_MIN = 18, (3, 9)
FF_ENCODERS = {"libx264": True, "aac": True, "libvpx-vp9": False}            # True = required; libvpx-vp9 → mattes (title behind the person)
FF_FILTERS = ("lut3d", "minterpolate", "adeclip", "alimiter", "acompressor", "ebur128", "loudnorm", "astats", "atempo", "xfade")
FONTS = ("Unbounded.ttf", "Montserrat.ttf", "JetBrainsMono.ttf")
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
    "yt-dlp": {"brew": "yt-dlp"},                                             # brew brings deno (YouTube); distro packages lag behind the sites
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

def parakeet_model():
    """Parakeet runs on what the user already has: the Handy app's GGUF or a model converted from it. None → Whisper only."""
    import glob
    conv = os.path.join(CACHE, "models", "parakeet-v3-handy", "model.safetensors")
    if os.path.exists(conv): return conv
    g = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--handy-computer--parakeet-tdt-0.6b-v3-gguf/snapshots/*/*.gguf"))
    return g[0] if g else None

def venv_specs(p):
    """name → (python version, import check, pip packages, extra index for torch, what it is for). Per platform."""
    cpu_torch = None if (p["mac"] or p["nvidia"]) else "https://download.pytorch.org/whl/cpu"   # Linux without a GPU: CPU wheels (≈ 200 MB, not 2.5 GB)
    if p["mac"]:
        asr = (["mlx_whisper"], ["mlx-whisper"]) if p["apple_silicon"] else (["whisper"], ["openai-whisper"])
        vis = (["Vision", "Quartz", "Foundation"], ["pyobjc-framework-Vision", "pyobjc-framework-Quartz"])
    else:
        asr, vis = (["whisper"], ["openai-whisper"]), ([], [])
    # person_matte.py --mode birefnet (title behind a person WITH headphones / glasses / props): BiRefNet through transformers
    mat = (["torch", "torchvision", "transformers", "timm", "kornia", "einops"], ["torch", "torchvision", "transformers", "timm", "kornia", "einops"])
    specs = {
        "venv": ("3.12", ["numpy", *asr[0], *vis[0], *mat[0]], ["numpy", *asr[1], *vis[1], *mat[1]], None if p["apple_silicon"] or p["mac"] else cpu_torch,
                 "transcribe.py (Whisper), numpy scripts, person_matte.py (BiRefNet)" + (", Apple Vision" if p["mac"] else "")),
        "dfvenv": ("3.11", ["df", "torchaudio", "soundfile"], ["deepfilternet", "soundfile", "torch==2.4.1", "torchaudio==2.4.1"], cpu_torch,
                   "voice_clean.py, dualmic.py, dialogue.py"),
    }
    if p["apple_silicon"] and parakeet_model():
        specs["pkvenv"] = ("3.12", ["parakeet_mlx", "gguf"], ["parakeet-mlx", "gguf"], None, "transcribe_parakeet.py (first-pass map of raw clips)")
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

def check(p, want_covers=False):
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
        R.add(ok, f"env {name}", what, ("venv", name))
    if p["apple_silicon"] and not parakeet_model():
        R.add(False, "parakeet", "no Handy model here — transcription runs on Whisper (fine)", required=False)
    cx = ver(["codex", "--version"], r"(\d+\.\d+[\w.\-]*)")
    R.add(bool(cx), "codex (covers)", cx or "optional: generated cover plates (scripts/codex_image.sh) — --install --with covers, then `codex login`",
          ("covers", None) if want_covers else None, required=want_covers)
    fonts = [f for f in FONTS if not (os.path.exists(fp := os.path.join(CACHE, "fonts", f)) and os.path.getsize(fp))]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import projects_dir; pd = projects_dir.saved()
    R.add(True, "projects folder", pd or "the folder Claude Code is open in (asked before each new project)", required=False)
    R.add(not fonts, "fonts", "template fonts in ~/.cache/reel-studio/fonts" + (" — setup_env.sh downloads them" if fonts else ""), required=False)
    return R

def limits(p):
    out = []
    if not p["mac"]:
        out += ["Apple Vision (macOS only): face_zones.py, people_zones.py, person_matte.py, cutout.py do not run — no people-aware "
                "9:16 crop of landscape footage (16:9 canvas, or crop keys by hand), no title behind the person, no cut-out covers",
                "hardware decode (videotoolbox): software decode, proxies take longer"]
    if not p["apple_silicon"]:
        out += ["MLX (Apple Silicon only): Whisper runs as openai-whisper" + (" on CUDA" if p["nvidia"] else " on the CPU — several times slower"),
                "Parakeet (transcribe_parakeet.py): use transcribe.py for the first pass"]
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
    return manual

def show(p, R):
    print(f"platform: {p['name']}" + (f" · package manager: {p['pm']}" if p["pm"] else "") + (" · NVIDIA GPU" if p["nvidia"] else ""))
    for state, name, info in R.rows: print(f"  {state:<8} {name:<20} {info}")
    lim = limits(p)
    if lim: print("not on this platform:"); [print("  - " + x) for x in lim]

def main():
    sys.stdout.reconfigure(line_buffering=True)   # keep our lines in order with the installers' output
    ap = argparse.ArgumentParser(description="Check / install the skill's dependencies for this OS.")
    ap.add_argument("--install", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--with", dest="extras", action="append", default=[], choices=["covers"],
                    help="optional parts the user agreed to: covers = Codex CLI for generated cover plates")
    a = ap.parse_args()
    covers = "covers" in a.extras
    p = plat(); R = check(p, covers)
    if a.install and R.fix and p["system"] in ("Darwin", "Linux"):
        show(p, R); print("installing:")
        manual = install(p, R, a.dry_run)
        if not a.dry_run: R = check(p, covers); print("after install:")
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
