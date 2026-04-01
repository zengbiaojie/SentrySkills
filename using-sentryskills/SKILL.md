---
name: using-sentryskills
description: Automatically runs SentrySkills security checks on EVERY task. Before any response, execute the runtime hook to ensure self-guard decision evidence.
---

# Using SentrySkills Self-Guard

## 📋 What Is SentrySkills?

**SentrySkills** is a **rule library + usage guide** for AI agent security:

- ✅ **Rule Engine**: 33+ detection rules across AI/LLM attacks, Web Security, Data Leaks, Code Security
- ✅ **Check Script**: `self_guard_runtime_hook_template.py` - can be called synchronously or asynchronously
- ✅ **Usage Guide**: This document - tells frameworks HOW to use the rules
- ✅ **Logging System**: Multi-format logging (JSONL events, turn logs, state files)

**What Frameworks Provide**:
- 🔹 **Big Model Pre-Assessment**: Framework's internal LLM judgment of risk level
- 🔹 **Scheduling Logic**: Decision between synchronous vs asynchronous execution
- 🔹 **Subagent Spawning**: Background process capability (Claude Code / Codex / OpenClaw)

**Analogy**:
- SentrySkills = Traffic laws + traffic light rules
- Framework = Driver + road condition judgment
- Rules = "Stop on red, go on green"
- Execution = Driver sees red and stops, sees green and goes

---

## ⚠️ IMPORTANT: This Skill Runs Automatically

This skill is **designed to run on EVERY task** - it should be configured in your AGENTS.md to execute automatically.

---

## 🎯 Goal

Establish unified trigger discipline using a **two-path execution model**: fast pre-assessment on every task, full pipeline only when needed.

---

## 📊 Risk Assessment Matrix

For Framework Implementers: Use this matrix to decide execution mode.

| Condition | Risk Level | Execution Mode |
|-----------|------------|----------------|
| `planned_actions` contains HIGH-risk action + prompt has sensitive words | **HIGH** | Synchronous Blocking |
| `planned_actions` contains HIGH-risk action + prompt has injection markers | **CRITICAL** | Synchronous Blocking |
| `planned_actions` contains only LOW-risk actions | **LOW** | Async Subagent |
| No HIGH-risk signals detected | **LOW** | Async Subagent |

**HIGH-risk actions**: `execute_command`, `write_file`, `delete_file`, `batch_modify`, `network_call`

**Sensitive words**: `output token`, `print password`, `print secret`, `show api key`, `dump`, `reveal secret`, `output credential`

**Injection markers**: `ignore previous instructions`, `jailbreak`, `forget everything`, `act as`, `override protocol`, `developer mode`

---

## 🌳 Decision Tree

```
Start (Every Turn)
  ↓
Is tool in [execute_command, write_file, delete_file, batch_modify, network_call]?
  ↓
┌─Yes────────────────────────────────────────┐
│ Does prompt contain sensitive words OR      │
│ injection markers?                          │
│  ↓ Yes                                     │
│  ├─ HIGH/CRITICAL Risk                     │
│  └─→ Run Synchronous Check (Step 2a)       │
│  ↓ No                                      │
│  ├─ MEDIUM Risk                            │
│  └─→ Run Synchronous Check (Step 2a)       │
└────────────────────────────────────────────┘
  ↓ No (LOW-risk actions)
├─ LOW Risk
└─→ Spawn Async Subagent (Step 2b)
```

---

## 🔄 Execution Flow

### Step 1 — Fast Pre-Assessment (Framework's Internal Judgment)

**What**: Framework checks `user_prompt` + `planned_actions` for HIGH-risk signals

**Who**: Framework (Claude Code / Codex / OpenClaw) - using its internal LLM

**Output**: `risk_level = HIGH | MEDIUM | LOW`

```python
# Pseudo-code for framework's pre-assessment
def assess_risk(user_prompt: str, planned_actions: list) -> str:
    HIGH_RISK_ACTIONS = ["execute_command", "write_file", "delete_file", "batch_modify", "network_call"]
    SENSITIVE_WORDS = ["output token", "print password", "show api key", "dump", "reveal secret"]
    INJECTION_MARKERS = ["ignore previous", "jailbreak", "act as", "override protocol"]

    has_high_risk_action = any(action in HIGH_RISK_ACTIONS for action in planned_actions)
    has_sensitive_words = any(word in user_prompt.lower() for word in SENSITIVE_WORDS)
    has_injection = any(marker in user_prompt.lower() for marker in INJECTION_MARKERS)

    if has_high_risk_action and (has_sensitive_words or has_injection):
        return "CRITICAL" if has_injection else "HIGH"
    elif has_high_risk_action:
        return "MEDIUM"
    else:
        return "LOW"
```

---

### Step 2a — HIGH/MEDIUM Path (Synchronous Blocking)

**When**: `risk_level in [HIGH, MEDIUM, CRITICAL]`

