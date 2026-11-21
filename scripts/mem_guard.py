#!/usr/bin/env python3
"""Memory guard: runs a heavy command (a local model, DeepFilterNet, Remotion) and kills it before it freezes the machine.

    python3 -I mem_guard.py [--max-gb 12] [--min-free-gb 4] [--max-vram-gb N] -- <command and its arguments>

Every half second it checks two things and kills the command and all its children when either is violated:
  * the memory of the command's process tree — macOS: «footprint» (includes GPU memory, shared on Apple Silicon);
    Linux: PSS from /proc/<pid>/smaps_rollup (fallback VmRSS); with --max-vram-gb also its NVIDIA memory (nvidia-smi);
  * what is left for the machine itself — macOS: its own estimate (kern.memorystatus_level); Linux: MemAvailable and, inside a
    cgroup v2 with a memory limit (a container, a systemd slice), the smaller of that and memory.max − memory.current
    (reclaimable file cache of the cgroup not counted as used).
Prints the peak. Exit code: the command's own; 137 when the guard killed it (the reason is printed) or the kernel OOM-killed it.
Why: a model on MLX / MPS / CPU can take all the memory on a big input — the machine swaps and freezes. Python scripts of the
skill call common.guard_reexec() and run themselves under this; shell steps (render.sh) call it explicitly. No psutil, no RLIMIT_AS.
"""
import argparse
import os
import re
import signal
import subprocess
import sys
import time

PAGE = 16384
LINUX = sys.platform.startswith("linux")


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


if not LINUX:
    def available_gb():
        """Free memory as macOS itself estimates it (kern.memorystatus_level, % of all memory): it counts the file cache (model
        weights just read from disk, say) as available, since the system gives it back on demand. vm_stat (free + inactive)
        does not, and under a loading model it underestimates the headroom several times."""
        level = int(subprocess.run(["sysctl", "-n", "kern.memorystatus_level"], capture_output=True, text=True).stdout.strip() or 0)
        total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip())
        return level / 100 * total / 2**30

    def footprint_gb(pids):
        total = 0.0
        for pid in pids:
            out = subprocess.run(["footprint", "-p", str(pid)], capture_output=True, text=True).stdout
            m = re.search(r"Footprint:\s+([\d.]+)\s+(KB|MB|GB)", out)
            if m:
                total += float(m.group(1)) / {"KB": 2**20, "MB": 2**10, "GB": 1}[m.group(2)]
        return total

    def children():
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True).stdout
        kids = {}
        for line in out.split("\n"):
            p = line.split()
            if len(p) == 2:
                kids.setdefault(int(p[1]), []).append(int(p[0]))
        return kids

else:
    def _cgroup_dir():
        for line in _read("/proc/self/cgroup").splitlines():
            if line.startswith("0::"):
                return "/sys/fs/cgroup" + line[3:].strip().rstrip("/")
        return None

    def available_gb():
        """MemAvailable (the kernel's estimate; counts reclaimable cache as free, like macOS's level) and, in a cgroup v2 with a
        limit, the room left under that limit — the cgroup's inactive file cache is reclaimable, so it is not counted as used."""
        m = re.search(r"^MemAvailable:\s+(\d+) kB", _read("/proc/meminfo"), re.M)
        free = int(m.group(1)) / 2**20 if m else 0.0
        d = _cgroup_dir()
        if d:
            lim, cur = _read(d + "/memory.max").strip(), _read(d + "/memory.current").strip()
            if lim.isdigit() and cur.isdigit():
                f = re.search(r"^inactive_file (\d+)$", _read(d + "/memory.stat"), re.M)
                used = int(cur) - (int(f.group(1)) if f else 0)
                free = min(free, (int(lim) - used) / 2**30)
        return free

    def footprint_gb(pids):
        """PSS: shared pages split between the processes that map them, so a tree's sum does not count a library twice."""
        total = 0.0
        for pid in pids:
            roll = _read("/proc/%d/smaps_rollup" % pid)
            m = (re.search(r"^Pss:\s+(\d+) kB", roll, re.M) or re.search(r"^Rss:\s+(\d+) kB", roll, re.M)
                 or re.search(r"^VmRSS:\s+(\d+) kB", _read("/proc/%d/status" % pid), re.M))
            if m:
                total += int(m.group(1)) / 2**20
        return total

    def children():
        kids = {}
        for name in os.listdir("/proc"):
            if name.isdigit():
                st = _read("/proc/%s/stat" % name)   # "pid (comm) state ppid …" — comm may hold spaces and parentheses
                if ")" in st:
                    kids.setdefault(int(st[st.rindex(")") + 2:].split()[1]), []).append(int(name))
        return kids


