# sentryskills-orchestrator

Two-path orchestrator for preflight + runtime + output guard.

## Purpose

- coordinate the full pipeline (preflight → runtime → output guard → final decision)
- run synchronously in the current process (HIGH path) or as a subagent (LOW path)
- merge reason codes and matched rules
- compute final decision and write auditable records

## Core outputs

- `final_action`
- `decision_chain`
- `trace_id`
- `output_guard.safe_response`
