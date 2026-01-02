"""Custom exceptions and exit codes for wt CLI."""
from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    FAILURE = 1
    USAGE_ERROR = 2
    MISSING_DEPENDENCY = 3


class WtError(Exception):
    """Base exception for wt errors."""

    exit_code: int = ExitCode.FAILURE
    suggestion: str | None = None

    def __init__(self, message: str, suggestion: str | None = None) -> None:
        super().__init__(message)
        self.suggestion = suggestion


class CommandFailedError(WtError):
    """Raised when an external command fails."""

    exit_code = ExitCode.FAILURE

    def __init__(self, command: str, stderr: str) -> None:
        message = f"Command failed: {command}"
        suggestion = "Check the command output and try again."
        if stderr:
            message = f"{message}\n{stderr.strip()}"
        super().__init__(message, suggestion=suggestion)


class NotInGitRepoError(WtError):
    """Raised when not inside a non-bare git repository."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self) -> None:
        super().__init__(
            "Not inside a non-bare git repository.",
            suggestion="Run this command from within a non-bare git repository.",
        )


class BranchExistsError(WtError):
    """Raised when target branch already exists."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self, branch: str) -> None:
        super().__init__(
            f"Branch '{branch}' already exists.",
            suggestion=f"Use 'wt checkout {branch}' to switch to it.",
        )


class BaseBranchNotFoundError(WtError):
    """Raised when base branch doesn't exist."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self, base: str) -> None:
        super().__init__(
            f"Base branch '{base}' not found locally or on remote.",
            suggestion="Use --base to specify a different base branch.",
        )


class GhNotInstalledError(WtError):
    """Raised when gh CLI is not installed."""

    exit_code = ExitCode.MISSING_DEPENDENCY

    def __init__(self) -> None:
        super().__init__(
            "GitHub CLI (gh) is not installed.",
            suggestion="Install it from https://cli.github.com/",
        )


class UncommittedChangesError(WtError):
    """Raised when there are uncommitted changes."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self) -> None:
        super().__init__(
            "Uncommitted changes detected.",
            suggestion="Commit or stash changes, or use --force to override.",
        )


class UnpushedCommitsError(WtError):
    """Raised when there are unpushed commits."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self) -> None:
        super().__init__(
            "Unpushed commits detected.",
            suggestion="Push your changes, or use --force to override.",
        )


class NotInWorktreeError(WtError):
    """Raised when command must run from a worktree."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self) -> None:
        super().__init__(
            "This command must be run from inside a wt-managed worktree.",
            suggestion=(
                "Navigate to a worktree created with 'wt new' or 'wt checkout'."
            ),
        )


class InvalidFeatureNameError(WtError):
    """Raised when a feature name is invalid."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Invalid feature name '{name}'.",
            suggestion="Use only lowercase letters, digits, '.', '_', or '-'.",
        )


class UsageError(WtError):
    """Raised for invalid usage conditions."""

    exit_code = ExitCode.USAGE_ERROR


class BranchNotFoundError(UsageError):
    """Raised when a branch cannot be found."""

    def __init__(self, branch: str) -> None:
        super().__init__(
            f"Branch '{branch}' not found locally or on remote.",
            suggestion="Check the branch name or fetch from the remote.",
        )
