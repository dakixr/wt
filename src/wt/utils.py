"""Utility functions for wt."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

from wt.errors import InvalidFeatureNameError

console = Console()


def normalize_feat_name(name: str) -> str:
    """Normalize feature name: lowercase, spaces to dashes, validate chars."""
    normalized = name.lower().strip()
    normalized = re.sub(r"\s+", "-", normalized)
    if not re.match(r"^[a-z0-9._-]+$", normalized):
        raise InvalidFeatureNameError(normalized)
    return normalized


def derive_feat_name_from_branch(branch: str, prefix: str) -> str:
    """Derive feature name from branch, stripping prefix if present."""
    if branch.startswith(prefix):
        return branch[len(prefix) :]
    return branch


def launch_ai_tui(tui_command: str, cwd: Path) -> bool:
    """Launch AI TUI in the given directory. Returns True if launched."""
    if shutil.which(tui_command) is None:
        console.print(
            f"[yellow]Warning:[/yellow] AI TUI '{tui_command}' not found in PATH. Skipping."
        )
        return False
    subprocess.run([tui_command], cwd=cwd, check=False)
    return True
