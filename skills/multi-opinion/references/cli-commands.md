# Команды CLI (советники)

Внешние AI-CLI, которых `multi-opinion` опрашивает как **совет**: каждый
независимо изучает проблему и код (read-only) и предлагает подходы к решению.
Это **не** ревью артефакта — модели ничего не правят.

> **Без переменных окружения.** Рабочая директория всегда `/tmp/multi-opinion`,
> таймаут на советника всегда 900 секунд. Команды стартуют из корня контекста
> (`context_root.txt`), чтобы советник мог инспектировать репозиторий локально.

Путь к скиллу в примерах — `~/.claude/skills/multi-opinion`. Подставь свой.

## Проверка доступности

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
for d in "$HOME"/.nvm/versions/node/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done
which codex    2>/dev/null && echo "codex: available"    || echo "codex: not found"
which agy      2>/dev/null && echo "gemini (agy): available" || echo "gemini (agy): not found"
which claude   2>/dev/null && echo "claude: available"   || echo "claude: not found"
which opencode 2>/dev/null && echo "glm (opencode): available" || echo "glm (opencode): not found"
```

Должен быть доступен хотя бы один. Пропусти и отметь отсутствующих.

## Сборка пакета проблемы

Оркестратор сам пишет файл с контекстом проблемы (что решаем, что уже
пробовали, что работает / что нет, ограничения, какие файлы важны), затем:

```bash
# context_root — каталог с кодом, который советники смотрят read-only ("-" если кода нет)
~/.claude/skills/multi-opinion/scripts/build-opinion-pack.sh /abs/path/to/repo /tmp/mo-problem.md
```

Билдер пишет `/tmp/multi-opinion/prompt.md` (преамбула советника + контекст
проблемы), `problem.md` и `context_root.txt`, и редактирует распространённые
шаблоны секретов. В no-code режиме (`-`) он также кладёт копии
`problem.md`/`prompt.md` **внутрь** папки `no-code`: песочница GLM (OpenCode)
жёстко отклоняет чтение за пределами выданной папки, и без этих копий GLM
сжигал ход на авто-отказах вместо ответа.

## Форма запуска

Каждый советник — отдельный вызов `scripts/run-advisor.sh`. Никогда не объединяй
советников в одну shell-строку (один отказ отменит остальных). В Claude Code:
один вызов `Bash` на советника, `run_in_background: true`, `timeout: 900000`.

Перед каждым запуском выставь PATH:

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
for d in "$HOME"/.nvm/versions/node/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done
ROOT=$(cat /tmp/multi-opinion/context_root.txt)
```

### Codex (GPT-5.5, read-only)

`-o` пишет только финальное сообщение; поток событий уходит в `/dev/null`,
поэтому обёртка ловит чистый ответ. Промпт подаётся через stdin.

```bash
~/.claude/skills/multi-opinion/scripts/run-advisor.sh codex --cwd "$ROOT" -- \
  sh -c 'OUT=$(mktemp); codex exec --skip-git-repo-check -C "$0" -m gpt-5.5 -c "model_reasoning_effort=\"xhigh\"" -s read-only -o "$OUT" - < /tmp/multi-opinion/prompt.md > /dev/null; cat "$OUT"; rm -f "$OUT"' "$ROOT"
```

### Claude (read-only — обеспечивается только промптом)

> В отличие от codex (sandbox) и glm (агент `plan`), у claude нет жёсткого
> read-only-флага: запрет правок задаётся инструкцией в `prompt.md`. Для совета
> этого достаточно (ревьюим внешний код), но это не песочница.

```bash
~/.claude/skills/multi-opinion/scripts/run-advisor.sh claude --cwd "$ROOT" -- \
  claude --add-dir "$ROOT" -p "$(cat /tmp/multi-opinion/prompt.md)"
```

### GLM 5.2 (через OpenCode, read-only `plan` agent)

Если установлен скилл `glm`, советник GLM получает его research-инструменты
(веб-поиск / чтение страниц / `zread` по GitHub, плюс фолбек
tavily/firecrawl): префикс ниже переиспользует конфиг и ключи из
`~/.claude/skills/glm/scripts/` — единый источник правды (`.env` там
git-ignored). Без скилла `glm` строки ничего не подключают, и GLM просто
отрабатывает по памяти и локальным файлам (как раньше).

