#!/usr/bin/env python3
"""Batch-run converted AgentDojo framework cases with a framework agent.

Currently only the Codex runner is implemented. Other runner names are accepted
as CLI values so the batch interface can stay stable as more runners are added.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FRAMEWORK_ROOT = SCRIPT_DIR / "agentdojo_framework"
DEFAULT_RUNS_ROOT = SCRIPT_DIR / "agentdojo_batch_runs"
DEFAULT_RUNNER = "codex"
DEFAULT_CODEX_MODEL = "gpt-5.2"
RUNNER_CHOICES = ("codex", "claude", "claude-code")
SUBPROCESS_TEXT_KWARGS = {
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
}


class BatchRunError(RuntimeError):
    """Raised for invalid batch-run configuration or unrecoverable failures."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-run AgentDojo framework cases.")
    parser.add_argument("--framework-root", type=Path, default=DEFAULT_FRAMEWORK_ROOT)
    parser.add_argument("--manifest", type=Path, default=None, help="Defaults to <framework-root>/manifest.json.")
    parser.add_argument("--runner", choices=RUNNER_CHOICES, default=DEFAULT_RUNNER)
    parser.add_argument("--out", type=Path, default=None, help="Exact output run directory.")
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--suite", action="append", default=[], help="Suite to include. Can be repeated.")
    parser.add_argument("--case", action="append", default=[], help="Exact case_id to include. Can be repeated.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Skip cases with an existing run_result.json.")
    parser.add_argument("--overwrite", action="store_true", help="Remove an existing run directory before starting.")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--jobs", type=int, default=4, help="Maximum number of cases to run concurrently.")

    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default=DEFAULT_CODEX_MODEL)
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--full-auto", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--codex-arg", action="append", default=[], help="Extra argument passed to `codex exec`.")
    parser.add_argument(
        "--clean-codex-state",
        action="store_true",
        help="Clean non-auth Codex runtime state before each `codex exec`. Requires --jobs 1.",
    )
    parser.add_argument("--timeout", type=int, default=None, help="Per-case agent timeout in seconds.")
    parser.add_argument("--reset", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--evaluate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Run inside the original visible directories instead of materializing per-run copies.",
    )
    return parser.parse_args()


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(data), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", errors="ignore")


def print_json(data: Any) -> None:
    print(json.dumps(jsonable(data), indent=2, ensure_ascii=True))


def sanitize_name(value: str) -> str:
    allowed = []
    for char in value:
        if char.isalnum() or char in ("-", "_", "."):
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed).strip("._") or "run"


def default_run_name(args: argparse.Namespace) -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"{args.runner}_{args.model}" if args.runner == "codex" else args.runner
    return f"{timestamp}_{sanitize_name(suffix)}"


def resolve_run_dir(args: argparse.Namespace) -> Path:
    if args.out is not None:
        return args.out.resolve()
    run_name = args.run_name or default_run_name(args)
    return (args.runs_root / run_name).resolve()


def safe_remove_tree(path: Path, allowed_parent: Path) -> None:
    path = path.resolve()
    allowed_parent = allowed_parent.resolve()
    if path == allowed_parent or allowed_parent not in path.parents:
        raise BatchRunError(f"Refusing to remove path outside runs root: {path}")
    shutil.rmtree(path)


def remove_cleanup_target(path: Path, *, is_dir: bool) -> dict[str, Any]:
    record: dict[str, Any] = {"path": str(path), "removed": False}
    try:
        if is_dir:
            if path.exists():
                shutil.rmtree(path)
                record["removed"] = True
        elif path.exists():
            path.unlink()
            record["removed"] = True
    except OSError as exc:
        record["error"] = str(exc)
    return record


def clean_codex_state(visible_dir: Path) -> dict[str, Any]:
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()
    cleanup = {
        "codex_home": str(codex_home),
        "targets": [],
    }

    cleanup["targets"].append(remove_cleanup_target(visible_dir / ".codex", is_dir=True))

    for name in (
        "history.jsonl",
        "sandbox.log",
        "logs_2.sqlite-shm",
        "logs_2.sqlite-wal",
    ):
        cleanup["targets"].append(remove_cleanup_target(codex_home / name, is_dir=False))

    return cleanup


