// Record a public web page for b-roll when the user gives a URL instead of a screen recording (hermes-worker reel,
// 2026-11-06: the challenge's own screen recording did not exist; the landing page was captured here instead).
//
// Usage: node site_capture.mjs <project> <url> [--name site] [--size 1920x1080] [--scale 1.3333] [--mobile]
//                              [--hero 14] [--scroll 11] [--chrome <binary>]
// → <project>/work/broll/<name>_hero.mp4    the page LOADING (blank → page) plus its own animations, `--hero` s
//   <project>/work/broll/<name>_scroll.mp4  an eased scroll top → bottom, `--scroll` s (skipped for a page that does not scroll)
//   <project>/work/site/<name>_hero.png, <name>_full.png   the first screen and the whole page (after the scroll revealed it)
//   SITE_CAPTURE_DONE
// Frames come from CDP Page.startScreencast with their own timestamps and are turned into CFR 30 fps H.264 by frames2mp4.py
// (in a temp folder on the internal disk: thousands of small JPEGs on an exFAT project volume would each take 1 MB).
// Defaults: a 1920×1080 desktop viewport at device scale 4/3 → 2560×1440 frames (a 16:9 Reel2K needs no upscale). For a
// vertical reel record the mobile site: --size 430x932 --scale 3 --mobile.
// Chrome: --chrome, else $CHROME, else Google Chrome.app, else Remotion's chrome-headless-shell under reel/node_modules/.remotion.
// A throwaway profile (no cookies, no sign-in) — public pages only; never log in or type anything into the page.
// Then: make_proxies.py … --extra work/broll/<name>_hero.mp4 (non-DJI extras keep their aspect at canvas width, no LUT).
import { spawn, execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, writeFileSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const argv = process.argv.slice(2);
const VALUED = new Set(["--name", "--size", "--scale", "--hero", "--scroll", "--chrome"]);
const pos = argv.filter((a, i) => !a.startsWith("-") && !(i > 0 && VALUED.has(argv[i - 1])));
const opt = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : d; };
if (argv.includes("--help") || argv.includes("-h") || pos.length < 2) {
  console.log("usage: node site_capture.mjs <project> <url> [--name site] [--size 1920x1080] [--scale 1.3333] [--mobile] [--hero 14] [--scroll 11] [--chrome <binary>]");
  process.exit(argv.includes("--help") || argv.includes("-h") ? 0 : 2);
}
const P = resolve(pos[0]); const URL_ = pos[1];
const NAME = opt("name", "site");
const [W, H] = opt("size", "1920x1080").split("x").map(Number);
const DSF = Number(opt("scale", String(4 / 3)));
const MOBILE = argv.includes("--mobile");
const HERO_S = Number(opt("hero", "14")), SCROLL_S = Number(opt("scroll", "11"));
const HERE = dirname(fileURLToPath(import.meta.url));

const req = createRequire(join(P, "reel", "package.json"));
let WebSocket;
try { WebSocket = req("ws"); } catch { console.error(`no 'ws' package under ${P}/reel/node_modules — run scaffold.sh first`); process.exit(1); }

function findChrome() {
  const c = opt("chrome", process.env.CHROME);
  if (c) return c;
  const mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  if (existsSync(mac)) return mac;
  const root = join(P, "reel", "node_modules", ".remotion");
  const walk = (d, depth) => {
    if (depth > 4 || !existsSync(d)) return null;
    for (const f of readdirSync(d)) {
      const p = join(d, f);
      if (f === "chrome-headless-shell" && statSync(p).isFile()) return p;
      if (statSync(p).isDirectory()) { const r = walk(p, depth + 1); if (r) return r; }
    }
    return null;
  };
  const r = walk(root, 0);
  if (r) return r;
  console.error("no Chrome: pass --chrome, set $CHROME, or run `npx remotion browser ensure` in reel/"); process.exit(1);
}

