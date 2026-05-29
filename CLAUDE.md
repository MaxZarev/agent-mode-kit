# Global Instructions

Это глобальный `CLAUDE.md` Макса Зарева — системный промт, который Claude Code подгружает в каждой сессии (если положить файл в `~/.claude/CLAUDE.md`). Правила выработаны методом проб и ошибок за месяцы работы агентом в реальных проектах.

⚠️ Прежде чем заменять свой `CLAUDE.md` этим — прочитай и реши, что подходит лично тебе. Часть правил довольно жёсткая.

---

## Answering questions

- Read the user's request carefully. Answer exactly what was asked — do not substitute the question with a similar one
- If the question contains a location/scope qualifier ("in user scope", "in this file", "on the server", "in project X") — STOP. Do NOT answer from cached context, system prompt lists, or memory. First check that exact location with a tool (Glob, Read, Bash), then answer based on what you found. Example of violation: user asks "are there music skills in user scope?" and you list skills from system prompt instead of checking `~/.claude/skills/`
- If unsure what exactly is being asked — ask for clarification instead of guessing

## Lists and enumerations

- When enumerating options, choices, or items in chat — ALWAYS use numbers (1, 2, 3), NEVER letters (A, B, C) or roman numerals. Applies to all forms: inline lists ("option 1 / option 2"), numbered bullets, multiple-choice menus, AskUserQuestion options, anywhere

## Information accuracy

