---
name: secret-input
description: Collect one or SEVERAL env values (API keys, tokens, passwords, and any other .env config values) from the user WITHOUT the values passing through chat or terminal output. Opens a local one-shot web page where the user fills the values; a script writes them to .env. Use whenever a secret or env value is needed from the user — never ask to paste it into the chat. Triggers — «вставь ключ», «добавь API-ключ», «добавь ключи», «сохрани токен», «нужен ключ от…», «положи в .env», «заполним .env», "store api key", "collect secret", "set up env vars", "need a token".
---

# secret-input — collect env values without chat or terminal

Core rule this skill enforces: **the values must never appear in the
conversation, in command output, or in logs.** The user fills them into a local
page or native dialog; a script writes them to `.env`; you (the agent) only
learn the variable names and the status.

This is not only for secrets — any env value (URLs, ids, config strings) can be
collected the same way.

## The flow — local web page (cross-platform, needs Node)

1. Check Node: `node --version`. If missing, offer to install it first
   (macOS: `brew install node`; Windows: `winget install OpenJS.NodeJS.LTS`;
   Linux: distro package manager) — tell the user what you are about to install
   and why. If they decline or there is no package manager → use the manual
   fallback below.
2. Figure out: which variables are needed, destination `.env` path, a human
   label, and optionally a format prefix per variable (`NAME:sk-` for
   OpenAI-style keys). The prefix is a hint only, it never blocks saving —
   but still don't guess prefixes you are not sure about.
3. Run (from the project directory, so `./.env` resolves):

   ```
   node <skill-dir>/scripts/collect-secret.mjs \
     --name TELEGRAM_BOT_TOKEN \
     --name OPENAI_API_KEY:sk- \
     --label "Ключи для бота" \
     --hint "Токен — из BotFather; ключ OpenAI — из platform.openai.com" \
     --env-path .env
   ```

   - Repeat `--name` for every variable you want pre-filled; one page collects
     them all at once. `:PREFIX` after a name adds a format RECOMMENDATION:
     the page shows it in the field placeholder and warns once if the value
     starts differently, but the user can always save anyway.
   - With no `--name` the page starts with one empty row — the user types both
     the name and the value themselves.
   - On the page the user can edit variable names, add extra rows («+ добавить
     переменную») and remove rows — so don't worry if you are not sure about
     the exact set; pre-fill what you know.
   - NOTE: the flag is `--env-path`, NOT `--env-file` — node intercepts
     `--env-file` as its own CLI option and the script never sees it.
4. Tell the user in plain words, no jargon: «Сейчас в браузере откроется
   страничка — заполните значения и нажмите „Сохранить всё". Сюда в чат
   ничего вставлять не нужно.»
5. The script blocks until the values are saved, then prints one
   `OK: NAME saved to … (length N)` line per variable — relay success to the
   user. It may also print a `WARN:` line if `.env` is not gitignored — fix
   `.gitignore` then. On `TIMEOUT` (5 min default) just offer to run it again.

The page runs on `127.0.0.1` with a random port + one-time token, accepts a
single successful submit, then the server exits. Nothing leaves the machine.

There is intentionally no minimum-length or whitespace validation: env files
hold all kinds of values, not just long keys. A value containing spaces or
special characters is written in double quotes (`NAME="a b c"`) so dotenv
parsers read it back as one string.

## Fallback — manual edit (no Node, install declined)

No scripts involved: append placeholder lines (`NAME=`) to the `.env` file
yourself, tell the user which values go where, and ask them to open the file
in their own editor and paste the values directly there — never into the chat.
Then verify presence as described below.

## After saving — verify presence, not value

- Check each line exists — e.g. `grep -c "^NAME=" .env` — and report
  «записано». **Never** `cat` the file or print the lines themselves.
- Ensure `.env` is in `.gitignore`; add it if missing.
- Continue the original task using the env vars by name.

## Other destinations (Vercel, CI, cloud)

Always collect to `.env` first with this skill, then push to the platform by
piping from the file without printing the value, e.g.:
`grep '^NAME=' .env | cut -d= -f2- | npx vercel env add NAME production`.
Never echo the value in between.

## Hard rules

- Never ask the user to paste a secret into the chat. If they do it anyway,
  warn them the value is now in the conversation history and recommend
  rotating/reissuing it after the task.
- Never echo, log, or read back the stored values; scripts intentionally print
  only name + destination + length.
- Non-technical users: describe every step as an action they can see
  («откроется страничка»), never as infrastructure.
- If the browser page doesn't open (headless/SSH session), rerun with
  `--no-open` and give the user the printed URL to open manually — it only
  works on that same machine.

## Adjusting behavior

Read `scripts/collect-secret.mjs` header for all flags (`--timeout`,
`--no-open`, etc.) before changing defaults.
