"""Tests for wt merge command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from wt.cli import app

runner = CliRunner()


def test_merge_merges_into_base_and_deletes_worktree(
    git_repo: Path, monkeypatch
) -> None:
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "my-feature", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "my-feature"
    assert worktree_path.exists()

    (worktree_path / "feature.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.txt"], cwd=worktree_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add feature"], cwd=worktree_path, check=True
    )

    monkeypatch.chdir(worktree_path)
    result = runner.invoke(app, ["merge", "--no-push"])
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

    # Base branch is now the current branch at init time (main), not hard-coded "develop"
    subprocess.run(["git", "checkout", "main"], cwd=git_repo, check=True)
    assert (git_repo / "feature.txt").exists()

    state_path = git_repo / ".wt" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["worktrees"] == []


def test_merge_requires_worktree(git_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["merge", "--no-push"])
    assert result.exit_code != 0
    assert "worktree" in result.stdout.lower()
