"""Tests for wt path command."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from wt.cli import app

runner = CliRunner()


def setup_state(repo: Path, worktrees: list[dict]) -> None:
    """Create .wt/state.json with provided worktrees."""
    wt_dir = repo / ".wt"
    wt_dir.mkdir(parents=True, exist_ok=True)
    state_path = wt_dir / "state.json"
    state_path.write_text(json.dumps({"worktrees": worktrees}), encoding="utf-8")


class TestPathByName:
    def test_success(self, git_repo: Path, monkeypatch) -> None:
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

        result = runner.invoke(app, ["path", "my-feature"])

        assert result.exit_code == 0
        assert result.stdout == f"{worktree_path}\n"

    def test_not_found(self, git_repo: Path, monkeypatch) -> None:
        setup_state(git_repo, [])
        monkeypatch.chdir(git_repo)

        result = runner.invoke(app, ["path", "missing"])

        assert result.exit_code != 0
        assert "not found" in result.stdout.lower()


class TestPathNoArgs:
    def test_no_worktrees(self, git_repo: Path, monkeypatch) -> None:
        setup_state(git_repo, [])
        monkeypatch.chdir(git_repo)

        result = runner.invoke(app, ["path"])

        assert result.exit_code != 0
        assert "no worktrees" in result.stdout.lower()
