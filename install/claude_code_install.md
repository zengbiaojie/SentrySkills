# Claude Code Installation Guide

Complete guide to installing SentrySkills with Claude Code CLI/IDE extension using the new **one-click plugin system**.

## 📋 Requirements

- **Claude Code** CLI or IDE extension (VS Code/JetBrains)
- **Python** 3.8+ installed and in PATH
- **Git** (for cloning repository)

---

## 🚀 Quick Start (Recommended)

### One-Command Installation

```bash
# Step 1: Clone SentrySkills
git clone https://github.com/AI45Lab/SentrySkills.git ~/SentrySkills

# Step 2: Run installer
cd SentrySkills
python install/install.py
```

**That's it!** The installer will:

1. ✅ Create plugin structure with 4 security skills
2. ✅ Install scripts and detection rules
3. ✅ Register plugin with Claude Code
4. ✅ Configure automatic skill loading
5. ✅ Verify installation

**Installation output:**
```
✅ Installation completed successfully!

Next steps:
  1. Restart Claude Code
  2. Run: claude skill list
  3. Check if SentrySkills skills appear
```

### Restart IDE

**Important**: Completely close and reopen your IDE (VS Code/JetBrains/etc.)

- ❌ **Don't** just reload the window
- ✅ **Do** fully restart the IDE application

### Verify Installation

```bash
claude skill list
```

You should see:
```
using-sentryskills      - Main entry point
sentryskills-preflight  - Pre-execution checks
sentryskills-runtime    - Runtime monitoring
sentryskills-output     - Output validation
```

---

## 🧹 Uninstallation

```bash
cd SentrySkills
python install/uninstall.py --force
```

The uninstaller will:
- ✅ Remove all 4 skills from Claude Code
- ✅ Clean up plugin cache
- ✅ Remove plugin registration
- ✅ Verify complete removal

---

## 📖 What Gets Installed

### Plugin Structure

```
~/.claude/
├── plugins/
│   └── cache/
│       └── local-marketplace/
│           └── sentryskills/
│               └── 0.1.5/
│                   ├── .claude-plugin/
│                   │   └── plugin.json
│                   ├── skills/
│                   │   ├── using-sentryskills/
│                   │   ├── sentryskills-preflight/
│                   │   ├── sentryskills-runtime/
│                   │   └── sentryskills-output/
│                   ├── scripts/
│                   │   └── self_guard_runtime_hook_template.py
│                   └── references/
│                       ├── detection_rules.json
│                       └── runtime_policy.*.json
└── skills/
    ├── using-sentryskills/
    ├── sentryskills-preflight/
    ├── sentryskills-runtime/
    └── sentryskills-output/
```

### Components

**Skills (4)**:
- `using-sentryskills` - Entry point, orchestrates security checks
- `sentryskills-preflight` - Pre-execution threat detection
- `sentryskills-runtime` - Runtime behavior monitoring
- `sentryskills-output` - Output data redaction

**Scripts (19)**:
- Main security pipeline: `self_guard_runtime_hook_template.py`
- Detection rules engine
- Policy enforcement
- Logging and state management

**References (18)**:
- 33+ detection rules across 4 categories
- 3 policy profiles (balanced, strict, permissive)
- Configuration schemas and documentation

---

## ⚙️ How It Works

### Skill-Based Architecture

SentrySkills now uses Claude Code's **skill system** instead of hooks:

```
User Request
    ↓
Claude Code loads using-sentryskills skill
    ↓
Step 0: Framework Pre-Assessment
    ↓
Step 1: Run Security Script
    ↓
Step 2: Route to HIGH or LOW Path
    ↓
┌──────────────┬──────────────┐
│  HIGH Path   │  LOW Path    │
│  (Blocking)  │  (Async)     │
│              │              │
│ Execute 3    │ Spawn        │
│ sub-skills   │ subagent     │
│              │              │
│ • preflight  │ • preflight  │
│ • runtime    │ • runtime    │
│ • output     │ • output     │
│              │              │
│ Block if     │ Proceed +    │
│ any BLOCK    │ check later  │
└──────────────┴──────────────┘
    ↓              ↓
Final Decision
```

### Decision Flow

```
Every task → Pre-Assessment
                 ↓
         HIGH risk signals?
        ┌─────────┴──────────┐
       YES                   NO
        ↓                    ↓
  Synchronous          Asynchronous
  (wait for result)    (proceed immediately)
        ↓                    ↓
  Execute sub-skills    Spawn subagent
  • preflight           • Check next turn
  • runtime
  • output
        ↓
  Most conservative wins
  block > downgrade > allow
```

