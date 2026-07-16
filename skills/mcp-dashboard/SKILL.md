---
name: mcp-dashboard
description: Show and manage the user's MCP servers per project via a local HTML dashboard — a projects × servers matrix (columns grouped: user scope / built-in / claude.ai connectors / plugins / local / .mcp.json) with an "all projects" master row, click-to-toggle cells, a stale-leftover cleanup panel, and a "copy changes" block the agent then applies safely to ~/.claude.json (backup + atomic write, secrets never shown). Use when the user wants an OVERVIEW or per-project ON/OFF control of already-configured MCP servers — e.g. «что у меня с MCP», «какие MCP подключены/включены», «покажи дашборд MCP», «включи/выключи <server> в проекте X», «отключи context7 везде кроме этого проекта», "show my MCPs", "mcp dashboard", "which MCP servers are enabled where", "disable an MCP for this project", or when the user pastes an "=== MCP CHANGES ===" block. Can also copy an already-configured local server into another project («добавь/подключи exa в проект X», when exa is already connected somewhere). NOT for connecting a brand-NEW server or OAuth sign-in — that's the connect-mcp skill.
allowed-tools: Bash, Read, Write
---

# mcp-dashboard — see and control MCP servers per project

Claude Code keeps all MCP state in `~/.claude.json`: global (user-scope) servers,
per-project local servers, per-project disable lists, and approval state for
`.mcp.json` servers. This skill renders that state as a single local HTML page
the user can browse and toggle, then applies their changes through a script that
backs up the config and never touches anything except the MCP keys.

Talk to the user in plain language: "a page will open in your browser", "click
the checkmarks", "copy the block and paste it here" — not "I'll mutate
disabledMcpServers". Never print secret values (the page already masks them).

**Scope guard:** adding a brand-new server (a URL, an npx command, OAuth) is the
`connect-mcp` skill's job. This skill *shows* what exists, flips existing
servers on/off per project, and can copy an **already-configured local server**
into another project (`add:` — «добавь exa в проект X» works here when exa is
local somewhere).

## Placeholders

- `<skill-dir>` — the folder containing this SKILL.md (where `scripts/` lives).
- `<tmp>` — a scratch folder outside the user's project (session scratchpad if
  you have one).
- `python3` — on Windows use `python` (or `py`). The script is stdlib-only,
  Python 3.9+, works on macOS / Windows / Linux.

## Step 1 — Build and open the dashboard

```bash
python3 <skill-dir>/scripts/mcp_dashboard.py build --out <tmp>
```

It prints the absolute path of `mcp-dashboard.html`, possibly followed by:

- `FIRST RUN: …` — a baseline of the user's projects was just saved. Tell the
  user they can hide unneeded projects right on the page (the ✕ in a column
  header) and those won't show up next time.
- `NEW PROJECT: <path>` lines — projects that appeared since the last run.
  **Mention them to the user** ("с прошлого раза появились новые проекты: …");
  on the page they carry a «новый» badge.
- `RUDIMENT: <name> — …` lines — stale leftovers: server names that sit in
  disable/approval lists of some projects but no longer exist as servers
  anywhere. **Mention them** ("в конфиге остались следы удалённых серверов: …")
  and offer to clean them up — the page has a «Рудименты» panel with a
  «очистить» button, or compose `cleanup:` lines yourself (Direct mode).

Open the page for the user:

- macOS: `open "<path>"`
- Windows: `start "" "<path>"`
- Linux: `xdg-open "<path>"`

