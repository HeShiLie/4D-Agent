# Personal Notes

A space for humans to save tentative, unverified, but potentially valuable thoughts.

## Three subdirectories

| Directory | Purpose | Format |
|-----------|---------|--------|
| `inbox/` | Quick scratch, don't know where it goes yet | None — can be messy |
| `ideas/` | Hypotheses not yet in a formal plan | Minimal front matter |
| `analyses/` | Human interpretation of experiment results (not machine logs) | Minimal front matter |

## How this differs from other directories

| Content | Location |
|---------|----------|
| What commands were run, where output is | `working_logs/runs/` |
| What I think happened after looking at output | `notes/analyses/` |
| A sudden idea for a new metric | `notes/ideas/` |
| A decision to implement that metric next week | `plans/active/` |
| A verified, reusable technical fact | `knowledge/` |
| A significant technical decision with rationale | `adr/` |

Key distinction: `runs/` records facts, `analyses/` records human interpretation.

## Flow

```
inbox/ → ideas/ → plans/active/ → runs/ + analyses/ → knowledge/ → adr/
```

Most notes stay in `notes/` or get discarded — that's normal.

## File template (optional)

```markdown
---
status: raw
created: YYYY-MM-DD
related:
  - working_logs/runs/xxx.md
---

# Title

## What I observed
## My hypothesis
## How to verify
```

`related` and front matter are optional. The point is to make writing frictionless.

## Agent rules

- Do not load notes by default.
- Read a note only when explicitly referenced or when searching prior ideas/analyses.
- Treat notes as hypotheses, not verified facts.
- Do not promote note content to knowledge, plans, or decisions without user approval.