def load_manifest(args: argparse.Namespace) -> dict[str, Any]:
    framework_root = args.framework_root.resolve()
    manifest_path = (args.manifest or framework_root / "manifest.json").resolve()
    if not manifest_path.exists():
        raise BatchRunError(f"Manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list):
        raise BatchRunError(f"Invalid manifest format: {manifest_path}")
    return manifest


def select_cases(manifest: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    cases = list(manifest["cases"])
    if args.suite:
        suites = set(args.suite)
        cases = [case for case in cases if case.get("suite") in suites]
    if args.case:
        case_ids = set(args.case)
        cases = [case for case in cases if case.get("case_id") in case_ids]
    if args.limit is not None:
        cases = cases[: args.limit]
    return cases


def command_display(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def resolve_case_paths(case: dict[str, Any]) -> tuple[Path, Path]:
    visible_dir = Path(case["visible_dir"]).resolve()
    hidden_dir = Path(case["hidden_dir"]).resolve()
    if not visible_dir.exists():
        raise BatchRunError(f"Visible directory not found for {case['case_id']}: {visible_dir}")
    if not hidden_dir.exists():
        raise BatchRunError(f"Hidden directory not found for {case['case_id']}: {hidden_dir}")
    return visible_dir, hidden_dir


def copy_json_file(src: Path, dst: Path) -> None:
    write_json(dst, read_json(src))


def prepare_runtime_state(source_hidden: Path, target_hidden: Path) -> None:
    source_state = source_hidden / "runtime_state"
    target_state = target_hidden / "runtime_state"
    initial_path = source_state / "initial_environment.json"
    if not initial_path.exists():
        raise BatchRunError(f"Missing initial runtime state: {initial_path}")
    initial_environment = read_json(initial_path)
    write_json(target_state / "initial_environment.json", initial_environment)
    write_json(target_state / "current_environment.json", initial_environment)
    write_json(target_state / "action_trace.json", [])


def prepare_case_config(source_hidden: Path, target_hidden: Path, agentdojo_root: str | None) -> None:
    config = read_json(source_hidden / "case_config.json")
    if agentdojo_root:
        config["agentdojo_root"] = str(Path(agentdojo_root).resolve())
    write_json(target_hidden / "case_config.json", config)


def rewrite_runtime_wrappers(visible_dir: Path) -> None:
    win_python = SCRIPT_DIR / ".venv" / "Scripts" / "python.exe"
    posix_python = SCRIPT_DIR / ".venv" / "bin" / "python"
    fallback_python = Path(sys.executable)
    bat = f"""@echo off
setlocal
set "HERE=%~dp0"
set "PY={win_python}"
set "FALLBACK_PY={fallback_python}"

if exist "%PY%" (
  "%PY%" "%HERE%agentdojo_tool.py" %*
) else if exist "%FALLBACK_PY%" (
  "%FALLBACK_PY%" "%HERE%agentdojo_tool.py" %*
) else (
  python "%HERE%agentdojo_tool.py" %*
)
"""
    sh = f"""#!/usr/bin/env sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PY="{posix_python.as_posix()}"
FALLBACK_PY="{fallback_python.as_posix()}"

if [ -x "$PY" ]; then
  exec "$PY" "$HERE/agentdojo_tool.py" "$@"
elif [ -x "$FALLBACK_PY" ]; then
  exec "$FALLBACK_PY" "$HERE/agentdojo_tool.py" "$@"
elif command -v python3 >/dev/null 2>&1; then
  exec python3 "$HERE/agentdojo_tool.py" "$@"
else
  exec python "$HERE/agentdojo_tool.py" "$@"
fi
"""
    write_text(visible_dir / "run_tool.bat", bat)
    write_text(visible_dir / "run_tool.sh", sh)


def materialize_case(case: dict[str, Any], case_run_dir: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    source_visible, source_hidden = resolve_case_paths(case)
    materialized_root = case_run_dir
    target_visible = materialized_root / "visible"
    target_hidden = materialized_root / "hidden"
    if materialized_root.exists():
        shutil.rmtree(materialized_root)
    shutil.copytree(source_visible, target_visible)
    target_hidden.mkdir(parents=True, exist_ok=True)
    prepare_case_config(source_hidden, target_hidden, manifest.get("agentdojo_root"))
    prepare_runtime_state(source_hidden, target_hidden)
    rewrite_runtime_wrappers(target_visible)
    return target_visible, target_hidden


def add_evaluator_materials(case: dict[str, Any], target_hidden: Path) -> None:
    _source_visible, source_hidden = resolve_case_paths(case)
    for name in (
        "evaluate.py",
        "oracle_spec.json",
        "source_mapping.json",
        "clean_environment.json",
        "environment.md",
        "grading_notes.md",
    ):
        src = source_hidden / name
        if src.exists():
            shutil.copy2(src, target_hidden / name)


def sync_runtime_state_for_evaluation(visible_dir: Path, hidden_dir: Path) -> None:
    visible_state_candidates = [
        visible_dir / "runtime_state",
        visible_dir / ".runtime_state",
    ]
    hidden_state = hidden_dir / "runtime_state"
    existing_states = [path for path in visible_state_candidates if path.exists()]
    if not existing_states:
        return

    visible_state = next((path for path in existing_states if runtime_state_has_nonempty_trace(path)), existing_states[0])
    hidden_state.mkdir(parents=True, exist_ok=True)
    for name in ("current_environment.json", "action_trace.json"):
        src = visible_state / name
        if src.exists():
            shutil.copy2(src, hidden_state / name)


def runtime_state_has_nonempty_trace(state_dir: Path) -> bool:
    trace_path = state_dir / "action_trace.json"
    if not trace_path.exists():
        return False
    try:
        trace = read_json(trace_path)
    except (OSError, json.JSONDecodeError):
        return True
    return bool(trace)


def reset_case_state(visible_dir: Path) -> subprocess.CompletedProcess[str]:
    run_tool = visible_dir / ("run_tool.bat" if os.name == "nt" else "run_tool.sh")
    return subprocess.run(
        [str(run_tool), "reset"],
        cwd=visible_dir,
        capture_output=True,
        **SUBPROCESS_TEXT_KWARGS,
    )


def build_codex_command(args: argparse.Namespace, visible_dir: Path, output_path: Path) -> list[str]:
    codex_bin = shutil.which(args.codex_bin) or args.codex_bin
    command = [codex_bin, "exec"]
    if args.full_auto:
        command.append("--full-auto")
    command.extend(["--sandbox", args.sandbox, "-m", args.model])
    command.extend(args.codex_arg)
    command.extend(["-o", str(output_path), "--cd", str(visible_dir)])
    return command


def run_codex_case(args: argparse.Namespace, visible_dir: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    input_path = visible_dir / "input.md"
    command = build_codex_command(args, visible_dir, output_path)
    with input_path.open("r", encoding="utf-8") as stdin:
        return subprocess.run(
            command,
            cwd=SCRIPT_DIR,
            stdin=stdin,
            capture_output=True,
            timeout=args.timeout,
            **SUBPROCESS_TEXT_KWARGS,
        )


def evaluate_case(hidden_dir: Path, output_path: Path, evaluation_path: Path) -> subprocess.CompletedProcess[str]:
    evaluator = hidden_dir / "evaluate.py"
    if not evaluator.exists():
        raise BatchRunError(f"Evaluator not found: {evaluator}")
    return subprocess.run(
        [sys.executable, str(evaluator), "--output", str(output_path), "--out", str(evaluation_path)],
        cwd=hidden_dir.parent / "visible",
        capture_output=True,
        **SUBPROCESS_TEXT_KWARGS,
    )


def unsupported_runner_result(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "runner": args.runner,
        "status": "not_implemented",
        "error": f"Runner `{args.runner}` is not implemented yet. Use --runner codex.",
    }


def run_one_case(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    case: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    case_id = case["case_id"]
    case_run_dir = run_dir / "cases" / case_id
    result_path = case_run_dir / "run_result.json"
    if args.resume and result_path.exists():
        return {"case_id": case_id, "status": "skipped_existing", "result_path": str(result_path)}
    if case_run_dir.exists():
        shutil.rmtree(case_run_dir)
    case_run_dir.mkdir(parents=True, exist_ok=True)

    if args.in_place:
        visible_dir, hidden_dir = resolve_case_paths(case)
    else:
        visible_dir, hidden_dir = materialize_case(case, case_run_dir, manifest)

    output_path = case_run_dir / "output.md"
    stdout_path = case_run_dir / "stdout.txt"
    stderr_path = case_run_dir / "stderr.txt"
    evaluation_path = case_run_dir / "evaluation_result.json"
    started_at = dt.datetime.now(dt.timezone.utc)
    started = time.monotonic()
    result: dict[str, Any] = {
        "case_id": case_id,
        "suite": case.get("suite"),
        "runner": args.runner,
        "visible_dir": str(visible_dir),
        "hidden_dir": str(hidden_dir),
        "output_path": str(output_path),
        "started_at_utc": started_at.isoformat(),
    }

    if args.runner != "codex":
        result.update(unsupported_runner_result(args))
        write_json(result_path, result)
        return result

    if args.reset:
        reset_result = reset_case_state(visible_dir)
        result["reset_returncode"] = reset_result.returncode
        result["reset_stdout"] = reset_result.stdout
        result["reset_stderr"] = reset_result.stderr
        if reset_result.returncode != 0:
            result["status"] = "reset_failed"
            result["duration_seconds"] = round(time.monotonic() - started, 3)
            write_json(result_path, result)
            return result

    if args.clean_codex_state:
        result["codex_state_cleanup"] = clean_codex_state(visible_dir)

    command = build_codex_command(args, visible_dir, output_path)
    result["command"] = command
    result["command_display"] = command_display(command)
    try:
        completed = run_codex_case(args, visible_dir, output_path)
        result["agent_returncode"] = completed.returncode
        write_text(stdout_path, completed.stdout)
        write_text(stderr_path, completed.stderr)
        result["stdout_path"] = str(stdout_path)
        result["stderr_path"] = str(stderr_path)
        result["status"] = "agent_completed" if completed.returncode == 0 else "agent_failed"
    except subprocess.TimeoutExpired as exc:
        write_text(stdout_path, exc.stdout or "")
        write_text(stderr_path, exc.stderr or "")
        result["status"] = "agent_timeout"
        result["agent_returncode"] = None
        result["timeout_seconds"] = args.timeout
        result["stdout_path"] = str(stdout_path)
        result["stderr_path"] = str(stderr_path)

    if args.evaluate and result.get("agent_returncode") == 0:
        sync_runtime_state_for_evaluation(visible_dir, hidden_dir)
        if not args.in_place:
            add_evaluator_materials(case, hidden_dir)
        evaluation = evaluate_case(hidden_dir, output_path, evaluation_path)
        result["evaluation_returncode"] = evaluation.returncode
        result["evaluation_stdout"] = evaluation.stdout
        result["evaluation_stderr"] = evaluation.stderr
        result["evaluation_path"] = str(evaluation_path)
        if evaluation_path.exists():
            result["evaluation"] = read_json(evaluation_path)

    result["finished_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    write_json(result_path, result)
    return result


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(jsonable(row), ensure_ascii=False) + "\n")


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"total": len(results), "status_counts": {}}
    for result in results:
        status = result.get("status", "unknown")
        summary["status_counts"][status] = summary["status_counts"].get(status, 0) + 1
    evaluated = [r for r in results if isinstance(r.get("evaluation"), dict)]
    if evaluated:
        summary["evaluated"] = len(evaluated)
        summary["task_success"] = sum(1 for r in evaluated if r["evaluation"].get("task_success"))
        summary["attack_success"] = sum(1 for r in evaluated if r["evaluation"].get("attack_success"))
        summary["attack_received"] = sum(1 for r in evaluated if r["evaluation"].get("attack_received"))
    return summary


def result_failed(result: dict[str, Any]) -> bool:
    failed = result.get("status") not in {"agent_completed", "skipped_existing"}
    eval_failed = result.get("evaluation_returncode") not in (None, 0)
    return bool(failed or eval_failed)


def persist_progress(run_dir: Path, results: list[dict[str, Any]]) -> None:
    write_jsonl(run_dir / "results.jsonl", results)
    write_json(run_dir / "summary.json", summarize(results))


def exception_result(case: dict[str, Any], exc: BaseException) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "suite": case.get("suite"),
        "status": "runner_exception",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "finished_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def cancelled_result(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "suite": case.get("suite"),
        "status": "cancelled",
        "finished_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def run_selected_cases(
    *,
    args: argparse.Namespace,
    manifest: dict[str, Any],
    cases: list[dict[str, Any]],
    run_dir: Path,
) -> list[dict[str, Any]]:
    total = len(cases)
    max_workers = min(args.jobs, total)
    results: list[dict[str, Any]] = []
    pending: dict[Future[dict[str, Any]], tuple[int, dict[str, Any]]] = {}
    next_index = 0
    stop_scheduling = False

    def submit_next(executor: ThreadPoolExecutor) -> None:
        nonlocal next_index
        case = cases[next_index]
        index = next_index + 1
        next_index += 1
        print(f"[start {index}/{total}] {case['case_id']}", flush=True)
        future = executor.submit(run_one_case, args=args, manifest=manifest, case=case, run_dir=run_dir)
        pending[future] = (index, case)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while next_index < total and len(pending) < max_workers:
            submit_next(executor)

        while pending:
            done, _not_done = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index, case = pending.pop(future)
                if future.cancelled():
                    result = cancelled_result(case)
                else:
                    try:
                        result = future.result()
                    except BaseException as exc:
                        result = exception_result(case, exc)

                results.append(result)
                persist_progress(run_dir, results)
                status = result.get("status", "unknown")
                print(f"[done {len(results)}/{total}] {case['case_id']} status={status}", flush=True)

                if args.fail_fast and result_failed(result):
                    stop_scheduling = True

            if stop_scheduling:
                for future in pending:
                    future.cancel()
            else:
                while next_index < total and len(pending) < max_workers:
                    submit_next(executor)

    return results


def run(args: argparse.Namespace) -> int:
    if args.runner != "codex" and not args.dry_run:
        raise BatchRunError(f"Runner `{args.runner}` is not implemented yet. Use --runner codex.")
    if args.jobs < 1:
        raise BatchRunError("--jobs must be >= 1.")
    if args.clean_codex_state and args.jobs != 1:
        raise BatchRunError("--clean-codex-state removes shared Codex runtime files and requires --jobs 1.")

    manifest = load_manifest(args)
    cases = select_cases(manifest, args)
    if not cases:
        raise BatchRunError("No cases selected.")

    run_dir = resolve_run_dir(args)
    if run_dir.exists() and args.overwrite:
        safe_remove_tree(run_dir, args.runs_root.resolve())
    if run_dir.exists() and not args.resume and not args.dry_run:
        raise BatchRunError(f"Run directory already exists. Use --resume or --overwrite: {run_dir}")

    config = {
        "runner": args.runner,
        "framework_root": str(args.framework_root.resolve()),
        "manifest": str((args.manifest or args.framework_root / "manifest.json").resolve()),
        "run_dir": str(run_dir),
        "case_count": len(cases),
        "model": args.model if args.runner == "codex" else None,
        "sandbox": args.sandbox if args.runner == "codex" else None,
        "jobs": args.jobs,
        "in_place": args.in_place,
        "evaluate": args.evaluate,
        "clean_codex_state": args.clean_codex_state,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    if args.dry_run:
        print_json(config)
        for case in cases:
            print(case["case_id"])
        return 0

    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "run_config.json", config)

    print(f"Running {len(cases)} case(s) with jobs={args.jobs}", flush=True)
    results = run_selected_cases(args=args, manifest=manifest, cases=cases, run_dir=run_dir)

    summary = summarize(results)
    write_json(run_dir / "summary.json", summary)
    print_json(summary)
    print(f"Run directory: {run_dir}")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except BatchRunError as exc:
        print(f"Batch run failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
