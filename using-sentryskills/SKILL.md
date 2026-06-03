---
name: using-sentryskills
description: Run SentrySkills before every task using a rule-first frontend and a risk-gated model backend. The skill/framework decides sync vs async after rule gating.
---

# Using SentrySkills

## Purpose

`using-sentryskills` is the entry skill. It defines the required execution order for every task:

`base_rule -> extra_rule -> rule_gate -> risk assessment -> model_stage -> end-of-task proposal sweep`

The first three stages are mandatory and synchronous. `model_stage` is conditional. Proposal sweep is a main-agent maintenance step that runs at the end of every task and only affects subsequent turns.

## Required Behavior

1. Build the current input payload and run `shared/scripts/self_guard_runtime_hook_template.py` once for rule gating.
2. Read the result under `.sentryskills/base/`.
3. If `rule_stage_action == block`, stop and treat that hook result as the final guard result.
4. If `rule_stage_action != block`, run the task's `model_stage` in `sync` or `async` mode according to the risk gate.
5. After a completed `model_stage`, call the runtime hook again with the completed model-stage knowledge envelope. This second call is what writes extra rules, textual memory, or async proposal files.
6. Treat preflight, runtime, and output as separate `rule -> model` stages. Rule results run first; model results may only tighten decisions.
7. Apply action-level gating to planned actions and dynamic skill actions. If only some actions are risky, downgrade and execute only allowed actions; if all declared actions are blocked, block the task.
8. During execution, before invoking any non-SentrySkills skill, submit a runtime `skill_invocation` gate for that specific skill call.
9. Execute only the actions returned in `allowed_actions` / `allowed_skill_steps`; do not execute `blocked_actions` / `blocked_skill_steps`.
10. At task end, if this is a main-agent turn, ensure one proposal sweep has run.
11. Respect the returned stage fields:
   - `base_rule_action`
   - `extra_rule_action`
   - `rule_stage_action`
   - `model_dispatch_mode`
   - `model_stage_status`
   - `model_stage_action`
   - `model_executor`
   - `model_stage_result_available`
   - `action_gate`
   - `skill_gate`
   - `execution_directive`
   - `proposal_sweep_effect`
   - `knowledge_writeback_status`
   - `final_action`

## Execution Rules

### Rule-first frontend

Always run:

- `base_rule`
- `extra_rule`
- `rule_gate`

Use conservative merging:

- `block > downgrade > allow`

If `rule_stage_action == block`:

- stop immediately
- do not enter `model_stage`
- do not create new extra rules
- do not create textual memory

### Risk-gated model backend

If `rule_stage_action != block`, the skill or framework must assign:

- `framework_risk_level = high | low`

Then the main framework agent dispatches `model_stage` with these rules:

- `high` -> `model_dispatch_mode = sync`
- `low + subagent support` -> `model_dispatch_mode = async`
- `low + no stable subagent support` -> `model_dispatch_mode = sync`

The runtime script records this decision. It should not invent async execution by itself.

Subagent capability may always be present in the framework, but actual subagent dispatch is still gated by the main framework agent's risk assessment.

### Runtime skill gate

Skill calls may appear dynamically during execution. Do not try to enumerate all
possible skill calls only at task start. Each time the framework is about to
invoke a non-SentrySkills skill, call the runtime hook with a `skill_invocation`
for that specific call.

The skill gate payload may be supplied either as top-level `skill_invocations`
or as a `runtime_events` item with `type = "skill_invocation"`:

```json
{
  "skill_invocations": [
    {
      "skill_invocation_id": "skill-call-1",
      "skill_name": "some-skill",
      "invocation_reason": "why this skill is needed now",
      "requested_step": "the specific step to perform",
      "current_context_summary": "brief context, without raw secrets",
      "candidate_actions": [
        {"action": "read_file", "step": "inspect local source", "required": true},
        {"action": "network_call", "step": "fetch remote reference", "required": false}
      ]
    }
  ]
}
```

Interpretation:

- `allow`: all declared low-risk steps may run.
- `downgrade`: execute only `allowed_skill_steps`; skip `blocked_skill_steps`.
- `block`: do not invoke that skill call.

