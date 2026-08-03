---
status: active
created: YYYY-MM-DD
---

# <Task Title>

## User Goal

> Written by the user. Can be informal, any language, incomplete.
> Agent must NOT delete, overwrite, or alter this section.

...

## For Agent: Execution Protocol

1. Read and follow `docs/agent/always.md`.

2. Based on **User Goal**, fill in:
   - `Agent Refined Plan`
   - `Required Agent Resources`
   - `Acceptance Criteria`

3. To find available Rules, Skills, or Playbooks, check:
   - `docs/registry/agent_system.md`
   - Do not load everything — only what's relevant.

4. When refining:
   - User Goal is the highest source of truth.
   - Do not omit any explicit user requirement.
   - Do not expand scope beyond what was asked.
   - Non-blocking side issues: note them, don't pursue them.
   - If there's ambiguity, danger, or high cost: ask the user first.

5. After implementation and verification, fill in the **Execution Report**.

6. Before user approval:
   - Set status to `awaiting_approval`, not `completed`.
   - Do not archive the plan.
   - Do not describe experimental results as final conclusions.

7. After user approval, complete this **archival checklist** (do not skip):
   - [ ] Update status to `completed`, move to `plans/completed/`.
   - [ ] Update `docs/working_logs/active.md`.
   - [ ] **Register new assets**: new scripts → `registry/scripts.md`; new data/outputs → `registry/outputs.md` or `registry/datasets.md`.
   - [ ] **Register new agent resources**: new rules/skills/playbooks → `registry/agent_system.md`.
   - [ ] If document structure changed, update `docs/README.md`.
   - [ ] If an experiment was run, write a run log to `working_logs/runs/`.
   - [ ] **Evaluate Code Map**: per `rule:human-code-review`, decide if this implementation needs a new or updated `docs/code_maps/` document.

## Agent Refined Plan

### Understanding

<!-- Agent's interpretation of the task, in a few sentences -->

### Scope

#### In Scope

- ...

#### Out of Scope

- ...

### Steps

1. ...
2. ...
3. ...

## Required Agent Resources

### Rules

- ...

### Skills

- ...

### Playbooks

- ...

## Acceptance Criteria

- [ ] ...
- [ ] ...
- [ ] ...

---

## Execution Report

### Summary

- ...

### Changed Files

| File | Change |
|------|--------|

### Commands

```bash
# Key commands executed
```

### Verification Results

```text
# Output and conclusions
```

### Outputs

- ...

### Remaining Issues

- ...

### Human Review Guide

#### What changed conceptually

- ...

#### Execution flow

```mermaid
flowchart TD
    A[...] --> B[...]
```

#### Core pseudocode

```text
...
```

#### Key code pointers

* `path/file.py:function_name`

#### Code maps created/updated

* (link to new or updated code map, or N/A)

### Suggested Next Step

- ...
