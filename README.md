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

**Quick Start - One-Command Installation:**

```bash
# Clone repository
git clone https://github.com/AI45Lab/SentrySkills.git ~/SentrySkills

# Run one-click installer
cd SentrySkills
python install/install.py
```

That's it! Restart your IDE and you're protected. ✅

**What gets installed:**
- ✅ SentrySkills plugin (4 skills)
- ✅ Security scripts (19 files)
- ✅ Detection rules and policies (18 files)
- ✅ Auto-configuration for Claude Code

**Uninstall anytime:**
```bash
python install/uninstall.py --force
```

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
├── using-sentryskills/          # ① Entry point + orchestration
├── sentryskills-preflight/      # ② Pre-execution checks
├── sentryskills-runtime/        # ③ Runtime monitoring
└── sentryskills-output/         # ④ Output validation
```

## ⚙️ Configuration

- **Balanced** (default): Standard security
- **Strict**: Maximum security
- **Permissive**: Minimal interference

## 🔄 Skill Package Execution Flow

SentrySkills uses a **two-path execution model** — fast pre-assessment on every task, full pipeline only when needed:

```
┌─────────────────────────────────────────────────────────────┐
│  using-sentryskills (Entry Point + Orchestration)          │
│     ├─ Triggered automatically via AGENTS.md                │
│     ├─ Step 0: Fast Pre-Assessment (framework LLM)         │
│     │  └─ Analyzes prompt + planned_actions + history      │
│     ├─ Step 1: Run main security script                    │
│     │  └─ self_guard_runtime_hook_template.py              │
│     └─ Step 2: Route to HIGH or LOW path                   │
├──────────────────┬──────────────────────────────────────────┤
│  2a. HIGH Path   │  2b. LOW Path                           │
│  (synchronous,   │  (asynchronous, non-blocking)            │
│   blocking)      │                                         │
│  ├─ Execute in   │  ├─ Main agent proceeds immediately      │
│  │  current      │  ├─ Spawn subagent for full pipeline    │
│  │  process      │  │   (runs in parallel)                  │
│  │               │  └─ Check result at next turn            │
│  ├─ Call 3 sub-skills:                                     │
│  │  ├─ sentryskills-preflight                              │
│  │  ├─ sentryskills-runtime                                │
│  │  └─ sentryskills-output                                 │
│  │               │                                          │
│  ├─ Integrate    │  (Subagent runs same pipeline)           │
│  │  all 4        │     ├─ sentryskills-preflight           │
│  │  decisions    │     ├─ sentryskills-runtime             │
│  │               │     └─ sentryskills-output              │
│  └─ Result       │     ├─ Integrate all 4 decisions        │
│     controls     │     └─ Write to JSONL log               │
│     this turn    │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

### Sub-Skill Details

**sentryskills-preflight** (Pre-Execution):
- Analyzes user prompt for malicious intent
- Checks planned actions against 33+ detection rules
- Returns: `preflight_decision`, `matched_rules`, `risk_summary`

**sentryskills-runtime** (During Execution):
- Monitors runtime events (file ops, network calls)
- Detects behavioral anomalies and goal drift
- Returns: `runtime_decision`, `alerts`, `trust_annotations`

**sentryskills-output** (Post-Execution):
- Scans response for sensitive data
- Redacts secrets, credentials, private keys
- Returns: `output_guard_decision`, `leakage_detected`, `safe_response`

### Decision Flow

```
Every task → Fast Pre-Assessment (Step 0)
                      ↓
             HIGH risk signals?
            ┌─────────┴──────────┐
           YES                   NO
            ↓                    ↓
     Step 1: Run script      Step 1: Run script
     Step 2a: HIGH Path      Step 2b: LOW Path
       (synchronous)           (asynchronous)
            ↓                    ↓
     ┌─────────────────┐     Proceed immediately
     │ Execute 3 sub-│     + spawn subagent
     │ skills:        │     ├─ sentryskills-preflight
     │ ├─ preflight  │     ├─ sentryskills-runtime
     │ ├─ runtime    │     └─ sentryskills-output
     │ └─ output     │     └─ Check at next turn
     └─────────────────┘
            ↓
     Integrate all 4 decisions:
     script + preflight + runtime + output
            ↓
     Use most conservative action:
     block > downgrade > allow
            ↓
     Final Decision + self_guard_path
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
