---
name: tg-copy
description: Compose a formatted Telegram message/post from given content and copy it to the macOS clipboard so that pasting into Telegram (Cmd+V) preserves bold, italic and monospace formatting. Explicit /tg-copy invocation only.
disable-model-invocation: true
allowed-tools: Bash, Write, Read
---

Turn the user's content into a polished Telegram message, get the text
approved in chat, then place it on the clipboard with rich formatting.
The user pastes it into Telegram with Cmd+V. This is a clipboard utility
for ad-hoc messages; for scheduled channel posts with animated emoji use
the `tg-schedule` skill instead.

## Workflow

### 1. Compose the message text

Source material: `$ARGUMENTS`, recent conversation context, or a file the
user points to. Write in the user's language (usually Russian).

Readability is the whole point — a Telegram post is skimmed on a phone
screen, not read like an article. Rules:

- First line — a short bold headline with a leading emoji.
- **Paragraphs of 1–3 lines max (~250 chars).** If a paragraph runs longer,
  split it or turn it into marker lines. A wall of text is a hard failure
  even if the content is good.
- Blank line between every block.
- Enumerations, steps, features — always as separate lines with emoji
  markers or numbers, never buried inside a paragraph.
- **Emoji generously and variedly — Telegram convention.** Every marker
  line gets its own emoji matched to its meaning, not the same ✅ repeated;
  section labels get one too. Draw from the full range: 🔧 ⚙️ 🛠 (fixes),
  ✅ ❌ ⚠️ (status), 🚀 ⚡ 🔥 (wins), 💡 🧠 (ideas), 📦 📁 🗂 (files/things),
  🔑 🔒 🍪 (access), 📊 📈 (data), 👉 ➡️ (pointers), 🎯 🏁 (results).
  Aim for an emoji every 2–3 lines of the post; body sentences can carry
  one inline when it fits naturally. Stop short of noise: one emoji per
  line, not chains.
- Bold section labels with an emoji («🔍 Что случилось:», «📋 Рецепт:»,
  «🎯 Итог:») every few blocks so the eye can anchor.
- **Bold 1–2 key phrases inside body text** — the skim path: reading only
  the bold parts should convey the gist of the post.
- Italic for asides and qualifiers; `code` style for tool names, commands,
  paths.
- End with a takeaway or call-to-action line, not a trailing detail.

After composing, run the `anti-slop` skill on the draft (read its SKILL.md
and apply its rules) — posts full of AI tells read as spam in Telegram.

### 2. Get the text approved in chat

Show the full draft in the chat (markdown bold/italic maps 1:1 to the
future HTML) and stop: ask the user for edits or an "ок". Do NOT touch the
clipboard yet — the user must be able to iterate on wording cheaply,
without pasting anything.

Apply requested edits and show the updated draft again; repeat until the
user approves.

### 3. Write the HTML fragment

Save to a temp file (scratchpad or `mktemp`). Telegram keeps only inline
formatting, so use exactly these tags:

- `<b>`, `<i>`, `<u>`, `<s>` — emphasis
- `<code>` — monospace (tool names, commands)
- `<a href="…">` — links
- `<br>` — line breaks (do NOT use `<p>`, `<ul>`, `<li>`, headings —
  they paste as plain text or add stray spacing)

Wrap everything in one div so the paste has a uniform font:

```html
<div style="font-family: Helvetica; font-size: 13px;">
🎬 <b>Headline</b><br><br>
Body text with <b>key phrase</b> and <code>tool-name</code>…<br><br>
<b>🔍 Section:</b><br>
⚙️ point one<br>
🚀 point two
</div>
```

Emoji are written as-is (UTF-8), never as entities.

### 4. Copy to clipboard

```bash
<skill-dir>/scripts/tg-clipboard.sh /path/to/post.html
```

The script converts HTML→RTF (`textutil`), puts HTML + RTF + plain-text
flavors on the clipboard in one AppleScript call, verifies the flavors are
actually there (`clipboard info`), and prints a plain-text preview. Read the
script if a different flavor mix is ever needed.

Why three flavors: it is still one paste — Telegram Desktop reads the HTML
flavor, native Telegram for macOS reads RTF, everything else falls back to
plain text. A rich-only clipboard makes some apps paste raw RTF source
("hieroglyphs"), so the plain-text fallback is not optional.

### 5. Report to the user

The text was already approved in step 2, so no need to repeat it — just
confirm the clipboard is set and remind: paste with plain **Cmd+V** —
Cmd+Shift+V strips formatting. If the user says the clipboard is empty or
unformatted, something overwrote it in between (clipboard managers do
this) — just rerun step 4.
