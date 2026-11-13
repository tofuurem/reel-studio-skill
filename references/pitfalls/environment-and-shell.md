# Environment and shell

Traps of zsh, background jobs, disks and external volumes — mostly in ad-hoc commands.

- **zsh modifiers inside strings**: `$H:flags` is read as `:f` (ffmpeg saw `1920ags`), `"$n:layout"` as `:l` → write `${W}:${H}`, `${n}:layout`.
- **A zsh glob that matches nothing aborts the whole command line** (`no matches found`), even behind `&&` and under `set -e` — an `rm -f dir/*.mp4` once stopped the re-encode after it → `setopt null_glob` or arrays `g=(…(N))`. Under `null_glob`, `ls <glob with no match>` lists the current folder: test new globs.
- **`pgrep -f "a\|b"` is not alternation** → the waiter exits at once while the job runs. One literal pattern: `pgrep -f "work/prep.sh"`.
- **After `pkill`-ing a background job to patch a script** → restart it explicitly and confirm with `pgrep -fl`.
- **System disk near full** → `df -h /` before proxies (`make_proxies.py` warns). Safe to reclaim: `uv cache clean`, `npm cache clean --force`, the session scratchpad, `work/voice/in`, `work/stills`, `work/faces`. Never wipe `~/Library/Caches` or the user's renders without asking. Ad-hoc `npx remotion` runs leave bundles in `$TMPDIR`: `rm -rf "$TMPDIR"/remotion-webpack-bundle-* "$TMPDIR"/react-motion-render*`.
- **Remotion versions** → never `create-video@latest` or an unpinned `npm i @remotion/…`; `scaffold.sh` pins `REMOTION_VERSION`. tsc and renders wait for `SCAFFOLD_OK`.
- **A `coverage/` folder in the cwd breaks numba tools** (`module 'coverage' has no attribute 'types'`) → `cd <project>` and run Python with `-I`.
- **`python3` without `-I` on the iCloud Desktop fails with «Interrupted system call»** → always `-I`, or `cd` elsewhere for snippets.
- **External exFAT volume** → never run `npm` inside `reel/` (≈ 24 k files × 1 MB clusters; npm replaces the `node_modules` link with a real folder).
- **AppleDouble `._*` sidecars** sit next to every file on exFAT / network volumes, also files written by ffmpeg or Python; shell globs skip them, `os.listdir` does not (a copy loop copied the 4 KB sidecar and skipped the real file; frame lists shifted) → every new loop over a folder skips names starting with `.` (or uses `glob("*.ext")`) and checks copied sizes.
- **`rm -rf` on a folder at the top level of a mounted drive is refused** by Claude Code → make test folders deeper (`/Volumes/<drive>/<folder>/…`) or ask the user.
- **yt-dlp `SSL: UNEXPECTED_EOF` while curl reaches the site** → the connection is filtered; retries do not help: a VPN does, or ask the user for the file.