const TMP = mkdtempSync(join(tmpdir(), "site_capture_"));
const PORT = 9300 + Math.floor(Math.random() * 600);
const chrome = spawn(findChrome(), ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${join(TMP, "profile")}`,
  "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--mute-audio", `--window-size=${W},${H}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const cleanup = () => { try { chrome.kill("SIGTERM"); } catch {} };
process.on("exit", cleanup);

async function pageWs() {
  for (let i = 0; i < 80; i++) {
    try { const j = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); const p = j.find((t) => t.type === "page"); if (p) return p.webSocketDebuggerUrl; } catch {}
    await sleep(250);
  }
  throw new Error("chrome did not start");
}
const ws = new WebSocket(await pageWs(), { perMessageDeflate: false, maxPayload: 512 * 1024 * 1024 });
await new Promise((r) => ws.once("open", r));
let id = 0; const pending = new Map(); const listeners = [];
ws.on("message", (m) => { const d = JSON.parse(m);
  if (d.id && pending.has(d.id)) { const { res, rej } = pending.get(d.id); pending.delete(d.id); d.error ? rej(new Error(JSON.stringify(d.error))) : res(d.result); }
  else if (d.method) listeners.forEach((f) => f(d)); });
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
const evalJs = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.value;

await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: DSF, mobile: MOBILE });
if (MOBILE) await send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });

async function screencast(name, ms, during) {
  const dir = join(TMP, name); mkdirSync(dir, { recursive: true });
  const frames = [];
  const onFrame = (d) => {
    if (d.method !== "Page.screencastFrame") return;
    const { data, metadata, sessionId } = d.params;
    const f = join(dir, `f${String(frames.length).padStart(5, "0")}.jpg`);
    writeFileSync(f, Buffer.from(data, "base64")); frames.push({ f, t: metadata.timestamp });
    send("Page.screencastFrameAck", { sessionId }).catch(() => {});
  };
  listeners.push(onFrame);
  await send("Page.startScreencast", { format: "jpeg", quality: 95, maxWidth: Math.round(W * DSF), maxHeight: Math.round(H * DSF), everyNthFrame: 1 });
  const t0 = Date.now();
  if (during) await during();
  const left = ms - (Date.now() - t0); if (left > 0) await sleep(left);
  await send("Page.stopScreencast"); listeners.splice(listeners.indexOf(onFrame), 1);
  writeFileSync(join(dir, "frames.json"), JSON.stringify(frames));
  console.log(`${name}: ${frames.length} frames`);
  return dir;
}
const toMp4 = (dir, out) => execFileSync("python3", ["-I", join(HERE, "frames2mp4.py"), dir, out, "--size", `${Math.round(W * DSF / 2) * 2}x${Math.round(H * DSF / 2) * 2}`], { stdio: "inherit" });

mkdirSync(join(P, "work", "broll"), { recursive: true }); mkdirSync(join(P, "work", "site"), { recursive: true });
const heroDir = await screencast("hero", HERO_S * 1000, async () => { await send("Page.navigate", { url: URL_ }); });
toMp4(heroDir, join(P, "work", "broll", `${NAME}_hero.mp4`));

const scrollH = await evalJs("document.documentElement.scrollHeight");
const canScroll = scrollH > H + 40;
if (canScroll) {
  const scrollDir = await screencast("scroll", SCROLL_S * 1000, async () => {
    await sleep(600);
    const T = Math.max(1000, (SCROLL_S - 2.5) * 1000);
    await evalJs(`new Promise(res => { const max = document.documentElement.scrollHeight - innerHeight; const t0 = performance.now();
      const ease = x => x < .5 ? 4*x*x*x : 1 - Math.pow(-2*x + 2, 3) / 2;
      function step(now) { const k = Math.min(1, (now - t0) / ${T}); scrollTo(0, max * ease(k)); k < 1 ? requestAnimationFrame(step) : res(1); }
      requestAnimationFrame(step); })`);
  });
  toMp4(scrollDir, join(P, "work", "broll", `${NAME}_scroll.mp4`));
} else console.log(`page height ${scrollH} ≤ viewport: no scroll take`);

await evalJs("scrollTo(0, 0)"); await sleep(800);
const full = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: W, height: scrollH, scale: 1 } });
writeFileSync(join(P, "work", "site", `${NAME}_full.png`), Buffer.from(full.data, "base64"));
const hero = await send("Page.captureScreenshot", { format: "png" });
writeFileSync(join(P, "work", "site", `${NAME}_hero.png`), Buffer.from(hero.data, "base64"));
ws.close(); cleanup(); rmSync(TMP, { recursive: true, force: true });
console.log("SITE_CAPTURE_DONE", join(P, "work", "broll", `${NAME}_hero.mp4`), canScroll ? join(P, "work", "broll", `${NAME}_scroll.mp4`) : "");
process.exit(0);
