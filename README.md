# SentrySkills

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

### OpenClaw / Claude Code (Recommended)

```bash
# Install ClawHub CLI
npm i -g clawhub

# Install SentrySkills
clawhub install sentry-skills

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
git clone https://github.com/zengbiaojie/SentrySkills.git ~/.codex/sentryskills
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

## ⚙️ Configuration

- **Balanced** (default): Standard security
- **Strict**: Maximum security
- **Permissive**: Minimal interference

## 📊 Event Flow

```
Input → Preflight → Runtime → Output → Decision
           ↓          ↓        ↓
       Block/Allow  Monitor  Redact
```

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

- **Issues**: https://github.com/zengbiaojie/SentrySkills/issues
- **Documentation**: [install/](install/)
