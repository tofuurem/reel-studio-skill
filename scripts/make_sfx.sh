#!/bin/zsh
# Small synthesized sounds (no licensing, no network): tick (a counter), pop (chip/badge/mark), done (a result lands),
# whoosh (chapter tag), softwhoosh (a scan or a slide), and for action reels hit (the drop / a punch), shutter (a photo
# moment, a freeze), rewind (a replay), riser (into a drop or a reveal), beep (low battery, a warning), powerdown (the end).
# whoosh / softwhoosh / pop / hit come in sfxVariants versions (whoosh, whoosh2, whoosh3 …): reelgen.sfx() cycles them, so
# two whooshes in a row are never the same sample («одинаковый вжух на каждый переход — странно», Halloween reel).
# Usage: make_sfx.sh <project-dir>   → reel/public/audio/sfx/*.wav
# tick / pop / done keep their fixed synthesis gains (the numbers.json levels were tuned on them); everything else is
# peak-normalised to −6 dBFS. Levels in Remotion come from numbers.json (sfx*: quiet, ≈ 20 LU under speech; hit is the
# one loud exception in an action reel).
set -e
D="$1/reel/public/audio/sfx"; mkdir -p "$D"
ff(){ ffmpeg -v error -nostdin -y "$@"; }
ST="aformat=sample_rates=48000:channel_layouts=stereo"
ff -f lavfi -i "anoisesrc=d=0.03:c=white:r=48000" -af "bandpass=f=3400:w=1200,afade=t=in:d=0.002,afade=t=out:st=0.008:d=0.022,volume=34dB,$ST" "$D/tick.wav"
ff -f lavfi -i "sine=f=880:d=0.18:r=48000" -af "volume=9dB,afade=t=in:d=0.01,afade=t=out:st=0.06:d=0.12,$ST" "$D/done.wav"
for v in "pop 620" "pop2 540" "pop3 710"; do set -- ${=v}
  ff -f lavfi -i "sine=f=${2}:d=0.14:r=48000" -af "volume=12dB,afade=t=in:d=0.004,afade=t=out:st=0.03:d=0.11,lowpass=f=2400,$ST" "$D/$1.wav"; done
# whooshes: pink noise through a band, swelled by a sin² envelope. Variants: name seed duration lowpass highpass
for v in "whoosh 7 0.55 3200 180" "whoosh2 13 0.48 2700 220" "whoosh3 19 0.62 3700 150" "softwhoosh 11 0.38 1800 250" "softwhoosh2 23 0.34 1500 300" "softwhoosh3 29 0.42 2100 220"; do
  set -- ${=v}; st=$(python3 -c "print(round($3-0.08,3))")
  ff -f lavfi -i "anoisesrc=d=${3}:c=pink:r=48000:seed=$2" -af "highpass=f=${5},lowpass=f=${4},volume='pow(sin(PI*t/${3}),2)':eval=frame,afade=t=out:st=$st:d=0.08,$ST" "$D/$1.raw.wav"
done
# hit: a pitch-dropping body (kick-like) + a short noise crack
for v in "hit 55 1" "hit2 48 2" "hit3 63 3"; do set -- ${=v}
  ff -f lavfi -i "aevalsrc='0.9*sin(2*PI*($2+110*exp(-t*28))*t)*exp(-t*6)+0.35*(random(${3})*2-1)*exp(-t*45)':d=0.7:s=48000" -af "lowpass=f=5000,afade=t=out:st=0.55:d=0.15,$ST" "$D/$1.raw.wav"; done
ff -f lavfi -i "aevalsrc='(random(5)*2-1)*(exp(-t*140)+0.8*gte(t,0.075)*exp(-(t-0.075)*140))':d=0.25:s=48000" -af "highpass=f=1400,lowpass=f=9000,$ST" "$D/shutter.raw.wav"
ff -f lavfi -i "aevalsrc='0.4*sin(2*PI*(700+500*sin(2*PI*2.2*t))*t)*(0.6+0.4*sin(2*PI*31*t))+0.15*(random(7)*2-1)':d=0.75:s=48000" -af "bandpass=f=1200:w=1600,afade=t=in:d=0.04,afade=t=out:st=0.6:d=0.15,$ST" "$D/rewind.raw.wav"
ff -f lavfi -i "anoisesrc=d=0.9:c=pink:r=48000:seed=31" -af "highpass=f=400,volume='pow(t/0.9,3)':eval=frame,afade=t=out:st=0.86:d=0.04,$ST" "$D/riser.raw.wav"
ff -f lavfi -i "sine=f=1760:d=0.12:r=48000" -af "afade=t=in:d=0.005,afade=t=out:st=0.08:d=0.04,$ST" "$D/beep.raw.wav"
ff -f lavfi -i "aevalsrc='0.8*sin(2*PI*(650*exp(-t*2.2))*t)*exp(-t*1.2)':d=1.0:s=48000" -af "afade=t=out:st=0.75:d=0.25,$ST" "$D/powerdown.raw.wav"
peak(){ ffmpeg -hide_banner -nostdin -i "$1" -af astats=measure_overall=Peak_level:measure_perchannel=0 -f null - 2>&1 | grep "Peak level" | tail -1 | sed 's/.*Peak level dB: //'; }
for r in "$D"/*.raw.wav; do f=${r%.raw.wav}.wav; g=$(python3 -c "print(round(-6-($(peak "$r")),2))"); ff -i "$r" -af "volume=${g}dB" "$f"; rm "$r"; done
for f in "$D"/*.wav; do printf "%-12s %s dB peak\n" "$(basename "$f" .wav)" "$(peak "$f")"; done
echo SFX_OK "$D"
