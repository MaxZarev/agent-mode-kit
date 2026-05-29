# Russian Slop Patterns

## Slop Words (overused in AI-generated Russian text)

These words appear far more frequently in LLM output than in natural human Russian writing. Their presence in clusters is a strong AI signal.

### Adjectives / Participles
- ключевой, важнейший, фундаментальный, критический, значимый
- уникальный, беспрецедентный, революционный, инновационный, передовой
- комплексный, всесторонний, многогранный, целостный, системный
- эффективный, оптимальный, результативный, продуктивный
- динамичный, стремительный, масштабный, глобальный
- неотъемлемый, неразрывный, неоспоримый, несомненный, бесспорный
- органичный, гармоничный, сбалансированный

### Nouns
- ландшафт, палитра, спектр, парадигма, экосистема, фреймворк
- синергия, трансформация, оптимизация, имплементация
- тенденция, динамика, вектор, траектория
- потенциал, перспектива, горизонт, контекст
- стейкхолдер, бенчмарк, драйвер (роста), катализатор
- краеугольный камень, фундамент, основа основ, столп

### Verbs
- обеспечивать, способствовать, содействовать
- формировать, трансформировать, оптимизировать
- подчёркивать (важность), акцентировать (внимание)
- интегрировать, имплементировать, масштабировать
- выстраивать, выявлять, задействовать
- демонстрировать, иллюстрировать, свидетельствовать

### Adverbs (kill almost all of them)
- безусловно, несомненно, бесспорно, однозначно
- существенно, значительно, кардинально, принципиально
- органично, гармонично, неразрывно, всецело
- активно, эффективно, успешно, динамично
- по сути, в целом, в конечном счёте, в конечном итоге

## Filler Phrases (throat-clearing)

Remove these. State the point directly.

### Openers
- "Стоит отметить, что..."
- "Важно подчеркнуть, что..."
- "Необходимо отметить..."
- "Нельзя не отметить..."
- "Следует обратить внимание на..."
- "В данном контексте..."
- "В современных реалиях..."
- "В условиях стремительно меняющегося мира..."
- "На сегодняшний день..."
- "В эпоху цифровой трансформации..."
- "Как известно..."
- "Не секрет, что..."
- "Очевидно, что..."

### Emphasis crutches
- "И это неслучайно."
- "И это не преувеличение."
- "И это только начало."
- "Давайте разберёмся."
- "Давайте рассмотрим подробнее."

### Meta-commentary
- "В данной статье мы рассмотрим..."
- "Рассмотрим основные аспекты..."
- "Перейдём к рассмотрению..."
- "Подводя итоги, можно сказать..."
- "Резюмируя вышесказанное..."

## Formulaic Phrases

These multi-word constructions are strong AI signals. Replace with direct statements.

| Avoid | Why |
|-------|-----|
| "играет ключевую роль" | Vague. Name the specific contribution. |
| "является неотъемлемой частью" | Just say what it does. |
| "открывает новые горизонты" | Empty grandeur. |
| "выводит на новый уровень" | What level? Be specific. |
| "в условиях современных вызовов" | Name the specific challenge. |
| "позволяет эффективно решать" | Say what it solves and how. |
| "представляет собой уникальный" | Just describe it. |
| "способствует развитию" | Who does what specifically? |
| "обеспечивает комплексный подход" | Meaningless. Be concrete. |
| "создаёт прочную основу для" | Foundation of what, exactly? |
| "в конечном счёте" | Usually deletable. |
| "тем не менее" (overused) | Once per text max. Vary: "но", "однако", "при этом". |
| "таким образом" (as conclusion) | Weak closer. State the conclusion directly. |

## Structural Patterns (Russian-specific)

### The "Не только X, но и Y" crutch
Russian AI text overuses "не только... но и..." to create false depth. State both things directly.

**Avoid:** "Это не только повышает эффективность, но и создаёт новые возможности."
**Better:** "Эффективность растёт. Появляются варианты, которых раньше не было."

### The "С одной стороны... с другой стороны" formula
Balanced-sounding but hollow. Pick a side or state the tension directly.

**Avoid:** "С одной стороны, это создаёт определённые трудности. С другой стороны, открывает новые перспективы."
**Better:** "Трудности есть — [назвать какие]. Но [конкретная выгода] перевешивает."

### Канцелярит (bureaucratic language)
Russian LLMs inherit Soviet-era bureaucratic patterns. Kill them.

- "осуществлять" → "делать"
- "производить" (in abstract sense) → конкретный глагол
- "в рамках" → skip or use "в", "на", "при"
- "на данный момент" → "сейчас"
- "в настоящее время" → "сейчас"
- "является" → skip, use dash or direct predicate
- "данный" → "этот"
- "вышеуказанный/нижеследующий" → just name the thing
- "в связи с тем, что" → "потому что"
- "ввиду того, что" → "потому что"

### Numbered list disguised as prose
"Во-первых... Во-вторых... В-третьих..." — strong AI signal when mechanical. If the items don't build on each other, just list them or weave naturally.

### The "Подводя итог" conclusion
Explicit signposting of conclusions. Let the conclusion speak for itself.

**Avoid:** "Подводя итог, можно сказать, что данный подход демонстрирует высокую эффективность."
**Better:** Just state the conclusion without the preamble.

## Passive Voice (Russian)

Russian passive constructions to catch and rewrite:

| Passive | Active |
|---------|--------|
| "было принято решение" | "[кто] решил" |
| "проводится работа" | "[кто] работает над" |
| "были достигнуты результаты" | "[кто] добился" |
| "уделяется особое внимание" | "[кто] сосредоточился на" |
| "осуществляется контроль" | "[кто] контролирует" |
| "ведётся разработка" | "[кто] разрабатывает" |

## Rhythm in Russian

Russian sentences naturally run longer than English ones. Do not force English-style staccato rhythm onto Russian prose — it reads as unnatural. Instead:
- Mix long complex sentences with short direct ones
- Avoid 3+ sentences of the same length in a row
- Do not abuse dash (тире) as a dramatic pause — one per paragraph max
- Avoid comma-heavy bureaucratic constructions (3+ subordinate clauses)
