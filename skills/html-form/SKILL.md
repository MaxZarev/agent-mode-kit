---
name: html-form
description: "Generate a single throwaway local HTML page so the user can make a structured choice or input visually (checkboxes, radio groups, text fields, dropdowns, sliders) and copy the result back into chat as structured text the agent can parse. Use when collecting several toggles/selections/fields at once is easier visually than back-and-forth Q&A or AskUserQuestion — e.g. picking which items/tools/options to enable, filling a small config, multi-field input, prioritizing a list. Triggers (RU): 'сделай форму с чекбоксами', 'отрисуй чеклист и я отмечу', 'собери мой выбор', 'дай страницу заполню и вставлю обратно', 'html форму чтобы я выбрал'. Triggers (EN): 'make an HTML form/picker I fill and paste back', 'generate a checklist page', 'build a throwaway editor for these options'. NOT for production web pages, real app UI, or a single yes/no — use AskUserQuestion for 1-4 simple choices."
allowed-tools: Write, Bash, Read
---

# html-form — collect structured input via a throwaway HTML page

A recognized Claude Code pattern (Anthropic blog: *"the unreasonable effectiveness of HTML"*):
build a single-file, purpose-built HTML page, let the user fill it in a browser, and end
with an **export button** that turns their UI actions back into structured text to paste
into chat. No server, no build step, no dependencies.

## When to use vs. not

Use when the user must make **many** selections / fill **multiple** fields and doing it as
chat Q&A would be tedious: "pick which of these 50 tools to enable", "fill this config",
"rate/prioritize this list".

Do NOT use for 1–4 simple mutually-exclusive choices — `AskUserQuestion` is better there.
Do NOT use to build real/production web UI.

## Workflow

1. **Build the page** from the template. Read the skeleton:
   `<skill-dir>/assets/template.html`
   Copy it to the session scratchpad dir, then edit only the `TITLE`, `SUBTITLE`, and
   `ITEMS` config block at the top of the `<script>`. Do not touch the CSS/JS below it
   unless the user needs a field type the template lacks.
2. **Write** the adapted file into the scratchpad dir (NOT the user's project), e.g.
   `<scratchpad>/<name>-form.html`.
3. **Open it** for the user:
   - macOS: `open "<path>"`
   - Linux: `xdg-open "<path>"`
4. Tell the user to fill it, click **Copy result**, and paste the block back into chat.
5. **Parse** the pasted block (format below) and act on it.

## Output format the page produces (parse this)

```
=== FORM RESULT: <title> ===

[checkboxes]
ON: itemA, itemB, ...
OFF: itemC, itemD, ...

[fields]
key1 = value1
key2 = value2
комм: itemA = first line\nsecond line
```

Sections appear only if that field type is present. `ON`/`OFF` cover every checkbox so you
always know the full intent (selected AND deselected), not just the positives.

Multiline values (textareas, per-checkbox comments) are emitted as ONE line with literal
`\n` in place of newlines — decode when parsing. Per-checkbox comments use the key
`комм: <checkbox id>` and are included only when non-empty.

## Supported field types (in `ITEMS`)

- `{type:"section", label}` — a group header (visual only).
- `{type:"checkbox", id, label, desc?, badge?, checked?, comment?}` — `badge` is a small
  colored tag (e.g. `"read"`, `"write"`, `"danger"`, `"rec"`); `checked:true` pre-selects
  (use for your recommended defaults); `comment:true` (or a placeholder string) adds an
  auto-growing MULTILINE textarea under the row — the user's notes/corrections for that
  item, exported as `комм: <id> = ...` (newlines escaped as `\n`).
- `{type:"radio", id, label, options:[...], value?}` — single choice.
- `{type:"select", id, label, options:[...], value?}` — dropdown.
- `{type:"text", id, label, placeholder?, value?}` / `{type:"textarea", ...}`.
- `{type:"slider", id, label, min, max, step?, value?}`.

## Hard requirements (the template already satisfies these — keep them)

- **Single self-contained file** — inline CSS + JS, no external assets, works from `file://`.
- **Export button** that builds the structured block above.
- **Clipboard fallback** — try `navigator.clipboard`, fall back to `execCommand('copy')`,
  and ALWAYS mirror the result into a readonly `<textarea>` so the user can `Cmd+C` manually
  (clipboard API is often blocked on `file://`).
- **Pre-check your recommendations** and label them with a `rec` badge so the user starts
  from a sensible state, not a blank one.

If you need a field type or layout the template doesn't cover, read the template fully and
extend the small renderer — keep the export format stable so parsing back still works.
