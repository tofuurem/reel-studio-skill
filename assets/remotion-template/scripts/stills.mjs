// Render several frames of a composition with one shared browser (fast QA).
// Usage: node scripts/stills.mjs <CompId> <frame> [frame…]   → ../work/stills/fNNNN.jpg (half size)
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition, openBrowser } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browserExecutable = fs.existsSync(CHROME) ? CHROME : null; // see remotion.config.ts
const [compId, ...rest] = process.argv.slice(2);
if (!compId || !rest.length) { console.error("usage: node scripts/stills.mjs <CompId> <frame> [frame…]"); process.exit(2); }
// only what the page needs: the footage folder switch (the whole process.env used to be injected into the page)
const envVariables = { REMOTION_FOOTAGE_DIR: process.env.REMOTION_FOOTAGE_DIR ?? (compId.endsWith("2K") ? "footage2k" : "footage") };
const frames = rest.map(Number);
const out = path.resolve("../work/stills"); fs.mkdirSync(out, { recursive: true });
// One bundle dir per run (parallel QA runs used to clobber a shared one), always removed: bundle() copies public/
// (≈1 GB of proxies), and leftover temp bundles once filled the disk.
const bundleDir = path.resolve(`../work/bundle_${process.pid}`);
try {
  const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts"), outDir: bundleDir, onProgress: () => {} });
  const browser = await openBrowser("chrome", { chromiumOptions: { gl: "angle" }, browserExecutable });
  try {
    const composition = await selectComposition({ serveUrl, id: compId, puppeteerInstance: browser, envVariables, browserExecutable });
    for (const f of frames) {
      await renderStill({ composition, serveUrl, output: `${out}/f${String(f).padStart(4, "0")}.jpg`, frame: f, imageFormat: "jpeg", jpegQuality: 80, puppeteerInstance: browser, chromiumOptions: { gl: "angle" }, scale: 0.5, envVariables, browserExecutable });
      process.stdout.write(`${f} `);
    }
  } finally {
    await browser.close({ silent: true });
  }
} finally {
  fs.rmSync(bundleDir, { recursive: true, force: true });
}
console.log("\nDONE");
