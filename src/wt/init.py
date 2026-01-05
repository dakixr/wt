"""Initialization script execution for wt."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console


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


def resolve_init_script(config_script: str | None, wt_root: Path) -> str | None:
    """Resolve the init script to run.

    Priority:
    1. Explicit config value if set
    2. Fallback to .wt/hooks/init.sh if exists
    """
    if config_script:
        return config_script

    default_hook = wt_root / "hooks" / "init.sh"
    if default_hook.exists() and default_hook.is_file():
        return str(default_hook)

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
