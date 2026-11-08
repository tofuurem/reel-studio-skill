import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { body, display } from "../fonts";
import { alpha, colors } from "../theme";
import { BeforeAfter } from "./BeforeAfter";
import { CodeDiff } from "./CodeDiff";
import { CodeTyping, typingFrames } from "./CodeTyping";
import { LowerThird } from "./LowerThird";
import { NotifyStack } from "./Notify";
import { RepoList } from "./RepoCard";

/* Studio preview of the blocks/ kit (Root.tsx registers it as "BlocksDemo"); a reel places blocks from work/gen_reel.py
 * instead (references/craft/blocks.md). The star counts below are placeholders, not facts. */

const BEFORE = `def seq(a, b, kids, name):
    if b - a < 1:
        raise SystemExit(name)
    return tag("Sequence", kids,
               from_=a, dur=b - a)`;

const AFTER = `def seq(a, b, kids, name, pre=False):
    if b - a < 1:
        raise SystemExit(name)
    pm = N["premount"] if pre else None
    return tag("Sequence", kids,
               from_=a, dur=b - a,
               premountFor=pm)`;

const TYPED = `// слово → кадр, без ручных чисел
const a = R.fw("референс");
const b = R.fw("короче", a);
export const card = {
  from: a, to: b,
  name: "card · ref", // кадр сцены
};`;

const Name: React.FC<{ text: string }> = ({ text }) => (
  <div style={{ position: "absolute", left: 64, top: 196, fontFamily: body, fontWeight: 800, fontSize: 30, letterSpacing: 3, textTransform: "uppercase", color: colors.muted }}>{text}</div>
);

/** Stand-in for footage under the lower thirds. */
const FakeShot: React.FC = () => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse 520px 640px at 540px 700px, ${alpha(colors.accent2, 0.22)} 0%, transparent 70%), linear-gradient(180deg, ${colors.panelSolid} 0%, ${colors.bg} 100%)` }}>
    <div style={{ position: "absolute", left: 340, top: 420, width: 400, height: 520, borderRadius: "50% 50% 44% 44%", background: alpha(colors.ink, 0.07) }} />
  </AbsoluteFill>
);

const Plate: React.FC<{ big: string; sub: string; tone: string; bg: string }> = ({ big, sub, tone, bg }) => (
  <AbsoluteFill style={{ background: bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", gap: 18, paddingBottom: 150 }}>
    <div style={{ fontFamily: display, fontWeight: 900, fontSize: 200, letterSpacing: -6, color: tone, lineHeight: 1 }}>{big}</div>
    <div style={{ fontFamily: body, fontWeight: 700, fontSize: 40, color: colors.muted }}>{sub}</div>
  </AbsoluteFill>
);

const T_DIFF = 150;
const T_TYPE = 14 + typingFrames(TYPED) + 50;
const T_REPO = 170;
const T_NOTE = 160;
const T_LT = 100;
const T_BA = 190;
const starts = [0, T_DIFF, T_DIFF + T_TYPE, T_DIFF + T_TYPE + T_REPO, T_DIFF + T_TYPE + T_REPO + T_NOTE, T_DIFF + T_TYPE + T_REPO + T_NOTE + T_LT, T_DIFF + T_TYPE + T_REPO + T_NOTE + 2 * T_LT];
export const BLOCKS_DEMO_FRAMES = starts[6] + T_BA;

export const BlocksDemo: React.FC = () => (
  <AbsoluteFill style={{ background: colors.boardBg }}>
    <Sequence name="CodeDiff" from={starts[0]} durationInFrames={T_DIFF}>
      <Name text="CodeDiff" />
      <CodeDiff file="scripts/reelgen.py" lang="py" before={BEFORE} after={AFTER} size={30} at={4} y={420} />
    </Sequence>
    <Sequence name="CodeTyping" from={starts[1]} durationInFrames={T_TYPE}>
      <Name text="CodeTyping" />
      <CodeTyping file="work/cue.ts" code={TYPED} at={4} y={460} />
    </Sequence>
    <Sequence name="RepoList" from={starts[2]} durationInFrames={T_REPO}>
      <Name text="RepoList" />
      <RepoList
        y={300}
        short
        items={[
          { at: 4, owner: "remotion-dev", name: "remotion", stars: 31200, lang: "TypeScript", langColor: colors.accent2 },
          { at: 18, owner: "heygen-com", name: "hyperframes", stars: 8400, lang: "HTML", langColor: colors.accent },
          { at: 32, owner: "FFmpeg", name: "FFmpeg", stars: 52800, lang: "C", langColor: colors.muted },
          { at: 46, owner: "ggml-org", name: "whisper.cpp", stars: 44100, lang: "C++", langColor: colors.bad },
          { at: 60, owner: "yt-dlp", name: "yt-dlp", stars: 121000, lang: "Python", langColor: colors.ok },
        ]}
        pick={1}
        pickAt={110}
      />
    </Sequence>
    <Sequence name="NotifyStack" from={starts[3]} durationInFrames={T_NOTE}>
      <Name text="NotifyStack" />
      <NotifyStack
        y={300}
        items={[
          { at: 6, app: "Рендер", title: "Reel2K готов", text: "1440×2560, 2:14, громкость −16 LUFS", time: "3 мин" },
          { at: 30, app: "Сборка", title: "Тесты прошли", text: "128 из 128 за 41 секунду", time: "2 мин", iconBg: colors.okPlate },
          { at: 54, app: "Почта", title: "Ответ от монтажёра", text: "Глянул черновик: по темпу всё отлично, переходы мягкие", time: "1 мин", iconBg: colors.accent2 },
          { at: 78, app: "Календарь", title: "Созвон через 10 минут", text: "Обсуждаем второй выпуск", time: "сейчас", iconBg: colors.badPlate },
        ]}
      />
    </Sequence>
    <Sequence name="LowerThird · mask" from={starts[4]} durationInFrames={T_LT}>
      <FakeShot />
      <Name text="LowerThird · mask" />
      <LowerThird name="Алексей Смирнов" kicker="разработчик · lofiroom" at={6} />
    </Sequence>
    <Sequence name="LowerThird · bar" from={starts[5]} durationInFrames={T_LT}>
      <FakeShot />
      <Name text="LowerThird · bar" />
      <LowerThird variant="bar" name="Алексей Смирнов" kicker="разработчик · lofiroom" at={6} />
    </Sequence>
    <Sequence name="BeforeAfter" from={starts[6]} durationInFrames={T_BA}>
      <Name text="BeforeAfter" />
      <BeforeAfter
        y={330}
        at={4}
        a={<Plate big="4:12" sub="рендер до прокси" tone={colors.muted} bg={colors.panelSolid} />}
        b={<Plate big="0:48" sub="рендер с прокси" tone={colors.accent2} bg={`linear-gradient(${alpha(colors.accent, 0.16)}, ${alpha(colors.accent, 0.16)}), ${colors.panelSolid}`} />}
        moves={[
          [96, 0.12],
          [140, 0.5],
        ]}
      />
    </Sequence>
  </AbsoluteFill>
);