**How**: Framework runs the full pipeline **before** executing the tool

#### 2a.1 Write Input File

```bash
cat > ./sentry_skill_log/input.json << 'EOF'
{
  "session_id": "<session id>",
  "turn_id": "<turn id>",
  "project_path": "<absolute path to current project>",
  "user_prompt": "<the user's request>",
  "planned_actions": ["<action1>", "<action2>"],
  "candidate_response": "",
  "intent_tags": ["<tag1>"]
}
EOF
```

#### 2a.2 Run Full Pipeline

```bash
python shared/scripts/self_guard_runtime_hook_template.py \
  ./sentry_skill_log/input.json \
  --policy-profile balanced \
  --out ./sentry_skill_log/result.json
```

#### 2a.3 Read Result

```bash
result=$(cat ./sentry_skill_log/result.json | jq -r '.final_action')
# result = "allow" | "downgrade" | "block"
```

#### 2a.4 Execute Decision

- `allow` → Execute the tool normally
- `downgrade` → Execute with downgraded output (add uncertainty notice)
- `block` → **Refuse to execute** the tool

#### 2a.5 Include Evidence

Final response must include:
- `self_guard_final_action: <allow|downgrade|block>`
- `self_guard_trace_id: <trace id from result>`
- `self_guard_events_log: ./sentry_skill_log/index.jsonl`
- `self_guard_path: synchronous`

---

### Step 2b — LOW Path (Async Subagent)

**When**: `risk_level == LOW`

**How**: Main agent proceeds immediately, subagent runs in background

#### 2b.1 Main Agent: Immediate Execution

- Do **not** wait for security check
- Execute the tool immediately
- Include in response:
  - `self_guard_path: async-subagent`
  - `self_guard_subagent_pending: true`

#### 2b.2 Subagent: Background Check

Framework spawns a subagent that:

```bash
# Subagent writes input
cat > ./sentry_skill_log/subagent_input_<turn_id>.json << 'EOF'
{
  "session_id": "<session id>",
  "turn_id": "subagent-<turn id>",
  "project_path": "<absolute path>",
  "user_prompt": "<original user prompt>",
  "planned_actions": ["<original actions>"],
  "candidate_response": "",
  "intent_tags": ["async_monitor"],
  "mode": "async"
}
EOF

# Subagent runs pipeline
python shared/scripts/self_guard_runtime_hook_template.py \
  ./sentry_skill_log/subagent_input_<turn_id>.json \
  --policy-profile balanced \
  --append-output ./sentry_skill_log/index.jsonl
```

#### 2b.3 Next-Turn Check

At the **start of the next turn**, before responding:

```python
import json
from pathlib import Path

def check_prior_subagent_result():
    index_path = Path("./sentry_skill_log/index.jsonl")
    if not index_path.exists():
        return None

    with open(index_path, "r") as f:
        lines = f.readlines()
        if not lines:
            return None

        # Read last line (most recent subagent result)
        last_result = json.loads(lines[-1])
        return last_result.get("final_action")

# At start of each turn
prior_action = check_prior_subagent_result()
if prior_action == "block":
    # Prior turn was blocked - refuse this turn
    response = f"⚠️ Previous turn was blocked by SentrySkills (trace: {last_result['trace_id']})"
elif prior_action == "downgrade":
    # Prior turn was downgraded - add uncertainty notice
    response += "\n\n⚠️ Previous action triggered security downgrade."
else:
    # Prior turn allowed - continue normally
    pass
```

---

## 🔧 Framework Integration Examples

### Claude Code Integration

