"""Print pauses (RMS below threshold) in a wav window. usage: pauses.py wav start dur [thr_db=-36] [min_s=0.25]"""
import subprocess, sys, struct, math
wav, s, d = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]); thr = float(sys.argv[4]) if len(sys.argv) > 4 else -36; mn = float(sys.argv[5]) if len(sys.argv) > 5 else 0.25
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(s), "-t", str(d), "-i", wav, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
n = len(raw) // 2; a = struct.unpack(f"<{n}h", raw); w = 160  # 10 ms
env = []
for i in range(0, n - w, w):
    seg = a[i:i + w]; rms = math.sqrt(sum(x * x for x in seg) / w) / 32768
    env.append(20 * math.log10(rms + 1e-9))
# smooth 3
sm = [max(env[max(0, i - 1):i + 2]) for i in range(len(env))]
out = []; start = None
for i, v in enumerate(sm):
    if v < thr and start is None: start = i
    if v >= thr and start is not None:
        if (i - start) * 0.01 >= mn: out.append((s + start * 0.01, s + i * 0.01))
        start = None
if start is not None and (len(sm) - start) * 0.01 >= mn: out.append((s + start * 0.01, s + len(sm) * 0.01))
print(" ".join(f"{a:.2f}-{b:.2f}({b-a:.2f})" for a, b in out))
