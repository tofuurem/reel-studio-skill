#!/usr/bin/env python3
"""Memory guard: runs a heavy command (a local model, DeepFilterNet, Remotion) and kills it before it freezes the Mac.

    python3 -I mem_guard.py [--max-gb 12] [--min-free-gb 4] -- <command and its arguments>

Every half second it checks two things and kills the command and all its children when either is violated:
  * the footprint of the command's process tree (macOS «footprint» — includes GPU memory, which is shared on Apple Silicon);
  * what is left for the Mac itself (macOS's own estimate, kern.memorystatus_level): headroom for the system and the apps.
Prints the peak. Exit code: the command's own; 137 when the guard killed it (the reason is printed).
Why: a model on MLX / MPS can take all the shared memory on a big input — the Mac swaps and freezes. Python scripts of the skill
call common.guard_reexec() and run themselves under this; shell steps (render.sh) call it explicitly. No-op on Linux (no «footprint»).
"""
import argparse
import os
import re
import signal
import subprocess
import sys
import time

PAGE = 16384


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


def tree(root):
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True).stdout
    kids = {}
    for line in out.split("\n"):
        p = line.split()
        if len(p) == 2:
            kids.setdefault(int(p[1]), []).append(int(p[0]))
    res, stack = [], [root]
    while stack:
        p = stack.pop()
        res.append(p)
        stack += kids.get(p, [])
    return res


def stop(proc):
    """TERM, then KILL, to the command's whole tree: its process group AND every descendant by pid — Remotion starts Chrome
    detached, in a group of its own, so killpg alone left it running. The tree is read before the first signal: once the
    command dies its children are reparented to launchd and can no longer be found."""
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
    ap.add_argument("--every", type=float, default=0.5)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        sys.exit("no command")
    free0 = available_gb()
    if free0 < a.min_free_gb + 1:
        sys.exit("too little free memory to start (%.1f GB free) — close something and run again" % free0)
    proc = subprocess.Popen(cmd, start_new_session=True)
    def on_signal(signum, _frame):   # Ctrl-C, kill or a tool timeout on the guard must not leave the command running unwatched
        stop(proc); print("MEM_GUARD: interrupted (signal %d) — the command was stopped" % signum, file=sys.stderr); sys.exit(128 + signum)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, on_signal)
    peak, reason = 0.0, None
    while proc.poll() is None:
        fp = footprint_gb(tree(proc.pid))
        free = available_gb()
        peak = max(peak, fp)
        if fp > a.max_gb:
            reason = "the command took %.1f GB (ceiling %.1f)" % (fp, a.max_gb)
        elif free < a.min_free_gb:
            reason = "the system has %.1f GB left (reserve %.1f)" % (free, a.min_free_gb)
        if reason:
            stop(proc)
            print("MEM_GUARD: stopped — %s. Peak %.1f GB." % (reason, peak), file=sys.stderr)
            sys.exit(137)
        time.sleep(a.every)
    print("MEM_GUARD: peak %.1f GB, %.1f GB was free" % (peak, free0), file=sys.stderr)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
