# SentrySkills

[![Docs](https://img.shields.io/badge/docs-website-blue?style=flat-square)](https://zengbiaojie.github.io/SentrySkills/)
[![GitHub](https://img.shields.io/badge/github-AI45Lab%2FSentrySkills-181717?style=flat-square&logo=github)](https://github.com/AI45Lab/SentrySkills)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

**Self-guarding security framework for AI agents. Three-stage protection (preflight → runtime → output) with predictive risk analysis. Zero dependencies, production-ready.**

## 🎯 What It Does

SentrySkills protects AI agents from:

- **Preflight**: Detects threats before execution
- **Runtime**: Monitors behavior during execution
- **Output**: Redacts sensitive data in responses
- **Predictive**: Warns about potential risks before they materialize

## ✨ Key Features

- **Zero dependencies** - 100% Python standard library
- **33+ detection rules** - AI attacks, web vulnerabilities, data leaks, code security
- **7 risk predictors** - Anticipates problems before execution
- **Policy profiles** - Balanced, strict, permissive modes
- **Full traceability** - JSONL event logs

## 📥 Installation

### Claude Code (Recommended)

```bash
git clone https://github.com/AI45Lab/SentrySkills.git ~/SentrySkills
```

Configure PreToolUse hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash|Write|Edit|NotebookEdit|WebFetch|WebSearch",
      "hooks": [{
        "type": "command",
        "command": "python \"/path/to/SentrySkills/shared/scripts/claude_code_hook.py\""
      }]
    }]
  }
}
```

Restart IDE and you're protected!

📖 **[Detailed guide →](install/claude_code_install.md)**

### OpenClaw

```bash
# Install ClawHub CLI
npm i -g clawhub

# Install SentrySkills
clawhub install sentryskills

# Enable auto-protection
cat > ~/.codex/AGENTS.md << 'EOF'
# Security: SentrySkills runs automatically
Before EVERY response, run:
python ./skills/sentry-skills/shared/scripts/self_guard_runtime_hook_template.py input.json --policy-profile balanced --out result.json
EOF

# Restart OpenClaw
```

📖 **[Detailed guide →](install/openclaw_install.md)**

### Codex (Legacy)

```bash
git clone https://github.com/AI45Lab/SentrySkills.git ~/.codex/sentryskills
mkdir -p ~/.agents/skills
ln -s ~/.codex/sentryskills ~/.agents/skills/sentryskills
```

📖 **[Detailed guide →](install/codex_install.md)**

## 🛡️ Detection Coverage

**AI/LLM Attacks**: Prompt injection, jailbreak, system prompt leakage
**Web Security**: SQL injection, XSS, command injection, SSTI, path traversal
**Data Leaks**: SSH keys, AWS credentials, API keys, database strings
**Code Security**: Hardcoded secrets, weak crypto, unsafe eval/exec
**Predictive**: Resource exhaustion, scope creep, privilege escalation, data exfiltration

### Skill Package Structure

```
sentry-skills/
├── using-sentryskills/          # ① Entry point
├── sentryskills-orchestrator/   # ② Coordination layer
├── sentryskills-preflight/      # ③ Pre-execution checks
├── sentryskills-runtime/        # ④ Runtime monitoring
└── sentryskills-output/         # ⑤ Output validation
```

## ⚙️ Configuration

- **Balanced** (default): Standard security
- **Strict**: Maximum security
- **Permissive**: Minimal interference

## 🔄 Skill Package Execution Flow

SentrySkills uses a **two-path execution model** — fast pre-assessment on every task, full pipeline only when needed:

```
┌─────────────────────────────────────────────────────────────┐
│  1. using-sentryskills (Entry Point)                        │
│     ├─ Triggered automatically via AGENTS.md                │
│     ├─ Fast Pre-Assessment: scans prompt + planned_actions  │
│     └─ Routes to HIGH path or LOW path                      │
├──────────────────┬──────────────────────────────────────────┤
│  2a. HIGH Path   │  2b. LOW Path                           │
│  (synchronous,   │  (non-blocking)                         │
│   blocking)      │                                         │
│  ├─ Full pipeline│  ├─ Main agent proceeds immediately      │
│  │  runs in      │  ├─ Host framework spawns subagent       │
│  │  current proc │  │   for full pipeline in parallel      │
│  └─ Result       │  └─ Result written to JSONL,            │
│     controls     │     checked at start of next turn       │
│     this turn    │                                         │
├──────────────────┴──────────────────────────────────────────┤
│  3. sentryskills-preflight (Pre-Execution)                  │
│     ├─ Analyzes user prompt for malicious intent            │
│     ├─ Checks planned actions against detection rules       │
│     └─ Returns: allow / downgrade / block                   │
├─────────────────────────────────────────────────────────────┤
│  4. sentryskills-runtime (During Execution)                 │
│     ├─ Monitors runtime events (file ops, network calls)    │
│     ├─ Detects behavioral anomalies and goal drift          │
│     └─ Returns: continue / downgrade / stop                 │
├─────────────────────────────────────────────────────────────┤
│  5. sentryskills-output (Post-Execution)                    │
│     ├─ Scans response for sensitive data                    │
│     ├─ Redacts secrets, credentials, private keys           │
│     └─ Returns: allow / downgrade / block                   │
├─────────────────────────────────────────────────────────────┤
│  6. sentryskills-orchestrator (Final Decision)              │
│     ├─ Compiles all stage results                           │
│     ├─ Applies policy profile (balanced/strict/permissive)  │
│     └─ Outputs final_action + trace ID + self_guard_path    │
└─────────────────────────────────────────────────────────────┘
```

### Decision Flow

```
Every task → Fast Pre-Assessment (prompt + planned_actions)
                      ↓
             HIGH risk signals?
            ┌─────────┴──────────┐
           YES                   NO
            ↓                    ↓
     Full pipeline          Proceed immediately
     (blocking,             + subagent runs pipeline
      current process)        in parallel → JSONL log
            ↓                    ↓
     Preflight BLOCK ──────────────────────→ block
            ↓ allow
     Runtime STOP ───────────────────────→ block
            ↓ continue
     Output BLOCK/DOWNGRADE ─────────────→ block / downgrade
            ↓ allow
     Final Decision: allow / downgrade / block
                 + self_guard_path: synchronous | async-subagent
```

### Key Points

- **Fast path**: LOW-risk tasks proceed with zero latency; subagent monitors in parallel
- **Safe path**: HIGH-risk tasks block until full pipeline completes
- **Early termination**: Any BLOCK in the HIGH path stops immediately
- **Traceability**: Every stage emits events with shared trace ID; `self_guard_path` identifies which mode ran

## 📈 Performance

- **Latency**: ~50-100ms per check
- **Memory**: <50MB
- **No LLM calls**

## 📋 Requirements

- Python 3.8+
- No external dependencies

## 🤝 Contributing

Contributions welcome:

- Report vulnerabilities privately
- Submit PRs for new detection patterns
- Improve documentation and performance

## 🔗 Links

- **GitHub Pages**: https://zengbiaojie.github.io/SentrySkills/
- **ClawHub**: https://clawhub.ai/zengbiaojie/sentryskills
- **Issues**: https://github.com/AI45Lab/SentrySkills/issues
- **Documentation**: [install/](install/)
