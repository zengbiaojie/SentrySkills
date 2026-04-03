#!/usr/bin/env python3
"""
SentrySkills Claude Code Plugin Uninstaller
Uninstall script for SentrySkills plugin
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_success(msg: str):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.RESET}")

def print_error(msg: str):
    print(f"{Colors.RED}[FAIL] {msg}{Colors.RESET}")

def print_info(msg: str):
    print(f"{Colors.BLUE}[INFO] {msg}{Colors.RESET}")

def print_step(msg: str):
    print(f"{Colors.BOLD}{msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.RESET}")

def get_project_root() -> Path:
    """Get the project root directory"""
    current_file = Path(__file__).resolve()
    return current_file.parent.parent

def get_claude_config_dir() -> Path:
    """Get Claude Code configuration directory"""
    home = Path.home()
    config_dir = home / ".claude"

    if not config_dir.exists():
        # Try Windows AppData
        appdata = Path(os.environ.get('APPDATA', ''))
        if appdata:
            config_dir = appdata / "Claude" / "claude-code"

    return config_dir

def uninstall_plugin() -> bool:
    """Uninstall the SentrySkills plugin"""
    print_step("Uninstalling plugin...")

    try:
        # Try to uninstall using claude plugin uninstall
        result = subprocess.run(
            ["claude", "plugin", "uninstall", "sentryskills", "--scope", "local"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )

        if result.returncode == 0:
            print_success("Plugin uninstalled successfully")
            # Show output
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"   {line}")
            return True
        else:
            # Plugin might not be installed, check error
            stderr = result.stderr.lower() if result.stderr else ""
            if "not found" in stderr or "not installed" in stderr:
                print_info("Plugin was not installed")
                return True
            else:
                print_error(f"Failed to uninstall: {result.stderr}")
                return False

    except subprocess.TimeoutExpired:
        print_error("Uninstallation timed out")
        return False
    except FileNotFoundError:
        print_error("claude command not found")
        return False
    except Exception as e:
        print_error(f"Failed to uninstall: {e}")
        return False

def cleanup_skills() -> bool:
    """Remove SentrySkills skills from .claude/skills directory"""
    print_step("Cleaning up skills directory...")

    try:
        config_dir = get_claude_config_dir()
        skills_dir = config_dir / "skills"

        if not skills_dir.exists():
            print_info("Skills directory does not exist")
            return True

        # SentrySkills skill names
        skill_names = [
            "using-sentryskills",
            "sentryskills-preflight",
            "sentryskills-runtime",
            "sentryskills-output"
        ]

        removed_count = 0
        for skill_name in skill_names:
            skill_path = skills_dir / skill_name
            if skill_path.exists():
                shutil.rmtree(skill_path)
                print_success(f"  Removed: {skill_name}")
                removed_count += 1

        if removed_count > 0:
            print_success(f"Removed {removed_count} skill(s)")
        else:
            print_info("No SentrySkills skills found")

        return True

    except Exception as e:
        print_error(f"Failed to cleanup skills: {e}")
        return False

def cleanup_installed_plugins() -> bool:
    """Remove SentrySkills entry from installed_plugins.json"""
    print_step("Cleaning up installed_plugins.json...")

    try:
        config_dir = get_claude_config_dir()
        installed_json = config_dir / "plugins" / "installed_plugins.json"

        if not installed_json.exists():
            print_info("installed_plugins.json does not exist")
            return True

        # Read existing plugins
        with open(installed_json, 'r', encoding='utf-8') as f:
            installed = json.load(f)

        # Remove sentryskills entry if present
        if "sentryskills@local-marketplace" in installed["plugins"]:
            del installed["plugins"]["sentryskills@local-marketplace"]

            # Write back
            with open(installed_json, 'w', encoding='utf-8') as f:
                json.dump(installed, f, indent=2, ensure_ascii=False)

            print_success("Removed sentryskills from installed_plugins.json")
        else:
            print_info("sentryskills not found in installed_plugins.json")

        return True

    except Exception as e:
        print_error(f"Failed to cleanup installed_plugins.json: {e}")
        return False

def cleanup_plugin_cache() -> bool:
    """Remove SentrySkills plugin cache directory"""
    print_step("Cleaning up plugin cache...")

    try:
        config_dir = get_claude_config_dir()
        plugin_cache = config_dir / "plugins" / "cache" / "local-marketplace" / "sentryskills"

        if not plugin_cache.exists():
            print_info("Plugin cache does not exist")
            return True

        # Remove entire sentryskills cache directory
        shutil.rmtree(plugin_cache)
        print_success(f"Removed plugin cache: {plugin_cache}")

        return True

    except Exception as e:
        print_error(f"Failed to cleanup plugin cache: {e}")
        return False

def cleanup_plugin_directory(plugin_dir: Path, force: bool = False) -> bool:
    """Remove the plugin directory"""
    print_step("Cleaning up plugin directory...")

    if not plugin_dir.exists():
        print_info(f"Plugin directory does not exist: {plugin_dir}")
        return True

    try:
        if not force:
            # Ask for confirmation
            response = input(f"{Colors.YELLOW}Remove plugin directory '{plugin_dir}'? (y/N): {Colors.RESET}")
            if response.lower() != 'y':
                print_info("Skipped directory cleanup")
                return True

        shutil.rmtree(plugin_dir)
        print_success(f"Plugin directory removed: {plugin_dir}")
        return True

    except Exception as e:
        print_error(f"Failed to remove directory: {e}")
        return False

def verify_uninstallation() -> bool:
    """Verify that the plugin was uninstalled"""
    print_step("Verifying uninstallation...")

    try:
        result = subprocess.run(
            ["claude", "plugin", "list"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )

        if result.returncode == 0:
            output = result.stdout.lower()
            if "sentryskills" in output:
                print_warning("Plugin still appears in installed plugins list")
                print_info("You may need to restart Claude Code")
                return False
            else:
                print_success("Plugin successfully removed from installed plugins")
                return True
        else:
            print_warning("Could not verify uninstallation")
            return True

    except Exception as e:
        print_warning(f"Verification failed: {e}")
        return True

def main():
    """Main uninstallation function"""
    parser = argparse.ArgumentParser(
        description="Uninstall SentrySkills Claude Code Plugin",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--plugin-dir",
        type=str,
        default=None,
        help="Plugin directory path to remove (default: sentryskills-claude-code)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts"
    )

    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep plugin directory after uninstallation"
    )

    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}SentrySkills Plugin Uninstaller v0.1.5{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

    # Get project root
    project_root = get_project_root()
    print_info(f"Project root: {project_root}")

    # Determine plugin directory
    if args.plugin_dir:
        plugin_dir = Path(args.plugin_dir).resolve()
    else:
        plugin_dir = project_root / "sentryskills-claude-code"

    print_info(f"Plugin directory: {plugin_dir}\n")

    # Step 1: Uninstall plugin
    if not uninstall_plugin():
        print_error("\nUninstallation failed during plugin removal")
        sys.exit(1)

    # Step 2: Clean up plugin directory (optional)
    if not args.keep_files:
        print()
        if not cleanup_plugin_directory(plugin_dir, args.force):
            print_warning("\nPlugin directory cleanup failed")
            print_info(f"You may need to manually remove: {plugin_dir}")
    else:
        print()
        print_info(f"Keeping plugin directory: {plugin_dir}")

    # Step 3: Clean up skills directory
    print()
    cleanup_skills()

    # Step 4: Clean up installed_plugins.json
    print()
    cleanup_installed_plugins()

    # Step 5: Clean up plugin cache
    print()
    cleanup_plugin_cache()

    # Step 6: Verify uninstallation
    print()
    if verify_uninstallation():
        print(f"\n{Colors.GREEN}{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}✅ Uninstallation completed successfully!{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*60}{Colors.RESET}\n")
        print_info("To reinstall, run: python install/install.py\n")
        sys.exit(0)
    else:
        print_warning("\nUninstallation completed with warnings")
        print_info("You may need to restart Claude Code\n")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Uninstallation cancelled by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
