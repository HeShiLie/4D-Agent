# Code Maps — Human Code Understanding Layer

## Positioning

```text
registry        = where things are (asset index)
code_maps       = how things work (implementation understanding)
knowledge       = external concepts and background
ADR             = why a decision was made
working_logs    = what happened recently
```

Code Maps are the human entry point for understanding code. They solve the problem of "human-code disconnect" — when AI-generated code grows, humans need a way to answer "how does this module actually run?" in minutes, not hours.

## When a code map is required

Create or update a code map when **any** of these apply:

1. The script/module is a **primary entry point** for users or other scripts
2. There is a **3+ step** data processing pipeline
3. There are significant **branches, retries, caching, state machines, or async flows**
4. It submits training, evaluation, or data generation **expensive jobs**
5. It calls multiple modules, but the entry file **doesn't reveal the full flow**
6. The implementation contains **research-critical algorithms**
7. A human reviewer **cannot answer "how does it run?" within a few minutes**

## When a code map is NOT needed

- Parameter-forwarding scripts, simple shell wrappers
- Single-format conversion tools
- One-off migration/fix scripts
- Small, obvious utilities (< 50 lines)
- Pure configuration files
- Low-complexity glue code

## Template selection

| Template | Use for | Required sections |
|----------|---------|-------------------|
| [TEMPLATE_LIGHT](TEMPLATE_LIGHT.md) | Default. Most scripts and modules | Purpose, Flow Diagram, Core Pseudocode, Code Pointers |
| [TEMPLATE_FULL](TEMPLATE_FULL.md) | Core pipelines, complex state, key algorithms | Light + Mental Model, Critical Branches, Data Contracts, Invariants, Side Effects, Change Impact |

**Decision rule**: If the module has multiple critical branches, manages internal state, coordinates multiple models, or has high algorithmic complexity → use full. Otherwise → use light.

## Three-level reading model

```text
Level 1: Concept Review
  Read Purpose + Flow Diagram
  Answer: Is the overall approach correct?

Level 2: Behavior Review
  Read Core Pseudocode + Critical Branches + Data Contracts + Invariants
  Answer: Are there missing cases or risks?

Level 3: Code Review
  Follow Code Pointers to inspect key implementations
  Answer: Does the code correctly implement the above behavior?
```

## Hard rules

1. **A code map describes only the current real implementation.** Never describe planned behavior as if it already exists.
2. **Must reference concrete code paths and symbols** (`file.py:ClassName.method`). A code map without Code Pointers is incomplete.
3. **Diagrams must stay in sync with code**: when control flow, data flow, or external behavior changes, update the code map in the same task. Internal refactoring that doesn't change behavior does not require an update.

## Directory organization

```text
code_maps/
├── systems/     # Cross-module pipelines (e.g., full inference, evaluation)
├── scripts/     # Single script level (e.g., cluster worker scripts)
└── modules/     # Core algorithms/modules (e.g., depth alignment, SLAM)
```

## Relationship with Plans

- **Plan's Human Review Guide**: explains "what changed this time" (temporary, archived with plan)
- **Code Map**: explains "how the system works now" (permanent, evolves with code)

When an implementation is done, the agent first explains the logic in the Plan's Human Review Guide. Only long-lived, maintenance-worthy flows should be further materialized as permanent code maps.
