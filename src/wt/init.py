"""Initialization script execution for wt."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

HOOK_SCRIPT_EXTENSIONS = {".sh", ".bash", ".zsh", ".fish", ".py"}
INTERPRETER_COMMANDS = {"bash", "sh", "zsh", "fish", "python", "python3"}


@dataclass
class InitContext:
    """Context passed to init scripts via environment variables."""

    wt_root: Path  # .wt directory
    repo_root: Path  # Repository root
    worktree_path: Path  # Created worktree
    feat_name: str  # Feature name
    branch: str  # Full branch name
    base_branch: str  # Base branch


def build_init_env(ctx: InitContext) -> dict[str, str]:
    """Build environment variables for init script."""
    env = os.environ.copy()
    env.update(
        {
            "WT_ROOT": str(ctx.wt_root),
            "WT_REPO_ROOT": str(ctx.repo_root),
            "WT_WORKTREE_PATH": str(ctx.worktree_path),
            "WT_FEAT_NAME": ctx.feat_name,
            "WT_BRANCH": ctx.branch,
            "WT_BASE_BRANCH": ctx.base_branch,
        }
    )
    return env


def get_user_hooks_dir() -> Path:
    """Get the user-level wt hooks directory."""
    return Path("~/.wt/hooks").expanduser()


def _hook_command(path: Path) -> str:
    """Build a shell command for a hook path."""
    quoted = shlex.quote(str(path))
    if path.suffix == ".py":
        return f"python {quoted}"
    return quoted


def _find_hook_reference(reference: str, wt_root: Path) -> Path | None:
    """Resolve a hook filename from repo or user hook directories."""
    path = Path(reference).expanduser()
    if path.is_absolute() or reference.startswith("~"):
        return path if path.exists() and path.is_file() else None

    if len(path.parts) > 1:
        return None

    for hooks_dir in (wt_root / "hooks", get_user_hooks_dir()):
        candidate = hooks_dir / reference
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _resolve_config_script(config_script: str, wt_root: Path) -> str:
    """Resolve hook references inside an explicit init_script value."""
    try:
        tokens = shlex.split(config_script)
    except ValueError:
        return config_script

    if not tokens:
        return config_script

    if len(tokens) == 1:
        hook = _find_hook_reference(tokens[0], wt_root)
        return _hook_command(hook) if hook else config_script

    resolved_tokens = tokens.copy()
    changed = False
    command_name = Path(tokens[0]).name
    for index, token in enumerate(tokens[1:], start=1):
        token_suffix = Path(token).suffix
        should_resolve = (
            command_name in INTERPRETER_COMMANDS
            or token_suffix in HOOK_SCRIPT_EXTENSIONS
            or token.startswith("~")
        )
        if should_resolve:
            hook = _find_hook_reference(token, wt_root)
            if hook:
                resolved_tokens[index] = str(hook)
                changed = True

    return shlex.join(resolved_tokens) if changed else config_script


def resolve_init_script(config_script: str | None, wt_root: Path) -> str | None:
    """Resolve the init script to run.

    Priority:
    1. Explicit config value if set
    2. Repository hook .wt/hooks/init.sh or .wt/hooks/init.py
    3. User hook ~/.wt/hooks/init.sh or ~/.wt/hooks/init.py
    """
    if config_script:
        return _resolve_config_script(config_script, wt_root)

    for default_hook in (
        wt_root / "hooks" / "init.sh",
        wt_root / "hooks" / "init.py",
        get_user_hooks_dir() / "init.sh",
        get_user_hooks_dir() / "init.py",
    ):
        if default_hook.exists() and default_hook.is_file():
            return _hook_command(default_hook)

    return None


def run_init_script(
    script: str,
    ctx: InitContext,
    console: Console,
    strict: bool = False,
) -> bool:
    """Run the init script in the worktree directory.

    Returns True if successful, False otherwise.
    """
    env = build_init_env(ctx)

    console.print(f"[dim]Running init script: {script}[/dim]")

    try:
        result = subprocess.run(
            script,
            shell=True,
            cwd=ctx.worktree_path,
            env=env,
        )

        if result.returncode != 0:
            if strict:
                console.print(
                    f"[red]✗[/red] Init script failed with exit code {result.returncode}"
                )
                return False
            else:
                console.print(
                    f"[yellow]⚠[/yellow] Init script failed (exit code {result.returncode}), continuing anyway"
                )
                return True  # Continue despite failure in non-strict mode

        console.print("[green]✓[/green] Init script completed")
        return True

    except Exception as e:
        if strict:
            console.print(f"[red]✗[/red] Init script error: {e}")
            return False
        else:
            console.print(f"[yellow]⚠[/yellow] Init script error: {e}, continuing anyway")
            return True
