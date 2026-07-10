# Команды CLI

Внешние AI-CLI, которые вызывает `multi-review`. Базовый путь — лёгкий:
ревьюеры получают сгенерированный промпт с локальными путями и сами инспектируют
файлы. Не вставляй полный diff или склеенный полный артефакт в промпты Codex или
Claude.

> **Без переменных окружения.** Скрипты не читают конфигурацию из env. Всё, что
> нужно, передаётся позиционными аргументами или флагами. Рабочая директория
> всегда `/tmp/multi-review`, таймаут на ревьюера всегда 900 секунд.

В примерах ниже путь к скиллу — `~/.claude/skills/multi-review`. Подставь тот
путь, куда скилл установлен у тебя (например `~/.agents/skills/multi-review` для
Codex/Gemini/Cursor).

## Проверка доступности

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
for d in "$HOME"/.nvm/versions/node/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done
which codex 2>/dev/null && echo "codex: available" || echo "codex: not found"
which agy 2>/dev/null && echo "gemini (Antigravity agy): available" || echo "gemini (Antigravity agy): not found"
which claude 2>/dev/null && echo "claude: available" || echo "claude: not found"
which opencode 2>/dev/null && echo "glm (opencode): available" || echo "glm (opencode): not found"
```

Если `which claude` не находит бинарь, проверь также
`$HOME/.local/bin/claude` прежде чем отмечать Claude как недоступный.

## Сборка пакета ревью

Оба билдера пишут готовый к использованию `/tmp/multi-review/prompt.md`.

### Режим кода

Запускается из корня git-репозитория. Базовый ref — опциональный аргумент
(по умолчанию `main`):

```bash
# сравнить с main (значение по умолчанию):
~/.claude/skills/multi-review/scripts/build-code-review-pack.sh

# сравнить с другой веткой:
~/.claude/skills/multi-review/scripts/build-code-review-pack.sh develop
```

Режим охвата (scope) определяется автоматически: `branch`,
`branch-with-uncommitted` или `working-tree`. Выходные файлы включают
`mode.txt`, `project_root.txt`, `context_root.txt`, `scope_mode.txt`,
`base.txt`, `changed_files.txt`, `agents_excerpts.md`, `diff_size.txt` и
`prompt.md`. Если охваченный diff большой (> 50 КБ), билдер также пишет
`diff-trimmed.txt` как опциональный вспомогательный вход для Gemini. Перед
выходом он удаляет временный полный diff.

### Режим текста

Первый аргумент — тип контента, дальше — один или несколько путей к файлам:

```bash
~/.claude/skills/multi-review/scripts/build-text-review-pack.sh spec \
  /abs/path/to/spec.md /abs/path/to/related-notes.md
```

Тип контента — одно из: `article`, `spec`, `plan`, `prompt`, `legal`,
`marketing`, `generic`. Выходные файлы включают `mode.txt`, `content_type.txt`,
`files.txt`, `context_root.txt`, `prompt.md`, `artifact_size.txt` и
`artifact-excerpt.txt`.

Текстовый билдер не создаёт склеенный полный артефакт. `artifact-excerpt.txt`
ограничен 220 строками на файл и существует только как вспомогательный материал
для CLI, которые могут ненадёжно читать локальные файлы.

## Форма запуска

Каждый ревьюер запускается отдельным вызовом
`scripts/run-external-reviewer.sh`. Никогда не объединяй ревьюеров в одну
shell-строку.

```
run-external-reviewer.sh <имя-ревьюера> --cwd <директория> [--stdin <файл>] -- <команда...>
```

- Claude Code: один вызов инструмента `Bash` на ревьюера с
  `run_in_background: true` и `timeout: 900000`.
- Codex / shell: один shell-вызов на ревьюера; если поддерживаются фоновые
  задачи — запускай их независимо и дождись всех.

Обёртка пишет `<reviewer>.out`, `<reviewer>.status` и `<reviewer>.meta` в
`/tmp/multi-review` и завершается успешно, чтобы один упавший ревьюер не отменил
весь запуск. Флаг `--cwd` задаёт локальный корень контекста, из которого
стартует CLI.

## Codex

Используй `codex exec --cd`, чтобы Codex мог нативно инспектировать репозиторий
или директорию документа. `--skip-git-repo-check` сохраняет работу
текстовых ревью вне git-репозитория.

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH" && \
CONTEXT_ROOT=$(cat /tmp/multi-review/context_root.txt) && \
~/.claude/skills/multi-review/scripts/run-external-reviewer.sh codex --cwd "$CONTEXT_ROOT" -- \
  codex exec --skip-git-repo-check --cd "$CONTEXT_ROOT" "$(cat /tmp/multi-review/prompt.md)"
```

