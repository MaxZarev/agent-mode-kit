---
name: html-presentation
description: "Build a self-contained dark-theme HTML slide deck for presenting live at a meeting, lesson, or talk — keyboard-driven, with progressive reveal (fragments), audience-interaction slides (quizzes with 'цифра в чат', hidden answers, chili-pepper difficulty votes), and a final reconcile pass against the host's plan. Use whenever the user wants a presentation or slides from an outline/plan/conspect: 'сделай презентацию', 'собери слайды к сессии/встрече/докладу', 'слайды с раскрытием по клику', 'голосовалка с перчиками', 'make me a slide deck', 'HTML presentation from this plan' — even if they don't say 'HTML'. NOT for PowerPoint/Google Slides files or for lesson conspects (those are markdown)."
---

# html-presentation — live-meeting slide deck from a host's plan

One self-contained HTML file (CSS + JS inline, no dependencies), opened straight from disk
in a browser. Dark projector-friendly theme, amber accent, `clamp()`/vh typography that
scales to any screen. The presenter drives everything with one key: Space reveals the next
fragment, and when the slide is exhausted, advances to the next slide.

Born from the session-5 deck of the claude-agents course — the patterns here (progressive
reveal, chat-interaction badges, hidden answers, chili votes) survived a real live session.

## Inputs

1. **The host's plan** — a bullet outline, lesson-plan.md, conspect, or dictated notes.
   This is the source of truth for structure AND terminology. If there is no plan at all,
   ask for one (or for 5 minutes of dictation) before building anything.
2. **Existing images** — if the material already has illustrations (lesson assets, robots,
   schemes), reuse them: relative paths, placed where they reinforce a point. Don't
   generate new images unless asked.

## Workflow

### 1. Map the plan to a slide skeleton

- Each top-level block of the plan → a numbered `divider` slide (01, 02, …).
- Each sub-topic → one content slide. One idea per slide; 3–6 bullets max.
- Every content slide carries a badge with its block: `01 · recap`.
- Propose the skeleton (block list + slide count per block) to the user before writing
  all the content if the plan is large or ambiguous — cheaper to move blocks now.

### 2. Build the deck from the template

Copy `assets/template.html` (next to this file) to the target location and replace the
demo slides. **Keep the CSS and the JS untouched** — they encode the reveal mechanics,
quiz highlighting, progress bar, and keyboard handling that are already proven live.

Choosing a slide type per sub-topic: see `references/slide-types.md` (read it — the
catalog maps content shapes to markup and lists non-obvious details like `data-reveal`).

Writing rules that make a deck presentable rather than readable:

- Slides support a **speaker**, they don't replace one. Short lines; the key term of each
  bullet in `<b>`; details and examples go into `.sub`, not the main line.
- Everything after a slide's heading is `class="frag"` — the presenter talks first,
  reveals second. A slide that shows everything at once kills the discussion.
- Answers are always hidden: quiz debriefs, chili ratings, "your turn" checklists live in
  `.answer.frag` so the audience commits (votes in chat) before seeing the resolution.
- Sprinkle interaction: every 5–7 slides something with a `.badge.chat` — a quiz, an open
  question, a vote. These badges are the presenter's cue to pause.
- Language of the deck = language of the plan (usually Russian).

### 3. Reconcile against the plan (do not skip)

This step exists because it failed once in real use: a slide invented its own framing
("руками · лёгкий скилл · конвейер") that didn't match what the host meant, and he caught
it only by re-reading the deck against his notes.

Walk the source plan item by item and check:

- every plan item is covered by a slide (or consciously dropped — say so);
- terminology on the slides is **the host's**, not your paraphrase — the host will speak
  over these slides from memory of their own plan;
- nothing on the slides introduces structure or claims absent from the plan.

Report the mapping (plan item → slide) with any gaps or renames, and fix what the user
flags.

### 4. Deliver

- Save next to the source material (for course sessions: `content/<course>/session-N/`).
- Tell the user to open the file in a browser; keys: ← → slides, Space/click reveal.
- Offer optional extras only after the base deck is approved: a separate chili vote deck
  (see "Separate vote deck" in `references/slide-types.md`), Lottie animation on a copy
  (`text-to-lottie` skill), or deploying the deck (Vercel) if remote voting is wanted.