def tree(root):
    kids = children()
    res, stack = [], [root]
    while stack:
        p = stack.pop()
        res.append(p)
        stack += kids.get(p, [])
    return res


def vram_gb(pids):
    """NVIDIA memory held by these pids (0 without nvidia-smi, or when the pids live in another pid namespace)."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return 0.0
    want, total = set(pids), 0.0
    for line in out.splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) == 2 and p[0].isdigit() and int(p[0]) in want and p[1].isdigit():
            total += int(p[1]) / 1024
    return total


def oom_kills():
    """The cgroup's oom_kill counter (Linux, cgroup v2): tells a kernel OOM kill from any other SIGKILL."""
    if not LINUX:
        return 0
    m = re.search(r"^oom_kill (\d+)$", _read((_cgroup_dir() or "/nonexistent") + "/memory.events"), re.M)
    return int(m.group(1)) if m else 0


def stop(proc):
    """TERM, then KILL, to the command's whole tree: its process group AND every descendant by pid — Remotion starts Chrome
    detached, in a group of its own, so killpg alone left it running. The tree is read before the first signal: once the
    command dies its children are reparented to launchd / init and can no longer be found."""
    pids = [p for p in tree(proc.pid) if p != os.getpid()]
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try: os.killpg(proc.pid, sig)
        except OSError: pass
        for p in pids:
            try: os.kill(p, sig)
            except OSError: pass
        for _ in range(10):
            if proc.poll() is not None and not any(alive(p) for p in pids): return
            time.sleep(0.3)


def alive(pid):
    try: os.kill(pid, 0); return True
    except OSError: return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-gb", type=float, default=12.0, help="ceiling for the command itself, GB")
    ap.add_argument("--min-free-gb", type=float, default=4.0, help="memory always left to the system and the apps, GB")
    ap.add_argument("--max-vram-gb", type=float, default=None, help="Linux + NVIDIA: ceiling for the command's GPU memory, GB")
    ap.add_argument("--every", type=float, default=0.5)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        sys.exit("no command")
    free0 = available_gb()
    if free0 < a.min_free_gb + min(1.0, a.max_gb):   # room for the reserve plus (up to 1 GB of) the command
        sys.exit("too little free memory to start (%.1f GB free) — close something and run again" % free0)
    oom0 = oom_kills()
    proc = subprocess.Popen(cmd, start_new_session=True)
    def on_signal(signum, _frame):   # Ctrl-C, kill or a tool timeout on the guard must not leave the command running unwatched
        stop(proc); print("MEM_GUARD: interrupted (signal %d) — the command was stopped" % signum, file=sys.stderr); sys.exit(128 + signum)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, on_signal)
    peak, vpeak, reason = 0.0, 0.0, None
    while proc.poll() is None:
        pids = tree(proc.pid)
        fp = footprint_gb(pids)
        free = available_gb()
        peak = max(peak, fp)
        vr = vram_gb(pids) if a.max_vram_gb is not None else 0.0
        vpeak = max(vpeak, vr)
        if fp > a.max_gb:
            reason = "the command took %.1f GB (ceiling %.1f)" % (fp, a.max_gb)
        elif a.max_vram_gb is not None and vr > a.max_vram_gb:
            reason = "the command took %.1f GB of GPU memory (ceiling %.1f)" % (vr, a.max_vram_gb)
        elif free < a.min_free_gb:
            reason = "the system has %.1f GB left (reserve %.1f)" % (free, a.min_free_gb)
        if reason:
            stop(proc)
            print("MEM_GUARD: stopped — %s. Peak %.1f GB." % (reason, peak), file=sys.stderr)
            sys.exit(137)
        time.sleep(a.every)
    rc = proc.returncode
    if rc == -signal.SIGKILL and oom_kills() > oom0:
        print("MEM_GUARD: the kernel OOM-killed the command (the memory limit was hit between two checks). Peak %.1f GB." % peak,
              file=sys.stderr)
        sys.exit(137)
    print("MEM_GUARD: peak %.1f GB%s, %.1f GB was free" % (peak, ", GPU %.1f GB" % vpeak if vpeak else "", free0), file=sys.stderr)
    sys.exit(128 - rc if rc < 0 else rc)


if __name__ == "__main__":
    main()
