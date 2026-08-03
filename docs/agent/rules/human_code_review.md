---
status: active
scope: documentation
last_verified: 2026-07-14
owner: {{OWNER}}
applies_to:
  - docs/code_maps/
  - docs/working_logs/plans/
---

# Rule: Human Code Review — Code Map Maintenance

## When to create a code map

A code map is required when new or significantly rewritten code meets **any** of these:

1. It is a **primary entry point** for users or other scripts
2. It has a **3+ step** data processing pipeline
3. It has significant **branches, retries, caching, state machines, or async flows**
4. It submits training, evaluation, or data generation **expensive jobs**
5. It calls multiple modules, but the entry file **doesn't reveal the full flow**
6. It contains **research-critical algorithms**
7. A human reviewer **cannot answer "how does it run?" within a few minutes**

## When a code map is NOT needed

- Parameter-forwarding scripts, simple shell wrappers
- Single-format conversion tools
- One-off migration/fix scripts
- Small, obvious utilities (< 50 lines)
- Pure configuration files
- Low-complexity glue code

## When to update a code map

| Trigger | Action |
|---------|--------|
| New major entrypoint or pipeline created | Create a corresponding `docs/code_maps/` document |
| Control flow, data flow, or external behavior changes | Update the affected code map in the same task |
| Script internals change without conceptual behavior change | Code map update not required |
| Existing code map no longer matches implementation | Fix it in the same task; do not defer |

## Hard rules

1. **A code map documents the current implementation, not the intended design.** Do not describe planned behavior as if it already exists.
2. **Every code map must list concrete code paths and named symbols.** A diagram without Code Pointers is not considered complete.
3. **Mermaid/pseudocode must match the code.** If a diagram shows a branch that doesn't exist in code (or vice versa), it is an error that must be fixed.

## Template selection

- **Default: light template** (`TEMPLATE_LIGHT.md`): Purpose + Flow Diagram + Core Pseudocode + Code Pointers
- **Complex modules: full template** (`TEMPLATE_FULL.md`): When the module has multiple critical branches, manages internal state, coordinates multiple models, or has high algorithmic complexity

## Human Review Guide in Plans

Every Plan's Execution Report must include a `Human Review Guide` section:

- **What changed conceptually**: 1-2 sentences on the core logic change
- **Execution flow**: Mermaid diagram of the new/changed flow
- **Core pseudocode**: Pseudocode of the core logic
- **Key code pointers**: Critical files and symbols
- **Code maps created/updated**: Links to new or updated code maps (if applicable)

### When to create a permanent code map vs. only write the review guide

- The Plan's Human Review Guide explains "what changed this time" (temporary)
- Only **long-lived, maintenance-worthy flows** get a permanent code map
- One-off tasks and small changes only need the review guide in the plan

## Storage paths

```text
docs/code_maps/
├── systems/     # Cross-module pipelines
├── scripts/     # Single scripts
└── modules/     # Core algorithms/modules
```

## Link from registry/scripts.md

When a script has a corresponding code map, add to its registry entry:
```
**Code Map**: [`docs/code_maps/scripts/xxx.md`](../code_maps/scripts/xxx.md)
```
