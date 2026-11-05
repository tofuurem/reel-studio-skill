# CapCut (macOS) draft format — what matters for the import

Location: `~/Movies/CapCut/User Data/Projects/com.lveditor.draft/<draft name>/`
- `draft_info.json` — the timeline (also `draft_info.json.bak`, `template-2.tmp` copies).
- `draft_meta_info.json` — material list with original paths.
- `audio_record/*.aac` — voiceovers recorded inside CapCut (`##_draftpath_placeholder_<id>_##/audio_record/...` in paths).
- `Resources/audioAlg/*_human.wav` — CapCut's own voice-isolation outputs for individual segments (partial, not reusable).
- `../root_meta_info.json` — `all_draft_store[]` with `draft_name`, `tm_draft_modified` (µs), `tm_duration`.

Inside `draft_info.json` (all times are **microseconds**):
- `canvas_config.width/height` (1080x1920 for reels), `fps`, `duration`.
- `materials.videos[]` — `id`, `type` (`video`|`photo`), `path`, `material_name`, `duration`, `crop`.
- `materials.audios[]` — `type` (`record`|`music`|`extract`), `path`, `name`.
- `materials.texts[]` — `content` is a JSON string with `text`.
- `materials.effects[]` — `type: "lut"` with `name` ending in `.cube` = colour LUT applied per segment.
- `materials.speeds[]` — `speed` (1.0 normal), referenced from segments via `extra_material_refs`.
- `materials.transitions[]`, `materials.material_animations[]` (in/out animations like "Chroma Wave"), `materials.audio_fades[]`.
- `tracks[]` — `type` (`video`|`audio`|`text`|`sticker`|`effect`), `segments[]`:
  - `material_id`, `target_timerange{start,duration}` (timeline), `source_timerange{start,duration}` (source),
  - `speed`, `volume` (0.001 = muted sliver), `clip{scale,transform,rotation,flip}`, `extra_material_refs[]`, `common_keyframes[]` (non-empty = animated zoom/pan).
- The first `video` track is the main cut; later video tracks hold overlays (screenshots, PiP). `photo` segments on overlay tracks = the user's planned inserts: keep their timing even if you replace the picture.

`scripts/capcut_export.py` normalises all of this into `work/cutlist.json` + `work/draft_summary.md`; per segment it keeps `srcDur` (source seconds, ≠ `dur` when the speed changed), `volume`, `transform {scale, scaleY, x, y, rotation, flipH}`, `crop {x0, y0, x1, y1}` and `keyframes: true` when the framing is animated. Frames are computed at the composition fps (30): `from = round(tlStart*fps)`, `trimBefore = round(srcStart*fps)`.
