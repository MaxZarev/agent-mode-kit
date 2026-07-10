# Установка внешних CLI

Скиллу нужен **хотя бы один** из внешних AI-CLI: `codex`, `gemini`, `claude`
или `glm` (через OpenCode). Чем больше установлено — тем выше покрытие ревью.
Если у пользователя нет ни одного, предложи установить любой из них по
инструкции ниже.

> Для способов через **npm** нужен [Node.js 18+](https://nodejs.org/).
> Команды установки и авторизации часто меняются — при сомнении сверяйся с
> официальной документацией (ссылки в конце каждого раздела).

## Проверка, что уже установлено

```bash
which codex 2>/dev/null && echo "codex: есть"  || echo "codex: нет"
which agy   2>/dev/null && echo "gemini (agy): есть" || echo "gemini (agy): нет"
which claude 2>/dev/null && echo "claude: есть" || echo "claude: нет"
which opencode 2>/dev/null && echo "glm (opencode): есть" || echo "glm (opencode): нет"
```

## Codex CLI (OpenAI)

Установка (любой способ):

```bash
# Официальный установщик (macOS / Linux):
curl -fsSL https://chatgpt.com/codex/install.sh | sh

# npm:
npm install -g @openai/codex

# Homebrew:
brew install codex
```

Авторизация: запусти `codex` — при первом запуске предложат войти через
аккаунт ChatGPT или ввести API-ключ.

Документация: <https://developers.openai.com/codex/>

## Gemini → Antigravity CLI (`agy`, Google)

> Старый `gemini` CLI (npm-пакет `@google/gemini-cli`) и его бесплатный вход
> Gemini Code Assist for individuals **отключены Google 18 июня 2026**. Все
> тарифы (free / AI Pro / Ultra) переехали на **Antigravity CLI** — закрытый
> нативный бинарь `agy`. Это и есть текущий способ дёргать модели Gemini из CLI.

```bash
# Официальный установщик (macOS / Linux) — ставит бинарь в ~/.local/bin/agy:
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

Авторизация: запусти `agy` один раз — при первом обращении к модели откроется
браузерный вход в аккаунт Google (по SSH — печатает URL и одноразовый код).
Учётные данные кэшируются в системном Keychain. Бесплатный тариф ограничен
~20 запросами в день; платные подписки (AI Pro / Ultra) поднимают лимит.

Неинтерактивный запуск (как использует скилл): `agy -p "<промпт>"` — печатает
ответ и читает stdin. Бинарь тихо само-обновляется в фоне.

Документация: <https://antigravity.google/docs/>

## Claude Code CLI (Anthropic)

```bash
# Нативный установщик (macOS / Linux / WSL):
curl -fsSL https://claude.ai/install.sh | bash

# Windows PowerShell:
irm https://claude.ai/install.ps1 | iex

# npm:
npm install -g @anthropic-ai/claude-code

# Homebrew:
brew install --cask claude-code
```

Авторизация: запусти `claude` и войди через браузер. Требуется подписка Claude
(Pro / Max / Team / Enterprise) или доступ через API-провайдера; бесплатный
тариф Claude.ai доступа к Claude Code не даёт.

Документация: <https://code.claude.com/docs/>

## GLM via OpenCode (Z.ai GLM Coding Plan)

Ревьюер `glm` — это **GLM 5.2** от Z.ai, запускаемый через **OpenCode**
(`opencode run --agent plan ...`, read-only). Нужна подписка GLM Coding Plan.

```bash
# npm (нужен Node.js 18+):
npm install -g opencode-ai@latest

# или официальный установщик (macOS / Linux):
curl -fsSL https://opencode.ai/install | bash
```

Авторизация: `opencode auth login` → выбери **Z.AI Coding Plan** → вставь
API-ключ Z.ai (ключ хранится в `~/.local/share/opencode/auth.json`, вне git).
Проверка модели: `opencode models | grep zai-coding-plan` (должен быть
`zai-coding-plan/glm-5.2`).

> ⚠️ Z.ai — китайский провайдер. GLM-ревьюер читает файлы из корня контекста и
> отправляет их Z.ai. Не подключай его на NDA-репозиториях с ПДн/секретами.

Документация: <https://opencode.ai/docs/> · <https://docs.z.ai/devpack/overview>

## После установки

Проверь, что бинарь виден в PATH (`which <cli>`), и что он авторизован (запусти
CLI один раз). Затем скилл `multi-review` подхватит доступные CLI автоматически —
см. `references/cli-commands.md`.
