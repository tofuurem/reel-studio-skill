# Numbers in one place

Generated from `numbers.json` by `scripts/numbers_gen.py` — edit the JSON, not this file. Timings are frames at 30 fps on the 1080×1920 canvas (Reel2K scales everything by 4/3). Scripts read the same values (`scripts/common.py`), the template imports them from `src/numbers.ts` (`N.<key>`).

**Cuts and covering layers**

| key | value | what | why | used by |
|---|---|---|---|---|
| `xfade` | 7 | dissolve on every timeline cut (frames) | the outgoing clip is held muted under the incoming one | gen_timeline.py --xfade |
| `layerFade` | 12 | board / b-roll fade in and out (frames) | crossfade between boards; the timeline dissolve is a different thing | BRoll, Board |
| `coverBefore` | 8 | a cutaway or board over a cut starts at least this many frames before the cut | the outgoing face must not peek out | reelgen.py R.cover / R.cutaway / R.board |
| `coverAfter` | 19 | … and ends at least this many frames after it | xfade 7 + layerFade 12: its fade-out must start after the incoming shot's own dissolve, less shows a stray face or the dark carrier | reelgen.py R.cover / R.cutaway / R.board |
| `montageOverlap` | 2 | hard cuts inside a montage: next shot starts this many frames before the previous ends (with fadeIn/fadeOut 0) | no dip to the carrier between shots | gen_reel.py |
| `flashPeak` | 0.42 | flash on a chapter cut, peak opacity | 0.85 read as a strobe | ui/Flash.tsx |
| `flashFrames` | 16 | flash length (frames) |  | ui/Flash.tsx |
| `tagFrames` | 80 | chapter tag on screen (frames) | long enough to read two words, short enough not to become chrome | ui/Chapter.tsx, reelgen.py R.chapter |
| `tagY` | 200 | chapter tag top (px) | above the card band | ui/ChapterTag.tsx |
| `fadeFromBlack` | 15 | cold open on a cutaway: FadeFromBlack (frames) | the talking head must not peek on frame 0 | the Sequence around FadeFromBlack in gen_reel.py |
| `premount` | 30 | premountFor on every media Sequence (frames) | videos mount before they are shown: no black first frame in Studio, steadier renders | gen_timeline.py, reelgen.py seq(premount=True) |
| `chapterLead` | 4 | Chapter: the flash starts on the cut, the tag and its whoosh this many frames later (frames) | the light hit reads as the cause of the tag | ui/Chapter.tsx, reelgen.chapter() |
| `endTail` | 90 | frames after the last word for the end card / closing plate (default) | channel pill + slow fade, no «watch the previous video» | reelgen.py R.write, template Reel.tsx |

**Captions**

| key | value | what | why | used by |
|---|---|---|---|---|
| `capMaxWords` | 8 | words per page | two lines = fewer switches | make_captions.py --max-words |
| `capMaxSec` | 3.4 | seconds per page |  | make_captions.py --max-sec |
| `capMaxChars` | 54 | characters per page (spaces included) | 50 px Montserrat 700 in a 920 px column wraps to a third line above ~60 characters and then climbs into the card band | make_captions.py --max-chars |
| `capFontPx` | 50 | caption font size (px) |  | Captions.tsx |
| `capBottomPad` | 400 | caption block paddingBottom (px) → bottom line at y ≈ 1520 | clear of the Instagram caption/buttons | Captions.tsx |
| `capBridgeMs` | 1400 | gap below which two pages soft-swap (ms) | a fade to zero between two phrases is the blinking line | Captions.tsx |
| `capSwap` | 4 | soft swap overlap (frames, linear) |  | Captions.tsx |
| `capFade` | 9 | fade in/out around a real pause (frames) |  | Captions.tsx |
| `capHoldMs` | 650 | hold after the last word (ms) |  | Captions.tsx |

**Audio levels (Remotion volume; the render then sets the whole mix to the target with a static gain)**

