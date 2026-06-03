# SentrySkills

[![Docs](https://img.shields.io/badge/docs-website-blue?style=flat-square)](https://zengbiaojie.github.io/SentrySkills/)
[![GitHub](https://img.shields.io/badge/github-AI45Lab%2FSentrySkills-181717?style=flat-square&logo=github)](https://github.com/AI45Lab/SentrySkills)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

SentrySkills is a self-guarding security framework for AI agents. The current version uses a **rule-first frontend** and a **conditional model backend**:

`base_rule -> extra_rule -> rule_gate -> risk assessment -> model_stage(sync or async) -> end-of-task proposal sweep`

## What changed in the new version

- All tasks go through the rule frontend first.
- `base_rule` and `extra_rule` are always synchronous.
- `rule_gate` uses `block > downgrade > allow`.
- `model_stage` is only entered when the rule stage does not block.
- Knowledge writeback is only allowed after a completed `model_stage`.
- The main framework agent performs one proposal sweep at task end.
- Dynamic calls to other skills are gated at runtime before the skill executes.
- Planned and skill actions are gated individually; downgrade means execute allowed actions only.
- Preflight, runtime, and output each follow rule-then-model evaluation.
- Runtime state is workspace-local under `.sentryskills/base` and `.sentryskills/extra`.

## Core modules

- `using-sentryskills`
  Entry skill and execution contract
- `sentryskills-preflight`
  Base-rule pre-execution checks
- `sentryskills-runtime`
  Base-rule runtime monitoring
- `sentryskills-output`
  Base-rule output protection
- `sentryskills-extra`
  Extra-rule detection plus post-model knowledge management
- `shared/scripts/self_guard_runtime_hook_template.py`
  Main runtime script

## Decision model

### Rule-first frontend

The system always runs:

- `base_rule`
- `extra_rule`
- `rule_gate`

If `rule_stage_action == block`, the turn ends immediately. No model stage and no knowledge writeback are allowed.

### Risk-gated model backend

If `rule_stage_action != block`, the main framework agent may enter `model_stage`.

Dispatch policy:

- assign `framework_risk_level = high | low`
- `high -> sync`
- `low + subagent support -> async`
- `low + no stable subagent support -> sync`

Subagent capability may exist at all times, but actual dispatch is still decided by the main framework agent after risk assessment.

### Runtime skill gate

Other skills may be invoked dynamically while a task is already running. Before
calling any non-SentrySkills skill, the framework should submit a
`skill_invocation` payload to the runtime hook. The hook returns a `skill_gate`
section with:

- `allowed_skill_steps`
- `blocked_skill_steps`
- `requires_confirmation`
- `safe_substitute_steps`

`downgrade` means selective execution: run only the allowed low-risk steps and
skip the blocked skill actions. Runtime events produced by that skill should
carry `skill_name` or `skill_invocation_id` so the hook can verify that the
actual actions match the allowed steps. Ungated or not-allowed skill actions are
reported as runtime risk signals.

### Action-level downgrade

The runtime hook reports an `action_gate` with `allowed_actions`,
`blocked_actions`, `blocked_action_reasons`, and `execution_directive`.

- `allow`: execute all declared actions.
- `downgrade`: execute only allowed actions.
- `block`: execute no declared actions.

If a task declares multiple actions and only some are risky, the framework
should skip the blocked actions and continue with the allowed subset. If every
declared action is blocked, the final action becomes `block`.

### Rule then model by stage

Each major stage has a rule layer and an optional model layer:

- `preflight_rule -> preflight_model`
- `runtime_rule -> runtime_model`
- `output_rule -> output_model`

Rules run first. Model results can add stricter findings but cannot relax a
rule-layer block. Extra rules may declare `phase_scope`; prompt-injection rules
normally apply to preflight/runtime, while output rules focus on leakage and
unsafe final text.

### Knowledge writeback

Only a completed `model_stage` may generate:

- candidate extra rules
- textual memory
- dedup audit
- validation audit
- promoted active extra rules

Pure rule hits do not create new knowledge.

If `model_stage` is completed by an async subagent, the result is first written as a proposal file. The main framework agent later sweeps proposal files at task end and performs the actual rule update pipeline. Proposal sweep only affects subsequent turns and never rewrites the already finalized current turn.

Rule learning uses a unified promotion context, not experiment-specific modes:

- `promotion_context.source_type`: `online`, `evolution`, `benchmark`, `manual`, or `shadow`.
- `promotion_context.update_mode`: `learn`, `candidate_only`, or `read_only`.
- `promotion_context.promotion_policy`: `conservative`, `variant_validated`, `shadow_confirmed`, or `manual_reviewed`.
- `promotion_context.snapshot_request = true`: writes `.sentryskills/extra/memory/rule_snapshot_manifest.json`.

Actual use and experiments share the same pipeline: model-stage observations become candidate rules with evidence, candidates are validated, validated rules are promoted into the active store, and snapshots make a fixed rule version available for serving or evaluation. Evaluation runs should use `update_mode = read_only` against a selected snapshot so ASR/TSR is measured without rule growth.

Missed-risk learning does not require the model to identify the risk first. The hook can trigger a rule-proposer task from:

- short user feedback such as `feedback_text = "刚才被攻击了，不要再允许这种行为"` or `feedback = "this should not have executed"`
- `feedback.known_risk = true` or `feedback.attack_success = true`
- explicit `outcome_signals`
- automatic outcome signals such as blocked actions, runtime alerts, sensitive reads, or output leakage

When this happens and rules are not read-only, the summary records `model_stage_status = rule_proposer_required` or `knowledge_writeback_status = awaiting_rule_proposer`, with `pending_rule_proposer_task` containing the evidence bundle. The framework model should complete that task and call the hook again with `model_stage.rule_candidates`.

User feedback can be a single sentence:

```json
{
  "feedback_text": "刚才被攻击了，不要再允许这种 skill 指令"
}
```

Frameworks and benchmark runners may provide the richer structured label:

```json
{
  "promotion_context": {
    "source_type": "evolution",
    "update_mode": "learn",
    "source_case_id": "case-001"
  },
  "feedback": {
    "known_risk": true,
    "attack_success": true,
    "risk_source": "benchmark_label",
    "attack_family": "skill_injection",
    "failed_guard_stage": "model_stage",
    "why_failed": "The model allowed a malicious instruction embedded in a skill.",
    "positive_evidence": ["malicious instruction text", "risky action trace"],
    "negative_evidence": ["nearby benign skill usage"]
  }
}
```

## Runtime outputs

The runtime script now exposes these stage fields in summaries and logs:

- `base_rule_action`
- `extra_rule_action`
- `rule_stage_action`
- `framework_risk_level`
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
- `promotion_context`
- `final_action`

`model_stage_status` values:

- `skipped`: rule stage blocked, so model stage was intentionally not run
- `pending`: async/subagent model stage is waiting for a result
- `required_not_provided`: non-blocked turn needs model stage, but the framework has not yet called the hook again with a completed `model_stage`
- `completed`: model stage result was provided and consumed

`final_action` is always the executable decision for the current turn. Async model results do not retroactively rewrite an already finished turn.

New extra rules are promoted only after validation. The framework model should attach `validation_cases.positive` and `validation_cases.negative` to each proposed rule; the runtime hook deterministically runs the candidate rule against those cases and rejects rules that miss generated positives or match generated negatives. Candidates may also include `source_case_id`, `source_cases`, `evidence_source`, `attack_family`, `generalization_basis`, `positive_variants`, `negative_variants`, `promotion_target`, and `promotion_rationale`.

## Storage layout

- `.sentryskills/base/`
  - unified logs
  - turn results
  - session state
  - index
- `.sentryskills/extra/`
  - active extra rules
  - candidate extra rules
  - textual memory
  - dedup audit
  - validation audit
  - promotion audit
  - rule snapshot manifest

## Framework integration

- Claude Code
  Prefer hook-enforced rule-first execution; model stage should be dispatched after framework risk assessment.
- Codex / OpenClaw
  Use `SKILL.md` + `AGENTS.md` discipline. Only low-risk turns may use async/subagent model-stage execution; otherwise treat `model_stage` as synchronous.

See:

- [install/claude_code_install.md](install/claude_code_install.md)
- [install/codex_install.md](install/codex_install.md)
- [install/openclaw_install.md](install/openclaw_install.md)
- [install/experiment_protocol.md](install/experiment_protocol.md)

## Requirements

- Python 3.8+
- no external Python dependencies for the core runtime path
