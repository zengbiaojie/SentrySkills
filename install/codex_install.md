# Installing SentrySkills for Codex

Enable SentrySkills in Codex via native skill discovery. Just clone and symlink.

## Prerequisites

- Git

## Installation

1. **Clone the SentrySkills repository:**
   ```bash
   git clone https://github.com/AI45Lab/SentrySkills.git ~/.codex/sentryskills
   ```

2. **Create the skills symlink:**
   ```bash
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/sentryskills ~/.agents/skills/sentryskills
   ```

   **Windows (PowerShell):**
   ```powershell
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills"
   cmd /c mklink /J "$env:USERPROFILE\.agents\skills\sentryskills" "$env:USERPROFILE\.codex\sentryskills"
   ```

3. **Restart Codex** (quit and relaunch the CLI) to discover the skills.

## ⚠️ Important: Skill Installation ≠ Automatic Execution

**Installing the skill only makes SentrySkills "available" - it will NOT run automatically!**

- ❌ **Skill Only**: You must manually run `/skills use sentryskills` each time
- ✅ **Skill + AGENTS.md**: SentrySkills runs automatically on every task

**Enforcement Differences**:
- **Claude Code**: Has system-level hooks (truly enforced, cannot be bypassed)
- **Codex**: Relies on AGENTS.md prompts (LLM voluntarily follows, can be ignored)

**Security Recommendations**:
- Production environments: Use Claude Code
- Development environments: Use Codex + AGENTS.md

## Step 4: Enable Automatic Protection (Recommended)

To enable automatic protection on every task, configure AGENTS.md:

### One-Command Setup (Quickest)

```bash
# Copy the template to Codex config directory
cp ~/.codex/sentryskills/AGENTS.template.md ~/.codex/AGENTS.md
```

This copies the pre-configured template with complete execution flow and HIGH/LOW path logic.

### Restart Codex Again

After adding AGENTS.md, restart Codex once more. SentrySkills will now run automatically on every task!

**What's the difference?**
- ❌ Without AGENTS.md: You must manually run `/skills use sentryskills` each time
- ✅ With AGENTS.md: SentrySkills runs automatically on every task

## AGENTS.md Path Location

**Codex Default Path**: `~/.codex/AGENTS.md`

- **Linux/Mac**: `/home/username/.codex/AGENTS.md`
- **Windows**: `C:\Users\username\.codex\AGENTS.md`

**Verify Path**:
```bash
# Check if file exists
ls -la ~/.codex/AGENTS.md

# View content (first 20 lines)
head -20 ~/.codex/AGENTS.md

# Windows PowerShell
dir "$env:USERPROFILE\.codex\AGENTS.md"
```

**Custom Path**: Specify AGENTS.md location in Codex configuration (refer to Codex documentation)

## Verify Installation

```bash
ls -la ~/.agents/skills/sentryskills
```

You should see a symlink (or junction on Windows) pointing to your SentrySkills directory.

**Check the skill is loaded:**
In Codex, run:
```
/skills list
```

You should see `sentryskills` in the list of available skills.

## Updating

```bash
cd ~/.codex/sentryskills && git pull
```

Skills update instantly through the symlink.

## Uninstalling

```bash
rm ~/.agents/skills/sentryskills
```

Optionally delete the clone: `rm -rf ~/.codex/sentryskills`

## Quick Start

After installation, you have two options:

### Option A: Automatic Mode (Recommended)

If you completed Step 4 above, SentrySkills is already configured to run automatically. No extra action needed!

Just start using Codex normally - SentrySkills will protect every task.

### Option B: Manual Mode

If you didn't configure AGENTS.md, you need to manually activate SentrySkills each time:

```
/skills use sentryskills
```

Then proceed with your task. SentrySkills will run once for that session.

**⚠️ Recommendation:** Use Automatic Mode for consistent protection.

## What SentrySkills Protects Against

When active (manual or automatic), SentrySkills protects your Codex agent with:
- **Preflight checks** - Detects threats before execution
- **Runtime monitoring** - Watches behavior during execution
- **Output guards** - Redacts sensitive data in responses
- **Predictive analysis** - Anticipates potential risks

All with **zero external dependencies** (100% Python standard library).

## Troubleshooting

### Skills not showing up

1. Verify the symlink exists:
   ```bash
   ls -la ~/.agents/skills/
   ```

2. Check Codex can read the skill:
   ```bash
   cat ~/.agents/skills/sentryskills/SKILL.md
   ```

3. Restart Codex completely (quit and relaunch)

### Symlink creation fails on Windows

Make sure you're running PowerShell as Administrator, or use:
```powershell
# As Administrator
New-Item -ItemType Junction -Path "$env:USERPROFILE\.agents\skills\sentryskills" -Target "$env:USERPROFILE\.codex\sentryskills"
```

### Permission denied

Ensure you have write permissions:
```bash
chmod +w ~/.agents/skills
```

## What Gets Installed

The skill package includes:
- **using-sentryskills** - User-facing entry point
- **sentryskills-orchestrator** - Central coordination
- **sentryskills-preflight** - Pre-execution checks
- **sentryskills-runtime** - Runtime monitoring
- **sentryskills-output** - Output validation & redaction
- **shared/** - Core Python modules and configurations

All with **zero external dependencies** (Python stdlib only).
