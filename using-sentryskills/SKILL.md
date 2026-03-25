---
name: using-sentryskills
description: Automatically runs SentrySkills security checks on EVERY task. Before any response, execute the runtime hook to ensure self-guard decision evidence.
---

# Using SentrySkills Self-Guard

## ⚠️ IMPORTANT: This Skill Runs Automatically

This skill is **designed to run on EVERY task** - it should be configured in your AGENTS.md to execute automatically.

## Goal
Establish unified trigger discipline: as long as external response exists, must run self-guard runtime hook before final output.

## When to Trigger
**Always trigger on:**
- Every task that produces output
- Every command execution
- Every file operation
- Every network call

**Never skip** - security checks should be universal.

## Execution Flow

1. **Write** current task context to `./sentry_skill_log/input.json`:
```json
{
  "session_id": "<session id>",
  "turn_id": "<turn id>",
  "project_path": "<absolute path to current project>",
  "user_prompt": "<the user's request>",
  "planned_actions": ["<action1>", "<action2>"],
  "candidate_response": "<the response you are about to give>",
  "intent_tags": ["<tag1>"]
}
```

2. **Run** the script:
```bash
python shared/scripts/self_guard_runtime_hook_template.py \
  ./sentry_skill_log/input.json \
  --policy-profile balanced \
  --out ./sentry_skill_log/result.json
```

3. **Read** `./sentry_skill_log/result.json` for `final_action`:
   - `allow`: output normally.
   - `downgrade`: downgrade expression and declare uncertainty.
   - `block`: refuse or redact, do not output original candidate.

4. **Delete** `./sentry_skill_log/input.json`.

5. Final response must include minimum evidence:
   - `self_guard_final_action`
   - `self_guard_trace_id`
   - `self_guard_events_log`

## Exceptions and Degradation
1. If hook execution fails or is unavailable: must explicitly declare "security self-check not completed" and adopt conservative output.
2. If log directory is not writable: use writable temporary directory to execute hook, and give real log path in evidence fields.

## Common Anti-patterns
1. Reply first then run hook afterward.
2. Judge risk by text only without actually running script.
3. `downgrade` still gives high-confidence conclusions.
4. `block` still outputs original sensitive candidate content.
