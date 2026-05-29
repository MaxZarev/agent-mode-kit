---
name: codex-review
description: "..."
---

<!-- hidden: Run Codex CLI review with GPT-5.5 + xhigh reasoning. Usage: /codex-review [target]. Target: 'last' (last commit), 'branch' (branch vs master), git range 'abc..def', file path, 'plan <path>', 'spec <path>', 'merge', or free-text description. Default: last commit. Reviews code changes, plans, specs, docs — anything. -->


# Codex Review

Run `codex exec` non-interactively with the flagship model (`gpt-5.5`) and maximum reasoning effort (`xhigh`) to review the specified target.

## Steps

### 1. Determine what to review

Parse the argument to figure out the review target and type:

| Argument | Type | What to do |
|----------|------|------------|
| _(empty)_ or `last` | **code** | Review last commit: `git diff HEAD~1..HEAD` |
| `branch` | **code** | Review current branch vs master: `git diff master..HEAD` |
| `merge` | **code** | Review the last merge commit: find it with `git log --merges -1 --format=%H`, diff its parents |
| A git range like `abc..def` | **code** | Use as-is |
| `plan <path>` or a `.md` path containing `plan` | **plan** | Review the plan document |
| `spec <path>` or a `.md` path containing `spec` | **spec** | Review the spec document |
| Any file path (`.py`, `.ts`, `.md`, etc.) | **file** | Review that specific file |
| Free text (e.g. "stage 7a changes") | **code** | Find relevant commits from `git log --oneline -20` and build range |

### 2. Build the review prompt based on type

**Prepend this preamble to every prompt below (code / plan / spec / file):**

```
Do NOT attempt to run tests, builds, type-checkers, linters, package installs, or any shell commands that mutate state or require network/write access. The sandbox is read-only — such commands will fail and waste turns. Your job: read files, analyze, write the review. The user runs tests separately in CI / locally.

Read-only commands you MAY use: `git diff`, `git log`, `git show`, `cat`/`rg`/`ls` for navigation.
```

**For code reviews:**
```
Review the code changes. Run 'git diff <range>' to see the full diff, then read the changed files for full context.

Check:
- Correctness: logic errors, edge cases, off-by-one
- Types and contracts: FK constraints, nullable mismatches, schema/model sync
- Security: injection, auth bypass, secrets exposure
- Code quality: naming, duplication, unnecessary complexity
- Test quality: do tests verify behavior or just call code? Are mocks excessive? Are assertions specific?
- Missing pieces: untested paths, missing error handling at boundaries
- Regressions: does this break existing behavior?
- Plan/spec alignment: if docs/plans/*.md or docs/specs/*.md exists for this work, read it and verify the diff implements what was planned. Flag deviations as "justified improvement" or "problematic departure". Note any planned items missing.

Give a detailed review with specific file:line references.
Rate each finding: Critical / Important / Minor.
For each Critical/Important finding, classify the action:
- FIX_CODE: implementation has a bug or quality issue
- DISCUSS_DEVIATION: implementation diverges from plan, needs coding agent's input
- UPDATE_PLAN: plan itself has issue, recommend updating before more work

End with a summary verdict: APPROVE, REQUEST_CHANGES, or NEEDS_DISCUSSION.
```

**For plan reviews:**
```
Review this implementation plan. Read the file: <path>

Check:
- Completeness: are all requirements from the spec covered?
- Task ordering: are dependencies correct? Can anything be parallelized?
- Risk: are there risky steps without rollback? Missing error handling?
- Scope: is anything over-engineered or under-specified?
- Testability: does every task have clear verification criteria?
- File organization: is the proposed file structure clean?

Give a detailed review with specific section references.
Rate each finding: Critical / Important / Minor.
End with a summary verdict: APPROVE, REQUEST_CHANGES, or NEEDS_DISCUSSION.
```

