# ViSTR-Agent — Agent Entry Point

Tool-augmented MLLM agent system for the ViSTR-Bench leaderboard (visual spatial-temporal
reasoning benchmark, 15 subtasks / 1,340 binary video-QA pairs).

## Instructions

1. Read `docs/agent/always.md` (core rules, every session).
2. Read `docs/working_logs/active.md` (current work state).
3. Read `docs/knowledge/vistr_bench.md` before touching benchmark-related logic.
4. When you need to find scripts/data/outputs, check `docs/registry/`.
5. When you need operational procedures, check `docs/registry/agent_system.md` for available skills.
6. Follow the golden rules in `CLAUDE.md`.

## Entry files
| File | When to read |
|------|--------------|
| `docs/agent/always.md` | Every session start |
| `docs/working_logs/active.md` | Every session start |
| `docs/knowledge/vistr_bench.md` | Before benchmark/agent work |
| `docs/registry/agent_system.md` | When planning or looking for capabilities |
| `docs/agent/rules/*.md` | When working in that domain |
| `docs/agent/skills/*/SKILL.md` | When executing that procedure |
| `docs/agent/playbooks/*.md` | When troubleshooting or doing complex workflows |
