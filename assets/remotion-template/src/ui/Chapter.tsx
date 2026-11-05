import React from "react";
import { Sequence } from "remotion";
import { N } from "../numbers";
import { ChapterTag } from "./ChapterTag";
import { Flash } from "./Flash";
import { Sfx, type SfxName } from "./Sfx";

/**
 * A chapter start: the flash on the cut, the tag and its whoosh N.chapterLead frames later (fixed offsets — they drifted
 * between projects when typed by hand). Put it in <Sequence from={cut} durationInFrames={N.chapterLead + N.tagFrames}>
 * (reelgen.chapter() does).
 */
export const Chapter: React.FC<{ n: string; title: string; flash?: boolean; sound?: boolean; whoosh?: SfxName }> = ({ n, title, flash = true, sound = true, whoosh = "whoosh" }) => (
  <>
    {flash ? (
      <Sequence name="flash" durationInFrames={N.flashFrames + 2}>
        <Flash />
      </Sequence>
    ) : null}
    <Sequence name="tag" from={N.chapterLead} durationInFrames={N.tagFrames}>
      <ChapterTag n={n} title={title} />
    </Sequence>
    {sound ? (
      <Sequence name="whoosh" from={N.chapterLead} durationInFrames={N.sfxFrames}>
        <Sfx kind={whoosh} />
      </Sequence>
    ) : null}
  </>
);
