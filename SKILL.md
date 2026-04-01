---
name: sentryskills
description: SentrySkills - AI agent security framework with 33+ detection rules. Protects against prompt injection, data leaks, unsafe commands, and code vulnerabilities.
license: MIT
---

# SentrySkills - AI Agent Security Framework

**SentrySkills** is a comprehensive security framework for AI agents, providing rule-based protection against common threats with zero external dependencies.

## What Is SentrySkills?

SentrySkills is a **skill package** containing multiple specialized skills that work together to protect AI agents:

- ✅ **33+ Detection Rules** - AI/LLM attacks, Web Security, Data Leaks, Code Security
- ✅ **Three-Stage Protection** - Preflight → Runtime → Output guard
- ✅ **Zero Dependencies** - Python 3.8+ standard library only
- ✅ **Multi-Framework Support** - Works with Claude Code, Codex, OpenClaw

## Skill Packages

This project contains multiple skill packages:

### 1. **using-sentryskills** (Main Entry Point)

**When to use**: This is the primary skill you should enable in your AGENTS.md

**What it does**:
- Fast pre-assessment on every task
- Decides between synchronous (HIGH-risk) and asynchronous (LOW-risk) execution
- Orchestrates other skills (preflight, runtime, output, orchestrator)
- Handles two-path execution model

**Who should use**: All users who want automatic security protection

**Installation**: See [install/](install/) for framework-specific guides

---

### 2. **sentryskills-orchestrator** (Coordination)

**When to use**: Automatically called by `using-sentryskills`

**What it does**:
- Coordinates when to trigger sub-skills
- Decides block/downgrade/allow based on all check results
- Manages execution modes (synchronous vs async subagent)

**Who should use**: Not for direct use - automatically invoked by main skill

---

### 3. **sentryskills-preflight** (Pre-Execution)

**When to use**: Automatically called by orchestrator

**What it does**:
- Analyzes user intent before execution
- Checks planned actions for security risks
- Detects prompt injection and manipulation attempts

**Who should use**: Not for direct use - automatically invoked by orchestrator

---

### 4. **sentryskills-runtime** (Execution Monitoring)

**When to use**: Automatically called by orchestrator

**What it does**:
- Monitors events during execution
- Tracks data sources and credibility
- Detects behavioral anomalies

**Who should use**: Not for direct use - automatically invoked by orchestrator

---

### 5. **sentryskills-output** (Output Validation)

**When to use**: Automatically called by orchestrator

**What it does**:
- Redacts sensitive data from responses
- Checks for information leakage
- Validates safe response generation

**Who should use**: Not for direct use - automatically invoked by orchestrator

---

## Quick Start

### Step 1: Choose Your Framework

- **Claude Code**: See [install/claude_code_install.md](install/claude_code_install.md)
- **Codex**: See [install/codex_install.md](install/codex_install.md)
- **OpenClaw**: See [install/openclaw_install.md](install/openclaw_install.md)

### Step 2: Configure AGENTS.md

Add to your framework's AGENTS.md:

```markdown
# SentrySkills Security

Enable automatic security checks by loading the using-sentryskills skill.

See [install/](install/) for detailed configuration examples.
```

### Step 3: Restart Your Agent

Restart your framework and SentrySkills will automatically protect every task.

---

## How It Works

### Two-Path Execution Model

SentrySkills uses a two-path architecture for optimal performance:

```
┌─────────────────────────────────────────┐
│ Step 1: Fast Pre-Assessment            │
│  (Framework's internal judgment)        │
│  ↓                                      │
│  HIGH risk? → Synchronous Check         │
│  LOW risk?  → Async Subagent            │
└─────────────────────────────────────────┘
```

**For detailed implementation**: See [using-sentryskills/SKILL.md](using-sentryskills/SKILL.md)

---

## Use Cases

Use SentrySkills when your AI agent needs to:

- ✅ **Access sensitive data** - credentials, secrets, private information
- ✅ **Execute commands** - shell commands, system modifications
- ✅ **Make network requests** - external APIs, web services
- ✅ **Generate code** - database queries, API calls, file operations
- ✅ **Run in production** - any security-critical environment
- ✅ **Handle multi-turn conversations** - detect manipulation across interactions

**Examples**:
```
✅ Use: Reading environment variables or config files
✅ Use: Executing shell commands or scripts
✅ Use: Modifying system files or configurations
✅ Use: Generating database queries or API calls
❌ Skip: Simple read-only queries on public docs
❌ Skip: Basic explanations without system access
```

---

## Policy Profiles

SentrySkills includes three pre-configured security policies:

| Profile | Description | Use When |
|---------|-------------|----------|
| **balanced** | Standard security (default) | Most production environments |
| **strict** | Maximum security | High-security environments, sensitive data |
| **permissive** | Minimal interference | Development, testing, trusted environments |

Configure via `--policy-profile` flag when calling the script.

---

## Detection Coverage

### Preflight Stage
- Prompt injection patterns
- Malicious intent detection
- Sensitive topic inference
- Action classification

### Runtime Stage
- Event monitoring
- Source tracking
- Anomaly detection
- Behavioral analysis

### Output Stage
- Sensitive data redaction
- Source disclosure handling
- Confidence assessment
- Safe response generation

### Predictive Analysis
- Resource exhaustion prediction
- Scope creep detection
- Privilege escalation warning
- Data exfiltration path analysis
- Multi-turn grooming detection

---

## Configuration Files

Located in `shared/references/`:

- `runtime_policy.*.json` - Security policy profiles (balanced, strict, permissive)
- `detection_rules.json` - 33+ detection rule definitions
- `input_schema.json` - Input validation schema

---

## Logging

All security events are logged to `./sentry_skill_log/`:

- `index.jsonl` - Global event log (all turns)
- `turns/YYYYMMDD_HHMMSS_<turn_id>/` - Per-turn detailed logs
- `.self_guard_state/` - Session state persistence
- `hook_result_*.json` - Hook execution results

---

## Performance

- **Latency**: 30-100ms per check
- **Memory**: <50MB baseline
- **Dependencies**: Zero (Python stdlib only)

---

## Security Properties

- ✅ **No data exfiltration** - All processing is local
- ✅ **No LLM calls** - Pure rule-based and heuristic
- ✅ **Audit trail** - Complete event log for compliance
- ✅ **Transparent** - All decisions include reason codes

---

## Documentation

- **Installation Guides**: [install/](install/)
- **Main Skill**: [using-sentryskills/SKILL.md](using-sentryskills/SKILL.md)
- **Orchestrator**: [sentryskills-orchestrator/SKILL.md](sentryskills-orchestrator/SKILL.md)
- **Project Overview**: [docs/index.html](docs/index.html)

---

## License

MIT License - See [LICENSE](LICENSE) for details.