Then tell the user, briefly: the page is a matrix — **rows are projects, columns
are servers**, grouped by where each server comes from (глобальные user scope /
встроенные / коннекторы claude.ai / плагины / локальные / проектные `.mcp.json`).
✓ = enabled, ✕ = disabled, ? = a repo `.mcp.json` server not yet approved,
— = not connected to that project, ⛔ = blocked globally by `deniedMcpServers`
in `~/.claude/settings.json` — clicking the ⛔ in the «Все проекты» row queues
an unblock (an `unblock:` line), after which the project cells become live for
fine-tuning in the same batch.
The top row **«Все проекты»** toggles a server at once in every project where
it exists (± means "enabled in some projects, not all"); the project rows below
are for fine-tuning. Local and `.mcp.json` servers show a faint «+» in projects
where they are not connected — clicking it queues "connect here" (on apply the
script copies a local server's config entry inside `~/.claude.json`, or merges
a `.mcp.json` entry into the target repo's `.mcp.json` and approves it). To
change something: click the cells, press **«Скопировать изменения»**, and
paste the copied block back into the chat.

The page has a "where do you work" switch (top-left), **«Claude Desktop» by
default**, remembered between runs. In Desktop mode the claude.ai connector
columns collapse into one non-clickable column «управляется в приложении
Claude Desktop»: the Desktop app pulls connectors straight from the claude.ai
account and ignores per-project config entirely (`disabledMcpServers`,
`deniedMcpServers`, `disableClaudeAiConnectors` — verified), so toggling them
from here would change nothing — the user switches them via the tools icon in
the app itself or by unlinking the connector on claude.ai. Users working in
Claude Code CLI/IDE switch to «Claude Code (CLI)» — there per-project connector
toggles do work. All other groups are toggleable in both modes.

Known limitation to keep in mind: claude.ai connectors and plugin servers are
listed only once they've been toggled off somewhere via `/mcp` — the local
config has no registry of "enabled everywhere" connectors. If the user asks
about a connector that isn't listed, it may still exist; disabling it by name
via Direct mode works (the script warns about unknown names but applies).

If the user only wanted to *see* the picture — you're done after opening the page.

Options: `--include-missing` also lists projects whose folder was deleted
(hidden by default). `CLAUDE_CONFIG_DIR` is honored if the user relocated
`~/.claude.json`.

## Step 2 — Apply the pasted changes

When the user pastes a block like:

```
=== MCP CHANGES ===
mode: cli
hide: /Users/x/old-experiment
show: /Users/x/comeback
unblock: claude.ai Gmail
project: /Users/x/proj
add: exa
enable: context7
disable: notion, claude.ai Gmail
cleanup: old-removed-server
=== END ===
```

`hide:` / `show:` lines (one path each) only control which projects the
dashboard displays, and `mode:` (cli | desktop) is the "where do you work"
switch — all three go to the skill's own state file, never to `~/.claude.json`,
and don't affect any MCP server. `cleanup:` removes the named leftovers from
the project's disable/approval lists (the script refuses to "clean" a name
that is still a live server). `add:` connects an existing server to this
project: for a local-scope server the script copies its definition
(command/URL, env, headers — secrets included, config-to-config, never through
the chat) from the project where it is already configured and un-disables it;
for a repo `.mcp.json` server it merges the entry into the TARGET project's
`.mcp.json` file and approves it (`enabledMcpjsonServers`) — tell the user a
file in the target repo was changed, they may want to commit it. Global
servers don't need `add:` (they're everywhere already). `unblock:` / `block:`
are GLOBAL lines (no project needed): they remove/add the name in
`deniedMcpServers` of `~/.claude/settings*.json` (timestamped backup of each
touched settings file). Direct mode: «разблокируй Gmail» → `unblock:` line;
«заблокируй X везде» → `block:` line. Caveat to relay: the Claude Desktop app
ignores `deniedMcpServers` for claude.ai connectors — un/blocking them matters
only for CLI/IDE sessions (the script warns about this in desktop mode).

1. Save it **verbatim** to `<tmp>/mcp-changes.txt` (Write tool — avoids shell
   quoting issues; server names may contain spaces).
2. Apply:

   ```bash
   python3 <skill-dir>/scripts/mcp_dashboard.py apply <tmp>/mcp-changes.txt
   ```

3. Relay the result in plain language: what was switched where, that a backup
   of the config was saved (the script prints its path), and that the changes
   take effect in **new** Claude Code sessions — a chat that is already open
   keeps its old server list until restarted.

If the script errors (unknown project path, unreadable block), re-run `build`
and ask the user to copy a fresh block — don't hand-edit `~/.claude.json`.

Add `--dry-run` first only if the block looks hand-typed or suspicious; blocks
copied from the page are safe to apply directly.

## Direct mode — no page needed