### Execution Paths

**HIGH Path (Synchronous)**:
- Triggers when: Framework detects HIGH risk signals
- Behavior: Blocks until full security pipeline completes
- Use case: Dangerous operations (file deletion, network calls, credential access)

**LOW Path (Asynchronous)**:
- Triggers when: Framework detects LOW risk signals
- Behavior: Proceeds immediately, monitors in background
- Use case: Safe operations (read files, list directories)

---

## 🔧 Advanced Configuration

### Policy Profiles

Change security level by modifying environment variable:

```json
// ~/.claude/settings.json
{
  "env": {
    "SENTRYSKILLS_PROFILE": "strict"
  }
}
```

**Available profiles:**
- `balanced` (default) - Standard security
- `strict` - Maximum security, more false positives
- `permissive` - Minimal interference

### Project-Level Configuration

For project-specific settings, create `.claude/settings.local.json`:

```json
{
  "env": {
    "SENTRYSKILLS_PROFILE": "permissive"
  }
}
```

### Skill Invocation (Manual)

You can manually invoke SentrySkills skills:

```
/sentryskills-preflight
```

This runs preflight checks on the current context.

---

## 🐛 Troubleshooting

### Skills Not Visible

**Symptoms**: `claude skill list` doesn't show SentrySkills skills.

**Solutions**:

1. **Verify installation**:
   ```bash
   ls ~/.claude/skills/
   ```
   Should show: using-sentryskills, sentryskills-preflight, sentryskills-runtime, sentryskills-output

2. **Restart IDE completely**:
   - VS Code: File → Exit (not reload)
   - JetBrains: File → Exit
   - Terminal: Start new session

3. **Check plugin status**:
   ```bash
   claude plugin list
   ```
   Look for: `sentryskills@local-marketplace`

### Installation Fails

**Symptoms**: Installer shows errors during execution.

**Solutions**:

1. **Check Python version**:
   ```bash
   python --version  # Should be 3.8+
   ```

2. **Run with verbose output**:
   ```bash
   python install/install.py 2>&1 | tee install.log
   ```

3. **Clean partial installation**:
   ```bash
   python install/uninstall.py --force
   python install/install.py
   ```

### Uninstallation Incomplete

**Symptoms**: Some files remain after uninstall.

**Solution**: Manually clean up:

```bash
# Remove skills
rm -rf ~/.claude/skills/using-sentryskills
rm -rf ~/.claude/skills/sentryskills-*

# Remove plugin cache
rm -rf ~/.claude/plugins/cache/local-marketplace

# Clean installed_plugins.json (edit manually)
# Remove sentryskills@local-marketplace entry
```

### Plugin Shows "failed to load"

**Symptoms**: `claude plugin list` shows "failed to load" error.

**Explanation**: This is **normal and expected**. The local marketplace is not registered to avoid system errors, but the plugin still works correctly.

**Verification**: Skills should still be visible and functional:
```bash
claude skill list
```

---

## 📊 Performance Impact

| Metric | Value |
|--------|-------|
| Installation time | ~5 seconds |
| Disk usage | ~5 MB |
| Memory overhead | <50MB |
| Latency per check | 30-100ms |
| CPU usage | Minimal |

---

## 📚 Next Steps

- 📖 [Main README](../README.md) - Project overview
- 🛡️ [Detection Rules](../shared/references/detection_rules.md) - Rule documentation
- ⚙️ [Policy Profiles](../shared/references/policy_profiles.md) - Configuration options
- 🐛 [Report Issues](https://github.com/AI45Lab/SentrySkills/issues)
- 💬 [Discussions](https://github.com/AI45Lab/SentrySkills/discussions)

---

## ❓ FAQ

**Q: Can I use SentrySkills with other frameworks?**

A: Yes! SentrySkills supports:
- **Claude Code** (this guide) - Plugin system
- **OpenClaw** - See [openclaw_install.md](openclaw_install.md)
- **Codex** - See [codex_install.md](codex_install.md)

**Q: Does SentrySkills call external APIs?**

A: No. All processing is local, no network calls, no LLM calls.

**Q: Can I customize detection rules?**

A: Yes. Edit `shared/scripts/detection_rules.json` and reinstall.

**Q: How do I update SentrySkills?**

A:
```bash
cd ~/SentrySkills
git pull
python install/uninstall.py --force
python install/install.py
```

**Q: Where are logs stored?**

A: In your project directory: `./sentry_skill_log/`

---

## 🤝 Contributing

Contributions welcome!

- Report vulnerabilities privately
- Submit PRs for new detection patterns
- Improve documentation and performance
- Add support for more frameworks

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
