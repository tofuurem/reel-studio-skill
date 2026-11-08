# LUTs

Camera LUTs (`.cube`) are not committed: they belong to the camera makers. `scripts/setup_env.sh` copies every `.cube`
from this folder, `~/Downloads` and CapCut's LUT folder into `~/.cache/reel-studio/luts/`.

Only log footage needs one (DJI D-Log, Sony S-Log, Panasonic V-Log …): download your camera's official LUT, drop it here or in
`~/Downloads`, and pass it with `--lut` (`--lut-map` for mixed cameras). Rec.709 and phone footage need none.

DJI Osmo Pocket 4 / 4P, Action 5 Pro and Action 4 write their colour profile into every file (the `djmd` track), so the
skill knows by itself which clips are Normal (no LUT), D-Log or D-Log M, and picks the matching cube when it is installed
under DJI's own file name — `DJI OSMO Pocket 4P D-Log to Rec.709 V2.0 size33.cube`, `DJI OSMO Action 5 Pro D-Log M to
Rec.709 V1.cube`, `DJI OSMO Action 4 D-Log M to Rec.709 V1.cube`. A log clip whose cube is missing is reported as
`NO LUT FOUND`; `python3 -I scripts/common.py lut <clip>` shows the choice and why.
