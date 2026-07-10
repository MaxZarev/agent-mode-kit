# Slide type catalog

Every type below exists as a working demo slide in `assets/template.html` — copy the markup
from there. This file explains when to use each type and the non-obvious details.

## Reveal mechanics (applies to every slide)

- The first element of a slide (badges + h2, usually) is visible immediately; everything
  else gets `class="frag"` and is revealed one-by-one with Space / Enter / ↓ / click.
- When all frags are revealed, the next Space advances to the next slide — so the presenter
  can drive the whole deck with one key.
- An `.answer` frag (or any frag with `data-reveal`) also adds `.revealed` to the slide,
  which highlights `.opt.correct` and dims wrong quiz options.
- Order of reveal = document order. Put the punch line last.

## Types

| Type | Markup root | Use for |
|------|-------------|---------|
| Title | `.slide.title-slide` | First slide: course/meeting badge, `h1` with `<em>` accent, `.route` (session roadmap in one line), `.note` with interaction format |
| Divider | `.slide.divider` | One per major block of the source plan; `.no` = zero-padded block number, `h2` = block name, `.lead` = why this block matters |
| Icon list | `.items` > `.item` with `.ic` | Theses, warnings, properties. 3–6 items max. Emoji as visual anchor |
| Numbered list | `.items` > `.item` with `.n` | Process steps, ordered workflow. `.sub` for who-does-it or example |
| Two cards | `.cards2` > `.card` | Comparing exactly two entities (A vs B). Second card is the frag |
| Quote pair | `.quote` + `.quote.frag` | Real-life analogy as dialog; `.who` attributes the speaker and maps it to the concept |
| Punch | `.punch` | One-line takeaway, `<em>` for the accent word. Often the last frag of a slide |
| Quiz | `.opts` > `.opt` / `.opt.correct` + `.answer[data-reveal]` | Audience votes a number in chat BEFORE reveal; add badge `.badge.chat` "цифра в чат" |
| Open question | `.punch` + one or more `.answer.frag` | Provocation, "your turn" exercises; several `.answer` blocks reveal the debrief in stages |
| Chili task | `.lead` (task) + `.answer[data-reveal]` with 🌶️ in verdict | Difficulty-rating games: task on screen, audience votes 1–3, reveal shows peppers + "Почему:" |
| Bad→good pairs | `.pair` with `.bad`/`.arr`/`.good` | Rewriting vague wording into verifiable wording; red → green |
| Split | `.split` > `.col` + `img.pic` | Theses next to an illustration (3:2 columns) |
| Banner image | `img.pic.banner.frag` | Full-width scheme/diagram revealed after the lead-in; `.pic.tall` for portrait images |
| Link-out | `.rules` + `.note` + `a.go` | Rules of a game + button opening a separate deck/demo/vote page in a new tab |
| Final | items without frags + `.punch` "Вопросы?" | 3 lines to remember — no reveal, they should all be visible at once |

## Badges

- First badge on every content slide = block context: `01 · короткое-имя-блока`.
- `.badge.chat` (green) marks audience interaction: `цифра в чат`, `словами в чат`,
  `голосуем в чат`. The presenter relies on these to remember to pause.
- `.badge.acc` (amber) marks something new/special being introduced on this slide.

## Separate vote deck (vote-slides pattern)

For a long difficulty-voting game (5–10 tasks), don't inflate the main deck — generate a
second standalone file (e.g. `vote-slides.html`) linked from a Link-out slide:

- Tasks live in a JS `CARDS` array (title, department/context, task text, difficulty 1–3,
  debrief) and slides are generated from it — easy to edit tasks without touching markup.
- Shuffle tasks so difficulty levels alternate unpredictably; include decoys and borderline
  cases — those spark the best discussion.
- Each slide: task first, answer hidden behind Reveal — peppers `🌶️".repeat(n)` plus
  a "Почему:" debrief.
- Default voting channel is the meeting chat (a number). A vote button that POSTs to a
  backend (`/api/vote` → Telegram) only works deployed, not from `file://` — degrade
  gracefully to "голосуйте цифрой в чат" on fetch failure.

## Optional: Lottie animations

If the `text-to-lottie` skill is available, animations can be added to a **copy** of the
finished deck (session-5 precedent: `presentation.html` → `presentation-lottie.html`).
Keep the plain version as the fallback for the live meeting.