If the user *names* exactly what to flip («выключи context7 в этом проекте»,
"disable notion everywhere except ~/work"), skip the page: compose the
`=== MCP CHANGES ===` block yourself (absolute project paths as listed in
`~/.claude.json`; comma-separated server names) and run `apply`. Use `build`'s
JSON knowledge if you need to check names first — or run `build` anyway and
read nothing but the printed path. Report the same way as in Step 2.

When the change touches a `claude.ai *` connector and the saved mode is
desktop (the default), the script prints a WARNING — relay it in plain
language: the Claude Desktop app won't notice this change (it manages
connectors itself — the tools icon in the app, or unlinking on claude.ai);
the change still counts for Claude Code CLI/IDE sessions. If the user says
they work in the terminal, offer to switch the saved mode with a
`mode: cli` line so the warning stops.

## What the script actually edits (for your understanding, not for chat)

- Global servers & claude.ai/plugin connectors: per-project
  `disabledMcpServers` array in the project's entry of `~/.claude.json` —
  the field the `/mcp` toggle persists (not in the official docs, but verified
  against live Claude Code behavior).
- Repo `.mcp.json` servers: `enabledMcpjsonServers` / `disabledMcpjsonServers`
  arrays in the project's entry. The documented location for these is
  `.claude/settings*.json` inside the project — the script *reads* those for
  state (denylist wins) but never writes them; if a name is pinned there, the
  script prints a WARNING and the user must edit that file instead.
- `add:` for a local server copies the raw definition between
  `projects[*].mcpServers` entries of `~/.claude.json` (source = the project
  where the name is defined; if several define it differently, the first
  alphabetically wins with a WARNING) and removes the name from the target's
  `disabledMcpServers`. For a `.mcp.json` server it merges the entry into
  `<target>/.mcp.json` (atomic write; refuses to touch a file that isn't valid
  JSON; skipped on --dry-run) and approves the name via the project entry —
  the ONLY case where the script writes outside `~/.claude.json`.
- `cleanup:` removes a stale name from the project's `disabledMcpServers`,
  `enabledMcpjsonServers` and `disabledMcpjsonServers` lists. Names that still
  are live servers are skipped with a WARNING. Names with no definition that
  are NOT connectors/plugins/built-ins are reported by `build` as `RUDIMENT:`
  lines and shown in the page's «Рудименты» panel instead of the matrix.
  (Built-in servers — `claude-in-chrome`, `ide` — have no config definition by
  design and get their own «Встроенные» column group, not a rudiment flag.)
- `deniedMcpServers` in `~/.claude/settings.json` + `settings.local.json`
  (globally blocked servers, rendered as ⛔): `unblock:` removes the name from
  both files, `block:` appends `{"serverName": …}` to `settings.json`. Only
  that key is touched; each modified settings file gets a timestamped backup
  (`.bak-mcpdash-…`). A per-project `enable` of a still-blocked name prints a
  WARNING suggesting `unblock:` instead.
- Everything else in `~/.claude.json` is left untouched; writes are atomic and
  preceded by a timestamped backup (`~/.claude.json.bak-mcpdash-…`). The backup
  is skipped when the block contains only `hide:`/`show:` lines (config not touched).
- The skill's own state — hidden projects + known projects (for new-project
  detection) + `uiMode` (the CLI/Desktop switch, desktop by default) — lives in
  `~/.claude/mcp-dashboard.json` (or under `CLAUDE_CONFIG_DIR`). Deleting that
  file resets visibility to "show all", re-baselines what counts as "new" and
  returns the switch to Desktop.

Caveat to keep in mind: other Claude Code sessions running *right now* may
rewrite `~/.claude.json` and lose the applied change — if the user reports a
toggle "didn't stick", suggest closing other sessions and re-applying.

## Troubleshooting

- **`python3` not found** — try `python` / `py -3`; if none, ask the user to
  install Python 3 (python.org, "Add to PATH" on Windows).
- **Page opens but is empty** — the browser blocked local JS? Any modern
  default browser works; re-open the printed path manually.
- **Copy button didn't copy** — the page falls back to a visible text field;
  tell the user to select and copy it manually.
- **User wants to add a server that isn't listed** — switch to the
  `connect-mcp` skill.
