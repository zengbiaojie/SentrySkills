# How SentrySkills Builds `base_rule`

## Overview

In SentrySkills, `base_rule` is not a single handcrafted rule. It is the merged result of three stable, synchronous stages:

`preflight -> runtime -> output_guard`

This design is explicit in the project documentation and in the runtime hook implementation. The repository treats this path as the fixed baseline security frontend, while `extra_rule` and later `model_stage` provide adaptive extensions on top of it.

## Construction Pipeline

### 1. Preflight

The first stage inspects the incoming task before execution. Its purpose is to decide whether the request itself already contains security boundary violations or risk signals.

Inputs:

- `user_prompt`
- `planned_actions`
- `intent_tags`
- `sensitivity_state`
- `policy`

Typical checks:

- explicit secret disclosure requests
- credential exfiltration intent
- prompt-injection and attack-pattern indicators
- risky explanation or summarization requests over sensitive context
- high-risk planned actions such as command execution, file writes, batch modification, or network calls
- presence of sensitive artifacts in the prompt, such as JWTs, connection strings, PII, or environment-variable references

Outputs:

- `preflight_decision = allow | downgrade | block`
- `risk_summary`
- `allowed_actions`
- `blocked_actions`
- `verification_requirements`
- `decision_reason_codes`

The key point is that preflight reasons over intent and planned behavior before the agent starts acting. This is a preventive layer.

### 2. Runtime

If preflight does not stop the turn early, the second stage evaluates runtime evidence.

Inputs:

- `runtime_events`
- `sources`
- `policy`

Typical checks:

- repeated retries or unstable execution
- single-source-only evidence chains
- rapid file-access bursts
- bulk operations
- critical runtime alerts

Outputs:

- `runtime_decision = continue | downgrade | stop`
- `alerts`
- `suggested_actions`
- `trust_annotations`
- `decision_reason_codes`

This stage is behavior-oriented rather than intent-oriented. It captures what the agent actually did or relied on, which preflight cannot fully know in advance.

### 3. Output Guard

The final base-rule stage validates the candidate answer before anything is returned.

Inputs:

- `candidate_response`
- `sensitivity_state`
- `trust_annotations`
- `policy`
- `leak_patterns`

Typical checks:

- secret or privacy leakage in the response
- reconstructive leakage from sensitive context
- whether redaction successfully removed the leak
- whether the answer relies only on a single unverified tool source

Outputs:

- `output_decision = allow | downgrade | block`
- `safe_response`
- `redaction_summary`
- `confidence_level`
- `source_disclosure`

This stage exists because unsafe behavior can manifest even when the original request looked acceptable. In other words, SentrySkills assumes that output safety must be checked independently instead of inferred from earlier stages.

## Merge Rule

The runtime hook merges the three stages into one `base_rule_action`.

The logic is:

- if `preflight_decision == block`, then `base_rule_action = block`
- if `runtime_decision == stop`, then `base_rule_action = block`
- if `output_decision == block`, then `base_rule_action = block`
- otherwise, if any stage returns a degraded decision, then `base_rule_action = downgrade`
- otherwise, `base_rule_action = allow`

In compact form, the precedence is:

`block > downgrade > allow`

Although the stage labels differ slightly (`continue` in runtime corresponds to non-blocking), the merged semantics are intentionally conservative.

## Why This Construction Makes Sense

### 1. Separation by failure mode

The three stages cover different failure modes:

- `preflight` handles unsafe intent and risky plans
- `runtime` handles behavioral drift and weak evidence chains
- `output_guard` handles leakage and overclaiming at the final response boundary

Using one monolithic rule layer would blur these distinctions. The staged design makes both enforcement and auditing clearer.

### 2. Defense in depth

A request that appears harmless at input time can still become unsafe during execution or in the final response. Splitting `base_rule` into three checkpoints creates redundancy:

- before acting
- while acting
- before speaking

This reduces dependence on any single detector.

### 3. Stable deterministic frontend

The project positions `base_rule` as the frozen baseline path. It is rule-first, synchronous, and mostly stdlib-based. That gives three research and engineering advantages:

- reproducibility across runs
- portability across agent frameworks
- easier attribution of why a turn was blocked or downgraded

This is especially important because the adaptive parts of the system, such as `extra_rule` growth and `model_stage`, are intentionally separated from the baseline.

### 4. Conservative trust handling

The runtime and output stages explicitly penalize single-source conclusions and suspicious evidence chains. This reflects an important design assumption of the project: security failures are not only about secret leakage, but also about unjustified certainty.

### 5. Action-aware rather than text-only

`preflight` does not only read user text; it also evaluates `planned_actions`. That is a sound design choice for agent systems, because many dangerous outcomes arise from intended operations such as command execution, file writes, or network calls, not just from the wording of the prompt.

### 6. Early exit when blocking is obvious

The implementation supports early exit when preflight already concludes `block`. This avoids unnecessary downstream computation and prevents later stages from weakening an already-clear denial decision.

## Minimal Description for a Paper

The following paragraph is sufficient for a methods section:

> In SentrySkills, the `base_rule` is constructed as the deterministic merge of three synchronous stages: preflight, runtime, and output guard. Preflight analyzes the user request and planned actions to detect unsafe intent, sensitive-disclosure requests, and high-risk operations before execution. Runtime monitors actual events and evidence quality, including retries, bulk operations, and single-source dependence. Output guard inspects the candidate response for leakage and unsupported certainty, applying redaction or blocking when necessary. The final `base_rule_action` is merged conservatively with precedence `block > downgrade > allow`, yielding a stable rule-first security frontend before any adaptive rule or model-based stage is entered.

## Code Anchors

The main implementation points are:

- `shared/scripts/self_guard_runtime_hook_template.py`
  - `preflight_decision(...)`
  - `runtime_decision(...)`
  - `output_guard(...)`
  - `decide_final_action(...)`
- `sentryskills-preflight/SKILL.md`
- `sentryskills-runtime/SKILL.md`
- `sentryskills-output/SKILL.md`
- `README.md`

