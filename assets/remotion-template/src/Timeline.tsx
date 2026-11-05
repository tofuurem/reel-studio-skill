import React from "react";
import { AbsoluteFill } from "remotion";
import { colors } from "./theme";

/** STUB so a fresh scaffold compiles and Studio opens. scripts/gen_timeline.py overwrites this file from
 *  work/cutlist.json (same exports: Timeline, TOTAL_FRAMES). */
export const Timeline: React.FC = () => <AbsoluteFill style={{ backgroundColor: colors.bg }} />;

export const TOTAL_FRAMES = 300;