## Claude

Используй `--add-dir`, чтобы дать доступ на чтение к корню контекста.

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH" && \
CONTEXT_ROOT=$(cat /tmp/multi-review/context_root.txt) && \
~/.claude/skills/multi-review/scripts/run-external-reviewer.sh claude --cwd "$CONTEXT_ROOT" -- \
  claude --add-dir "$CONTEXT_ROOT" -p "$(cat /tmp/multi-review/prompt.md)"
```

## Gemini (через Antigravity CLI `agy`)

> Бесплатный вход старого `gemini` CLI (Gemini Code Assist for individuals) был
> отключён Google 18 июня 2026; все тарифы переехали на **Antigravity CLI**
> (бинарь `agy`, ставится по `references/install-clis.md`). Под капотом — те же
> модели Gemini, поэтому ревьюер по-прежнему называется «Gemini». Если на машине
> ещё есть рабочий старый `gemini` (например, корпоративная лицензия), можно
> подставить его вместо `agy` тем же образом.

`agy` получает доступ на чтение к корню контекста (`--add-dir`), как codex/claude,
и инспектирует файлы сам. `--sandbox` снимает зависание на запросе разрешений в
неинтерактивном режиме; read-only обеспечивается, как у claude, **инструкцией в
промпте** — жёсткого флага у agy нет (`--sandbox` ограничивает терминал, но не
правку файлов). `--print-timeout 850s` согласует внутренний лимит agy с обёрткой:
по умолчанию у него 5 минут, и на тяжёлом ревью он иначе обрывает себя сам с
`timed out waiting for response`. agy медленный — ~30–50с только на старт.

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH" && \
for d in "$HOME"/.nvm/versions/node/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done && \
CONTEXT_ROOT=$(cat /tmp/multi-review/context_root.txt) && \
~/.claude/skills/multi-review/scripts/run-external-reviewer.sh gemini --cwd "$CONTEXT_ROOT" -- \
  agy --add-dir "$CONTEXT_ROOT" --sandbox --print-timeout 850s \
  --log-file /tmp/multi-review/gemini-agy.log \
  -p "$(cat /tmp/multi-review/prompt.md)

Inspect the files in the workspace yourself (read-only). Output findings only; do NOT edit any file."
```

### Пустой вывод gemini — самодиагностика

Пустой `gemini.out` при exit 0 (`empty_output`/`no_answer`) имеет три разные
причины; лог `/tmp/multi-review/gemini-agy.log` их различает:

```bash
grep -aiE "RESOURCE_EXHAUSTED|quota|Stream completed" /tmp/multi-review/gemini-agy.log | tail -5
```

- `RESOURCE_EXHAUSTED` / `Individual quota reached` → квота исчерпана. agy
  «глотает» 429: пишет её в свой лог, а не в stderr. Пометь
  `gemini: quota exhausted (resets in ~Nh — из лога)` и **не** перезапускай.
