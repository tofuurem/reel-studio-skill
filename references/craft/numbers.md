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
| `sfxReal` | 0.25 | a real recorded sound from sfx_find.py (Openverse), normalised to −20 LUFS — R.sfx(at, "real_<name>") | about as loud as the designed pops and whooshes at their levels | ui/Sfx.tsx, sfx_find.py |
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
| `wideMargin` | 54 | 16:9 canvas: margin of titles, HUDs and cards (px on 1920×1080) | 5 % of the frame; the Instagram safe zones do not apply to a horizontal video | face_zones.py (freeLeft / freeRight), project scenes |
| `wideBandTop` | 54 | 16:9 canvas: top of the card band | no reel header on a horizontal video | face_zones.py |
| `wideBandBottom` | 860 | 16:9 canvas: bottom of the card band | captions sit at y ≈ 880–960 (Captions.tsx LANDSCAPE) | face_zones.py |

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
| `snapJoin` | 0.8 | a pause at least this long counts as a sentence edge even without .?!… (s) | the recognizer often drops the full stop of spoken Russian | cut_from_transcript.py |
| `splitWindowSec` | 25 | ranges of one take further apart than this get their own alias proxy (s) | make_proxies encodes one window per clip: c0080 was 509 s of 4K for 70 s used | cut_from_transcript.py → make_proxies.py |

**Voice chain (voice_clean.py restores each source → dialogue.py builds and processes one dialogue stem → render.sh masters)**

