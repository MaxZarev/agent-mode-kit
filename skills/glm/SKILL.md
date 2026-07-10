---
name: glm
description: "Delegate a coding task to, or get an independent second opinion from, GLM 5.2 (Z.ai) running as a separate headless agent via OpenCode — distinct from the main Claude session. Use when the user wants to offload implementation of a subtask to the cheaper GLM worker, run GLM in parallel / batch several GLM tasks, or get a cross-review / second opinion from GLM on a diff, spec, plan, or implementation. Triggers: 'delegate to glm', 'ask glm', 'let glm implement', 'glm second opinion', 'run glm on', 'have glm review', '/glm'."
license: MIT
---

# glm — delegate to / consult GLM 5.2 via OpenCode

Runs **GLM 5.2** (Z.ai **GLM Coding Plan** subscription) as a separate headless
agent through **OpenCode**, so the main Claude session (the orchestrator) can
hand off implementation work or get an independent opinion from a different
model and vendor.

- Model: `zai-coding-plan/glm-5.2` (subscription quota — no per-token billing).
- Harness: OpenCode (`opencode run`), invoked through `scripts/glm-run.sh`.
- The Z.ai subscription key lives in OpenCode's own
  `~/.local/share/opencode/auth.json` (set once via `opencode auth login`) and,
  for the research MCP servers below, in a git-ignored `scripts/.env`
  (`ZAI_API_KEY`). It is never hardcoded in the config or this skill.
- **Research tools:** the worker is wired to Z.ai's own MCP servers (included in
  the Coding Plan, no extra cost) so GLM can search the web, read pages, and
  inspect GitHub repos on its own — see "Research tools" below.

## Two modes

Pick the mode from intent before running.

### `implement` — delegate a coding subtask (GLM **edits** files)

GLM autonomously inspects the target repo and writes changes (OpenCode `build`
agent). Use to offload a well-scoped subtask while the orchestrator stays on the
harder work, or to batch several independent subtasks across GLM in parallel.

```bash
~/.claude/skills/glm/scripts/glm-run.sh implement --cwd /abs/path/to/repo -- \
  "Implement X. Constraints: ... . When you hit an unfamiliar library or API,
   use web search / web reader to check the CURRENT docs, and zread to inspect
   the upstream repo, before coding. Run the tests when done and report what
   changed and what you looked up."
```

- Run from the target repo (`--cwd`). GLM works on the real working tree.
- **Always review GLM's diff before keeping it** — `git diff` after it finishes.
  Treat the output as a proposal, not a trusted change.
- For batching: launch several `glm-run.sh implement` calls, each in its own
  Bash tool invocation with `run_in_background: true`, then collect results.

### `review` — read-only second opinion (GLM **edits nothing**)

GLM inspects the artifact read-only (OpenCode `plan` agent) and returns findings
only. Use for a cross-review / second opinion on a diff, spec, plan, or a
finished implementation — independent of the orchestrator's own blind spots.

```bash
~/.claude/skills/glm/scripts/glm-run.sh review --cwd /abs/path/to/repo -- \
  "Review the uncommitted changes in this repo for correctness bugs and
   oversights. Inspect the files yourself. Verify any library/API/version claim
   against CURRENT docs with web search / web reader, and check referenced
   upstream repos with zread, instead of relying on memory. Output findings
   only; do not edit."
```

- For a plan/spec, point `--cwd` at the dir containing the file and name the
  file in the prompt, or pass the artifact text inline in the prompt.
- Treat GLM's findings as **hypotheses, not verdicts** — verify each against the
  real code/text before acting (same discipline as the `multi-review` skill).

## Research tools (web search / page reading / GitHub)

Plain GLM behind the coding endpoint has **no** web access — Claude Code's own
`WebSearch` is an Anthropic server-side tool and does not work against Z.ai. So
this skill gives the worker research ability via **Z.ai's own remote MCP
servers** (included in the Coding Plan, billed against the same subscription):

| MCP server | URL | What GLM can do |
|------------|-----|-----------------|
| `zai-web-search` | `…/api/mcp/web_search_prime/mcp` | Search the web for fresh sources (titles, URLs, summaries) — the GLM equivalent of `WebSearch`. |
| `zai-web-reader`  | `…/api/mcp/web_reader/mcp`        | Fetch and structure a specific page — equivalent of `WebFetch`. |
| `zai-zread`       | `…/api/mcp/zread/mcp`             | Interrogate a public GitHub repo: search docs, read its structure, read files. |
| `tavily` (fallback) | local stdio (`npx -y tavily-mcp@<pinned>`) | Web search/extract when the zai servers fail (429 / timeouts). Key `TAVILY_API_KEY` in `scripts/.env`. Queries go to Tavily (US). |
| `firecrawl` (fallback) | local stdio (`npx -y firecrawl-mcp@<pinned>`) | Page reading/scraping fallback. Key `FIRECRAWL_API_KEY` in `scripts/.env`. URLs go to Firecrawl (US). |

