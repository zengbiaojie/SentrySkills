"""Input validation utilities for TrinityGuard."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

try:
    from jsonschema import validate, ValidationError, Draft7Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    ValidationError = Exception  # Fallback

from exceptions import InputValidationError, PolicyValidationError

logger = logging.getLogger(__name__)

# Load input schema
SCHEMA_PATH = Path(__file__).parent.parent / "references" / "input_schema.json"
INPUT_SCHEMA = None

if JSONSCHEMA_AVAILABLE and SCHEMA_PATH.exists():
    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            INPUT_SCHEMA = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load input schema: {e}")


def validate_input(payload: Dict[str, Any], strict: bool = True) -> None:
    """Validate input payload against schema.

    Args:
        payload: Input payload to validate
        strict: Whether to use strict validation (raise exception) or log warning

    Raises:
        InputValidationError: If validation fails in strict mode
    """
    if not JSONSCHEMA_AVAILABLE:
        logger.warning("jsonschema not available, skipping input validation")
        return

    if INPUT_SCHEMA is None:
        logger.warning("Input schema not loaded, skipping validation")
        return

    try:
        validate(instance=payload, schema=INPUT_SCHEMA)
        logger.debug("Input validation passed")
    except ValidationError as e:
        error_msg = f"Input validation failed: {e.message}"
        if strict:
            raise InputValidationError(
                error_msg,
                details={
                    "field": ".".join(str(p) for p in e.path) if e.path else "root",
                    "failed_value": e.instance if hasattr(e, 'instance') else None
                }
            )
        else:
            logger.warning(error_msg)


def validate_policy(policy: Dict[str, Any]) -> None:
    """Validate policy configuration.

    Args:
        policy: Policy dictionary to validate

    Raises:
        PolicyValidationError: If policy is invalid
    """
    errors = []

    # Check required top-level keys
    required_keys = ["sensitive_event_types", "leak_patterns"]
    for key in required_keys:
        if key not in policy:
            errors.append(f"Missing required policy key: {key}")

    # Validate leak_patterns
    if "leak_patterns" in policy:
        if not isinstance(policy["leak_patterns"], list):
            errors.append("leak_patterns must be a list")
        else:
            for i, pattern in enumerate(policy["leak_patterns"]):
                if not isinstance(pattern, str):
                    errors.append(f"leak_patterns[{i}] must be a string")
                else:
                    # Try to compile regex
                    try:
                        import re
                        re.compile(pattern)
                    except re.error as e:
                        errors.append(f"leak_patterns[{i}] invalid regex: {e}")

    # Validate thresholds
    if "retry_threshold_downgrade" in policy:
        threshold = policy["retry_threshold_downgrade"]
        if not isinstance(threshold, int) or threshold < 0:
            errors.append("retry_threshold_downgrade must be a non-negative integer")

    if errors:
        raise PolicyValidationError(
            "Policy validation failed",
            details={"errors": errors}
        )


def sanitize_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize and clean input payload.

    Args:
        payload: Input payload to sanitize

    Returns:
        Sanitized payload
    """
    sanitized = {}

    # Copy safe fields
    for key in ["session_id", "turn_id", "request_id"]:
        if key in payload and isinstance(payload[key], str):
            sanitized[key] = payload[key][:1000]  # Limit length

    # Sanitize user_prompt
    if "user_prompt" in payload:
        prompt = payload["user_prompt"]
        if isinstance(prompt, str):
            # Limit length and strip null bytes
            sanitized["user_prompt"] = prompt[:1_000_000].replace("\x00", "")
        else:
            sanitized["user_prompt"] = str(prompt)[:1_000_000]

    if "planned_actions" in payload and isinstance(payload["planned_actions"], list):
        sanitized["planned_actions"] = []
        for item in payload["planned_actions"][:100]:
            if isinstance(item, dict):
                clean_action: Dict[str, Any] = {}
                for k, v in item.items():
                    if isinstance(v, str):
                        clean_action[str(k)[:200]] = v[:1000].replace("\x00", "")
                    else:
                        clean_action[str(k)[:200]] = v
                sanitized["planned_actions"].append(clean_action)
            else:
                sanitized["planned_actions"].append(str(item)[:500].replace("\x00", ""))

    if "intent_tags" in payload and isinstance(payload["intent_tags"], list):
        sanitized["intent_tags"] = [str(x)[:500] for x in payload["intent_tags"][:100]]

    # Sanitize runtime_events
    if "runtime_events" in payload and isinstance(payload["runtime_events"], list):
        sanitized["runtime_events"] = []
        for event in payload["runtime_events"][:100]:
            if isinstance(event, dict):
                clean_event = {}
                for k, v in event.items():
                    if isinstance(v, str):
                        clean_event[k] = v[:1000]
                    else:
                        clean_event[k] = v
                sanitized["runtime_events"].append(clean_event)

    # Sanitize dynamic skill invocation gates. These are runtime-time
    # declarations made immediately before invoking a non-SentrySkills skill.
    if "skill_invocations" in payload and isinstance(payload["skill_invocations"], list):
        sanitized["skill_invocations"] = []
        for invocation in payload["skill_invocations"][:100]:
            if isinstance(invocation, dict):
                clean_invocation = {}
                for k, v in invocation.items():
                    if isinstance(v, str):
                        clean_invocation[k] = v[:2000].replace("\x00", "")
                    elif isinstance(v, list):
                        clean_invocation[k] = []
                        for item in v[:100]:
                            if isinstance(item, dict):
                                clean_item = {}
                                for item_key, item_value in item.items():
                                    if isinstance(item_value, str):
                                        clean_item[str(item_key)[:200]] = item_value[:1000].replace("\x00", "")
                                    else:
                                        clean_item[str(item_key)[:200]] = item_value
                                clean_invocation[k].append(clean_item)
                            else:
                                clean_invocation[k].append(str(item)[:1000].replace("\x00", ""))
                    else:
                        clean_invocation[k] = v
                sanitized["skill_invocations"].append(clean_invocation)

    # Sanitize sources
    if "sources" in payload and isinstance(payload["sources"], list):
        sanitized["sources"] = []
        for source in payload["sources"][:50]:
            if isinstance(source, dict):
                clean_source = {}
                for k, v in source.items():
                    if isinstance(v, str):
                        clean_source[k] = v[:500]
                    else:
                        clean_source[k] = v
                sanitized["sources"].append(clean_source)

    # Sanitize candidate_response
    if "candidate_response" in payload:
        response = payload["candidate_response"]
        if isinstance(response, str):
            sanitized["candidate_response"] = response[:1_000_000].replace("\x00", "")
        else:
            sanitized["candidate_response"] = str(response)[:1_000_000]

    # Preserve framework-provided model stage payload for post-rule model evaluation
    if "model_stage" in payload and isinstance(payload["model_stage"], dict):
        model_stage = payload["model_stage"]
        clean_model_stage: Dict[str, Any] = {}
        if "action" in model_stage:
            clean_model_stage["action"] = str(model_stage["action"])[:100]
        for key in ["analysis"]:
            if key in model_stage:
                clean_model_stage[key] = str(model_stage[key])[:20_000].replace("\x00", "")
        for key in ["reason_codes", "findings"]:
            if key in model_stage and isinstance(model_stage[key], list):
                clean_model_stage[key] = [str(x)[:1000] for x in model_stage[key][:100]]
        for key in ["rule_candidates", "memory_candidates"]:
            if key in model_stage and isinstance(model_stage[key], list):
                clean_items = []
                for item in model_stage[key][:50]:
                    if not isinstance(item, dict):
                        continue
                    clean_item: Dict[str, Any] = {}
                    for item_key, item_value in item.items():
                        if isinstance(item_value, str):
                            clean_item[item_key] = item_value[:5000].replace("\x00", "")
                        elif isinstance(item_value, list):
                            clean_item[item_key] = [str(x)[:1000] for x in item_value[:50]]
                        elif isinstance(item_value, dict):
                            clean_nested: Dict[str, Any] = {}
                            for nested_key, nested_value in item_value.items():
                                if isinstance(nested_value, str):
                                    clean_nested[str(nested_key)[:200]] = nested_value[:2000].replace("\x00", "")
                                elif isinstance(nested_value, list):
                                    clean_nested[str(nested_key)[:200]] = [str(x)[:1000] for x in nested_value[:50]]
                                else:
                                    clean_nested[str(nested_key)[:200]] = nested_value
                            clean_item[item_key] = clean_nested
                        else:
                            clean_item[item_key] = item_value
                    clean_items.append(clean_item)
                clean_model_stage[key] = clean_items
        sanitized["model_stage"] = clean_model_stage

    for phase_key in ["preflight_model", "runtime_model", "output_model"]:
        if phase_key in payload and isinstance(payload[phase_key], dict):
            phase_model = payload[phase_key]
            clean_phase_model: Dict[str, Any] = {}
            if "action" in phase_model:
                clean_phase_model["action"] = str(phase_model["action"])[:100]
            if "analysis" in phase_model:
                clean_phase_model["analysis"] = str(phase_model["analysis"])[:20_000].replace("\x00", "")
            for key in ["reason_codes", "findings"]:
                if key in phase_model and isinstance(phase_model[key], list):
                    clean_phase_model[key] = [str(x)[:1000] for x in phase_model[key][:100]]
            for key in ["rule_candidates", "memory_candidates"]:
                if key in phase_model and isinstance(phase_model[key], list):
                    clean_items = []
                    for item in phase_model[key][:50]:
                        if not isinstance(item, dict):
                            continue
                        clean_item: Dict[str, Any] = {}
                        for item_key, item_value in item.items():
                            if isinstance(item_value, str):
                                clean_item[item_key] = item_value[:5000].replace("\x00", "")
                            elif isinstance(item_value, list):
                                clean_item[item_key] = [str(x)[:1000] for x in item_value[:50]]
                            elif isinstance(item_value, dict):
                                clean_item[item_key] = {
                                    str(nested_key)[:200]: (
                                        nested_value[:2000].replace("\x00", "")
                                        if isinstance(nested_value, str)
                                        else [str(x)[:1000] for x in nested_value[:50]]
                                        if isinstance(nested_value, list)
                                        else nested_value
                                    )
                                    for nested_key, nested_value in item_value.items()
                                }
                            else:
                                clean_item[item_key] = item_value
                        clean_items.append(clean_item)
                    clean_phase_model[key] = clean_items
            sanitized[phase_key] = clean_phase_model

    if "model_dispatch_mode" in payload:
        sanitized["model_dispatch_mode"] = str(payload["model_dispatch_mode"])[:100]

    if "framework_risk_level" in payload:
        sanitized["framework_risk_level"] = str(payload["framework_risk_level"])[:100]

    if "sentryskills_role" in payload:
        sanitized["sentryskills_role"] = str(payload["sentryskills_role"])[:100]

    if "process_pending_proposals" in payload:
        sanitized["process_pending_proposals"] = bool(payload["process_pending_proposals"])

    if "promotion_context" in payload and isinstance(payload["promotion_context"], dict):
        clean_context: Dict[str, Any] = {}
        for key, value in payload["promotion_context"].items():
            if isinstance(value, str):
                clean_context[str(key)[:200]] = value[:2000].replace("\x00", "")
            elif isinstance(value, bool):
                clean_context[str(key)[:200]] = value
            elif isinstance(value, list):
                clean_context[str(key)[:200]] = [str(x)[:1000].replace("\x00", "") for x in value[:50]]
            else:
                clean_context[str(key)[:200]] = value
        sanitized["promotion_context"] = clean_context

    if "feedback_text" in payload:
        sanitized["feedback_text"] = str(payload["feedback_text"])[:5000].replace("\x00", "")

    if "feedback" in payload and isinstance(payload["feedback"], str):
        sanitized["feedback"] = str(payload["feedback"])[:5000].replace("\x00", "")
    elif "feedback" in payload and isinstance(payload["feedback"], dict):
        clean_feedback: Dict[str, Any] = {}
        for key, value in payload["feedback"].items():
            if isinstance(value, str):
                clean_feedback[str(key)[:200]] = value[:5000].replace("\x00", "")
            elif isinstance(value, bool):
                clean_feedback[str(key)[:200]] = value
            elif isinstance(value, list):
                clean_feedback[str(key)[:200]] = [str(x)[:2000].replace("\x00", "") for x in value[:100]]
            elif isinstance(value, dict):
                clean_feedback[str(key)[:200]] = {
                    str(nested_key)[:200]: (
                        nested_value[:2000].replace("\x00", "")
                        if isinstance(nested_value, str)
                        else nested_value
                    )
                    for nested_key, nested_value in value.items()
                }
            else:
                clean_feedback[str(key)[:200]] = value
        sanitized["feedback"] = clean_feedback

    if "outcome_signals" in payload and isinstance(payload["outcome_signals"], list):
        clean_signals = []
        for item in payload["outcome_signals"][:50]:
            if isinstance(item, dict):
                clean_item: Dict[str, Any] = {}
                for key, value in item.items():
                    if isinstance(value, str):
                        clean_item[str(key)[:200]] = value[:5000].replace("\x00", "")
                    elif isinstance(value, list):
                        clean_item[str(key)[:200]] = [str(x)[:2000].replace("\x00", "") for x in value[:50]]
                    else:
                        clean_item[str(key)[:200]] = value
                clean_signals.append(clean_item)
            else:
                clean_signals.append(str(item)[:2000].replace("\x00", ""))
        sanitized["outcome_signals"] = clean_signals

    # Backward-compatible aliases. New integrations should use promotion_context.
    for key in ["learning_mode", "promotion_policy", "source_case_id"]:
        if key in payload:
            sanitized[key] = str(payload[key])[:200].replace("\x00", "")

    for key in ["freeze_rules", "allow_test_writeback", "finalize_experiment"]:
        if key in payload:
            sanitized[key] = bool(payload[key])

    for key in ["project_path", "project_root", "workspace_root", "repo_root"]:
        if key in payload and isinstance(payload[key], str):
            sanitized[key] = payload[key][:5000].replace("\x00", "")

    if "pending_model_task" in payload and isinstance(payload["pending_model_task"], dict):
        clean_pending: Dict[str, Any] = {}
        for key, value in payload["pending_model_task"].items():
            if isinstance(value, str):
                clean_pending[key] = value[:1000].replace("\x00", "")
            else:
                clean_pending[key] = value
        sanitized["pending_model_task"] = clean_pending

    return sanitized


