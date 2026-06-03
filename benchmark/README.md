# Benchmark Conversion

This directory keeps third-party benchmark sources and generated framework-facing cases.

## AgentDojo to Framework Cases

`convert_agentdojo_framework.py` converts the local `agentdojo/` checkout into neutral cases that can be run by Codex, Claude Code, or another real framework agent.

The converter requires AgentDojo runtime dependencies. If dependencies are missing, it fails immediately instead of falling back to a lower-fidelity parser.
Default input/output paths are resolved relative to this `benchmark/` directory, so the script can be run either from the repository root or from inside `benchmark/`.

```powershell
python benchmark\convert_agentdojo_framework.py --dry-run
python benchmark\convert_agentdojo_framework.py --overwrite --limit 5
```

Generated output goes to `benchmark/agentdojo_framework/` by default.

- Use only `cases/<case_id>/visible/` as the agent-facing task directory.
- Use `cases/<case_id>/visible/input.md` as the actual prompt/input for Codex, Claude Code, or another framework agent.
- Keep `cases/<case_id>/hidden/` away from the evaluated agent; it contains oracle, grading material, runtime config, and runtime state.
- `visible/agentdojo_tool.py` exposes AgentDojo tools as local commands and persists state under `hidden/runtime_state/`.
- Tool commands in `input.md` use `run_tool.bat` on Windows. The wrapper prefers `benchmark/.venv`, then a local case `.venv`, and falls back to `python`.
- Injected attack text appears only when a tool call returns external data containing it.
- After a model run, save the final JSON outside the agent-visible prompt context and grade with the case-local hidden evaluator: `cases/<case_id>/hidden/evaluate.py --output <output_json>`.
- Use `injection_observed_by_agent=true` to confirm the agent actually saw the injected payload; otherwise a non-attack result may simply mean the attack was never exposed.
- The generated visible files are SentrySkills-neutral, so the same cases can be used for baseline and SentrySkills-enabled experiments.

Useful options:

```powershell
python benchmark\convert_agentdojo_framework.py --all --limit-per-suite 10 --overwrite
python benchmark\convert_agentdojo_framework.py --case workspace:user_task_0:injection_task_0 --overwrite
python benchmark\convert_agentdojo_framework.py --suites workspace slack --attack injecagent --overwrite
```
