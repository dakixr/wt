"""Tests for wt list command."""
from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from typer.testing import CliRunner

from wt.cli import app

runner = CliRunner()


def setup_state(repo: Path, worktrees: list[dict]) -> None:
    """Create .wt/state.json with provided worktrees."""
    wt_dir = repo / ".wt"
    wt_dir.mkdir(parents=True, exist_ok=True)
    state_path = wt_dir / "state.json"
    state_path.write_text(json.dumps({"worktrees": worktrees}), encoding="utf-8")


class TestList:
    def test_list_shows_worktrees(self, git_repo: Path, monkeypatch) -> None:
        worktree_path = git_repo / ".wt/worktrees/my-feature"
        setup_state(
            git_repo,
            [
                {
                    "feat_name": "my-feature",
                    "branch": "feature/my-feature",
                    "path": str(worktree_path),
                    "base": "develop",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        )
        monkeypatch.chdir(git_repo)

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "my-feature" in result.stdout
        assert "feature/my-feature" in result.stdout

    def test_list_empty_state_no_worktrees(self, git_repo: Path, monkeypatch) -> None:
        setup_state(git_repo, [])
        monkeypatch.chdir(git_repo)

        result = runner.invoke(app, ["list"])

        assert result.exit_code != 0
        assert "no worktrees" in result.stdout.lower()


class TestListAll:
    def test_list_all_includes_remote_branches(self, git_repo: Path, monkeypatch) -> None:
        import wt.git as git

        worktree_path = git_repo / ".wt/worktrees/my-feature"
        setup_state(
            git_repo,
            [
                {
                    "feat_name": "my-feature",
                    "branch": "feature/my-feature",
                    "path": str(worktree_path),
                    "base": "develop",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        )
        monkeypatch.chdir(git_repo)

        original_run_git = git.run_git

        def fake_run_git(*args, **kwargs):
            if args == ("branch", "-r"):
                return CompletedProcess(
                    args=["git", "branch", "-r"],
                    returncode=0,
                    stdout="  origin/feature/my-feature\n  origin/feature/new-feature\n  origin/main\n",
                    stderr="",
                )
            return original_run_git(*args, **kwargs)

        monkeypatch.setattr(git, "run_git", fake_run_git)

        result = runner.invoke(app, ["list", "--all"])

        assert result.exit_code == 0
        assert "my-feature" in result.stdout
        assert "new-feature" in result.stdout
        assert "remote" in result.stdout

    def test_list_all_with_no_remote_branches(self, git_repo: Path, monkeypatch) -> None:
        import wt.git as git

        worktree_path = git_repo / ".wt/worktrees/my-feature"
        setup_state(
            git_repo,
            [
                {
                    "feat_name": "my-feature",
                    "branch": "feature/my-feature",
                    "path": str(worktree_path),
                    "base": "develop",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        )
        monkeypatch.chdir(git_repo)

        original_run_git = git.run_git

        def fake_run_git(*args, **kwargs):
            if args == ("branch", "-r"):
                return CompletedProcess(
                    args=["git", "branch", "-r"],
                    returncode=0,
                    stdout="  origin/feature/my-feature\n  origin/main\n",
                    stderr="",
                )
            return original_run_git(*args, **kwargs)

        monkeypatch.setattr(git, "run_git", fake_run_git)

        result = runner.invoke(app, ["list", "--all"])

        assert result.exit_code == 0
        assert "my-feature" in result.stdout
        assert "new-feature" not in result.stdout

    def test_list_all_empty_state_shows_only_remotes(self, git_repo: Path, monkeypatch) -> None:
        import wt.git as git

        setup_state(git_repo, [])
        monkeypatch.chdir(git_repo)

        original_run_git = git.run_git

        def fake_run_git(*args, **kwargs):
            if args == ("branch", "-r"):
                return CompletedProcess(
                    args=["git", "branch", "-r"],
                    returncode=0,
                    stdout="  origin/feature/new-feature\n  origin/main\n",
                    stderr="",
                )
            return original_run_git(*args, **kwargs)

        monkeypatch.setattr(git, "run_git", fake_run_git)

        result = runner.invoke(app, ["list", "--all"])

        assert result.exit_code == 0
        assert "new-feature" in result.stdout
        assert "remote" in result.stdout
