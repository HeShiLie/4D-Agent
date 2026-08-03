# Documentation Map

This directory is the project's documentation space, organized for human + agent collaboration.

## Directory structure

```
docs/
├── README.md                    ← You are here
├── agent/                       ← Agent knowledge base
│   ├── always.md                   Core rules (loaded every session)
│   ├── rules/                      Hard constraints by domain
│   ├── skills/                     On-demand operational procedures
│   └── playbooks/                  Complex workflows & troubleshooting
├── code_maps/                   ← Human code understanding layer
│   ├── README.md                   Positioning, templates, coverage criteria
│   ├── TEMPLATE_LIGHT.md           Default template (4 sections)
│   ├── TEMPLATE_FULL.md            Full template (complex modules)
│   ├── systems/                    Cross-module pipelines
│   ├── scripts/                    Single script level
│   └── modules/                    Core algorithms/modules
├── working_logs/                ← Work-in-progress tracking
│   ├── active.md                   Current work state (loaded every session)
│   ├── plans/                      Task plans
│   │   ├── active/                    In progress
│   │   └── completed/                 Done
│   ├── runs/                       Experiment run logs
│   └── daily/                      Daily work summaries
├── notes/                       ← Human's tentative thoughts (not auto-loaded)
│   ├── inbox/                      Unstructured scratch
│   ├── ideas/                      Hypotheses not yet planned
│   └── analyses/                   Human interpretation of results
├── knowledge/                   ← Reference material (loaded on demand)
├── adr/                         ← Architecture Decision Records
└── registry/                    ← Asset indexes
    ├── agent_system.md             Agent resources directory
    ├── scripts.md                  Script index
    ├── datasets.md                 Dataset index
    └── outputs.md                  Output index
```

## Usage conventions

| Type | When to read | When to write/update |
|------|--------------|----------------------|
| `agent/always.md` | Every session start | Core rules change |
| `agent/rules/` | Working in that domain | Rules change |
| `agent/skills/` | Executing that procedure | Procedure changes |
| `working_logs/active.md` | Every session start | Work state changes |
| `working_logs/runs/` | Reviewing experiments | After each experiment |
| `registry/` | Looking up scripts/data/outputs | New assets added or modified |
| `code_maps/` | Understanding how code works | New complex code, or implementation changes behavior |
| `notes/` | Plan references or searching prior ideas | Anytime (human observations) |
| `knowledge/` | Plan references or technical questions | Verified new knowledge |
| `adr/` | Understanding past decisions | Making significant technical decisions |

## Front matter convention

Every document should include:

```yaml
---
status: active | deprecated
scope: <domain>
last_verified: YYYY-MM-DD
owner: <name>
---
```