Both fallback servers are **version-pinned** in `scripts/opencode.json`: an
unpinned `npx -y <pkg>` re-resolves "latest" from the registry on every start,
which is slow and was observed to hang opencode on a cold npm cache.

The zai servers are primary; prompts in multi-opinion / multi-review tell GLM to
switch to tavily/firecrawl when a zai tool errors or rate-limits instead of
retrying it.

How it is wired (no key in any tracked file):

- The Z.ai MCP endpoints speak **Streamable HTTP**, but OpenCode's native
  `type:"remote"` only does SSE (it fails with `Invalid content type, expected
  "text/event-stream"`). So `scripts/opencode.json` registers each server as a
  **local** MCP that bridges through `npx -y mcp-remote … --transport http-only`.
- Auth is passed as `--header "Authorization:${AUTH_HEADER}"` where
  `AUTH_HEADER` = `Bearer {env:ZAI_API_KEY}`. The key comes from the environment
  and goes through the bridge's **env**, so it never appears in the process
  command line or in any tracked file.
- `scripts/glm-run.sh` sources `scripts/.env` (which holds `ZAI_API_KEY`,
  `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`) and exports
  `OPENCODE_CONFIG=scripts/opencode.json`, so these tools load **only**
  for the GLM worker — not for your other OpenCode usage.
- Available in both modes: `implement` (`build` agent) and `review` (`plan`
  agent) — they are read-only network calls, safe even in review.

> **Security note on `mcp-remote`:** this is a third-party npm package
> (`geelen/mcp-remote`) fetched fresh via `npx -y` on each run, acting as a local
> proxy that forwards MCP traffic — including your Z.ai bearer token — to the
> `api.z.ai` URLs above. It is the de-facto MCP HTTP bridge, but for stricter
> supply-chain hygiene you can pin a version (`mcp-remote@<x.y.z>`) in
> `scripts/opencode.json` after vetting it.

To make the worker actually use them, the prompt should say so (the examples
above do): tell GLM to verify library/API/version facts against current docs and
to inspect upstream repos instead of relying on memory. Optionally add Z.ai's
Vision MCP (`…/api/mcp/zai-mcp-server/mcp`) the same way for image understanding.

## How the orchestrator uses it

The main Claude session calls `scripts/glm-run.sh` via the Bash tool:

- One Bash call per GLM task. For long tasks use `run_in_background: true` and a
  generous `timeout` (e.g. `900000`).
- Read GLM's stdout, then decide: in `implement` mode review the diff; in
  `review` mode triage the findings.
- The skill path depends on where it is linked — e.g.
  `~/.claude/skills/glm/scripts/glm-run.sh`. Use the absolute path that exists.

## Safety & confidentiality (read before delegating)

- GLM runs on **Z.ai (Chinese provider)**. Everything OpenCode sends — file
  contents it reads, your prompt — leaves your machine. With the research MCP
  servers enabled, GLM's **search queries, the URLs it reads, and the GitHub
  repos it inspects** also go to Z.ai. Don't have it research anything you would
  not want that provider to see.
- In `implement` mode GLM has **read + write** access to the target repo.
- **Do NOT run GLM in NDA / client-PII / secret-bearing repositories.** Keep it
  to non-sensitive projects and to review of artifacts you have vetted. For
  sensitive work stay on the local Claude session.
- Keep secrets in `.env` (git-ignored) so a delegated GLM run cannot read them;
  do not point `--cwd` at a tree that contains real credentials.

## Prerequisites

- OpenCode installed (`opencode --version`).
- Authenticated: `opencode auth login` → **Z.AI Coding Plan** → paste Z.ai key.
- Verify the model is visible: `opencode models | grep zai-coding-plan`.
- **For the research tools** you also need:
  - `node` / `npx` on PATH (the `mcp-remote` bridge runs via `npx`).
  - A key file: copy `scripts/.env.example` to `scripts/.env` and put your Z.ai
    key in `ZAI_API_KEY` (the **same** key as `opencode auth login`). The `.env`
    is git-ignored. Without it the worker still runs — just with no web search /
    page reading / zread.
- Verify the MCP servers connect (no model quota used) — run from the `scripts`
  dir so it picks up `.env`:
  `set -a; . ./.env; set +a; OPENCODE_CONFIG="$PWD/opencode.json" opencode mcp list`
  All three (`zai-web-search`, `zai-web-reader`, `zai-zread`) should show
  **connected**. `Connection closed` means the key in `.env` is wrong/missing;
  `Invalid content type` would mean the bridge config was changed incorrectly.

## Files

| File | Purpose |
|------|---------|
| `scripts/glm-run.sh` | Wrapper that runs `opencode run` with the right model + agent per mode; loads `.env` and points OpenCode at `opencode.json` |
| `scripts/opencode.json` | Registers Z.ai's web-search / web-reader / zread MCP servers (auth via `{env:ZAI_API_KEY}`); loaded only for the worker via `OPENCODE_CONFIG` |
| `scripts/.env.example` | Template for `scripts/.env` holding `ZAI_API_KEY` for the research MCP servers (real `.env` is git-ignored) |
