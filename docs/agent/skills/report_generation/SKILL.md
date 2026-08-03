---
status: active
scope: general
last_verified: {{DATE}}
owner: {{OWNER}}
---

# Skill: Daily / Weekly Report Generation

## When to use

When the user asks for a daily report, weekly summary, or progress update.

This skill is read-only — it extracts and summarizes existing docs, it does not run experiments or modify code.

---

## Information sources (priority order)

1. **Plans** — `docs/working_logs/plans/completed/` and `active/`
   - Extract: Summary, Changed Files, Verification Results, Outputs, Remaining Issues
2. **Active state** — `docs/working_logs/active.md`
   - Extract: Current task, status, next action
3. **Run logs** — `docs/working_logs/runs/`
   - Extract: Experiment results, output paths, delivery status
4. **Registry** — `docs/registry/`
   - Supplement only: script names, output locations

Do not load the entire `docs/` tree. Read only what is relevant to the date range.

---

## Date filtering

### Daily report

Match files with `MMDD` prefix for the requested date:
- `plans/completed/0709*.md`, `plans/active/0709*.md`
- `active.md` (always)
- Related `runs/` entries

### Weekly report

Match all days in the natural week (Mon-Sun).

### Cross-day plans

A plan may be created on one day and completed on another. Include it if:
- Its Execution Report indicates completion within the reporting period
- It is currently in `active/` during the reporting period

---

## Output format

### Default style: topic-based

See `docs/working_logs/daily/_TEMPLATE.md` for the template.

Key principles:
- Group by work topic, not by completion status
- Natural language descriptions with inline details
- End each topic with a status tag
- No rigid section structure (no "Key Conclusions" / "Risks" / "Tomorrow")

### Collaborator style

For updates to collaborators — emphasize deliverables, paths, and usage instructions.

### Self style

For personal work logs — preserve exploration details, failed routes, and TODOs.

---

## Content rules

### Exploratory work

If the summary contains signals like "tried", "weak signal", "limited", "tentative":

Good: "Explored two evaluation approaches for terrain detection; VLM-based had no discriminating power, pose-based shows weak but directionally correct signal — using pose-based as interim metric."

Bad: "Completed terrain evaluation method." (overstates certainty)

### Confirmed deliverables

Only present as confirmed if the plan has:
- `status: awaiting_approval` or `completed`
- Complete Execution Report with verification results
- Outputs that actually exist

### Numbers

Preserve exact numbers from source docs. Do not round or approximate unless the source does.

---

## Execution steps

1. Determine report type (daily/weekly) and date range
2. Read `active.md`
3. Filter and read relevant plans, runs, and registry entries
4. Group content by topic (not by source file)
5. Deduplicate: prefer completed plan > active.md > run log > registry
6. Generate report in the requested style
7. Self-check: no fabricated numbers, no overclaimed results, remaining issues preserved

---

## Do not

- Fabricate experiment results or completion dates
- Move plan files or update registries
- Start training, inference, or cluster jobs
- Load the entire knowledge base into context
