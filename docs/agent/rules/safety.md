---
status: active
scope: general
last_verified: {{DATE}}
owner: {{OWNER}}
---

# Rule: Safety & Permissions

## When this applies

Always. These are non-negotiable constraints.

## Rules

1. **No silent deletions**: Never delete files, directories, or git branches without explicit user confirmation. If unsure, ask.

2. **No destructive git ops**: `git reset --hard`, `git push --force`, `git clean -f` — all require explicit user request.

3. **No secret exposure**: Never hardcode tokens, API keys, or credentials in scripts. Use environment variables. Never commit `.env` files.

4. **Confirm before expensive ops**: GPU training, large batch inference, cluster job submissions — always confirm with user first, stating estimated cost/time.

5. **Investigate before overwriting**: If you encounter unexpected state (unfamiliar files, lock files, uncommitted changes), investigate before taking action.

6. **File ownership**: If files are owned by a different user, use `sudo` carefully and only for the specific operation needed.

## Rationale

These rules exist because agent mistakes are hard to reverse and can destroy hours of work. The cost of asking is seconds; the cost of a wrong action is hours.