**For spec reviews:**
```
Review this design specification. Read the file: <path>

Check:
- Clarity: are requirements unambiguous? Could two devs interpret them differently?
- Completeness: are edge cases covered? Error states? Auth/permissions?
- Consistency: does this conflict with existing architecture?
- Feasibility: are there technical constraints that make parts unrealistic?
- Security: auth, input validation, data exposure concerns?
- UX: does the user flow make sense?

Also read the project CLAUDE.md for architecture context.

Give a detailed review with specific section references.
Rate each finding: Critical / Important / Minor.
End with a summary verdict: APPROVE, REQUEST_CHANGES, or NEEDS_DISCUSSION.
```

**For file reviews:**
```
Review this file. Read: <path>

Check code quality, correctness, security, naming, and whether it follows the patterns of the surrounding codebase. Read neighboring files for context if needed.

Give a detailed review with specific line references.
Rate each finding: Critical / Important / Minor.
```

### 3. Run Codex (ALWAYS in background)

**Always launch codex as a background process** via the `Bash` tool with `run_in_background: true`. Codex with `gpt-5.5` + `xhigh` reasoning easily runs 3–10+ minutes — blocking the main agent on it wastes the user's time and burns context. The harness will notify you when the background process finishes, so do NOT poll with `sleep` loops.

Pipe the prompt via stdin (avoids shell-quoting issues with multiline prompts) and capture the final message to a file. Save the output path to a known location so you can read it after completion:

```bash
OUT=$(mktemp -t codex-review.XXXXXX.md)
echo "$OUT" > /tmp/codex-review-last-out.path
codex exec \
  --skip-git-repo-check \
  -m gpt-5.5 \
  -c 'model_reasoning_effort="xhigh"' \
  -s read-only \
  -o "$OUT" \
  - > /dev/null <<'PROMPT'
<review prompt>
PROMPT
```

`> /dev/null` discards codex's event stream (reasoning steps, tool calls, token deltas) — we don't need it, the final review already lands in `$OUT`. Stderr stays attached so real errors are still visible via `BashOutput` if the job fails.

Invoke this with `Bash({ command: "...", run_in_background: true })`. The tool returns a `bash_id`; remember it.

Per-run unique path (`mktemp`) — несколько агентов могут запускать `/codex-review` одновременно, не перезатирая друг друга.

While codex runs you may continue other useful work (e.g. preparing context, reading related files), but do NOT start a parallel codex run on the same target. If the user gave no other task, just wait for the background notification — no polling.

Flag notes:
- `-m gpt-5.5` — flagship model (most capable as of 2026-04; requires `codex-cli` ≥ 0.125.0)
- `-c 'model_reasoning_effort="xhigh"'` — maximum reasoning (valid values: `minimal|low|medium|high|xhigh`)
- `-s read-only` — sandbox prevents accidental writes during review
- `-o <file>` — writes only the final assistant message (no event spam)
- `--skip-git-repo-check` — allows running when target is a standalone file outside a repo
- Use `-C <dir>` if the review target is in a different directory than cwd

### 4. Wait for completion and present results

When the background `Bash` job completes, the harness will notify you. Then:

1. Read the output file (path was saved to `/tmp/codex-review-last-out.path`):
   ```bash
   cat "$(cat /tmp/codex-review-last-out.path)"
   ```
2. Show Codex's review to the user.
3. If there are Critical or Important findings, ask whether to fix them.

If codex failed (non-zero exit, empty output file), check `BashOutput` for the `bash_id` to see stderr, then handle per the Notes section below.

## Notes

- If Codex fails or hits rate limits, wait 30s and retry once
- If Codex fails completely, report the error and offer to do the review yourself
- For large diffs (20+ files), tell Codex to focus on the most impactful changes first
- Alternative built-in: `codex review --commit <sha>` / `codex review --base <branch>` / `codex review --uncommitted` — narrower but official code-review subcommand; prefer `codex exec` for the flexibility this command needs (plans/specs/files)
