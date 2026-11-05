/**
 * Note: When using the Node.JS APIs, the config file
 * doesn't apply. Instead, pass options directly to the APIs.
 *
 * All configuration options: https://remotion.dev/docs/config
 */

import { Config } from "@remotion/cli/config";
import { N } from "./src/numbers";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(N.jpegQuality); // the default 80 bands dark gradients (boards, night footage)
Config.setOverwriteOutput(true);
// Keep "angle" (GPU). "swiftshader" drops stamps/cards on every other frame here; angle only mis-rasterises a tile on a
// rare frame under load — render with CONC=1 (render.sh) and check the file with glitch_scan.py.
// Linux / WSL2 without a GPU: "swangle" (software ANGLE); REMOTION_GL=angle-egl when a GPU is set up there.
Config.setChromiumOpenGlRenderer(process.platform === "darwin" ? "angle" : ((process.env.REMOTION_GL as "swangle" | "angle-egl" | "angle" | undefined) ?? "swangle"));
Config.setConcurrency(1); // 1 tab: no GPU contention → no single-frame dropouts; not slower here (render.sh CONC=…)

// The bundled chrome-headless-shell hangs when macOS has a virtual display (Screen Sharing "high
// performance" mode, DisplayLink, Sidecar): CVDisplayLinkCreateWithCGDisplay fails and no frame is
// ever produced. The installed Google Chrome copes, so prefer it when present.
import { existsSync } from "node:fs";
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
if (existsSync(CHROME)) Config.setBrowserExecutable(CHROME);
