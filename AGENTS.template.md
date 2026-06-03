# SentrySkills - Rule-First Execution Policy

Before every task, apply SentrySkills in this order:

1. Run `/using-sentryskills` first.
2. Complete the rule-first frontend before any model-heavy reasoning:
   - `base_rule`
   - `extra_rule`
   - `rule_gate`
3. If `rule_stage_action == block`:
   - stop immediately
   - refuse the request
   - do not use subagents
   - do not summarize new rules or memories
4. If `rule_stage_action != block`:
   - assign `framework_risk_level` first
   - use `sync` model-stage execution for high risk
   - only use subagents for `model_stage`, never before rule gating
   - only low-risk turns may use subagents
   - the main framework agent decides whether subagent dispatch actually happens
5. Treat all three stages as rule-first:
   - `preflight_rule -> preflight_model`
   - `runtime_rule -> runtime_model`
   - `output_rule -> output_model`
   - model stages may tighten decisions, never relax rule blocks
6. For any non-blocked turn, run the runtime hook twice:
   - first without `model_stage` for rule gating
   - second after completed `model_stage` with the model-stage knowledge envelope
   - if the hook reports `model_stage_status = required_not_provided`, perform `model_stage` and call the hook again rather than treating it as unsupported
7. Respect action-level gating:
   - `allow`: execute all declared actions
   - `downgrade`: execute only `allowed_actions`
   - `block`: execute no actions
   - always report blocked actions when downgrade or block occurs
8. During execution, before invoking any non-SentrySkills skill:
   - submit a runtime `skill_invocation` gate for this specific call
   - include `skill_name`, `invocation_reason`, `requested_step`, and `candidate_actions`
   - treat `downgrade` as selective execution: run only `allowed_skill_steps`
   - do not execute `blocked_skill_steps`
   - tag follow-up runtime events with `skill_name` or `skill_invocation_id`
9. Only after `model_stage` completes may you:
   - synthesize new extra rules
   - write textual memory
   - run dedup / validation / promotion
10. A completed `model_stage` must include a knowledge envelope:
   - put deterministic reusable patterns in `rule_candidates`
   - put non-rule-stable lessons in `memory_candidates`
   - every `rule_candidates` item must include generated `validation_cases.positive` and `validation_cases.negative`
   - use empty arrays only when there is genuinely no reusable knowledge
11. For async/subagent `model_stage`, write proposal files only; the subagent must not directly modify active extra rules.
12. At the end of every main-agent task, run one proposal sweep over pending async proposals.
13. Use one promotion lifecycle for actual use and experiments:
   - set `promotion_context.source_type` to the evidence source, such as `online`, `evolution`, `benchmark`, `manual`, or `shadow`
   - set `promotion_context.update_mode` to `learn`, `candidate_only`, or `read_only`
   - use `promotion_context.snapshot_request = true` to write a fixed rule snapshot
   - read-only turns must not write model knowledge, async proposals, or proposal sweep results
14. If the hook reports `model_stage_status = rule_proposer_required`:
   - run the model rule-proposer task in `pending_rule_proposer_task`
   - return structured `model_stage.rule_candidates` and `model_stage.memory_candidates`
   - include positive and negative validation cases for every rule candidate
13. If there is a pending async model task from a previous turn, check it before continuing the new turn.

Proposal sweep updates subsequent turns only. Do not rewrite the already finalized current turn.

When reporting the decision, include:

- `sentryskills_trace_id`
- `base_rule_action`
- `extra_rule_action`
- `rule_stage_action`
- `framework_risk_level`
- `model_dispatch_mode`
- `model_stage_status`
- `model_stage_result_available`
- `action_gate`
- `skill_gate`
- `execution_directive`
- `proposal_sweep_effect`
- `knowledge_writeback_status`
- `promotion_context`
- `rule_proposer_triggered`
- `final_action`
