# LUTs

Camera LUTs (`.cube`) are not committed: they belong to the camera makers. `scripts/setup_env.sh` copies every `.cube`
from this folder, `~/Downloads` and CapCut's LUT folder into `~/.cache/reel-studio/luts/`.

Only log footage needs one (DJI D-Log, Sony S-Log, Panasonic V-Log …): download your camera's official LUT, drop it here or in
`~/Downloads`, and pass it with `--lut` (`--lut-map` for mixed cameras). Rec.709 and phone footage need none.
