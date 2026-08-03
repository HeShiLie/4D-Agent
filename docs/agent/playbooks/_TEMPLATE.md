---
status: active
scope: {{DOMAIN}}
last_verified: {{DATE}}
owner: {{OWNER}}
---

# Playbook: {{PLAYBOOK_NAME}}

## When to use

<!-- Describe the trigger: what situation or symptom activates this playbook -->

## Step 1: {{DIAGNOSIS_OR_SETUP}}

<!-- First action to take -->

## Step 2: {{COMMON_CASES}}

### Case A: {{SCENARIO}}

| Symptom | Cause | Fix |
|---------|-------|-----|
| ... | ... | ... |

### Case B: {{SCENARIO}}

| Symptom | Cause | Fix |
|---------|-------|-----|
| ... | ... | ... |

## Step 3: If none of the above match

<!-- Fallback investigation strategy -->

1. ...
2. ...

## Step 4: After resolving

1. Verify the fix worked.
2. Record what happened in a run log (`docs/working_logs/runs/`).
3. If this is a new pattern, consider adding it to a rule or this playbook.