| key | value | what | why | used by |
|---|---|---|---|---|
| `targetLufs` | -16 | final integrated loudness (LUFS) |  | render.sh |
| `lufsTolerance` | 0.5 | render fails if the final file is further off the target than this (LU) | an auto-levelling limiter once shipped every reel at −14.9 | render.sh |
| `sourceLufs` | -24 | each speech source after match_loudness.py (LUFS over its used ranges) | takes from different mics sit at one level | match_loudness.py |
| `bedUnder` | 0.18 | music bed under speech | ≈ 20 LU down | MusicBed |
| `bedOpen` | 0.3 | bed in the cold open, wordless pauses and the tail |  | MusicBed |
| `bedTailSec` | 15 | bed length = cut list totalFrames / 30 + this (s) | covers the end card and the fade | make_bed.sh |
| `sfxWhoosh` | 0.22 | whoosh on a chapter tag |  | Chapter, Sfx |
| `sfxSoftWhoosh` | 0.14 | soft whoosh on a scan or slide (0.12–0.16) |  | Sfx |
| `sfxDone` | 0.22 | done.wav when a result lands (0.2–0.24) |  | Sfx |
| `sfxPop` | 0.2 | pop.wav on a chip, badge or mark (0.18–0.22) |  | Sfx |
| `sfxTick` | 0.32 | tick.wav while a number counts (0.3–0.35; 0.5 only for a lone timer) |  | Sfx |
| `sfxTickEvery` | 6 | tick spacing while counting (frames) |  | gen_reel.py |
| `bleepGain` | -18 | soft bleep peak (dBFS) | −16 read as loud | bleep.py --gain |
| `sfxFrames` | 45 | length of one Sfx sequence (frames) | long enough for the decay of every sound in audio/sfx | reelgen.sfx() |
| `bedRamp` | 15 | frames the bed takes to move between bedUnder and bedOpen | a jump in the bed level is heard as a cut | ui/Sfx.tsx MusicBed |
| `bedFadeOut` | 24 | bed fade at the very end of the reel (frames) |  | ui/Sfx.tsx MusicBed |
| `sfxHit` | 0.9 | impact on the drop / a punch (action reel) | the one sound that marks the big moment; everything else is the track's | Sfx kind=hit |
| `sfxShutter` | 0.6 | camera shutter (a photo moment, a freeze) |  | Sfx kind=shutter |
| `sfxRewind` | 0.55 | tape rewind (a replay, a «back to…» cut) |  | Sfx kind=rewind |
| `sfxRiser` | 0.35 | rising noise into a drop or a reveal (0.9 s, ends on the frame it is placed + 27) |  | Sfx kind=riser |
| `sfxBeep` | 0.3 | short electronic beep (a low battery, a warning) |  | Sfx kind=beep |
| `sfxPowerdown` | 0.6 | falling tone (the camera dies, the end) |  | Sfx kind=powerdown |
| `sfxVariants` | 3 | variants made of every whoosh / pop / hit (whoosh, whoosh2, whoosh3 …); reelgen.sfx cycles them | «одинаковый вжух на каждый переход — странно» (Halloween reel): the same sample twice in a row reads as a template | make_sfx.sh, reelgen.sfx() |

**Layout (px on 1080x1920)**

| key | value | what | why | used by |
|---|---|---|---|---|
| `safeTop` | 180 | nothing important above this y | Instagram header | theme.ts safe |
| `safeBottom` | 1560 | nothing important below this y | caption text, buttons | theme.ts safe |
| `safeRight` | 90 | right strip reserved for the like/comment buttons (px) |  | theme.ts safe |
| `safeX` | 64 | side margin of panels and cards |  | theme.ts safe |
| `cardTop` | 300 | default top of a card in the top band | below the chapter tag (y 200–280), above a medium-shot face | ui/Card.tsx |
| `bandTop` | 300 | board content band, top |  | Board |
| `bandBottom` | 1350 | board content band, bottom | captions sit below 1400 | Board |
| `stampMaxPx` | 92 | stamp font size when rotated (max) |  | ui/Stamp.tsx |
| `minTextPx` | 28 | smallest text on screen | ≈ 10 pt on a phone; smaller is unreadable | lint_reel.py |
| `punchDrift` | 0.04 | slow push-in added on top of the punch zoom | face zones are corrected by punch + drift | Clip.tsx, face_zones.py |
| `punchCenterY` | 730 | punch zoom origin y | eye line of a vertical talking head | Clip.tsx, face_zones.py |
| `coverCrop34Top` | 240 | cover 3:4 grid crop, top (bottom 1680) | Instagram profile grid | Cover.tsx guides |
| `coverCrop11Top` | 420 | cover 1:1 crop, top (bottom 1500); faces and the word stay inside | old square grid | Cover.tsx guides |

**Proxies**

| key | value | what | why | used by |
|---|---|---|---|---|
| `proxyCrf` | 18 | x264 CRF of the proxies |  | make_proxies.py --crf |
| `proxyPadSec` | 2 | --trim-to-cutlist pad on each side of the used range (s) | room for dissolves and small re-cuts without re-encoding | make_proxies.py |
| `jpegQuality` | 92 | Remotion frame JPEG quality | 80 bands dark gradients | remotion.config.ts |

**People-aware crop (16:9 camera → 9:16 canvas)**

