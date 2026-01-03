"""Tests for wt delete command."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from wt.cli import app

runner = CliRunner()


def test_delete_by_name(git_repo: Path, monkeypatch) -> None:
    """Delete worktree by name from base branch."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "my-feature", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "my-feature"
    assert worktree_path.exists()

    result = runner.invoke(app, ["delete", "my-feature", "--force"])
    assert result.exit_code == 0
    assert "Deleted" in result.stdout

    assert not worktree_path.exists()

    branch_list = subprocess.run(
        ["git", "branch", "--list", "feature/my-feature"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert branch_list.stdout.strip() == ""

    state_path = git_repo / ".wt" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["worktrees"] == []


def test_delete_by_branch_name(git_repo: Path, monkeypatch) -> None:
    """Delete worktree by branch name from base branch."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "my-feature", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "my-feature"
    assert worktree_path.exists()

    result = runner.invoke(app, ["delete", "feature/my-feature", "--force"])
    assert result.exit_code == 0

    assert not worktree_path.exists()


def test_delete_from_worktree(git_repo: Path, monkeypatch) -> None:
    """Delete current worktree when running from within it (backward compat)."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "my-feature", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "my-feature"
    assert worktree_path.exists()

    monkeypatch.chdir(worktree_path)
    result = runner.invoke(app, ["delete", "--force"])
    assert result.exit_code == 0

    assert not worktree_path.exists()

    branch_list = subprocess.run(
        ["git", "branch", "--list", "feature/my-feature"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert branch_list.stdout.strip() == ""


def test_delete_name_not_found(git_repo: Path, monkeypatch) -> None:
    """Error when deleting non-existent worktree."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["delete", "nonexistent"])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower()


def test_delete_non_tty_requires_name(git_repo: Path, monkeypatch) -> None:
    """Error when no TTY and no name provided."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "my-feature", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["delete"])
    assert result.exit_code != 0
    assert "required" in result.stdout.lower() or "name" in result.stdout.lower()


def test_delete_force_bypasses_checks(git_repo: Path, monkeypatch) -> None:
    """Force flag bypasses uncommitted/unpushed checks."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "my-feature", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "my-feature"
    assert worktree_path.exists()

    (worktree_path / "feature.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.txt"], cwd=worktree_path, check=True)

    result = runner.invoke(app, ["delete", "my-feature"])
    assert result.exit_code != 0
    assert "uncommitted" in result.stdout.lower()

    result = runner.invoke(app, ["delete", "my-feature", "--force"])
    assert result.exit_code == 0
    assert not worktree_path.exists()


def test_delete_with_remote_flag(git_repo: Path, monkeypatch) -> None:
    """Delete worktree with remote branch."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "my-feature", "--no-ai"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "my-feature"
    assert worktree_path.exists()

    result = runner.invoke(app, ["delete", "my-feature", "--remote", "--force"])
    assert result.exit_code == 0

    assert not worktree_path.exists()

    remote_branches = subprocess.run(
        ["git", "branch", "--remotes"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "feature/my-feature" not in remote_branches.stdout


def test_delete_stale_worktree_missing_path(git_repo: Path, monkeypatch) -> None:
    """Delete worktree when path has been manually removed from disk."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "stale-feature", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "stale-feature"
    assert worktree_path.exists()

    # Simulate external deletion of the worktree directory.
    shutil.rmtree(worktree_path)
    assert not worktree_path.exists()

    # Should succeed without --force (checks are skipped for missing paths).
    result = runner.invoke(app, ["delete", "stale-feature"])
    assert result.exit_code == 0
    assert "stale" in result.stdout.lower() or "warning" in result.stdout.lower()

    state_path = git_repo / ".wt" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["worktrees"] == []

    branch_list = subprocess.run(
        ["git", "branch", "--list", "feature/stale-feature"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert branch_list.stdout.strip() == ""


def test_delete_stale_worktree_with_force(git_repo: Path, monkeypatch) -> None:
    """Delete stale worktree with --force flag."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "stale-force", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "stale-force"
    shutil.rmtree(worktree_path)

    result = runner.invoke(app, ["delete", "stale-force", "--force"])
    assert result.exit_code == 0

    state_path = git_repo / ".wt" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["worktrees"] == []


def test_delete_stale_worktree_with_remote(git_repo: Path, monkeypatch) -> None:
    """Delete stale worktree with --remote flag."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "stale-remote", "--no-ai"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "stale-remote"
    shutil.rmtree(worktree_path)

    result = runner.invoke(app, ["delete", "stale-remote", "--remote", "--force"])
    assert result.exit_code == 0

    remote_branches = subprocess.run(
        ["git", "branch", "--remotes"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "feature/stale-remote" not in remote_branches.stdout


def test_delete_no_worktrees_from_base(git_repo: Path, monkeypatch) -> None:
    """Error when no worktrees exist from base branch."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["delete"])
    assert result.exit_code != 0
    assert "no worktrees" in result.stdout.lower()
