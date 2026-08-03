---
status: active
scope: general
last_verified: {{DATE}}
owner: {{OWNER}}
---

# Playbook: Initialize Workspace

## When to use

First session in a new workspace, OR when the user says "initialize docs" / "set up workspace".

## Input

User provides a **plain-language project description**. It can be informal, incomplete, or in any language. Example:

> "我要用 DepthAnything 对一批视频做深度估计，然后训练一个 NeRF。GPU 是 A100，数据在 NAS 上。"

## Agent execution steps

### Step 1: Parse user description

Extract from the description:
- **Project goal** (1-2 sentences)
- **Tech stack** (language, framework, GPU type, key libraries)
- **Main assets** (scripts, datasets, models, output directories)
- **Environment** (Python path, conda env, special env vars)
- **Constraints** (deadlines, shared resources, collaborators)

If critical information is missing, ask the user — don't guess.

### Step 2: Fill `CLAUDE.md`

Replace placeholders:
- `{{PROJECT_NAME}}` → concise project name
- `{{PROJECT_DESCRIPTION}}` → 1-2 sentence description
- `{{COMMON_COMMANDS_HERE}}` → key commands (or leave as TODO)
- Update the "Key paths" table with actual project paths

### Step 3: Generate `docs/agent/always.md`

Keep the structural rules (session start, permissions, documentation maintenance, notes policy). Add project-specific sections:

- **Environment**: Python path, conda env, GPU type, critical env vars
- **Permissions**: File ownership situation, sudo needs
- **Work habits**: Project-specific patterns (e.g., "always use `-u` for background Python")

### Step 4: Scan and populate registries

```bash
# Discover scripts
find . -name "*.sh" -o -name "*.py" | head -50

# Discover data directories
ls data/ 2>/dev/null; ls datasets/ 2>/dev/null

# Discover outputs
ls outputs/ 2>/dev/null; ls results/ 2>/dev/null
```

For each discovered asset, add a minimal entry to the relevant registry file (`scripts.md`, `datasets.md`, `outputs.md`).

### Step 5: Generate `docs/working_logs/active.md`

```markdown
---
status: active
last_updated: {{TODAY}}
---

# Active Work

## Current task
{{DERIVED_FROM_USER_DESCRIPTION}}

## Status
- Just initialized workspace docs

## Next recommended action
{{FIRST_THING_TO_DO}}

## Do not do
- {{ANY_CONSTRAINTS_USER_MENTIONED}}
```

### Step 6: Generate initial plan (if applicable)

If the user's description contains a clear next action or multi-step task:
1. Copy `docs/working_logs/plans/TEMPLATE.md` to `plans/active/{{DATE}}-{{SLUG}}.md`
2. Fill in "原始用户目标" with the user's description verbatim
3. Fill in the Agent Refined Plan section

### Step 7: Commit

```bash
git add -A
git commit -m "docs: initialize workspace from user description"
```

## Output

After this playbook completes, the workspace is ready:
- Agent can start any new session by reading `always.md` + `active.md`
- Registries reflect current project state
- If a plan was created, work can begin immediately

## Post-initialization

Tell the user:
1. What was generated
2. What (if anything) needs manual input
3. Suggested next step