```bash
GLM_CFG="$HOME/.claude/skills/glm/scripts/opencode.json"
[ -f "$HOME/.claude/skills/glm/scripts/.env" ] && { set -a; . "$HOME/.claude/skills/glm/scripts/.env"; set +a; }
[ -f "$GLM_CFG" ] && export OPENCODE_CONFIG="$GLM_CFG"
~/.claude/skills/multi-opinion/scripts/run-advisor.sh glm --cwd "$ROOT" -- \
  opencode run --dir "$ROOT" --agent plan --model zai-coding-plan/glm-5.2 \
  "$(cat /tmp/multi-opinion/prompt.md)

Web tools are OPTIONAL and NON-BLOCKING. You MAY use them to ground proposals in CURRENT docs and real upstream repos. Primary: the zai tools (web-search / web-reader / zread). If a zai tool errors, rate-limits (429), or is slow, SWITCH to the fallback tools — tavily (search/extract) and firecrawl (page reading) — instead of retrying it. If all web tools fail, continue from your own knowledge. Whatever happens with tools, you MUST end your turn with a complete final proposal written in plain prose — never finish on a tool call without writing the answer."
```

> GLM работает на Z.ai (китайский провайдер): к нему уходят файлы из корня
> контекста, а с research-инструментами — ещё и поисковые запросы и читаемые
> URL/репозитории. Фолбек-инструменты шлют поисковые запросы/URL в Tavily и
> Firecrawl (США). Не подключай GLM-советника на чувствительных проблемах с
> ПДн/секретами; для таких случаев пропусти его.

### Gemini (через Antigravity `agy`, read-only по промпту)

`agy` получает доступ на чтение к корню контекста (`--add-dir "$ROOT"`), как
codex/claude/glm, и инспектирует код сам. `--sandbox` снимает зависание на
запросе разрешений в неинтерактивном режиме. Read-only обеспечивается, как у
claude, **инструкцией в промпте** — жёсткого флага у agy нет (`--sandbox`
ограничивает терминал, но не правку файлов). `--print-timeout 850s` согласует
внутренний лимит agy с обёрткой: по умолчанию у него всего 5 минут, и на тяжёлой
задаче он иначе обрывает себя сам с `timed out waiting for response`. agy
медленный — ~30–50с уходит только на старт.

```bash
~/.claude/skills/multi-opinion/scripts/run-advisor.sh gemini --cwd "$ROOT" -- \
  agy --add-dir "$ROOT" --sandbox --print-timeout 850s \
  --log-file /tmp/multi-opinion/gemini-agy.log \
  -p "$(cat /tmp/multi-opinion/prompt.md)

Inspect the code in the workspace READ-ONLY to ground your proposals. Do NOT edit, create, or delete any file."
```

#### Пустой вывод gemini — самодиагностика

Пустой `gemini.out` при exit 0 (`empty_output`/`no_answer`) имеет три разные
причины; лог `/tmp/multi-opinion/gemini-agy.log` их различает:

```bash
grep -aiE "RESOURCE_EXHAUSTED|quota|Stream completed" /tmp/multi-opinion/gemini-agy.log | tail -5
```

- `RESOURCE_EXHAUSTED` / `Individual quota reached` → квота исчерпана. agy
  «глотает» 429: пишет её в свой лог, а не в stderr. Пометь
  `gemini: quota exhausted (resets in ~Nh — из лога)` и **не** перезапускай.
- Лог кончается успешным `Stream completed`, а stdout пуст → известный баг agy
  (#76 — потеря stdout вне TTY). Перезапусти **один раз** через псевдо-TTY:
  та же команда, но `script -q /dev/null agy …` вместо `agy …`.
- Ничего из этого → одна повторная попытка как есть; снова пусто → пометь
  пропущенным.

## Сбор результатов

После завершения всех — читай `/tmp/multi-opinion/<advisor>.out` и `.status`
каждого, затем синтезируй по `references/synthesize.md`.

| Ошибка | Действие |
| --- | --- |
| CLI не найден | Пропустить: `[tool] not installed` |
| ошибка авторизации | Пропустить: `[tool] authentication failed` |
| таймаут | Обёртка пишет `timeout` + частичный вывод |
| `empty_output` (статус обёртки) | Вывод пуст → `[tool] returned no proposal`; для gemini сначала самодиагностика по логу (см. выше), для остальных — перезапустить один раз |
| `no_answer` (статус обёртки) | Вывод есть, но это только логи tool-call'ов без финального предложения — перезапустить советника **один раз** с явным «отвечай по памяти, веб-тулы не используй», иначе пометить пропущенным |

Сбои не блокирующие. Если успешных советников ноль — остановись и сообщи.

> **Проверяй не только `.status`, но и содержимое `.out`.** Статус `ok`
> означает лишь код выхода 0 — обёртка сама ловит пустой вывод
> (`empty_output`) и чисто-логовый вывод (`no_answer`), но эвристика не
> идеальна: перед синтезом всё равно убедись, что в `.out` связный
> текст-ответ, а не только строки вида `⚙/✗/% <tool>`.

## Очистка

```bash
rm -rf /tmp/multi-opinion/
```