| key | value | what | why | used by |
|---|---|---|---|---|
| `dualmicAtten` | 12 | DeepFilterNet noise reduction limit per lav channel (dB) | full strength left a hollow «из толчка» voice (A/B by ear, Halloween vlog) | dualmic.py |
| `dualmicHard` | 3.0 | automix exponent: channel gain ∝ power^(this/2) share | pushes the far mic's late copy of a voice down (comb filtering) | dualmic.py |
| `voiceTargetDb` | -22.0 | active speech level of every clip before the render's static gain (dBFS) | clips varied by up to 25 dB between cameras and mics | dialogue.py |
| `voiceMaxGain` | 9.0 | most a quiet clip is lifted (dB) | +18 dB lifted mic hiss and DeepFilterNet artefacts into «a speaker about to blow» | dialogue.py |
| `voiceSegLo` | -26.0 | a speech segment quieter than this is lifted (dBFS) | a whisper inside a loud clip | dialogue.py |
| `voiceSegHi` | -19.0 | a speech segment louder than this is lowered (dBFS) | a shout inside a calm clip | dialogue.py |
| `voiceSegMax` | 4.0 | most a single segment is moved (dB) | ±10 dB per segment pumped the noise floor | dialogue.py |
| `ambDb` | -30.0 | camera sound under a picture beat ("amb"), active level (dBFS) | a dance or a ride in digital silence feels dead in a vlog without music | dialogue.py |
| `ambRealtimeSpeed` | 1.5 | a picture beat sped up this much or more plays its camera sound in real time, not time-stretched | Halloween v5 (2026-11-09): rides at ×12–×15 played their wind time-stretched — a grinding texture the user heard as a broken frame | dialogue.py |
| `dropoutMs` | 40 | digital zeros inside a take longer than this (a radio-mic dropout, a voice window's edge) get room tone | Halloween v5: c0081 had 0.5 s of zeros in the source (lav dropout) — a hole of digital silence at the start of the beach scene | dialogue.py |
| `rawDb` | -22.0 | camera sound instead of the voice ("raw") (dBFS) | DeepFilterNet swallowed a voice inside a costume | dialogue.py |
| `declipMinSamples` | 20 | samples at |x| ≥ 0.985 before a source counts as clipped and gets adeclip | adeclip on clean audio still rewrote the samples (diff up to −34 dBFS, 2026-11-07 audit) | voice_clean.py, dualmic.py |
| `noiseTargetDb` | 48 | how far under the speech the residual noise should sit after cleanup (dB); DeepFilterNet's limit = this − the source SNR | full-strength DeepFilterNet turned every pause into digital silence (−69 dB) and cut −3 dB at 3.15 kHz out of the voice; a floor ≈ 48 dB down is inaudible under −16 LUFS speech and keeps the pauses natural | voice_clean.py |
| `dfnMinAtten` | 6 | smallest DeepFilterNet limit used (dB); a source with SNR ≥ noiseTargetDb skips DeepFilterNet | a quiet room needs no neural cleanup — every pass costs some timbre | voice_clean.py |
| `dfnMaxAtten` | 18 | largest DeepFilterNet limit (dB) | more than ≈ 18 dB pumps the noise between words and hollows the voice («из толчка», «underwater») | voice_clean.py |
| `cutXfadeMs` | 10 | equal-power crossfade on every jump cut of the dialogue (ms, centred on the cut, from source handles) | a hard switch of the waveform clicks; 2–10 ms is the dialogue-editing norm, longer smears consonants | dialogue.py |
| `joinXfadeMs` | 40 | linear crossfade where two segments continue the same take (a gain change, not a cut) |  | dialogue.py |
| `hpfHz` | 80 | high-pass of the voice (12 dB/oct) | rumble, wind and lav handling noise live under the voice's fundamental (85–180 Hz) | voicelib.py |
| `phaseRotHz` | 300 | centre of the phase rotator (4 all-pass sections, Q 0.7) after the high-pass | speech waveforms are lopsided (+0.92 / −0.71 on the 2026-11-05 reel): rotating the phase lowers the peaks ≈ 2.5 dB without changing the spectrum (broadcast voice processing), so the limiter works less | voicelib.py |
| `eqAmount` | 0.7 | share of the measured deviation from the target speech spectrum that the tonal EQ corrects | a partial match keeps the speaker's own timbre | voicelib.py |
| `eqMaxCut` | 4.0 | deepest mud (315 Hz) / box (900 Hz) cut (dB) |  | voicelib.py |
| `eqMaxBoost` | 4.0 | largest presence boost at 3.5 kHz (dB) | the DJI lav under clothing sat ~20 dB down at 2–5 kHz vs its 400–500 Hz peak: dull, «muffled» | voicelib.py |
| `eqMaxAir` | 3.0 | largest air boost (9 kHz shelf, dB) | more lifts the lav's hiss and the AAC artefacts of the camera track | voicelib.py |
| `compOverDb` | 4.0 | the one compressor's threshold over the leveled speech (dB over voiceTargetDb) | three compressors/limiters in a row squeezed LRA from 8.5 to 2.6 LU; +2 dB / 2.5:1 on 10 ms frames still gave 3.9 LU on the 2026-11-05 reel, +4 / 2:1 / 30 ms gives 5.0 | voicelib.py |
| `compRatio` | 2.0 | its ratio |  | voicelib.py |
| `compKneeDb` | 6.0 | its soft knee (dB) |  | voicelib.py |
| `compAttackMs` | 15.0 | its attack (ms) |  | voicelib.py |
| `compReleaseMs` | 200.0 | its release (ms) |  | voicelib.py |
| `compWindowMs` | 30 | its RMS detector window (ms) | 10 ms frames compressed inside syllables | voicelib.py |
| `deessOverDb` | -6.0 | de-esser acts where the 6.5 kHz band is louder than the speech level + this (dB) and dominates the frame | a dark lav needs none; a bright one gets 2–4 dB on each «с/ш» | voicelib.py |
| `deessMaxDb` | 6.0 | deepest de-esser cut (dB) |  | voicelib.py |
| `stemLufs` | -24.0 | integrated loudness of the finished dialogue stem (reel/public/audio/dialogue.wav) | the music bed and SFX levels were tuned against speech at about this level; render.sh lifts the whole mix to targetLufs | dialogue.py |
| `stemPeakDb` | -10.0 | look-ahead peak ceiling of the stem (dBFS) | speech off a lav peaks 18–23 dB over its loudness; at −12 the limiter worked 31–66 % of the time (audible), at −10 ≈ 12 % with ≤ 5 dB on the rare peaks; render.sh adds ≈ +8 dB and its true-peak limiter catches the rest | voicelib.py |
| `truePeakDb` | -1.5 | master true-peak ceiling (dBTP; 4× oversampled limiter in render.sh) | sample-peak limiting let inter-sample peaks through; AAC adds ≈ 0.5 dB more | render.sh |
| `aacBitrate` | 320k | final AAC bitrate (the only lossy encode of the sound; Remotion renders PCM) | proxies 192k → Remotion 320k → final 192k = three extra generations on top of the camera's AAC | render.sh |
| `lraMax` | 9.0 | audio_qa warns above this loudness range of the final mix (LU) |  | audio_qa.py |
| `lraMin` | 3.0 | audio_qa warns below this (LU): over-compressed | the 2026-11-05 reel shipped at 2.6 LU | audio_qa.py |
| `expBelowDb` | 22.0 | optional expander (work/voice_tune.json «expander»): frames this far under the speech level are pulled down (dB) | a podcast edit ep. 1 (2026-11-13): room tails after words were the «эхо» the user heard; OFF unless the project asks | voicelib.py |
| `expRatio` | 2.5 | its downward ratio (1:x) |  | voicelib.py |
| `expRangeDb` | 15.0 | its deepest reduction (dB) | deeper sounded gated | voicelib.py |
| `notchMinDb` | 3.0 | a resonance (1/12-octave bump over the 1-octave trend) this high gets a narrow cut with «notches»: "auto" (dB) | a podcast edit: one host's voice boomed on 108 / 214 / 320 Hz (ep. 1) and 110 / 219 / 320 Hz (ep. 2) — narrow notches beat the broad 315 Hz cut | voicelib.py (notch_plan), voice_probe.py |
| `notchMaxCut` | 4.5 | deepest automatic notch (dB, Q 3) | ep. 1's approved host EQ: −4.5 at 108 Hz | voicelib.py (notch_plan), voice_probe.py |
| `levelerAmount` | 0.6 | optional slow leveler inside a take (work/voice_tune.json «leveler»): share of the way to voiceTargetDb | a podcast edit ep. 1: a voice that wandered 7 dB (distance to the mic) LRA 9.9 → 5.8; OFF unless the project asks | dialogue.py, eq_test.py |
| `levelerMaxDb` | 5.0 | its largest move (dB) | more lifted breaths and room | dialogue.py, eq_test.py |

**Picture: night lift, action pieces**

| key | value | what | why | used by |
|---|---|---|---|---|
| `nightStrong` | 20 | mean luma (0–255) below which a clip gets the strong shadow lift | night street clips came out of the LUT almost black on a phone | night_lift.py |
| `nightMedium` | 40 | … the medium lift | bar and porch clips: faces in the mud | night_lift.py |
| `nightMild` | 50 | … the mild lift; brighter clips are untouched | a global grade washed out the day clips | night_lift.py |
| `actionSlowmo` | 0.9 | a piece slower than this is retimed with motion-compensated interpolation (minterpolate) | the browser only repeats frames: 40 % slow motion of a 25 fps clip stuttered | actiongen.py |
| `actionPhraseBars` | 4 | bars per musical phrase on the reel grid (whips and big moments go on phrase starts) | Cudi «Pursuit Of Happiness (Nightmare)»: sections every 4 bars from the drop (frames 218/468/718/967/1217) | track_beats.py, actiongen.py |

**Motion timing**

| key | value | what | why | used by |
|---|---|---|---|---|
| `entranceMaxFrames` | 24 | longest entrance of one element (frames); a longer build is a stagger of several elements | HyperFrames motion doctrine (2026-11-08): a single slow element reads as lag | motion-design.md «Seams», blocks/* |
| `staggerMaxFrames` | 15 | total stagger of one group of items (first start → last start) | a longer cascade makes the viewer wait for the last item | motion-design.md, blocks/*, ChipRow / RepoCard lists |
| `exitShare` | 0.75 | an exit lasts this share of the matching entrance | leaving is faster than arriving; the eye has already read it | motion-design.md |
| `payoffPauseMin` | 9 | shortest still beat between an action and its result (frames) | the dramatic comma: count-up ends → hold → the stamp lands; straight to the result loses it | motion-design.md «Seams» |
| `payoffPauseMax` | 22 | longest still beat before a payoff (frames) | longer reads as a stall | motion-design.md «Seams» |
| `transitionKindsMax` | 3 | kinds of scene transition in one reel (dissolve, hand-off, whip …), repeated | a new transition per chapter reads as a template showcase | motion-design.md «Seams» |

**Seams**

| key | value | what | why | used by |
|---|---|---|---|---|
| `seamFxPerMin` | 3 | effect seams (anything but a dissolve / hard cut) per minute of a calm reel, at most | the user, 2026-11-09: «вжух на каждое действие» makes a terrible video — most cuts stay plain | gen_timeline.py budget check, transitions.md |
| `seamFxGapCuts` | 3 | plain cuts between two effect seams, at least (calm reel) | alternation: an effect only reads against plain cuts around it | gen_timeline.py budget check |
| `seamFxGapShots` | 4 | plain shots between two effect moments in an action reel (whip, crash, rgb, stutter, bump), at least — the drop and phrase starts excepted | same rule at action tempo | actiongen.py budget check |
| `seamRepeatSec` | 20 | the same seam kind does not come back within this many seconds | a repeated trick turns into a template | gen_timeline.py, actiongen.py |
| `seamPushOut` | 8 | push seam: frames the outgoing clip accelerates into the zoom before the cut | video-shotcraft crash-zoom card: over 10 f it reads as an ordinary push | Clip.tsx |
| `seamPushScale` | 1.16 | push seam: outgoing scale multiplier at the cut | enough to read as a move, the zoom blur hides the jump | Clip.tsx |
| `seamPushIn` | 12 | push seam: frames the incoming clip keeps pushing in while the blur clears | the camera keeps the same direction across the cut (motion-design.md «sign of a zoom») | Clip.tsx |
| `seamPushGrow` | 0.05 | push seam: incoming scale growth over seamPushIn | forward momentum that settles | Clip.tsx |
| `seamPushBlur` | 44 | push seam: radial zoom blur at the cut (px, @remotion/effects zoomBlur) | tested on a 2K proxy 2026-11-09: 40–50 hides the cut, 70+ smears the face | Clip.tsx |
| `seamBlurOut` | 8 | blur seam: frames the outgoing clip defocuses before the cut | motionmaxxing blur-matched cut: 3–8 f ramp | Clip.tsx |
| `seamBlurIn` | 9 | blur seam: frames the incoming clip resolves | ≈ 8 f | Clip.tsx |
| `seamBlurPx` | 18 | blur seam: defocus at the cut (px on the 1080 canvas) | both sides meet at the same blur | Clip.tsx |
| `seamLeakOut` | 22 | leak seam: frames the warm light builds before the cut (ease-in) | hidden cut through a light leak, slower in than out | Clip.tsx |
| `seamLeakIn` | 34 | leak seam: frames the light clears after the cut (ease-out) |  | Clip.tsx |
| `seamLeakPeak` | 0.5 | leak seam: peak opacity of the warm gradients | the user: no super-bright transitions — @remotion/effects lightLeak fills the frame solid yellow at its peak, not used | Clip.tsx |
| `seamLeakLift` | 0.3 | leak seam: brightness lift of the picture at the peak | with contrast −20 %, saturation −15 % it reads as light, not a white flash | Clip.tsx |
| `seamWipeFrames` | 14 | wipe seam: frames of a soft wipe in the reel's current (right → left) |  | Clip.tsx, seams.py |
| `seamWipeFeather` | 0.16 | wipe seam: soft edge width (share of the canvas width) | a hard edge looks like a slideshow | Clip.tsx |
| `seamMatchFrames` | 18 | match seam: frames the incoming clip eases from the matched framing back to its own | the head lands where the previous head was, then the frame settles | Clip.tsx, seams.py |
| `seamMatchMaxScale` | 1.45 | match seam: largest zoom used to line the heads up (beyond it → a plain dissolve, WARNING) | 2K proxies soften beyond ≈ 1.5 | seams.py |
| `shakePx` | 15 | action shake amplitude at the hit (px) | video-shotcraft: > 20 px reads as a glitch; was 22 px linear | Action.tsx |
| `shakeTau` | 1.8 | action shake decay constant (frames, e^(−t/τ)); gone in ≈ 6 f |  | Action.tsx |
| `rgbPx` | 10 | action RGB split at its peak (px on the 1080 canvas) | short and on a hit only; a constant split reads as a broken screen | Action.tsx |
| `rgbFrames` | 4 | action RGB split length (frames) |  | Action.tsx |
| `rgbMax` | 2 | RGB splits per reel, at most |  | actiongen.py budget check |
| `bumpScale` | 0.05 | bump cut: the shot pushes in by this much over bumpFrames on the beat | Remotion pushCut idea: a hard cut with a scale pulse | Action.tsx |
| `bumpFrames` | 7 | bump cut length (frames) |  | Action.tsx |
| `bumpFlash` | 0.18 | bump cut: white flash peak (2 frames); 0 = none | ≤ 0.2: a hint, not a strobe | Action.tsx |
| `crashMax` | 2 | crash zooms per reel, at most |  | actiongen.py budget check |
| `impactMax` | 3 | full-frame impacts (flash ≥ 0.3 or shake) per reel, at most | video-shotcraft beat-sync: 3 hits, ≥ 16 beats apart | actiongen.py budget check |
| `impactGapBeats` | 16 | beats between two full-frame impacts, at least |  | actiongen.py budget check |
| `stutterStep` | 3 | stutter into a drop: the picture advances every N frames | each step must move visibly or it reads as dropped frames | Action.tsx |
| `bridgeTail` | 0.8 | L-cut: seconds the outgoing scene's own sound carries under the next picture (scene changes, bridge option) | OpenMontage edit-director: 0.5–1.5 s on the hardest seams | dialogue.py |
| `bridgeLead` | 0.4 | J-cut: seconds the incoming scene's own sound starts before its picture |  | dialogue.py |
