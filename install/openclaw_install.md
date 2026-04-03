# Installing SentrySkills for OpenClaw

Install SentrySkills via ClawHub CLI for OpenClaw/Claude Code environments.

## Prerequisites

- Node.js and npm
- OpenClaw or Claude Code

## Installation

### Step 1: Install ClawHub CLI

```bash
npm i -g clawhub
clawhub --version
```

### Step 2: Search and Install SentrySkills

```bash
# Search for SentrySkills
clawhub search "sentry skills security"

# Install SentrySkills
clawhub install sentryskills
```

By default, ClawHub installs skills to `./skills/` in your current working directory.

If you have configured an OpenClaw workspace, ClawHub will use that workspace location unless you override it with `--workdir` or the `CLAWHUB_WORKDIR` environment variable.

### Step 3: Restart OpenClaw

```bash
# Start a new session
openclaw chat
```

The skill will be automatically loaded in the new session.

## ⚠️ Important: Skill Installation ≠ Automatic Execution

**Installing the skill only makes SentrySkills "available" - it will NOT run automatically!**

- ❌ **Skill Only**: You must manually run `/skills use sentry-skills` each time
- ✅ **Skill + AGENTS.md**: SentrySkills runs automatically on every task

**Enforcement Differences**:
- **Claude Code**: Has system-level hooks (truly enforced, cannot be bypassed)
- **OpenClaw**: Relies on AGENTS.md prompts (LLM voluntarily follows, can be ignored)

**Security Recommendations**:
- Production environments: Use Claude Code
- Development environments: Use OpenClaw + AGENTS.md

## Enable Automatic Protection (Recommended)

To enable automatic protection on every task, configure AGENTS.md:

### One-Command Setup

```bash
# Download and copy the template
curl -o ~/.openclaw/workspace/AGENTS.md https://raw.githubusercontent.com/AI45Lab/SentrySkills/main/AGENTS.template.md
```

Or manually create `~/.openclaw/workspace/AGENTS.md` with:

```bash
cat > ~/.openclaw/workspace/AGENTS.md << 'EOF'
# SentrySkills - Automatic Security Protection

Before EVERY response:

1. Run the SentrySkills pre-flight check:
   /skills use sentry-skills

2. Based on the result:
   - If blocked: Refuse the request and explain why
   - If allowed with warnings: Include warnings in response
   - If allowed: Proceed normally

3. Include in your response:
   - sentryskills_decision: <block|allow|downgrade>
   - sentryskills_trace_id: <trace_id_from_result>
EOF
```

### Step 4: Restart Again

Restart OpenClaw once more after adding AGENTS.md. SentrySkills will now protect every task!

## AGENTS.md Path Location

**OpenClaw Default Path**: `~/.openclaw/workspace/AGENTS.md`

- **Linux/Mac**: `/home/username/.openclaw/workspace/AGENTS.md`
- **Windows**: `C:\Users\username\.openclaw\workspace\AGENTS.md`

**Verify Path**:
```bash
# Check if file exists
ls -la ~/.openclaw/workspace/AGENTS.md

# View content (first 20 lines)
head -20 ~/.openclaw/workspace/AGENTS.md

# Windows PowerShell
dir "$env:USERPROFILE\.openclaw\workspace\AGENTS.md"
```

**Custom Path**: Specify AGENTS.md location in OpenClaw configuration (refer to OpenClaw documentation)

## Installation Location

Default installation path: `./skills/sentry-skills/`

OpenClaw loads skills from: `<workspace>/skills/`

## Verify Installation

```bash
# Check skill directory
ls -la ./skills/sentry-skills/

# Verify main skill file
cat ./skills/sentry-skills/SKILL.md
```

## Updating

```bash
clawhub update sentryskills
```

Or reinstall:
```bash
clawhub install sentryskills --force
```

## Uninstalling

```bash
clawhub uninstall sentryskills
```

Optionally remove AGENTS.md configuration:
```bash
rm ~/.openclaw/workspace/AGENTS.md
```

## What SentrySkills Protects Against

When active, SentrySkills provides:
- **Preflight checks** - Detects threats before execution
- **Runtime monitoring** - Watches behavior during execution
- **Output guards** - Redacts sensitive data in responses
- **Predictive analysis** - Anticipates potential risks

All with **zero external dependencies** (100% Python standard library).

## Troubleshooting

### ClawHub command not found

Ensure npm global bin is in your PATH:
```bash
npm config get prefix
# Add <prefix>/bin to your PATH
```

### Skill not loading after installation

1. Verify the skill directory exists:
   ```bash
   ls -la ./skills/sentry-skills/
   ```

2. Check SKILL.md is present:
   ```bash
   cat ./skills/sentry-skills/SKILL.md
   ```

3. Restart OpenClaw completely

### Automatic mode not working

If SentrySkills doesn't run automatically:

1. Verify AGENTS.md exists:
   ```bash
   cat ~/.openclaw/workspace/AGENTS.md
   ```

2. Check the path to the runtime hook is correct:
   ```bash
   python ./skills/sentry-skills/shared/scripts/self_guard_runtime_hook_template.py --help
   ```

3. Restart OpenClaw again

## Manual Mode

If you didn't configure AGENTS.md, you can manually invoke SentrySkills:

```
/skills use sentry-skills
```

Then proceed with your task. SentrySkills will run once for that session.

**⚠️ Recommendation:** Use Automatic Mode for consistent protection.

## Package Contents

The skill package includes:
- **using-sentry-skills** - User-facing entry point
- **sentry-skills-orchestrator** - Central coordination
- **sentry-skills-preflight** - Pre-execution checks
- **sentry-skills-runtime** - Runtime monitoring
- **sentry-skills-output** - Output validation & redaction
- **shared/** - Core Python modules and configurations

All with **zero external dependencies** (Python stdlib only).
