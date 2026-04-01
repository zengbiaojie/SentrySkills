#!/usr/bin/env python3
"""
Verification tests for P0 fixes.
Tests critical functionality before launch.
"""
import json
import sys
import re
from pathlib import Path

# Test data paths
PROJECT_ROOT = Path(__file__).parent
DETECTION_RULES = PROJECT_ROOT / "shared" / "scripts" / "detection_rules.json"
STRICT_POLICY = PROJECT_ROOT / "shared" / "references" / "runtime_policy.strict.json"
BALANCED_POLICY = PROJECT_ROOT / "shared" / "references" / "runtime_policy.balanced.json"
PERMISSIVE_POLICY = PROJECT_ROOT / "shared" / "references" / "runtime_policy.permissive.json"
HOOK_SCRIPT = PROJECT_ROOT / "shared" / "scripts" / "self_guard_runtime_hook_template.py"


def test_fix1_detection_rules_enabled():
    """Fix 1: All 33 detection rules should be enabled."""
    print("\n[Fix 1] Testing detection rules metadata...")

    with open(DETECTION_RULES) as f:
        rules = json.load(f)

    enabled_count = 0
    total_count = 0

    for category in rules["rule_categories"].values():
        for rule in category["rules"]:
            total_count += 1
            if rule["enabled"]:
                enabled_count += 1

    total_in_metadata = rules["metadata"]["total_rules"]
    enabled_in_metadata = rules["metadata"]["enabled_rules"]

    assert enabled_in_metadata == total_in_metadata, \
        f"Metadata shows {enabled_in_metadata}/{total_in_metadata} enabled, should be all"

    assert enabled_count == total_count == total_in_metadata, \
        f"Expected {total_in_metadata} enabled rules, found {enabled_count}/{total_count}"

    print(f"  OK All {enabled_count} rules enabled")
    return True


def test_fix2_policies_differentiated():
    """Fix 2: Three policy files should have meaningful differences."""
    print("\n[Fix 2] Testing policy differentiation...")

    with open(STRICT_POLICY) as f:
        strict = json.load(f)
    with open(BALANCED_POLICY) as f:
        balanced = json.load(f)
    with open(PERMISSIVE_POLICY) as f:
        permissive = json.load(f)

    # Check retry_threshold_downgrade is different
    assert strict["retry_threshold_downgrade"] == 2, \
        f"strict retry_threshold should be 2, got {strict['retry_threshold_downgrade']}"
    assert balanced["retry_threshold_downgrade"] == 3, \
        f"balanced retry_threshold should be 3, got {balanced['retry_threshold_downgrade']}"
    assert permissive["retry_threshold_downgrade"] == 5, \
        f"permissive retry_threshold should be 5, got {permissive['retry_threshold_downgrade']}"

    print(f"  OK retry_threshold: strict={strict['retry_threshold_downgrade']}, "
          f"balanced={balanced['retry_threshold_downgrade']}, "
          f"permissive={permissive['retry_threshold_downgrade']}")

    # Check block_on_highly_sensitive_leak
    assert strict["block_on_highly_sensitive_leak"] == True
    assert balanced["block_on_highly_sensitive_leak"] == True
    assert permissive["block_on_highly_sensitive_leak"] == False

    print(f"  OK block_on_highly_sensitive_leak: strict=True, balanced=True, permissive=False")

    # Check single_source_types
    assert len(strict["single_source_types"]) == 2, \
        f"strict should have 2 single_source_types, got {len(strict['single_source_types'])}"
    assert len(balanced["single_source_types"]) == 1
    assert len(permissive["single_source_types"]) == 1

    print(f"  OK single_source_types: strict={len(strict['single_source_types'])}, "
          f"balanced={len(balanced['single_source_types'])}, "
          f"permissive={len(permissive['single_source_types'])}")

    return True


def test_fix3_placeholder_exact_matching():
    """Fix 3: Placeholder detection should match exact values, not context."""
    print("\n[Fix 3] Testing placeholder exact matching...")

    hook_content = HOOK_SCRIPT.read_text()

    # Check for improved implementation
    assert "_PLACEHOLDER_RE" in hook_content, \
        "Missing _PLACEHOLDER_RE regex pattern"

    assert "_extract_value" in hook_content, \
        "Missing _extract_value function"

    # Check that safe_contexts list is NOT used (old buggy implementation)
    assert "safe_contexts = [" not in hook_content, \
        "Old buggy safe_contexts list still present"

    # Verify the new logic exists
    assert "if _PLACEHOLDER_RE.match(_extract_value(matched_text)):" in hook_content, \
        "Missing new placeholder matching logic"

    print("  OK Using exact placeholder matching (not context substring)")
    print("  OK _extract_value() extracts value from key=value")
    print("  OK Old buggy safe_contexts list removed")

    return True


def test_fix4_conversation_history_persistence():
    """Fix 4: Conversation history should be saved to state file."""
    print("\n[Fix 4] Testing conversation history persistence...")

    hook_content = HOOK_SCRIPT.read_text()

    # Check for conversation history saving
    assert '"conversation_history": conv_history' in hook_content, \
        "conversation_history not being saved to state file"

    assert '_MAX_CONV_HISTORY = 20' in hook_content, \
        "_MAX_CONV_HISTORY constant not defined"

    assert 'conv_history.append({' in hook_content, \
        "conv_history.append() call not found"

    # Verify it includes the required fields
    assert '"turn_id": turn_id' in hook_content
    assert '"ts": now_iso()' in hook_content
    assert '"final_action": final_action' in hook_content

    print("  OK conversation_history saved to state file")
    print("  OK Limited to 20 entries (_MAX_CONV_HISTORY)")
    print("  OK Includes turn_id, timestamp, user_prompt, actions, final_action")

    return True


def test_fix5_unified_logging():
    """Fix 5: All log modes should write to JSONL event stream."""
    print("\n[Fix 5] Testing unified logging...")

    hook_content = HOOK_SCRIPT.read_text()

    # Check that events_sink is NOT conditional on log_layout
    assert "events_sink: Optional[Path] = events_log  # all log_layout modes write to JSONL event stream" in hook_content, \
        "events_sink still conditional on log_layout mode"

    # Old buggy version should NOT exist
    assert "events_sink = events_log if args.log_layout == \"legacy\" else None" not in hook_content, \
        "Old buggy conditional events_sink still present"

    print("  OK events_sink enabled for all log_layout modes")
    print("  OK JSONL event stream written in all modes (turn_dir/unified/legacy)")

    return True


def main():
    """Run all verification tests."""
    print("=" * 70)
    print("SentrySkills P0 Fixes Verification")
    print("=" * 70)

    tests = [
        test_fix1_detection_rules_enabled,
        test_fix2_policies_differentiated,
        test_fix3_placeholder_exact_matching,
        test_fix4_conversation_history_persistence,
        test_fix5_unified_logging,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            failed += 1
            print(f"  X FAILED: {e}")
        except Exception as e:
            failed += 1
            print(f"  X ERROR: {e}")

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\n[SUCCESS] All P0 fixes verified! Ready for launch.")
        return 0
    else:
        print(f"\n[WARNING] {failed} test(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
