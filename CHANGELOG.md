# Changelog

All notable changes to SentrySkills will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-04-01

### Added

- **Two-Path Execution Architecture**: Fast pre-assessment on every task
  - HIGH-risk triggers synchronous blocking pipeline
  - LOW-risk proceeds immediately with parallel subagent monitoring
- **Claude Code Integration**: Complete PreToolUse hook support
  - Automatic security checks on Bash/Edit/Write/WebFetch/WebSearch tool calls
  - Detailed installation guide (`install/claude_code_install.md`)
- **Detection Rules Enhancement**: Enabled all 24 detection rules (previously only 11 active)
  - Added `; curl` pattern to `command_injection_basic` rule
- **Project Documentation**: Comprehensive Overview section in `docs/index.html`
  - Problem statement and solution explanation
  - Target audience definitions (Enterprise Teams, Security Engineers, Developers, Platform Builders)
  - Full bilingual support (English/Chinese)

### Changed

- **Updated Installation Documentation**: Rewrote all installation guides with two-path architecture
  - `README.md` - Updated execution flow diagrams
  - `SKILL.md` (root) - Updated Quick Enable AGENTS.md template
  - `install/README.md` - Removed broken links, simplified Quick Start
  - `install/codex_install.md` - Updated AGENTS.md template with two-path instructions
  - `install/openclaw_install.md` - Updated AGENTS.md template with two-path instructions
  - `sentryskills-orchestrator/README.md` - Updated for dual-mode execution
  - `docs/index.html` - Updated flow descriptions and added Claude Code installation tab

### Fixed

- **Critical Bug Fixes** in `self_guard_runtime_hook_template.py`:
  - Fixed `predictive_report_raw` UnboundLocalError in early exit path
  - Fixed `conv_history` not initialized in early exit path
  - Fixed `matched_rules` missing in high-risk action branch
  - Fixed preflight scan not including `planned_actions` content
  - Fixed output_guard not running extended detection rules
- **Removed Broken References** in `install/README.md`:
  - Removed `first_time_setup.md` (non-existent)
  - Removed `agents_config.md` (non-existent)
  - Removed `triggering_design.md` (non-existent)
  - Removed `AGENTS.md.template` reference
- **Documentation**:
  - Fixed license from MIT-0 to MIT in `docs/index.html`
  - Added bilingual i18n support for user group descriptions
  - Separated Claude Code installation tab from OpenClaw

### Removed

- **Test Files**: Cleaned up temporary test files
  - `test_command_injection.py`
  - `simple_test.py`
  - `hook_test.py`, `hook_test_prompt.py`
  - `test_hook_directly.py`
  - `verify_hook.py`
  - `TWO_PATH_ARCHITECTURE.md`

### Technical Details

**Detection Rules Status**:
- 24/24 rules now enabled (100% coverage)
- Categories: AI/LLM attacks, Web Security, Data Leaks, Code Security

**Hook Configuration**:
- PreToolUse hook runs complete three-stage check (preflight → runtime → output)
- Average latency: 30-100ms per check
- Exit codes: 0 (allow), 2 (block)

**Logging**:
- All hook executions logged to `sentry_skill_log/hook_result_*.json`
- Each log includes: session_id, turn_id, trace_id, final_action, matched_rules

**Migration Notes**:
- No breaking changes
- Existing configurations continue to work
- New two-path architecture is backward compatible

### Contributors

- @zengbiaojie

---

## [0.1.1] - 2026-03-25

### Added

- Initial release of SentrySkills
- Three-stage protection pipeline (preflight → runtime → output)
- 33+ detection rules across 4 categories
- 7 risk predictors
- Support for OpenClaw and Codex
- Policy profiles: balanced, strict, permissive
- JSONL event logging with trace IDs
- Zero external dependencies (Python 3.8+ stdlib only)

### Documentation

- GitHub Pages deployment
- Installation guides for OpenClaw and Codex
- Skill package structure documentation
