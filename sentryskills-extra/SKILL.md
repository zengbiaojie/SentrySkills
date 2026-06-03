---
name: sentryskills-extra
description: Extension layer for SentrySkills. It separates online extra-rule detection from post-model-stage knowledge management.
---

# SentrySkills Extra

## Purpose

`sentryskills-extra` has two distinct responsibilities:

- `extra_rule`: online rule extension after `base_rule`
- `extra_memory`: post-model-stage knowledge management
  and end-of-task proposal sweeping by the main agent

This skill must not use any framework-external model.

## Execution Boundary

### `extra_rule`

`extra_rule` runs during the online decision path:

- after `base_rule`
- before `rule_gate`
- using only active extra rules

It may:

- match active extra rules
- raise the rule-stage decision conservatively
- apply rules by `phase_scope` (`preflight`, `runtime`, `output`, or `all`)

It may not:

- generate candidate rules
- write textual memory
- run dedup or validation

### `extra_memory`

`extra_memory` runs only after `model_stage` is completed.

It may:

- synthesize candidate rules from model findings
- store textual memory
- deduplicate similar knowledge
- validate new candidate rules
- promote validated rules into `active_extra_rules.json`

For async subagent results:

- the subagent may only write proposal files
- proposal files are swept and consumed by the main agent
- async analysis does not directly modify active or candidate stores
- proposal sweep only affects subsequent turns

It must not run when:

- `rule_stage_action == block`
- `model_stage` is skipped
- `model_stage` is still pending

If the hook reports `model_stage_status = rule_proposer_required`, a feedback or
outcome signal indicated a possible missed risk. The framework must run a model
rule-proposer pass over `pending_rule_proposer_task` and call the hook again with
structured `model_stage.rule_candidates`.

## Model-Stage Knowledge Contract

After a completed `model_stage`, the framework agent must pass reusable knowledge to the runtime hook:

- `rule_candidates`: deterministic extra-rule proposals for patterns that can be checked locally
- `memory_candidates`: natural-language observations for patterns that are useful but not rule-stable

Do not rely on a prose-only analysis if a reusable rule or memory exists. The runtime can preserve fallback textual memory from `findings`, but executable rules must be supplied as structured `rule_candidates`.

Rule candidate fields:

- `pattern`
- `pattern_type`: `substring`, `regex`, or `planned_action`
- `phase_scope`: target stage or stages for this rule
- `risk_type`
- `trigger_condition`
- `suggested_action`: `downgrade` or `block`
- `reason_code`
- `evidence_items`
- `validation_cases`: generated positive and negative test cases for validating the proposed rule
- `source_case_id`: evolution or benchmark case that produced the candidate
- `source_cases`: related source case identifiers
- `evidence_source`: `online`, `evolution`, `benchmark`, `manual`, or `shadow`
- `attack_family`: generalized attack family, when known
- `generalization_basis`: why the rule should transfer beyond the source case
- `positive_variants` and `negative_variants`: additional generated validation samples
- `promotion_target`: intended active action, usually `downgrade` or `block`
- `promotion_rationale`: why this candidate is safe to promote

Memory candidate fields:

- `pattern_summary`
- `risk_type`
- `trigger_contexts`
- `why_not_rule_friendly`
- `evidence_items`
- `suggested_action`

For async model-stage execution, the subagent writes proposal files only. The main agent processes those proposal files during the end-of-task sweep.

Rule validation is deterministic. The framework model generates `validation_cases`; the runtime hook runs the candidate rule against those cases and only promotes rules that hit generated positives and avoid generated negatives. If no generated cases are provided, the hook falls back to conservative local evidence-based validation.

Rule promotion uses one lifecycle for actual use and experiments:

- `promotion_context.source_type`: `online`, `evolution`, `benchmark`, `manual`, or `shadow`
- `promotion_context.update_mode`: `learn`, `candidate_only`, or `read_only`
- `promotion_context.promotion_policy`: `conservative`, `variant_validated`, `shadow_confirmed`, or `manual_reviewed`
- `promotion_context.snapshot_request = true`: write a fixed rule snapshot manifest

Evolution data, benchmark data, online turns, shadow hits, and manual review all become evidence for the same promotion pipeline. Evaluation or serving runs that must not grow rules should use `update_mode = read_only`.

User feedback may be a short string:

- `feedback_text`: `刚才被攻击了，不要再允许这种行为`
- `feedback`: `this should not have executed`

Framework or evaluator labels may use structured `feedback`:

- `known_risk`
- `attack_success`
- `risk_source`
- `attack_family`
- `failed_guard_stage`
- `why_failed`
- `positive_evidence`
- `negative_evidence`

Without labels, explicit `outcome_signals` or automatic runtime/output signals
can still trigger a candidate-only rule proposer task.

Rules without `phase_scope` remain compatible and apply to all stages. Prompt
injection rules should normally scope to `preflight` and `runtime`; output rules
should focus on leakage, unsafe reconstruction, or unsafe final text.

## Storage

Workspace-local runtime state is stored under:

- `.sentryskills/extra/memory/active_extra_rules.json`
- `.sentryskills/extra/memory/candidate_extra_rules.jsonl`
- `.sentryskills/extra/memory/textual_memory.jsonl`
- `.sentryskills/extra/memory/validation_audit.jsonl`
- `.sentryskills/extra/memory/dedup_audit.jsonl`
- `.sentryskills/extra/memory/proposal_audit.jsonl`
- `.sentryskills/extra/memory/promotion_audit.jsonl`
- `.sentryskills/extra/memory/rule_snapshot_manifest.json`
- `.sentryskills/extra/proposals/pending/`
- `.sentryskills/extra/proposals/processed/`
- `.sentryskills/extra/proposals/rejected/`

## Model Constraint

Allowed:

- the framework's own primary model, if the framework provides a `model_stage` result

Not allowed:

- external APIs
- embedding models
- rerankers
- separate similarity models
- custom external classifiers
