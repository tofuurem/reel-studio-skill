# reel-studio

Скилл для [Claude Code](https://claude.com/claude-code): монтирует рилсы и влоги в [Remotion](https://www.remotion.dev) из черновика CapCut, сырых дублей, закадра со скринкастами или картинок. Чистит голос, делает субтитры и графику, рендерит в 2K. Умеет экшн-рилсы под бит трека и длинные влоги с двух камер.

## Установка

Вставь в Claude Code:

```text
Установи скилл reel-studio: склонируй https://github.com/tofuurem/reel-studio-skill в ~/.claude/skills/reel-studio, сначала спроси меня, ставить ли генерацию обложек через Codex CLI и звуковой модуль earshot (≈ 1,6 ГБ: живые звуковые эффекты вместо синтезированных и проверка звука в готовом ролике), затем запусти python3 -I ~/.claude/skills/reel-studio/scripts/deps.py --install (с --with covers и/или --with sound — что я выберу) и доведи до DEPS_OK. То, что требует пароля, дай мне выполнить самому.
```

Или вручную (на чистом Маке сначала `xcode-select --install`, чтобы появились `git` и `python3`):

```bash
git clone https://github.com/tofuurem/reel-studio-skill ~/.claude/skills/reel-studio
python3 -I ~/.claude/skills/reel-studio/scripts/deps.py --install
```

Проект создаётся в папке, где открыт Claude Code. Перед созданием Claude спросит, туда ли. Постоянную папку для проектов можно задать в `REEL_STUDIO_PROJECTS`.

`deps.py` без флагов только проверяет и пишет, чего не хватает. С `--install` ставит ffmpeg, node, uv и Python-окружения, при этом сам определяет систему. С `--with covers` ставит ещё Codex CLI для сгенерированных обложек: для него нужен вход в ChatGPT через `codex login`. С `--with sound` — [earshot](https://github.com/Leonxlnx/earshot) (≈ 1,6 ГБ, работает на процессоре): звуковые эффекты из его библиотеки вместо синтезированных, подбор настоящих звуков с [Openverse](https://openverse.org) по звучанию и проверка звука готового ролика «на слух». Без него Openverse-поиск тоже работает, только без ранжирования. Для расшифровки используется то, что есть на машине: Parakeet, если установлено приложение [Handy](https://handy.computer), иначе Whisper.

## Обновление

Вставь в Claude Code или Codex:

```text
Обнови скилл reel-studio: найди, куда он установлен (обычно ~/.claude/skills/reel-studio), сделай там git pull и коротко расскажи, что изменилось. Если в папке есть мои локальные правки или pull конфликтует, ничего не затирай и сначала спроси меня. Затем запусти python3 -I <папка скилла>/scripts/deps.py: если в новой версии появились необязательные части, которых у меня нет (например --with sound), спроси, ставить ли их; потом deps.py --install с выбранными --with и доведи до DEPS_OK — новая версия может требовать новых инструментов. То, что требует пароля, дай мне выполнить самому.
```

Или вручную: `git -C ~/.claude/skills/reel-studio pull`, затем `python3 -I ~/.claude/skills/reel-studio/scripts/deps.py --install`.

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
