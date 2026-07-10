---
name: estimate
description: "..."
---

<!-- hidden: Estimate development time and create cost breakdowns for projects. -->

# Project Estimation Skill

Estimate development time for new projects or modifications to existing ones. Produce a structured breakdown with optimistic/realistic/pessimistic ranges, a Google Sheets spreadsheet with formulas, and an HTML document for the client.

## Context: AI-Accelerated Development

The user develops with Claude Code running in 2-3 parallel windows. This dramatically changes time estimates:

- **Coding (AI-assisted)**: 3-5x faster than traditional manual development. Frontend, backend, CRUD, integrations, DevOps — all done by the agent.
- **Review & QA (manual/semi-manual)**: Code review, testing production features, backend verification, security checks — done with human oversight. This phase is NOT accelerated the same way and takes proportionally more time.
- **Planning & Analysis**: Reading specs, understanding requirements, designing architecture — partially accelerated but still requires human judgment.

## Workflow

### Step 1: Gather Requirements

Collect the project brief. Sources may include:
- Text pasted in chat
- PDF or HTML files (read them)
- Telegram messages (use tg-dialogs skill if needed)
- Links to documents (fetch them)

If requirements are vague or incomplete, ask clarifying questions. Focus on:
- Core features vs nice-to-haves
- Integrations with external services
- Auth/payments/admin panels (these add significant complexity)
- Mobile responsiveness requirements
- Deployment environment

### Step 2: Break Down into Phases and Tasks

Decompose the project into logical phases. Typical phases:

1. **Analysis & Architecture** — understanding specs, designing DB schema, choosing stack, planning API
2. **Environment Setup** — repo init, CI/CD, Docker, deployment pipeline
3. **Core Development** — main features, backend, frontend, integrations
4. **Admin Panel / CMS** (if applicable)
5. **Testing & QA** — manual testing, bug fixes, edge cases
6. **Code Review & Security** — reviewing AI-generated code, security audit
7. **Deployment & Launch** — production deploy, monitoring, DNS, SSL
8. **Buffer** — unexpected issues, scope changes, client feedback rounds

Within each phase, list specific tasks.

### Step 3: Estimate Each Task

For each task, estimate hours in three scenarios:

| Scenario | Meaning | Multiplier |
|----------|---------|------------|
| **Optimistic** | Everything goes smoothly, no surprises | 1.0x |
| **Realistic** | Normal amount of issues and iterations | 1.3-1.5x |
| **Pessimistic** | Significant complications, unclear requirements | 1.8-2.5x |

**Estimation rules:**

- **AI-coded tasks** (frontend, backend, CRUD, APIs, integrations): estimate as if a senior dev does it, then divide by 3-5x for the coding part. Add review time separately.
- **Review/QA tasks**: estimate at normal human speed. These are NOT accelerated. For every 2-4 hours of AI coding, budget 1-2 hours of review.
- **Infrastructure/DevOps**: partially accelerated (2-3x). Docker, CI/CD, deployment scripts are well-suited for AI but need careful verification.
- **Minimum task size**: 0.5 hours. Don't estimate below this — context switching overhead exists even with AI.
- **Client communication rounds**: budget 1-2 hours per major feedback round.

### Step 4: Ask About Current Workload

Before calculating timelines, ask the user:
> "How many hours per day/week can you dedicate to this project in the coming weeks?"

Use calendar skill if the user wants to check their schedule.

### Step 5: Create Google Sheets Spreadsheet

Use the gsheets skill to create a spreadsheet. Structure:

**Sheet 1: "Estimate"**

| A | B | C | D | E | F |
|---|---|---|---|---|---|
| Phase | Task | Type | Optim. (h) | Realistic (h) | Pessim. (h) |
| Analysis | Review specs | manual | 2 | 3 | 4 |
| Development | Auth API | ai+review | 1.5 | 2 | 3 |
| ... | ... | ... | ... | ... | ... |
| **TOTAL** | | | =SUM() | =SUM() | =SUM() |

Column C "Type" values:
- `ai` — fully AI-accelerated
- `ai+review` — AI coding + manual review
- `manual` — manual/semi-manual work
- `infra` — infrastructure/DevOps

**Sheet 2: "Timeline"**

| A | B | C | D |
|---|---|---|---|
| Parameter | Optim. | Realistic | Pessim. |
| Total hours | =formula | =formula | =formula |
| Hours per day | (user input) | (user input) | (user input) |
| Working days | =formula | =formula | =formula |
| Calendar weeks | =formula | =formula | =formula |
| Start date | (user input) | | |
| Estimated completion date | =formula | =formula | =formula |

**Formatting:**
- Bold headers, frozen first row
- Phase rows with background color to visually separate sections
- Totals row with bold + border
- Auto-width columns

### Step 6: Generate HTML Document for Client

Create a clean, professional HTML document. Save to a file the user can send.

Structure:
```
Development Timeline Estimate: [Project Name]
Date: [today's date]

1. Project Description (brief summary)
2. Phases and Tasks (table with phases, tasks, and hour ranges)
3. Total Estimate
   - Optimistic: X hours (~Y working days)
   - Realistic: X hours (~Y working days)
   - Pessimistic: X hours (~Y working days)
4. Timeline (with user's availability factored in)
5. Assumptions and Risks
6. Notes
```

**HTML styling:** clean, minimal, printable. Use a neutral color scheme (not flashy). The document should look professional when opened in a browser or printed to PDF. Include a simple CSS with proper typography, table borders, and responsive layout.

### Step 7: Present Results

Show the user:
1. Link to Google Sheets spreadsheet
2. Path to HTML file
3. Brief summary: total hours (realistic), estimated duration, key risks

Ask if adjustments are needed — the user often has domain knowledge that changes estimates (e.g., "this integration is actually simple because we already have the API" or "this part will be harder because the legacy code is messy").

## Estimation Heuristics by Feature Type

These are rough baselines for realistic estimates (AI-assisted development + review):

| Feature | Coding (h) | Review/QA (h) | Total (h) |
|---------|------------|---------------|-----------|
| Auth (email+password) | 1-2 | 1-2 | 2-4 |
| Auth (OAuth/social) | 2-3 | 1-2 | 3-5 |
| CRUD entity (simple) | 0.5-1 | 0.5 | 1-1.5 |
| CRUD entity (complex, relations) | 1-2 | 1 | 2-3 |
| Payment integration | 2-4 | 2-3 | 4-7 |
| Email/notification system | 1-2 | 1 | 2-3 |
| File upload + storage | 1-2 | 1 | 2-3 |
| Admin panel (basic) | 2-4 | 1-2 | 3-6 |
| Landing page | 1-2 | 0.5-1 | 1.5-3 |
| Dashboard with charts | 2-4 | 1-2 | 3-6 |
| API integration (per service) | 1-3 | 1-2 | 2-5 |
| Search (full-text) | 1-2 | 1 | 2-3 |
| Real-time (websockets) | 2-4 | 2-3 | 4-7 |
| Docker + CI/CD setup | 1-2 | 1 | 2-3 |
| Production deploy | 1-2 | 1-2 | 2-4 |

These are starting points — adjust based on actual project complexity. The heuristics assume a modern stack and clean requirements. Legacy code, unusual integrations, or poor documentation can 2-3x any estimate.

## Important Notes

- Always present ranges, never single numbers. Single-point estimates create false precision.
- The buffer phase (10-20% of total) is not optional — it accounts for unknowns.
- If the project scope is unclear, say so explicitly and note which parts have uncertain estimates.
- For very large projects (100+ hours realistic), suggest phased delivery with estimates per phase.
- Update estimates when new information surfaces — estimates are living documents.
