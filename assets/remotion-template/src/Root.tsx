import React from "react";
import { AbsoluteFill, Composition, Folder } from "remotion";
import { Reel, REEL_FRAMES } from "./Reel";
import { Action, ACTION_FRAMES } from "./Action";
import { Timeline, TOTAL_FRAMES } from "./Timeline";
import { FPS, H, W } from "./theme";

const base = { fps: FPS, width: W, height: H };

/** Same layout, rendered at 2K (exact 4/3 of the 1080-based canvas: 1440x2560, 2560x1440 for 16:9). Uses public/footage2k via REMOTION_FOOTAGE_DIR. */
const Reel2K: React.FC = () => (
  <AbsoluteFill style={{ width: W, height: H, scale: String(4 / 3), transformOrigin: "0% 0%" }}>
    <Reel />
  </AbsoluteFill>
);

/** The action reel (references/inputs/action-reel.md) at 2K; the shots are 2K pieces already. */
const Action2K: React.FC = () => (
  <AbsoluteFill style={{ width: W, height: H, scale: String(4 / 3), transformOrigin: "0% 0%" }}>
    <Action />
  </AbsoluteFill>
);

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Reel" component={Reel} durationInFrames={REEL_FRAMES} {...base} />
    <Composition id="Reel2K" component={Reel2K} durationInFrames={REEL_FRAMES} fps={FPS} width={(W * 4) / 3} height={(H * 4) / 3} />
    <Folder name="Action">
      <Composition id="Action" component={Action} durationInFrames={ACTION_FRAMES} {...base} />
      <Composition id="ActionTrack" component={Action} defaultProps={{ withTrack: true }} durationInFrames={ACTION_FRAMES} {...base} />
      <Composition id="Action2K" component={Action2K} durationInFrames={ACTION_FRAMES} fps={FPS} width={(W * 4) / 3} height={(H * 4) / 3} />
    </Folder>
    <Folder name="Scenes">
      <Composition id="Timeline" component={Timeline} durationInFrames={TOTAL_FRAMES} {...base} />
      {/* register each scene here too so it gets its own Studio timeline */}
    </Folder>
    {/* Covers (stills, references/craft/covers.md): copy assets/examples/Covers.example.tsx to src/Covers.tsx, then
        import { Cover1 } from "./Covers";   import { Still } from "remotion";
        <Folder name="Covers">
          <Still id="Cover1" component={Cover1} width={W} height={H} defaultProps={{ guides: false }} />
        </Folder>
        render: scripts/cover.sh <project> <covers>/public <abs out prefix> Cover1 … (guides: true for the crop check) */}
  </>
);