**PreToolUse Hook Configuration** (`.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": {
      "Bash|Write|Edit|NotebookEdit|WebFetch|WebSearch": {
        "command": "python",
        "args": [
          "d:\\work\\ai lab\\TrinitySafeSkills\\SentrySkills\\shared\\scripts\\claude_code_hook.py"
        ]
      }
    }
  }
}
```

**Hook Implementation** (`claude_code_hook.py`):

```python
import sys
import json
from pathlib import Path

# Fast Pre-Assessment
def is_high_risk(tool_name: str, tool_input: dict, user_prompt: str) -> bool:
    HIGH_RISK_TOOLS = ["Bash", "Write", "Edit", "NotebookEdit"]
    SENSITIVE_WORDS = ["output token", "print password", "show api key", "dump", "reveal"]
    INJECTION_MARKERS = ["ignore previous", "jailbreak", "act as", "override"]

    if tool_name not in HIGH_RISK_TOOLS:
        return False

    prompt_lower = user_prompt.lower()
    has_sensitive = any(word in prompt_lower for word in SENSITIVE_WORDS)
    has_injection = any(marker in prompt_lower for marker in INJECTION_MARKERS)

    return has_sensitive or has_injection

# Main hook logic
def main():
    # Read tool call from stdin
    hook_input = json.load(sys.stdin)
    tool_name = hook_input.get("name")
    tool_input = hook_input.get("input", {})
    user_prompt = hook_input.get("prompt", "")

    if is_high_risk(tool_name, tool_input, user_prompt):
        # HIGH path: Run synchronous check
        # ... (run full pipeline, check result, return exit code)
        return 0 if result["final_action"] != "block" else 2
    else:
        # LOW path: Immediate return + mark for subagent
        # Claude Code will spawn subagent automatically
        return 0

if __name__ == "__main__":
    sys.exit(main())
```

---

### Codex Integration

**AGENTS.md Configuration**:

```markdown
## SentrySkills Integration

### Trigger
Always trigger before any tool execution.

### Fast Pre-Assessment (Agent's Internal Judgment)

Check if `planned_actions` contains HIGH-risk action AND `user_prompt` contains sensitive words:

```
HIGH triggers:
- Actions: execute_command, write_file, delete_file, batch_modify, network_call
- Words: output token, print password, show api key, dump, reveal secret
- Markers: ignore previous, jailbreak, act as, override protocol
```

### HIGH Path (Synchronous)

When HIGH signal detected:

```xml
<run_sync>
  <script>shared/scripts/self_guard_runtime_hook_template.py</script>
  <input>./sentry_skill_log/input.json</input>
  <policy>balanced</policy>
  <output>./sentry_skill_log/result.json</output>
</run_sync>

<check_result>
  <if final_action="block">
    <refuse>Security policy violation</refuse>
  </if>
  <if final_action="downgrade">
    <add_uncertainty_notice/>
  </if>
</check_result>
```

### LOW Path (Async Subagent)

When no HIGH signal:

```xml
<proceed_immediately/>

<spawn_subagent>
  <name>sentry-skills-monitor</name>
  <input>./sentry_skill_log/subagent_input_{turn_id}.json</input>
  <command>python shared/scripts/self_guard_runtime_hook_template.py ./sentry_skill_log/subagent_input_{turn_id}.json --policy-profile balanced --append-output ./sentry_skill_log/index.jsonl</command>
  <mode>background</mode>
</spawn_subagent>
```

### Next-Turn Check

At start of each turn:

```xml
<check_prior_result>
  <read_file>./sentry_skill_log/index.jsonl</read_file>
  <parse_last_line/>
  <if final_action="block">
    <declare_prior_block/>
  </if>
</check_prior_result>
```
```

---

### OpenClaw Integration

**Configuration File** (`config/sentry_skills.yaml`):

```yaml
sentry_skills:
  enabled: true
  policy_profile: balanced

  # Fast Pre-Assessment Rules
  pre_assessment:
    high_risk_actions:
      - execute_command
      - write_file
      - delete_file
      - batch_modify
      - network_call

    sensitive_words:
      - output token
      - print password
      - show api key
      - dump
      - reveal secret

    injection_markers:
      - ignore previous
      - jailbreak
      - act as
      - override protocol

  # Execution Modes
  execution:
    synchronous:
      trigger: "high_risk_action AND (sensitive_words OR injection_markers)"
      timeout_ms: 5000

    asynchronous:
      trigger: "NOT (high_risk_action AND (sensitive_words OR injection_markers))"
      subagent_name: "sentry-skills-monitor"
      output_mode: "append_to_file"
      output_file: "./sentry_skill_log/index.jsonl"

  # Next-Turn Check
  next_turn_check:
    enabled: true
    check_file: "./sentry_skill_log/index.jsonl"
    on_prior_block: "refuse_with_notice"
    on_prior_downgrade: "add_uncertainty_notice"
```

---

## 🛡️ Fallback and Degradation

1. **Script Failure**: Explicitly declare "security self-check not completed" and adopt conservative output
2. **Log Directory Not Writable**: Use writable temporary directory; record real log path in evidence fields
3. **No Subagent Support**: Fall back to Step 2a (synchronous) for all requests
4. **Result Read Failure**: Treat as `block` - refuse to execute tool

---

## ⚠️ Common Anti-patterns

1. ❌ Reply first then run the hook afterward
2. ❌ Judge risk by text only without actually running the script
3. ❌ Skip Fast Pre-Assessment and always run full pipeline (defeats performance purpose)
4. ❌ `downgrade` still gives high-confidence conclusions
5. ❌ `block` still outputs the original sensitive candidate content
6. ❌ Forget to include `self_guard_path` in response
7. ❌ Skip next-turn check after async subagent

---

## 📚 Reference

- **Rule Engine**: `shared/scripts/self_guard_runtime_hook_template.py`
- **Detection Rules**: `shared/scripts/detection_rules.json`
- **Policy Profiles**: `shared/references/runtime_policy.*.json`
- **Log Directory**: `./sentry_skill_log/`
  - `index.jsonl` - Event log (all turns)
  - `logs/*.json` - Detailed turn logs
  - `hook_result_*.json` - Hook execution results
  - `.self_guard_state/*.json` - Session state