def validate_path(path: Path, must_exist: bool = False, allow_symlinks: bool = False) -> bool:
    """Validate file path.

    Args:
        path: Path to validate
        must_exist: Whether path must exist
        allow_symlinks: Whether to allow symbolic links

    Returns:
        True if valid

    Raises:
        InputValidationError: If path is invalid
    """
    if not isinstance(path, Path):
        path = Path(path)

    # Check for symlinks
    if not allow_symlinks and path.is_symlink():
        raise InputValidationError(
            f"Symbolic links not allowed: {path}",
            details={"path": str(path)}
        )

    # Check existence if required
    if must_exist and not path.exists():
        raise InputValidationError(
            f"Path does not exist: {path}",
            details={"path": str(path)}
        )

    # Check path is within allowed bounds
    try:
        path.resolve()
    except Exception as e:
        raise InputValidationError(
            f"Invalid path: {path}",
            details={"error": str(e)}
        )

    return True


def validate_file_size(path: Path, max_size_mb: int = 100) -> bool:
    """Validate file size is within limits.

    Args:
        path: Path to check
        max_size_mb: Maximum size in megabytes

    Returns:
        True if size is valid

    Raises:
        InputValidationError: If file is too large
    """
    if not path.exists():
        return True

    size_bytes = path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    if size_mb > max_size_mb:
        raise InputValidationError(
            f"File too large: {size_mb:.2f}MB (max: {max_size_mb}MB)",
            details={
                "path": str(path),
                "size_mb": size_mb,
                "max_size_mb": max_size_mb
            }
        )

    return True