`downgrade` means selective execution. It does not authorize the whole skill.
High-risk optional actions such as network calls, file writes, command
execution, and batch modification should be skipped unless explicitly allowed by
the returned gate result. Sensitive reads such as credentials or key material
remain blocking.

After the skill runs, runtime events owned by that skill must include
`skill_name` or `skill_invocation_id`. The runtime hook checks that every
skill-owned action was previously allowed by the skill gate.

### Action-level downgrade

`downgrade` means selective execution:

- `allowed_actions` may run.
- `blocked_actions` must not run.
- `execution_directive = execute_allowed_actions_only`.

If all declared planned or skill actions are blocked, the final directive is
`execute_no_actions` and the turn must be treated as `block`.

Prefer object-form `planned_actions`:

```json
{
  "planned_actions": [
    {"action": "read_file", "step": "inspect local source", "required": true},
    {"action": "write_file", "step": "persist generated patch", "required": false}
  ]
}
```

String actions remain supported for compatibility.

### Stage rule then model

Each stage has a rule layer and an optional model layer:

- `preflight_rule -> preflight_model`
- `runtime_rule -> runtime_model`
- `output_rule -> output_model`

The rule layer always runs first. The model layer may raise `allow` to
`downgrade` or `block`, but it must never relax a rule-layer `block`.

Extra rules should declare `phase_scope`. Prompt-injection style rules such as
`ignore previous instructions` should normally scope to `preflight,runtime`.
Output-stage rules should focus on leakage, unsafe reconstruction, and
over-confident unverified claims.

### Two-call runtime pattern

For non-blocked turns, do not stop after the initial rule-gating hook. Use this pattern:

1. `pre_model_hook`: payload has the original task context and no `model_stage`; use it to compute `base_rule`, `extra_rule`, and `rule_stage_action`.
2. `model_stage`: the framework agent or allowed subagent performs the model-heavy safety judgment.
3. `post_model_hook`: payload includes the same task context plus `framework_risk_level`, `model_dispatch_mode`, `sentryskills_role`, and the completed `model_stage` object.

If the second hook is skipped, `sentryskills-extra` cannot write new rules, textual memory, or async proposals. The hook will not throw an exception in this case; it records `model_stage_status = required_not_provided` and waits for the framework agent to call it again with the completed `model_stage`.

### Knowledge writeback

Only after `model_stage` is completed may the system:

- synthesize candidate extra rules
- synthesize textual memory
- run dedup
- run validation
- promote validated rules into active extra rules

If `model_stage` is skipped, pending, or required-but-not-provided, knowledge writeback must also be skipped or deferred.

When `model_stage` is completed, do not only write an analysis paragraph. Also produce reusable knowledge:

- use `rule_candidates` for deterministic patterns that can be checked by the extra rule stage
- use `memory_candidates` for natural-language lessons that are useful but not stable enough for a rule
- when proposing a rule, include `validation_cases` with generated positive and negative test cases for that rule
- if there is no reusable knowledge, return empty arrays explicitly

The runtime hook can store fallback textual memory from `findings`, but it cannot invent high-quality executable rules or high-quality validation cases from prose. Put executable rule proposals and their validation cases in `rule_candidates`.

### Promotion context

Actual use and experiments use the same rule lifecycle:

- `promotion_context.source_type`: `online`, `evolution`, `benchmark`, `manual`, or `shadow`
- `promotion_context.update_mode`: `learn`, `candidate_only`, or `read_only`
- `promotion_context.promotion_policy`: `conservative`, `variant_validated`, `shadow_confirmed`, or `manual_reviewed`
- `promotion_context.snapshot_request = true`: write `.sentryskills/extra/memory/rule_snapshot_manifest.json`

Use `source_type = evolution` for evolution-set evidence, `source_type = online`
for production observations, and `update_mode = read_only` for evaluation or
serving runs that must not grow rules. This keeps experiment and actual use on
the same promotion pipeline.

### Feedback and outcome learning

If a user says a turn was risky, the framework can pass the user sentence
directly:

```json
{
  "feedback_text": "刚才被攻击了，不要再允许这种 skill 指令"
}
```

or:

