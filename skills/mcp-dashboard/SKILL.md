---
name: mcp-dashboard
description: Show and manage the user's MCP servers per project via a local HTML dashboard — which servers exist (global / claude.ai connectors / local / .mcp.json), where each is enabled or disabled, with click-to-toggle cells and a "copy changes" block the agent then applies safely to ~/.claude.json (backup + atomic write, secrets never shown). Use when the user wants an OVERVIEW or per-project ON/OFF control of already-configured MCP servers — e.g. «что у меня с MCP», «какие MCP подключены/включены», «покажи дашборд MCP», «включи/выключи <server> в проекте X», «отключи context7 везде кроме этого проекта», "show my MCPs", "mcp dashboard", "which MCP servers are enabled where", "disable an MCP for this project", or when the user pastes an "=== MCP CHANGES ===" block. NOT for adding/connecting a NEW server or OAuth sign-in — that's the connect-mcp skill.
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
`connect-mcp` skill's job. This skill only *shows* what exists and flips
existing servers on/off per project.

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

Open the page for the user:

- macOS: `open "<path>"`
- Windows: `start "" "<path>"`
- Linux: `xdg-open "<path>"`

Then tell the user, briefly: the page shows every MCP server and every project;
✓ = enabled, ✕ = disabled, ? = a repo `.mcp.json` server not yet approved,
— = not connected to that project. To change something: click the cells, press
**«Скопировать изменения»**, and paste the copied block back into the chat.

If the user only wanted to *see* the picture — you're done after opening the page.

Options: `--include-missing` also lists projects whose folder was deleted
(hidden by default). `CLAUDE_CONFIG_DIR` is honored if the user relocated
`~/.claude.json`.

## Step 2 — Apply the pasted changes

When the user pastes a block like:

```
=== MCP CHANGES ===
hide: /Users/x/old-experiment
show: /Users/x/comeback
project: /Users/x/proj
enable: context7
disable: notion, claude.ai Gmail
=== END ===
```

`hide:` / `show:` lines (one path each) only control which projects the
dashboard displays — they go to the skill's own state file, never to
`~/.claude.json`, and don't affect any MCP server.

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
- Everything else in `~/.claude.json` is left untouched; writes are atomic and
  preceded by a timestamped backup (`~/.claude.json.bak-mcpdash-…`). The backup
  is skipped when the block contains only `hide:`/`show:` lines (config not touched).
- The skill's own state — hidden projects + known projects (for new-project
  detection) — lives in `~/.claude/mcp-dashboard.json` (or under
  `CLAUDE_CONFIG_DIR`). Deleting that file resets visibility to "show all"
  and re-baselines what counts as "new".

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
