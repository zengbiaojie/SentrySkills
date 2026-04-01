# Claude Code Installation Guide

Complete guide to installing SentrySkills with Claude Code CLI/IDE extension.

## Requirements

- **Claude Code** CLI or IDE extension (VS Code/JetBrains)
- **Python** 3.8+ installed and in PATH
- **Git** (for cloning repository)

## Installation

### Step 1: Clone SentrySkills

```bash
# Clone to home directory or preferred location
git clone https://github.com/AI45Lab/SentrySkills.git ~/SentrySkills

# Or on Windows
git clone https://github.com/AI45Lab/SentrySkills.git %USERPROFILE%\SentrySkills
```

### Step 2: Configure PreToolUse Hook

Create or edit `~/.claude/settings.json` (Linux/Mac) or `%USERPROFILE%\.claude\settings.json` (Windows):

#### Linux/Mac

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|NotebookEdit|WebFetch|WebSearch",
        "hooks": [
          {
            "type": "command",
            "command": "python \"/home/username/SentrySkills/shared/scripts/claude_code_hook.py\""
          }
        ]
      }
    ]
  }
}
```

#### Windows

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|NotebookEdit|WebFetch|WebSearch",
        "hooks": [
          {
            "type": "command",
            "command": "python \"D:/work/ai lab/TrinitySafeSkills/SentrySkills/shared/scripts/claude_code_hook.py\""
          }
        ]
      }
    ]
  }
}
```

**Important Notes:**
- Use **absolute paths** (not relative paths like `./SentrySkills`)
- Use **forward slashes** `/` or **double backslashes** `\\` on Windows
- Wrap paths in quotes if they contain spaces
- Adjust the path to match your actual installation location

### Step 3: Restart IDE

**Important**: Completely close and reopen your IDE (VS Code/JetBrains/etc.)

- ❌ **Don't** just reload the window
- ✅ **Do** fully restart the IDE application

## Verification

### Test 1: Run a Simple Command

In a new Claude Code session:

```
echo "hook test"
```

### Test 2: Check Log Files

In the same session:

```bash
ls ~/SentrySkills/sentry_skill_log/hook_result_*.json
```

You should see at least one `hook_result_*.json` file.

### Test 3: View Hook Result

```bash
cat ~/SentrySkills/sentry_skill_log/hook_result_*.json | tail -1 | python -m json.tool
```

**Expected output:**

```json
{
  "session_id": "...",
  "turn_id": "hook-...",
  "trace_id": "...",
  "policy_profile": "balanced",
  "final_action": "downgrade",
  "matched_rules": ["action:execute_command"],
  "decision_chain": {
    "preflight_decision": "downgrade",
    "runtime_decision": "continue",
    "output_decision": "allow"
  }
}
```

If you see this, SentrySkills is working! 🎉

## How It Works

### Execution Flow

```
User Request → Tool Call (Bash/Edit/Write/etc.)
                ↓
          PreToolUse Hook Triggers
                ↓
    ┌───────────────────────────────┐
    │ claude_code_hook.py           │
    │  - Reads tool name & input    │
    │  - Builds security context    │
    │  - Calls main pipeline        │
    └───────────────────────────────┘
                ↓
    ┌───────────────────────────────┐
    │ Three-Stage Security Check    │
    │  1. Preflight                 │
    │  2. Runtime                   │
    │  3. Output                    │
    └───────────────────────────────┘
                ↓
          Final Decision
        - allow (exit code 0)
        - block (exit code 2)
                ↓
          Tool executes or is refused
```

### What Gets Checked

**Every tool call is analyzed for:**

- **Command injection** (`; curl`, `| nc`, `&& wget`, etc.)
- **Prompt injection** (jailbreak, ignore instructions, etc.)
- **Credential leakage** (AWS keys, API tokens, passwords)
- **Sensitive file access** (`.env`, `/etc/passwd`, config files)
- **Data exfiltration** patterns

### Exit Codes

- **0**: Allow - tool proceeds normally
- **2**: Block - tool is refused, agent shows warning

### Logging

All hook executions are logged to `sentry_skill_log/`:

```
sentry_skill_log/
├── hook_result_*.json        # Individual hook results
├── logs/                      # Detailed execution logs
└── .self_guard_state/         # Session state tracking
```

## Advanced Configuration

### Project-Specific Settings

