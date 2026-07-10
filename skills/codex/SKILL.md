---
name: codex
description: "Delegate a coding task to, or get an independent second opinion from, Codex (OpenAI GPT-5.5, xhigh reasoning) running as a separate headless agent — distinct from the main Claude session. Use when the user wants to offload implementation of a subtask to Codex, run Codex in parallel, or get a cross-review / second opinion from Codex on a diff, spec, plan, or implementation. Triggers: 'delegate to codex', 'ask codex', 'let codex implement', 'codex second opinion', 'have codex try', '/codex'. For a structured code review of a target use the separate codex-review skill; for asking SEVERAL models at once use multi-opinion / multi-review."
license: MIT
---

# codex — delegate to / consult Codex (GPT-5.5)

Runs **Codex** (OpenAI **GPT-5.5**, `xhigh` reasoning) as a separate headless
agent via `codex exec`, so the main Claude session (the orchestrator) can hand
off implementation work or get an independent opinion from a different model and
vendor.

- Model: `gpt-5.5` with maximum reasoning (`xhigh`) by default.
- Harness: Codex CLI (`codex exec`), invoked through `scripts/codex-run.sh`.
- **Slow on purpose:** gpt-5.5 + xhigh routinely runs 3-10+ minutes. The
  orchestrator should launch it in the **background** and keep working, not
  block on it.

## Two modes

### `implement` — delegate a coding subtask (Codex **edits** files)

Codex inspects the target repo and writes changes (sandbox `workspace-write`).
Use to offload a well-scoped subtask, or to get a second, independent
implementation to compare against your own.

```bash
~/.claude/skills/codex/scripts/codex-run.sh implement --cwd /abs/path/to/repo -- \
  "Implement X. Constraints: ... . Keep changes minimal and explain what you changed."
```

- Codex works on the real working tree under `--cwd`.
- **Always review Codex's diff before keeping it** (`git diff`). Treat the
  output as a proposal, not a trusted change.

### `review` — read-only second opinion (Codex **edits nothing**)

Codex inspects the artifact read-only (sandbox `read-only`) and returns its
opinion. Use for an independent cross-review of a diff, spec, plan, or a
finished implementation.

```bash
~/.claude/skills/codex/scripts/codex-run.sh review --cwd /abs/path/to/repo -- \
  "Review the uncommitted changes for correctness bugs and oversights.
   Inspect the files yourself. Output findings only; do not edit."
```

- Treat Codex's findings as **hypotheses, not verdicts** — verify each against
  the real code before acting.
- For a structured, target-aware code review (last commit / branch / plan /
  spec) prefer the existing **`codex-review`** skill instead.

## How the orchestrator uses it

The main Claude session calls `scripts/codex-run.sh` via the Bash tool:

- One Bash call per Codex task, **`run_in_background: true`**, generous
  `timeout` (e.g. `900000`). The harness notifies you when it finishes — do NOT
  poll with `sleep`.
- In `implement` mode review the diff; in `review` mode triage the findings.
- Tune speed/quality with `--effort` (`minimal|low|medium|high|xhigh`); drop to
  `high`/`medium` for simple tasks to save minutes.

## Safety & confidentiality

- Codex runs on **OpenAI (US provider)** — your prompt and the files Codex
  reads leave your machine. In `implement` mode it has read + write access to
  the target repo.
- For NDA / client-PII repos treat this like any third-party processor: only
  use it where sending the code to OpenAI is permitted. Keep secrets in `.env`
  (git-ignored) so a delegated run cannot read them.
- Always review Codex's diff before keeping it.

## Prerequisites

- Codex CLI installed (`codex --version`, needs `codex-cli` ≥ 0.125.0 for
  `gpt-5.5`) and authenticated (run `codex` once and log in).

## Files

| File | Purpose |
|------|---------|
| `scripts/codex-run.sh` | Wrapper that runs `codex exec` with the right sandbox per mode |
