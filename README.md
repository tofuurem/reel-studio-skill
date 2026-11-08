# reel-studio

Скилл для [Claude Code](https://claude.com/claude-code): монтирует рилсы и влоги в [Remotion](https://www.remotion.dev) из черновика CapCut, сырых дублей, закадра со скринкастами или картинок. Чистит голос, делает субтитры и графику, рендерит в 2K. Умеет экшн-рилсы под бит трека и длинные влоги с двух камер.

## Установка

Вставь в Claude Code:

```text
Установи скилл reel-studio: склонируй https://github.com/tofuurem/reel-studio-skill в ~/.claude/skills/reel-studio, сначала спроси меня, ставить ли генерацию обложек через Codex CLI, затем запусти python3 -I ~/.claude/skills/reel-studio/scripts/deps.py --install (с --with covers, если я соглашусь) и доведи до DEPS_OK. То, что требует пароля, дай мне выполнить самому.
```

Или вручную (на чистом Маке сначала `xcode-select --install`, чтобы появились `git` и `python3`):

```bash
git clone https://github.com/tofuurem/reel-studio-skill ~/.claude/skills/reel-studio
python3 -I ~/.claude/skills/reel-studio/scripts/deps.py --install
```

Обновить уже установленный скилл (подтягивает новую версию и доставляет то, что ей нужно, например yt-dlp):

```bash
git -C ~/.claude/skills/reel-studio pull && python3 -I ~/.claude/skills/reel-studio/scripts/deps.py --install
```

Проект создаётся в папке, где открыт Claude Code. Перед созданием Claude спросит, туда ли. Постоянную папку для проектов можно задать в `REEL_STUDIO_PROJECTS`.

`deps.py` без флагов только проверяет и пишет, чего не хватает. С `--install` ставит ffmpeg, node, uv и Python-окружения, при этом сам определяет систему. С `--with covers` ставит ещё Codex CLI для сгенерированных обложек: для него нужен вход в ChatGPT через `codex login`. Для расшифровки используется то, что есть на машине: Parakeet, если установлено приложение [Handy](https://handy.computer), иначе Whisper.

## Платформы

| система | что работает |
|---|---|
| macOS, Apple Silicon | всё |
| macOS, Intel | всё, но Whisper без MLX медленнее, Parakeet нет |
| Linux, WSL2 | нет Apple Vision: кадрирования по людям, титра за человеком, вырезанных обложек |
| Windows | только через WSL2 |

Remotion бесплатен для частных лиц и маленьких команд, компаниям нужна [лицензия](https://www.remotion.dev/license).

LUT камеры в репозиторий не входит, подробности в [assets/luts](assets/luts/README.md).

## Использование

Попроси Claude Code своими словами: «собери рилс из этих дублей», «вот черновик в капкате», «экшн-рилс под трек». Основная инструкция скилла в [SKILL.md](SKILL.md).