For project-level configuration, create `.claude/settings.local.json` in your project root:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash|Write|Edit|NotebookEdit|WebFetch|WebSearch",
      "hooks": [{
        "type": "command",
        "command": "python \"D:/work/ai lab/TrinitySafeSkills/SentrySkills/shared/scripts/claude_code_hook.py\""
      }]
    }]
  }
}
```

This overrides global settings for this project only.

### Policy Profiles

Change security level by modifying `SENTRYSKILLS_PROFILE` environment variable:

```json
{
  "env": {
    "SENTRYSKILLS_PROFILE": "strict"
  }
}
```

Available profiles:
- **balanced** (default) - Standard security
- **strict** - Maximum security, more false positives
- **permissive** - Minimal interference

### Custom Matcher Patterns

Only hook specific tools:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash|Write",  // Only Bash and Write
      "hooks": [{
        "type": "command",
        "command": "python \"/path/to/claude_code_hook.py\""
      }]
    }]
  }
}
```

## Troubleshooting

### Hook Not Triggering

**Symptoms**: Commands execute without protection, no log files created.

**Solutions**:

1. **Use absolute paths** in settings.json
   ```json
   // ❌ Wrong
   "command": "python ./shared/scripts/claude_code_hook.py"

   // ✅ Correct
   "command": "python \"/home/user/SentrySkills/shared/scripts/claude_code_hook.py\""
   ```

2. **Completely restart IDE**
   - VS Code: File → Exit (not just reload window)
   - JetBrains: File → Exit
   - Terminal: Start new session

3. **Verify Python is in PATH**
   ```bash
   which python  # Linux/Mac
   where python  # Windows
   ```

   If not found, use absolute path:
   ```json
   "command": "C:\\Python314\\python.exe \"D:/SentrySkills/...\""
   ```

### Permission Denied

**Symptoms**: Hook script fails with permission error.

**Solution**: Add to `permissions.allow` in settings.json:

```json
{
  "permissions": {
    "allow": [
      "Bash(python \"/path/to/SentrySkills/shared/scripts/claude_code_hook.py\")"
    ]
  }
}
```

### Path Issues on Windows

**Symptoms**: Hook can't find script due to path/escape issues.

**Solutions**:

1. **Use forward slashes**:
   ```json
   "command": "python \"D:/work/ai lab/TrinitySafeSkills/SentrySkills/...\""
   ```

2. **Or double backslashes**:
   ```json
   "command": "python \"D:\\\\work\\\\ai lab\\\\TrinitySafeSkills\\\\SentrySkills\\\\...\""
   ```

3. **Quote paths with spaces**:
   ```json
   "command": "python \"D:/work/ai lab/TrinitySafeSkills/...\""
   ```

### Hook Too Slow

**Symptoms**: Noticeable delay before every command.

**Analysis**: Normal latency is 30-100ms per check.

**Solutions**:

1. **Check detection rules count** (should be ~24 rules enabled)
   ```bash
   python -c "import json; r=json.load(open('shared/scripts/detection_rules.json')); print(f'Enabled: {sum(1 for cat in r[\"rule_categories\"].values() for rule in cat[\"rules\"] if rule.get(\"enabled\"))}')"
   ```

2. **Use SSD** for SentrySkills directory (faster I/O)

3. **Disable debug logging**:
   ```json
   {
     "debug": ""
   }
   ```

### Test Hook Manually

Run hook script directly to debug:

```bash
# Linux/Mac
echo '{"tool_name":"Bash","tool_input":{"command":"echo test"}}' | \
  python ~/SentrySkills/shared/scripts/claude_code_hook.py

# Windows
echo {"tool_name:Bash,tool_input:{command:test}} | python D:\SentrySkills\shared\scripts\claude_code_hook.py
```

**Expected output**: Exit code 0 (allow) or 2 (block), with stderr message.

## Performance Impact

| Metric | Value |
|--------|-------|
| Latency per check | 30-100ms |
| Memory overhead | <50MB |
| CPU usage | Minimal |
 Disk I/O | ~5KB per check |

For typical usage (10-100 tool calls per session), total overhead is <1 second.

## Uninstallation

To remove SentrySkills:

1. **Remove hook from settings.json**:
   ```json
   {
     "hooks": {
       // Remove PreToolUse section
     }
   }
   ```

2. **Delete SentrySkills directory**:
   ```bash
   rm -rf ~/SentrySkills
   ```

3. **Restart IDE**

4. **Clean up logs** (optional):
   ```bash
   rm -rf ~/SentrySkills/sentry_skill_log/
   ```

## Next Steps

- 📖 [Main README](../README.md) - Project overview
- 🔧 [Configuration Guide](codex_install.md) - Advanced options
- 🐛 [Report Issues](https://github.com/AI45Lab/SentrySkills/issues)
- 💬 [Discussions](https://github.com/AI45Lab/SentrySkills/discussions)
