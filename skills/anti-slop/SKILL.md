---
name: anti-slop
description: Remove AI writing patterns (slop) from Russian and English prose. Use this skill whenever writing, editing, reviewing, or revising any text to eliminate predictable AI tells and make it sound human. Trigger when the user asks to "deslop", "remove AI patterns", "make it sound human", "check for slop", "remove slop", "write naturally", or uses Russian equivalents like "убери слоп", "сделай человечнее", "убери ИИ-штампы", "проверь на слоп", "напиши естественно", "убери канцелярит". Also trigger when the user drafts any substantial prose (posts, articles, newsletters, scripts, descriptions) and wants natural-sounding output. Works with both Russian and English text.
---

# Anti-Slop: Remove AI Writing Patterns from Prose

Strip predictable AI patterns from writing. Make prose sound like a specific human wrote it, not like a language model generated it.

The core problem: LLMs produce text with recognizable fingerprints — overused words, formulaic structures, false profundity, metronomic rhythm. Readers detect this instantly and lose trust. This skill teaches you to catch and fix these patterns.

## Language Detection

Detect the language of the input text and apply the appropriate rules:
- For Russian text: use `references/ru-patterns.md`
- For English text: use `references/en-patterns.md`
- For mixed text: apply rules for each language to the corresponding parts

Always read the relevant reference file before editing.

## Core Rules

### 1. Cut filler phrases

Remove throat-clearing openers, emphasis crutches, meta-commentary. State the content directly. See language-specific references for full catalogs.

### 2. Break formulaic structures

Avoid binary contrasts ("Not X. Y."), negative listings, dramatic fragmentation, self-posed rhetorical questions. See `references/structures.md`.

### 3. Eliminate AI tropes

Watch for the full catalog of AI writing tells: magic adverbs, "delve" and its cousins, the "serves as" dodge, false ranges, superficial analyses, invented concept labels, grandiose stakes inflation. See `references/tropes.md`.

### 4. Use active voice with human subjects

Every sentence needs a subject doing something. "The complaint becomes a fix" is wrong — name the person who fixed it. If no specific person fits, use "we" or "you".

### 5. Be specific

No vague declaratives ("The reasons are structural"). Name the specific thing. No lazy extremes ("every," "always," "never") doing vague work. No vague attributions ("Experts argue...").

### 6. Vary rhythm

Mix sentence lengths. Two items beat three. End paragraphs differently. No em dashes. Do not stack short punchy fragments for manufactured emphasis.

### 7. Trust readers

State facts directly. Skip softening, justification, hand-holding. No "Let's break this down." No fractal summaries (telling what you'll say, saying it, summarizing what you said).

### 8. Watch formatting tells

No bold-first bullets. No unicode arrows. No em dashes. No signposted conclusions ("In conclusion..."). No "Despite these challenges..." formulas.

### 9. Do not dilute

One point per section. Do not restate the same argument in ten different ways. Do not beat a single metaphor to death.

## Quick Checks

Run these before delivering any prose:

- Heavy use of adverbs or -ly words (Russian: -о/-е наречия)? Cut them.
- Any passive voice? Find the actor, make them the subject.
- Inanimate thing doing a human verb? Name the person.
- Any throat-clearing opener? Cut to the point.
- Any "not X, it's Y" contrasts? State Y directly.
- Any self-posed rhetorical question answered immediately? Fold into a statement.
- Three consecutive sentences match length? Break one.
- Paragraph ends with a punchy one-liner? Vary it.
- Em dash anywhere? Remove it.
- Vague declarative? Name the specific thing.
- Same metaphor used more than twice? Replace or cut.
- Tricolon (three-item list)? Use two items or one.
- "It's worth noting" / "Stoit otmetit'"? Delete.
- "Despite these challenges..." formula? Rewrite.
- Bold-first bullet pattern? Remove bold leads.

## Scoring

When reviewing text, rate 1-10 on each dimension:

| Dimension | Question |
|-----------|----------|
| Directness | Statements or announcements? |
| Rhythm | Varied or metronomic? |
| Trust | Respects reader intelligence? |
| Authenticity | Sounds like a specific human wrote it? |
| Density | Anything cuttable? |

Below 35/50: revise and explain what needs fixing.

## Reference Files

Read these before editing:

- `references/ru-patterns.md` — Russian slop words, phrases, and patterns (primary for Russian text)
- `references/en-patterns.md` — English slop words, phrases, and patterns
- `references/structures.md` — Structural patterns to avoid (language-agnostic)
- `references/tropes.md` — Full catalog of AI writing tropes with examples
