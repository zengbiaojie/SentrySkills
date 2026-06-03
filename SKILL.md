# SentrySkills

SentrySkills is a workspace-local self-guard framework for AI agents.

## Package structure

- `using-sentryskills`
  Entry skill that defines the full execution contract
- `sentryskills-preflight`
  Base-rule pre-execution analysis
- `sentryskills-runtime`
  Base-rule runtime monitoring
- `sentryskills-output`
  Base-rule output protection
- `sentryskills-extra`
  Extra-rule detection and post-model-stage knowledge management

## Current architecture

The current version follows:

`base_rule -> extra_rule -> rule_gate -> risk assessment -> model_stage(sync or async) -> end-of-task proposal sweep`

Key rules:

- the rule frontend always runs first
- dynamically invoked non-SentrySkills skills are gated at runtime before execution
- planned and skill actions are gated individually; downgrade executes only allowed actions
- preflight, runtime, and output each run rule-first with optional model tightening
- `block` at rule stage ends the turn
- async/subagent execution is only for low-risk `model_stage`
- non-blocked turns use a two-call hook pattern: rule-gating hook first, post-model hook after completed `model_stage`
- new extra knowledge is only written after completed `model_stage`
- completed `model_stage` must provide reusable knowledge as `rule_candidates` or `memory_candidates` when any reusable lesson exists
- runtime skill gate `downgrade` means selective execution of allowed skill steps only
- the main framework agent runs one proposal sweep at task end
- proposal sweep only affects subsequent turns
- actual use and experiments share `promotion_context`: set `source_type` for the evidence source, `update_mode` for learn/read-only behavior, and `snapshot_request` when a fixed rule snapshot is needed
- structured `feedback` and `outcome_signals` can trigger `rule_proposer_required` even when the original model did not identify risk

## Runtime state

Workspace-local state is stored at:

- `.sentryskills/base/`
- `.sentryskills/extra/`