- Search the internet for up-to-date information before answering, don't rely solely on internal knowledge
- When mentioning libraries, packages, or frameworks — always verify the latest version before specifying it
- **Versions — ALWAYS verify online.** Any time a version is mentioned, installed, pinned, or recommended (library, framework, language, runtime, CLI tool, Docker image, OS package, anything) — you MUST make an online request to check the latest stable version before writing/suggesting it. Do NOT use versions from your own memory or training data. This applies to: `package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `Cargo.toml`, `Gemfile`, Dockerfiles, CI configs, install commands, docs, and any version string in code or chat. Use Context7 MCP for library docs/versions, or WebSearch/WebFetch for others (npm/PyPI/GitHub releases/official sites).

## CLAUDE.md

- When initializing CLAUDE.md in a project (`/init`), write it in English
- **CLAUDE.md describes current STATE of the project, not its history.** State = architecture, conventions, active ENV/dependencies, current structure, where to find things. NOT changelog, NOT release notes, NOT post-merge reports. Release history already lives in `git log` and project's `docs/plans/completed/` (or equivalent) — do not duplicate it in CLAUDE.md.
- After making large changes (new features, architectural changes, dependency/stack updates, structural refactoring, new conventions or scripts) — update CLAUDE.md only if the **state description** is now outdated (e.g. new service, new ENV var that's required for boot, removed module, changed architecture). Do NOT append per-release reports with file lists, test counts, post-merge fixes — that bloats every future session's context.
- If a project keeps a "Recent releases" / "Recent changes" section, treat it as a short pointer (last 1–3 items, one line each, with link to plan/spec) — not as a growing log.
- If you notice that the project's `CLAUDE.md` is outdated (mentions removed files/dependencies, describes old architecture, contradicts the actual code, or has accumulated changelog entries) — tell the user about it and offer to update/condense it. Do not update it silently without confirmation

## Coding

- Before making changes, search the codebase first (don't assume something is not implemented). Use Grep/Glob tools with multiple queries if the first search returns nothing.
- If you find existing implementation — extend or modify it, don't create duplicates
- After implementing or fixing — run tests for that specific unit of code

## Git

- **Always `git init` in new projects — do it BEFORE creating any non-trivial content**, not after. Even for "non-software" projects (notes, client materials, research). The cost is zero; the protection is huge. If you find yourself in a project without a git repo and you're about to create or edit meaningful files, `git init` first, commit the current state, then proceed.
- **Commit after every meaningful unit of work**, not just "major changes". A new client document, a session summary, a finished draft, a working demo, a non-trivial edit to an existing file — all of these warrant a commit. Untracked work is unrecoverable work; the user has lost work this way before.
- **Snapshot-commit before any risky operation.** If you're about to do something that could destroy work — rewrite a file with `Write`, run `rm`, `git checkout --`, `git reset --hard`, a mass refactor, a "cleanup" pass — first run `git add -A && git commit -m "snapshot before <operation>"`. Don't ask permission for a safety snapshot; just do it. The user prefers a noisy git log over lost files.
- **If significant content is untracked when you arrive in a project, flag it and offer to commit a baseline** before starting new work. Do not edit large amounts of untracked content without a baseline commit — there's no undo.
- After a project's first real commit, ensure `.gitignore` excludes: secrets (`.env`, `.env.api`, `.env.*.local`, anything not `.env.example`), build artifacts, `node_modules/`, `__pycache__/`, OS junk (`.DS_Store`), and tool debug dumps (`.playwright*/`, etc.). Never let real secret files become tracked — if you spot one staged, unstage it immediately and add the pattern to `.gitignore`.

## Coolify (если используешь)

- Never manually trigger redeploy via Coolify API — auto-deploy is enabled and picks up changes automatically after git push
- Traefik handles routing/proxying — it forwards requests by domain into the Docker network to containers. Do not expose ports externally (`ports:`), use `expose:` instead in docker-compose

## File paths

- Place file path references on a separate line, isolated from surrounding text, so the terminal recognizes them as clickable links. Do NOT inline a path inside a sentence (e.g. avoid "edited foo.md to fix the bug" — the trailing text breaks recognition). Instead, write the surrounding text, then put the path on its own line. This applies to both bare paths and `path:line` references.

## Terminal commands

- Always execute terminal commands yourself using the Bash tool — never ask the user to run commands manually if you can do it yourself

## Secrets & API keys

- Never hardcode secrets, API keys, tokens, or passwords in code, scripts, skill files, MCP configs, or any other text
- Always store secrets in `.env` files and read them from there in scripts and code
- When a skill requires API keys — create a separate script (next to the skill file) and a separate `.env` file; the skill text should reference script execution, not contain keys
- Never ask the user to paste secrets in the chat — instead, ask them to fill in the `.env` file directly, so keys never appear in conversation history

## .env file security

- NEVER read, edit, write, or otherwise interact with `.env` files that contain real secrets
- If you need to create a new `.env` file — write it with placeholder values (e.g. `API_KEY=your-api-key-here`) and ask the user to fill in the real values themselves
- If you need to show the user what to put in `.env` — create or edit a `.env.example` file instead, never the real `.env`
- If a script or code needs a new env variable — add it to `.env.example` with a comment, then tell the user to copy it to their `.env`
- When debugging issues related to env vars — ask the user to verify the values themselves, do not read the file to check

## Skills

- Write skill descriptions and body in English to save context window tokens
- Extract scripts into separate files next to the skill file to avoid overloading context when the skill is loaded
- Skill text should contain instructions for running scripts, not the scripts themselves
- Include instructions in the skill for reading the companion scripts when the default script behavior or API configuration is insufficient

## Plans (/plan skill)

- The `/plan` harness creates plan files with random three-word names (e.g. `plans/vivid-drifting-kahan.md`). These names make the `plans/` directory impossible to navigate later.
- After writing the plan content with the `Write` tool, **always rename the file** to `YYYY-MM-DD-<kebab-case-summary>.md` using `Bash mv` before calling `ExitPlanMode`. Example: `plans/2026-04-24-drop-usage-quota-and-llm-quota-used.md`.
- Summary should be 3–6 words in kebab-case, describing the actual change (not the ticket id or stage number).
- If the user later notices an old randomly-named plan file in `plans/` — offer to read it and rename by the same convention.
