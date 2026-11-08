// Generated from references/craft/numbers.json by scripts/numbers_gen.py — edit the JSON, then re-run the script.
export const N = {
  // Cuts and covering layers
  xfade: 7, // dissolve on every timeline cut (frames)
  layerFade: 12, // board / b-roll fade in and out (frames)
  coverBefore: 8, // a cutaway or board over a cut starts at least this many frames before the cut
  coverAfter: 19, // … and ends at least this many frames after it
  montageOverlap: 2, // hard cuts inside a montage: next shot starts this many frames before the previous ends (with fadeIn/fadeOut 0)
  flashPeak: 0.42, // flash on a chapter cut, peak opacity
  flashFrames: 16, // flash length (frames)
  tagFrames: 80, // chapter tag on screen (frames)
  tagY: 200, // chapter tag top (px)
  fadeFromBlack: 15, // cold open on a cutaway: FadeFromBlack (frames)
  premount: 30, // premountFor on every media Sequence (frames)
  chapterLead: 4, // Chapter: the flash starts on the cut, the tag and its whoosh this many frames later (frames)
  endTail: 90, // frames after the last word for the end card / closing plate (default)
  // Captions
  capMaxWords: 8, // words per page
  capMaxSec: 3.4, // seconds per page
  capMaxChars: 54, // characters per page (spaces included)
  capFontPx: 50, // caption font size (px)
  capBottomPad: 400, // caption block paddingBottom (px) → bottom line at y ≈ 1520
  capBridgeMs: 1400, // gap below which two pages soft-swap (ms)
  capSwap: 4, // soft swap overlap (frames, linear)
  capFade: 9, // fade in/out around a real pause (frames)
  capHoldMs: 650, // hold after the last word (ms)
  // Audio levels (Remotion volume; the render then sets the whole mix to the target with a static gain)
  targetLufs: -16, // final integrated loudness (LUFS)
  lufsTolerance: 0.5, // render fails if the final file is further off the target than this (LU)
  bedUnder: 0.18, // music bed under speech
  bedOpen: 0.3, // bed in the cold open, wordless pauses and the tail
  bedTailSec: 15, // bed length = cut list totalFrames / 30 + this (s)
  sfxWhoosh: 0.22, // whoosh on a chapter tag
  sfxSoftWhoosh: 0.14, // soft whoosh on a scan or slide (0.12–0.16)
  sfxDone: 0.22, // done.wav when a result lands (0.2–0.24)
  sfxPop: 0.2, // pop.wav on a chip, badge or mark (0.18–0.22)
  sfxTick: 0.32, // tick.wav while a number counts (0.3–0.35; 0.5 only for a lone timer)
  sfxTickEvery: 6, // tick spacing while counting (frames)
  bleepGain: -18, // soft bleep peak (dBFS)
  sfxFrames: 45, // length of one Sfx sequence (frames)
  bedRamp: 15, // frames the bed takes to move between bedUnder and bedOpen
  bedFadeOut: 24, // bed fade at the very end of the reel (frames)
  sfxHit: 0.9, // impact on the drop / a punch (action reel)
  sfxShutter: 0.6, // camera shutter (a photo moment, a freeze)
  sfxRewind: 0.55, // tape rewind (a replay, a «back to…» cut)
  sfxRiser: 0.35, // rising noise into a drop or a reveal (0.9 s, ends on the frame it is placed + 27)
  sfxBeep: 0.3, // short electronic beep (a low battery, a warning)
  sfxPowerdown: 0.6, // falling tone (the camera dies, the end)
  sfxVariants: 3, // variants made of every whoosh / pop / hit (whoosh, whoosh2, whoosh3 …); reelgen.sfx cycles them
  // Layout (px on 1080x1920)
  safeTop: 180, // nothing important above this y
  safeBottom: 1560, // nothing important below this y
  safeRight: 90, // right strip reserved for the like/comment buttons (px)
  safeX: 64, // side margin of panels and cards
  cardTop: 300, // default top of a card in the top band
  bandTop: 300, // board content band, top
  bandBottom: 1350, // board content band, bottom
  stampMaxPx: 92, // stamp font size when rotated (max)
  minTextPx: 28, // smallest text on screen
  punchDrift: 0.04, // slow push-in added on top of the punch zoom
  punchCenterY: 730, // punch zoom origin y
  coverCrop34Top: 240, // cover 3:4 grid crop, top (bottom 1680)
  coverCrop11Top: 420, // cover 1:1 crop, top (bottom 1500); faces and the word stay inside
  wideMargin: 54, // 16:9 canvas: margin of titles, HUDs and cards (px on 1920×1080)
  wideBandTop: 54, // 16:9 canvas: top of the card band
  wideBandBottom: 860, // 16:9 canvas: bottom of the card band
  // Proxies
  proxyCrf: 18, // x264 CRF of the proxies
  proxyPadSec: 2, // --trim-to-cutlist pad on each side of the used range (s)
  jpegQuality: 92, // Remotion frame JPEG quality
  // People-aware crop (16:9 camera → 9:16 canvas)
  peopleFps: 4, // frames per second people_zones.py samples from the source
  peopleMinConf: 0.3, // lowest Vision confidence for a person box
  peopleFitMargin: 0.9, // share of the crop width the chosen people may fill
  peopleNearArea: 0.25, // a second person joins the crop only if their box is ≥ this share of the main one
  peopleStickyArea: 0.5, // the crop keeps its person while they are at least this share of the biggest one
  peopleSmoothSec: 0.8, // smoothing window of the per-frame crop centre (s)
  peoplePanMin: 0.05, // subject movement (share of the frame width) below which the crop is one fixed centre
  peoplePanSpeed: 0.35, // fastest crop pan (frame widths per second)
  peopleKeyEvery: 0.5, // seconds between crop keyframes of a panning segment
  // Cut from the transcript (whole scenes)
  snapBack: 6.0, // a range that starts inside a sentence grows back to its start, at most this many seconds
  snapFwd: 4.5, // a range that ends inside a sentence grows forward to its end, at most this many seconds
  snapJoin: 0.8, // a pause at least this long counts as a sentence edge even without .?!… (s)
  splitWindowSec: 25, // ranges of one take further apart than this get their own alias proxy (s)
  // Voice chain (voice_clean.py restores each source → dialogue.py builds and processes one dialogue stem → render.sh masters)
  dualmicAtten: 12, // DeepFilterNet noise reduction limit per lav channel (dB)
  dualmicHard: 3.0, // automix exponent: channel gain ∝ power^(this/2) share
  voiceTargetDb: -22.0, // active speech level of every clip before the render's static gain (dBFS)
  voiceMaxGain: 9.0, // most a quiet clip is lifted (dB)
  voiceSegLo: -26.0, // a speech segment quieter than this is lifted (dBFS)
  voiceSegHi: -19.0, // a speech segment louder than this is lowered (dBFS)
  voiceSegMax: 4.0, // most a single segment is moved (dB)
  ambDb: -30.0, // camera sound under a picture beat ("amb"), active level (dBFS)
  rawDb: -22.0, // camera sound instead of the voice ("raw") (dBFS)
  declipMinSamples: 20, // samples at |x| ≥ 0.985 before a source counts as clipped and gets adeclip
  noiseTargetDb: 48, // how far under the speech the residual noise should sit after cleanup (dB); DeepFilterNet's limit = this − the source SNR
  dfnMinAtten: 6, // smallest DeepFilterNet limit used (dB); a source with SNR ≥ noiseTargetDb skips DeepFilterNet
  dfnMaxAtten: 18, // largest DeepFilterNet limit (dB)
  cutXfadeMs: 10, // equal-power crossfade on every jump cut of the dialogue (ms, centred on the cut, from source handles)
  joinXfadeMs: 40, // linear crossfade where two segments continue the same take (a gain change, not a cut)
  hpfHz: 80, // high-pass of the voice (12 dB/oct)
  phaseRotHz: 300, // centre of the phase rotator (4 all-pass sections, Q 0.7) after the high-pass
  eqAmount: 0.7, // share of the measured deviation from the target speech spectrum that the tonal EQ corrects
  eqMaxCut: 4.0, // deepest mud (315 Hz) / box (900 Hz) cut (dB)
  eqMaxBoost: 4.0, // largest presence boost at 3.5 kHz (dB)
  eqMaxAir: 3.0, // largest air boost (9 kHz shelf, dB)
  compOverDb: 4.0, // the one compressor's threshold over the leveled speech (dB over voiceTargetDb)
  compRatio: 2.0, // its ratio
  compKneeDb: 6.0, // its soft knee (dB)
  compAttackMs: 15.0, // its attack (ms)
  compReleaseMs: 200.0, // its release (ms)
  compWindowMs: 30, // its RMS detector window (ms)
  deessOverDb: -6.0, // de-esser acts where the 6.5 kHz band is louder than the speech level + this (dB) and dominates the frame
  deessMaxDb: 6.0, // deepest de-esser cut (dB)
  stemLufs: -24.0, // integrated loudness of the finished dialogue stem (reel/public/audio/dialogue.wav)
  stemPeakDb: -10.0, // look-ahead peak ceiling of the stem (dBFS)
  truePeakDb: -1.5, // master true-peak ceiling (dBTP; 4× oversampled limiter in render.sh)
  aacBitrate: "320k", // final AAC bitrate (the only lossy encode of the sound; Remotion renders PCM)
  lraMax: 9.0, // audio_qa warns above this loudness range of the final mix (LU)
  lraMin: 3.0, // audio_qa warns below this (LU): over-compressed
  // Picture: night lift, action pieces
  nightStrong: 20, // mean luma (0–255) below which a clip gets the strong shadow lift
  nightMedium: 40, // … the medium lift
  nightMild: 50, // … the mild lift; brighter clips are untouched
  actionSlowmo: 0.9, // a piece slower than this is retimed with motion-compensated interpolation (minterpolate)
  actionPhraseBars: 4, // bars per musical phrase on the reel grid (whips and big moments go on phrase starts)
  // Motion timing
  entranceMaxFrames: 24, // longest entrance of one element (frames); a longer build is a stagger of several elements
  staggerMaxFrames: 15, // total stagger of one group of items (first start → last start)
  exitShare: 0.75, // an exit lasts this share of the matching entrance
  payoffPauseMin: 9, // shortest still beat between an action and its result (frames)
  payoffPauseMax: 22, // longest still beat before a payoff (frames)
  transitionKindsMax: 3, // kinds of scene transition in one reel (dissolve, hand-off, whip …), repeated
} as const;