- Лог кончается успешным `Stream completed`, а stdout пуст → известный баг agy
  (#76 — потеря stdout вне TTY). Перезапусти **один раз** через псевдо-TTY:
  та же команда, но `script -q /dev/null agy …` вместо `agy …`.
- Ничего из этого → одна повторная попытка как есть; снова пусто → пометь
  пропущенным.

## GLM (через OpenCode, модель `zai-coding-plan/glm-5.2`)

Четвёртый ревьюер — **GLM 5.2** от Z.ai, запускается через OpenCode read-only
(`--agent plan`: инспектирует файлы, ничего не правит). Как Codex и Claude, он
инспектирует репозиторий/документ локально из корня контекста, поэтому получает
тот же `prompt.md`, а не склеенный diff. Требуется установленный `opencode` и
авторизация подписки (`opencode auth login` → Z.AI Coding Plan).

Если установлен скилл `glm`, ревьюер GLM получает его research-инструменты
(веб-поиск / чтение страниц / `zread` по GitHub, плюс фолбек
tavily/firecrawl) — префикс с `GLM_CFG` переиспользует конфиг и
ключи из `~/.claude/skills/glm/scripts/` (единый источник правды; `.env`
git-ignored). Это позволяет GLM проверять заявления о версиях/API/библиотеках
по актуальным докам, а не по памяти. Без скилла `glm` строки ничего не
подключают — GLM ревьюит как раньше (память + локальные файлы).

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH" && \
for d in "$HOME"/.nvm/versions/node/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done && \
CONTEXT_ROOT=$(cat /tmp/multi-review/context_root.txt) && \
GLM_CFG="$HOME/.claude/skills/glm/scripts/opencode.json" && \
{ [ -f "$HOME/.claude/skills/glm/scripts/.env" ] && { set -a; . "$HOME/.claude/skills/glm/scripts/.env"; set +a; }; true; } && \
{ [ -f "$GLM_CFG" ] && export OPENCODE_CONFIG="$GLM_CFG"; true; } && \
~/.claude/skills/multi-review/scripts/run-external-reviewer.sh glm --cwd "$CONTEXT_ROOT" -- \
  opencode run --dir "$CONTEXT_ROOT" --agent plan --model zai-coding-plan/glm-5.2 \
  "$(cat /tmp/multi-review/prompt.md)

Web tools are OPTIONAL and NON-BLOCKING. You MAY use them to verify version/API/library claims against CURRENT docs and to check referenced upstream repos. Primary: the zai tools (web-search / web-reader / zread). If a zai tool errors, rate-limits (429), or is slow, SWITCH to the fallback tools — tavily (search/extract) and firecrawl (page reading) — instead of retrying it. If all web tools fail, continue from your own knowledge. Whatever happens with tools, you MUST end your turn with a complete review written in plain prose — never finish on a tool call without writing your findings."
```

> Подписка GLM Coding Plan работает только внутри поддерживаемых инструментов
> (OpenCode — один из них). Квоту считает Z.ai. Это китайский провайдер: **не
> подключай GLM-ревьюера на NDA-репозиториях с ПДн/секретами** — он читает файлы
> из корня контекста и отправляет их Z.ai. С research-инструментами к Z.ai
> уходят ещё и **поисковые запросы и читаемые URL/репозитории**, а через
> фолбек-инструменты — в Tavily и Firecrawl (США). Для чувствительных ревью
> пропусти GLM и оставь локальных ревьюеров.

## Обработка ошибок

| Ошибка | Действие |
| --- | --- |
| CLI не найден | Пропустить и записать: `[tool] not installed` |
| ошибка авторизации | Пропустить и записать: `[tool] authentication failed` |
| таймаут | Обёртка записывает `timeout`, затраченное время и частичный вывод |
| отсутствует stdin-файл | Обёртка записывает `stdin_missing`; пересобери входной файл и перезапусти |
| `empty_output` (статус обёртки) | Вывод пуст → `[tool] returned no findings`; для gemini сначала самодиагностика по логу (см. выше), для остальных — перезапустить один раз |
| `no_answer` (статус обёртки) | Вывод есть, но это только логи tool-call'ов без финального ревью — перезапустить ревьюера **один раз** с явным «отвечай по памяти, веб-тулы не используй», иначе пометить пропущенным |
| ненулевой код выхода | Захватить сводку stderr и продолжить |

Сбои внешних ревьюеров не блокирующие. Если успешных ревьюеров ноль —
остановись и сообщи пользователю.

> **Проверяй не только `.status`, но и содержимое `.out`.** Статус `ok` означает
> лишь код выхода 0 — обёртка сама ловит пустой вывод (`empty_output`) и
> чисто-логовый вывод (`no_answer`), но эвристика не идеальна: перед синтезом
> всё равно убедись, что в `.out` есть связный текст-ревью, а не только строки
> вида `⚙/✗/% <tool>`.

## Очистка

После финального отчёта:

```bash
rm -rf /tmp/multi-review/
```

Очистка — best-effort. Билдеры пересоздают директорию с нуля при следующем
запуске.