| key | value | what | why | used by |
|---|---|---|---|---|
| `peopleFps` | 4 | frames per second people_zones.py samples from the source | a person crossing the frame in ~1 s is seen 4 times; 10 s of 4K scan in ≈ 3 s | people_zones.py --fps |
| `peopleMinConf` | 0.3 | lowest Vision confidence for a person box | lower picks up posters and dark shapes | people_zones.py |
| `peopleFitMargin` | 0.9 | share of the crop width the chosen people may fill | a person touching both crop edges looks cut off | people_zones.py |
| `peopleNearArea` | 0.25 | a second person joins the crop only if their box is ≥ this share of the main one | small background crowd must not pull the crop away from the subject | people_zones.py |
| `peopleStickyArea` | 0.5 | the crop keeps its person while they are at least this share of the biggest one | a standing and a crouching person swap «biggest» every few frames; without stickiness the crop swings between them | people_zones.py |
| `peopleSmoothSec` | 0.8 | smoothing window of the per-frame crop centre (s) | one missed or wrong detection must not jerk the crop | people_zones.py |
| `peoplePanMin` | 0.05 | subject movement (share of the frame width) below which the crop is one fixed centre | a still shot that wobbles a few pixels reads as a shaky camera | people_zones.py |
| `peoplePanSpeed` | 0.35 | fastest crop pan (frame widths per second) | following a quick move faster than this looks like a glitch | people_zones.py |
| `peopleKeyEvery` | 0.5 | seconds between crop keyframes of a panning segment | enough to follow a walk, few enough for one ffmpeg expression per proxy | people_zones.py → make_proxies.py |

**Cut from the transcript (whole scenes)**

| key | value | what | why | used by |
|---|---|---|---|---|
| `snapBack` | 6.0 | a range that starts inside a sentence grows back to its start, at most this many seconds | Halloween vlog v2: «фразы обрезанные посередине» — a line that starts mid-thought reads as a mistake | cut_from_transcript.py |
| `snapFwd` | 4.5 | a range that ends inside a sentence grows forward to its end, at most this many seconds | same; forward is shorter — the punchline is usually already in | cut_from_transcript.py |
| `snapJoin` | 0.8 | a pause at least this long counts as a sentence edge even without .?!… (s) | Parakeet / Whisper often drop the full stop of spoken Russian | cut_from_transcript.py |
| `splitWindowSec` | 25 | ranges of one take further apart than this get their own alias proxy (s) | make_proxies encodes one window per clip: c0080 was 509 s of 4K for 70 s used | cut_from_transcript.py → make_proxies.py |

**Voice bus (two mics, levels, taming)**

| key | value | what | why | used by |
|---|---|---|---|---|
| `dualmicAtten` | 12 | DeepFilterNet noise reduction limit per lav channel (dB) | full strength left a hollow «из толчка» voice (A/B by ear, Halloween vlog) | dualmic.py |
| `dualmicHard` | 3.0 | automix exponent: channel gain ∝ power^(this/2) share | pushes the far mic's late copy of a voice down (comb filtering) | dualmic.py |
| `voiceTargetDb` | -22.0 | active speech level of every clip before the render's static gain (dBFS) | clips varied by up to 25 dB between cameras and mics | voice_mix.py |
| `voiceMaxGain` | 9.0 | most a quiet clip is lifted (dB) | +18 dB lifted mic hiss and DeepFilterNet artefacts into «a speaker about to blow» | voice_mix.py |
| `voiceSegLo` | -26.0 | a speech segment quieter than this is lifted (dBFS) | a whisper inside a loud clip | voice_mix.py |
| `voiceSegHi` | -19.0 | a speech segment louder than this is lowered (dBFS) | a shout inside a calm clip | voice_mix.py |
| `voiceSegMax` | 4.0 | most a single segment is moved (dB) | ±10 dB per segment pumped the noise floor | voice_mix.py |
| `ambDb` | -30.0 | camera sound under a picture beat ("amb"), active level (dBFS) | a dance or a ride in digital silence feels dead in a vlog without music | voice_mix.py |
| `rawDb` | -22.0 | camera sound instead of the voice ("raw") (dBFS) | DeepFilterNet swallowed a voice inside a costume | voice_mix.py |
| `tameOverDb` | 6.0 | compressor threshold above voiceTargetDb (dB) | a shout into a close lav sat 7 dB over the speech | voice_mix.py |
| `tameRatio` | 3.0 | compressor ratio above the threshold | gentle: the shout stays a shout | voice_mix.py |
| `tameCeilDb` | -12.0 | look-ahead limiter ceiling before the render gain (dBFS) | render.sh adds ≈ +9 dB; a 5 ms hard limiter on top crackled («колонки хрипят») | voice_mix.py |

**Picture: night lift, action pieces**

| key | value | what | why | used by |
|---|---|---|---|---|
| `nightStrong` | 20 | mean luma (0–255) below which a clip gets the strong shadow lift | night street clips came out of the LUT almost black on a phone | night_lift.py |
| `nightMedium` | 40 | … the medium lift | bar and porch clips: faces in the mud | night_lift.py |
| `nightMild` | 50 | … the mild lift; brighter clips are untouched | a global grade washed out the day clips | night_lift.py |
| `actionSlowmo` | 0.9 | a piece slower than this is retimed with motion-compensated interpolation (minterpolate) | the browser only repeats frames: 40 % slow motion of a 25 fps clip stuttered | actiongen.py |
| `actionPhraseBars` | 4 | bars per musical phrase on the reel grid (whips and big moments go on phrase starts) | Cudi «Pursuit Of Happiness (Nightmare)»: sections every 4 bars from the drop (frames 218/468/718/967/1217) | track_beats.py, actiongen.py |