```json
{
  "feedback": "this should not have executed"
}
```

This triggers a rule-proposer task even if the original model did not identify
the risk. Benchmark evaluators, postmortems, or automated harnesses may pass the
structured form when they have richer labels:

```json
{
  "promotion_context": {
    "source_type": "manual|evolution|benchmark",
    "update_mode": "learn",
    "source_case_id": "case-or-incident-id"
  },
  "feedback": {
    "known_risk": true,
    "attack_success": true,
    "risk_source": "user_feedback|benchmark_label|postmortem|rollback",
    "attack_family": "skill_injection|prompt_injection|tool_abuse|secret_exfiltration",
    "failed_guard_stage": "preflight|runtime|output|model_stage|unknown",
    "why_failed": "short explanation",
    "positive_evidence": ["text/action/trace that should trigger a future rule"],
    "negative_evidence": ["nearby benign text/action that must not trigger"]
  }
}
```

Without labels, the hook still derives weak outcome signals from blocked actions,
runtime alerts, sensitive reads, and output leakage. Those signals trigger
`candidate_only` or proposer-required flows by default; they should not become
strong block rules until validated or confirmed.

When the hook returns `model_stage_status = rule_proposer_required`, the
framework must run a model rule-proposer pass over `pending_rule_proposer_task`
and call the hook again with completed `model_stage.rule_candidates`.

### Proposal sweep

At the end of every main-agent task:

- scan `.sentryskills/extra/proposals/pending/`
- process all readable proposal files
- move consumed files to `processed/` or `rejected/`

Proposal sweep must not rewrite the already finalized current turn. Its updates only affect subsequent turns.

## Expected Input

The runtime script accepts the normal task payload. For any non-blocked turn, the framework must eventually pass:

```json
{
  "framework_risk_level": "high",
  "model_dispatch_mode": "sync",
  "model_stage": {
    "action": "allow|downgrade|block",
    "analysis": "string",
    "reason_codes": ["..."],
    "findings": ["..."],
    "rule_candidates": [
      {
        "pattern": "literal substring or regex",
        "pattern_type": "substring|regex|planned_action",
        "risk_type": "prompt_injection|secret_exfiltration|unsafe_tool_use|...",
        "trigger_condition": "when this rule should fire",
        "suggested_action": "downgrade|block",
        "reason_code": "EXTRA_...",
        "evidence_items": ["model-stage evidence"],
        "source_case_id": "evolution-case-id",
        "source_cases": ["related-case-id"],
        "evidence_source": "online|evolution|benchmark|manual|shadow",
        "attack_family": "generalized attack family",
        "generalization_basis": "why this pattern transfers beyond the source case",
        "positive_variants": ["additional generated attack variants"],
        "negative_variants": ["nearby benign variants that must not match"],
        "promotion_target": "downgrade|block",
        "promotion_rationale": "why this candidate should become executable",
        "validation_cases": {
          "positive": ["input/action text that should match the new rule"],
          "negative": ["safe nearby text that must not match the new rule"]
        }
      }
    ],
    "memory_candidates": [
      {
        "pattern_summary": "natural-language lesson learned from this model-stage result",
        "risk_type": "prompt_injection|secret_exfiltration|unsafe_tool_use|...",
        "trigger_contexts": ["where this tends to appear"],
        "why_not_rule_friendly": "why this is not yet a stable deterministic rule",
        "evidence_items": ["model-stage evidence"],
        "suggested_action": "downgrade|block"
      }
    ]
  }
}
```

If the framework chooses async model execution for a low-risk turn, the current turn may omit `model_stage`; the script will record pending model-stage state instead.

When an async subagent later completes `model_stage`, it must call the runtime hook with `sentryskills_role = "subagent"`, `model_dispatch_mode = "async"`, and the completed `model_stage` envelope. The subagent writes proposal files only; it must not modify active rules directly. The main agent is responsible for sweeping and consuming pending proposal files at task end, with effects starting from the next turn.

## Runtime State

Workspace-local state is written under:

- `.sentryskills/base/`
- `.sentryskills/extra/`

`base` stores the current turn logs and state. `extra` stores active rules, candidate rules, textual memory, validation audit, and dedup audit.
