"""GitHub CLI (gh) wrappers."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from wt.errors import GhNotInstalledError, CommandFailedError


def check_gh_installed() -> None:
    """Check if gh CLI is installed."""
    if shutil.which("gh") is None:
        raise GhNotInstalledError()


def create_pr(
    base: str,
    head: str,
    title: str | None = None,
    body: str | None = None,
    draft: bool = False,
    fill: bool = True,
    cwd: Path | None = None,
) -> str:
    """Create a PR and return the URL."""
    check_gh_installed()

    args = ["gh", "pr", "create", "--base", base, "--head", head]
    if fill and not title:
        args.append("--fill")
    if title:
        args.extend(["--title", title])
    if body:
        args.extend(["--body", body])
    if draft:
        args.append("--draft")

    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        command = " ".join(args)
        raise CommandFailedError(command, result.stderr)

    return result.stdout.strip()
